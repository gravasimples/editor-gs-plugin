"""Processo de síntese com voz clonada (Chatterbox Multilingual, checkpoint pt-BR da Resemble, MIT).
Roda no venv ~/.venvs/editor-gs-voz (Python 3.11 + torch), separado do venv do app. Protocolo: uma linha JSON por pedido no stdin,
uma linha JSON por resposta no stdout. Pedido: {"texto", "saida" (wav), "ref" (wav de referência), "idioma"?: "pt", "exagero"?: 0.5,
"cfg"?: 0.5, "temperatura"?: 0.8, "semente"?: int}. Antes de cada frase emite {"progresso": {"parte", "de", "s_gerados"}}; resposta final {"ok": true, "duracao_s", "partes", "tempo_s"} ou {"ok": false, "erro"}.
Primeira linha emitida: {"pronto": true, "device", "tempo_carga_s", "modelo"}.
Autorizada por Raphael em 31/10/2026; a voz clonada nunca é apresentada como gravação do Thiago."""
import json, os, re, sys, time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
REPO_BASE = "ResembleAI/chatterbox"
REPO_PTBR = "ResembleAI/Chatterbox-Multilingual-pt-br"
CACHE = Path(os.environ.get("EDITOR_GS_VOZ_CACHE", Path.home() / ".cache" / "editor-gs-voz")) / "chatterbox-ptbr"
MAX_CHARS = 280  # o modelo degrada acima de ~300 caracteres por chamada
PRONUNCIA = {"OBS": "ô bê ésse", "OBS Studio": "ô bê ésse Studio", "URL": "u erre éle", "HDMI": "agá dê ême i", "USB": "u ésse bê", "PC": "pê cê", "TV": "tê vê"}


def aplicar_pronuncia(texto, extra=None, base=True):
    """Siglas faladas letra a letra (o modelo tende a ler 'OBS' como palavra). Mais longas primeiro; só palavra inteira.
    base=False usa só o mapa `extra` (para testar a leitura crua do modelo). Valor vazio em `extra` apaga a entrada padrão."""
    mapa = dict(PRONUNCIA) if base else {}; mapa.update(extra or {})
    mapa = {k: v for k, v in mapa.items() if v}
    for k in sorted(mapa, key=len, reverse=True):
        texto = re.sub(r"(?<!\w)" + re.escape(k) + r"(?!\w)", mapa[k], texto)
    return texto


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def preparar_pasta():
    """Junta, numa pasta própria, os arquivos base (ve, s3gen, tokenizer) e o T3 ajustado em pt-BR."""
    from huggingface_hub import snapshot_download, hf_hub_download
    CACHE.mkdir(parents=True, exist_ok=True)
    base = Path(snapshot_download(repo_id=REPO_BASE, repo_type="model", revision="main",
                                  allow_patterns=["ve.pt", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"]))
    t3 = Path(hf_hub_download(repo_id=REPO_PTBR, filename="t3_pt_br.safetensors"))
    for src in list(base.iterdir()) + [t3]:
        dst = CACHE / src.name
        if not dst.exists():
            try:
                os.symlink(src.resolve(), dst)
            except OSError:
                import shutil; shutil.copy2(src, dst)
    return CACHE


def carregar(device=None):
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    pasta = preparar_pasta()
    try:
        m = ChatterboxMultilingualTTS.from_local(pasta, device, t3_model="t3_pt_br.safetensors")
    except RuntimeError as e:  # VRAM curta → CPU
        if device == "cuda" and "out of memory" in str(e).lower():
            _log("CUDA sem memória; usando CPU"); torch.cuda.empty_cache(); device = "cpu"
            m = ChatterboxMultilingualTTS.from_local(pasta, device, t3_model="t3_pt_br.safetensors")
        else:
            raise
    return m, device


def dividir(texto, max_chars=MAX_CHARS):
    """Divide em frases; junta frases curtas até max_chars; frase gigante é partida em vírgulas."""
    texto = re.sub(r"\s+", " ", texto).strip()
    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto) if f.strip()]
    partes, atual = [], ""
    for f in frases:
        if len(f) > max_chars:
            for sub in re.split(r"(?<=[,;:])\s+", f):
                pedacos = [sub]
                if len(sub) > max_chars:  # sem pontuação: corta por palavras
                    pedacos, p = [], ""
                    for w in sub.split():
                        if len(p) + len(w) + 1 <= max_chars:
                            p = (p + " " + w).strip()
                        else:
                            if p: pedacos.append(p)
                            p = w
                    if p: pedacos.append(p)
                for sub2 in pedacos:
                    if len(atual) + len(sub2) + 1 <= max_chars:
                        atual = (atual + " " + sub2).strip()
                    else:
                        if atual: partes.append(atual)
                        atual = sub2
            continue
        if len(atual) + len(f) + 1 <= max_chars:
            atual = (atual + " " + f).strip()
        else:
            partes.append(atual); atual = f
    if atual: partes.append(atual)
    return partes or [texto]


def sintetizar(m, device, pedido):
    import torch, torchaudio as ta
    texto = pedido["texto"]; ref = pedido["ref"]; saida = Path(pedido["saida"])
    if not Path(ref).exists():
        raise FileNotFoundError(f"referência não encontrada: {ref}")
    if pedido.get("semente") is not None:
        torch.manual_seed(int(pedido["semente"]))
    idioma = (pedido.get("idioma") or "pt")[:2].lower()
    exagero = float(pedido.get("exagero", 0.5)); cfg = float(pedido.get("cfg", 0.5)); temp = float(pedido.get("temperatura", 0.8))
    partes = dividir(aplicar_pronuncia(texto, pedido.get("pronuncia")))
    m.prepare_conditionals(ref, exaggeration=exagero)
    pausa = torch.zeros(1, int(m.sr * float(pedido.get("pausa_s", 0.25))))
    wavs = []
    for i, p in enumerate(partes):
        print(json.dumps({"progresso": {"parte": i + 1, "de": len(partes), "s_gerados": round(sum(x.shape[1] for x in wavs) / m.sr, 1)}}), flush=True)
        with torch.inference_mode():
            w = m.generate(p, language_id=idioma, exaggeration=exagero, cfg_weight=cfg, temperature=temp).cpu()
        wavs.append(w)
        if i < len(partes) - 1:
            wavs.append(pausa)
    wav = torch.cat(wavs, dim=1)
    saida.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(saida), wav, m.sr)
    return {"duracao_s": round(wav.shape[1] / m.sr, 3), "partes": len(partes), "sr": m.sr}


def main():
    t0 = time.time()
    m, device = carregar(os.environ.get("EDITOR_GS_VOZ_DEVICE"))
    print(json.dumps({"pronto": True, "device": device, "tempo_carga_s": round(time.time() - t0, 1), "modelo": REPO_PTBR}), flush=True)
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        if linha == "sair":
            break
        try:
            pedido = json.loads(linha); t1 = time.time()
            r = sintetizar(m, device, pedido); r.update(ok=True, tempo_s=round(time.time() - t1, 1))
        except Exception as e:  # noqa
            r = {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:300]}"}
        print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
