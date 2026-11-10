"""Processo de síntese com voz clonada pelo Qwen3-TTS-12Hz-0.6B-Base (Apache 2.0; motor escolhido pelo Raphael em 31/10/2026, 15h30).
Roda no venv ~/.venvs/editor-gs-qwen (Python 3.11 + torch 2.6 cu124 + qwen-tts), separado do venv do app e do venv do Chatterbox.
Mesmo protocolo do voz_clonada_worker.py: uma linha JSON por pedido no stdin, uma linha JSON por resposta no stdout.
Pedido: {"texto", "saida" (wav), "ref" (wav de referência), "ref_text"?: transcrição exata da referência (sem ela cai em x_vector_only, pior),
"idioma"?: "pt", "semente"?: int, "pronuncia"?: {} (valor vazio apaga a entrada padrão), "sem_pronuncia_padrao"?: bool, "aparar_bordas"?: true,
"pausa_s"?: 0.25, "temperatura"?, "top_p"?, "repeticao"?, "max_tokens"?}.
Antes de cada frase emite {"progresso": {"parte", "de", "s_gerados"}}; resposta final {"ok": true, "duracao_s", "partes", "tempo_s", "sr", "modo"} ou {"ok": false, "erro"}.
Primeira linha emitida: {"pronto": true, "motor": "qwen", "device", "dtype", "tempo_carga_s", "modelo"}.
Na GTX 1650 (Turing) o fp16 dá NaN; bf16 emulado funciona (~3,5 GB de VRAM, ~11 s de processamento por segundo de fala). Sem VRAM, cai para CPU fp32.
A voz clonada nunca é apresentada como gravação do Thiago."""
import json, os, sys, time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from voz_clonada_worker import aplicar_pronuncia, dividir  # só funções de texto (sem torch)

MODELO = os.environ.get("EDITOR_GS_QWEN_MODELO", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
MAX_CHARS = 200  # frases curtas: menos tokens por chamada, menos VRAM e menos chance de o modelo "cansar"
IDIOMAS = {"pt": "Portuguese", "en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "ja": "Japanese", "ko": "Korean", "ru": "Russian", "zh": "Chinese"}
GERACAO_PADRAO = {"temperatura": 0.9, "top_p": 0.9, "repeticao": 1.05, "max_tokens": 1024}


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def carregar(device=None):
    import torch
    from qwen_tts import Qwen3TTSModel
    if device is None:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.float32 if device == "cpu" else torch.bfloat16  # fp16 dá NaN na Turing; bf16 emulado funciona
    try:
        m = Qwen3TTSModel.from_pretrained(MODELO, device_map=device, dtype=dtype, attn_implementation="sdpa")
    except (RuntimeError, torch.cuda.OutOfMemoryError) as e:
        if device.startswith("cuda") and "out of memory" in str(e).lower():
            _log("CUDA sem memória; usando CPU"); torch.cuda.empty_cache(); device, dtype = "cpu", torch.float32
            m = Qwen3TTSModel.from_pretrained(MODELO, device_map=device, dtype=dtype, attn_implementation="sdpa")
        else:
            raise
    return m, device, str(dtype).replace("torch.", "")


def aparar_bordas(w, sr, limiar=0.012, margem_s=0.04, fade_s=0.015, piso_db=-42.0, burst_max_s=0.22, vao_min_s=0.15, quadro_s=0.01):
    """Limpa as pontas de cada frase gerada: (1) o Qwen costuma soltar um som curto (~0,15 s) antes de começar a falar, separado da fala por um
    vão de silêncio; aqui qualquer trecho sonoro com menos de `burst_max_s` seguido de vão >= `vao_min_s` no começo (ou precedido no fim) é descartado;
    (2) o quase-silêncio das pontas é cortado com `margem_s` e fade curto. Devolve (áudio, n_trechos_descartados)."""
    import numpy as np
    if w.size < sr // 10:
        return w, 0
    hop = max(1, int(sr * quadro_s)); n = w.size // hop
    if n < 4:
        return w, 0
    rms = np.sqrt(np.mean(w[: n * hop].reshape(n, hop) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-9)
    sonoro = db > piso_db
    # trechos sonoros contíguos (tolerando buracos menores que o vão mínimo)
    trechos = []; i = 0; vao_q = max(1, int(vao_min_s / quadro_s))
    while i < n:
        if not sonoro[i]:
            i += 1; continue
        j = i
        while j < n:
            k = j + 1
            while k < n and not sonoro[k] and k - j <= vao_q:
                k += 1
            if k < n and sonoro[k] and k - j <= vao_q:
                j = k; continue
            break
        trechos.append((i, j)); i = j + 1
    descartados = 0
    burst_q = int(burst_max_s / quadro_s)
    while len(trechos) > 1 and (trechos[0][1] - trechos[0][0]) < burst_q and (trechos[1][0] - trechos[0][1]) >= vao_q:
        trechos.pop(0); descartados += 1
    while len(trechos) > 1 and (trechos[-1][1] - trechos[-1][0]) < burst_q and (trechos[-1][0] - trechos[-2][1]) >= vao_q:
        trechos.pop(); descartados += 1
    if trechos:
        ini_q, fim_q = trechos[0][0], trechos[-1][1]
        w = w[max(0, ini_q * hop - int(sr * margem_s)): min(w.size, (fim_q + 1) * hop + int(sr * margem_s))]
    acima = np.flatnonzero(np.abs(w) > limiar)
    if acima.size == 0:
        return w, descartados
    m = int(sr * margem_s)
    ini = max(0, int(acima[0]) - m); fim = min(w.size, int(acima[-1]) + m)
    w = w[ini:fim].copy()
    k = min(int(sr * fade_s), w.size // 2)
    if k > 0:
        rampa = np.linspace(0.0, 1.0, k, dtype=np.float32)
        w[:k] *= rampa; w[-k:] *= rampa[::-1]
    return w, descartados


class Sintetizador:
    def __init__(self, m, device):
        self.m = m; self.device = device; self._prompts = {}

    def prompt(self, ref, ref_text):
        """create_voice_clone_prompt uma vez por (referência, texto) e reaproveita nas frases seguintes e nos pedidos seguintes."""
        chave = (str(ref), ref_text or "")
        if chave not in self._prompts:
            if ref_text:
                self._prompts[chave] = self.m.create_voice_clone_prompt(ref_audio=str(ref), ref_text=ref_text)
            else:
                self._prompts[chave] = self.m.create_voice_clone_prompt(ref_audio=str(ref), x_vector_only_mode=True)
            if len(self._prompts) > 8:  # não acumular prompts à toa
                self._prompts.pop(next(iter(self._prompts)))
        return self._prompts[chave]

    def sintetizar(self, pedido):
        import numpy as np, torch, soundfile as sf
        texto = pedido["texto"]; ref = Path(pedido["ref"]); saida = Path(pedido["saida"])
        if not ref.exists():
            raise FileNotFoundError(f"referência não encontrada: {ref}")
        ref_text = (pedido.get("ref_text") or "").strip() or None
        idioma = (pedido.get("idioma") or "pt")[:2].lower()
        language = IDIOMAS.get(idioma, "Auto")
        g = dict(GERACAO_PADRAO); g.update({k: pedido[k] for k in GERACAO_PADRAO if pedido.get(k) is not None})
        partes = dividir(aplicar_pronuncia(texto, pedido.get("pronuncia"), base=not pedido.get("sem_pronuncia_padrao")), max_chars=int(pedido.get("max_chars") or MAX_CHARS))
        aparar = pedido.get("aparar_bordas", True)
        prompt = self.prompt(ref, ref_text)
        semente = pedido.get("semente")
        pausa_s = float(pedido.get("pausa_s", 0.25))
        wavs, sr, descartados = [], 24000, 0
        for i, p in enumerate(partes):
            print(json.dumps({"progresso": {"parte": i + 1, "de": len(partes), "s_gerados": round(sum(len(x) for x in wavs) / sr, 1)}}), flush=True)
            if semente is not None:  # mesma semente em cada frase: o resultado é reproduzível frase a frase
                torch.manual_seed(int(semente))
                if self.device.startswith("cuda"):
                    torch.cuda.manual_seed_all(int(semente))
            with torch.inference_mode():
                ws, sr = self.m.generate_voice_clone(text=p, language=language, voice_clone_prompt=prompt, do_sample=True,
                                                     temperature=float(g["temperatura"]), top_p=float(g["top_p"]), repetition_penalty=float(g["repeticao"]),
                                                     max_new_tokens=int(g["max_tokens"]))
            w = np.asarray(ws[0], dtype=np.float32).reshape(-1)
            if not np.isfinite(w).all():
                raise RuntimeError("o modelo devolveu áudio inválido (NaN); tente outra semente ou CPU")
            if aparar:
                w, nd = aparar_bordas(w, sr); descartados += nd
            wavs.append(w)
            if i < len(partes) - 1:
                wavs.append(np.zeros(int(sr * pausa_s), dtype=np.float32))
        wav = np.concatenate(wavs) if len(wavs) > 1 else wavs[0]
        pico = float(np.max(np.abs(wav))) if wav.size else 0.0
        if pico > 0.99:  # evita estourar na conversão
            wav = wav * (0.99 / pico)
        saida.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(saida), wav, sr)
        return {"duracao_s": round(len(wav) / sr, 3), "partes": len(partes), "sr": sr, "modo": "icl" if ref_text else "x_vector_only", "sons_soltos_removidos": descartados}


def main():
    t0 = time.time()
    m, device, dtype = carregar(os.environ.get("EDITOR_GS_QWEN_DEVICE"))
    s = Sintetizador(m, device)
    print(json.dumps({"pronto": True, "motor": "qwen", "device": device, "dtype": dtype, "tempo_carga_s": round(time.time() - t0, 1), "modelo": MODELO}), flush=True)
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        if linha == "sair":
            break
        try:
            pedido = json.loads(linha); t1 = time.time()
            r = s.sintetizar(pedido); r.update(ok=True, tempo_s=round(time.time() - t1, 1))
        except Exception as e:  # noqa
            r = {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:300]}"}
            if "CUDA" in str(e) or "device-side assert" in str(e):
                r["erro"] += " (erro de CUDA: o processo vai reiniciar no próximo pedido)"
                print(json.dumps(r, ensure_ascii=False), flush=True)
                break  # depois de um assert de CUDA o contexto fica inválido; melhor encerrar e deixar a ponte reerguer
        print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
