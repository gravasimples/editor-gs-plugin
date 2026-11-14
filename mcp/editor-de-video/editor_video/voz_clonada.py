"""Voz clonada no Editor GS (local e gratuita; autorizada por Raphael em 31/10/2026).
- Dois motores, escolhidos por workspace/voz/<nome>/voz.json → "motor_escolhido": "qwen" (Qwen3-TTS-12Hz-0.6B-Base, Apache 2.0; escolhido pelo Raphael em
  31/10/2026 15h30 por soar mais parecido) ou "chatterbox" (Chatterbox Multilingual pt-BR, MIT; reserva). Padrão sem o campo: chatterbox.
- As vozes ficam em workspace/voz/<nome>/referencias/*.wav (fora do git) com voz.json opcional {"referencia", "motor_escolhido", "exagero", "cfg", "temperatura",
  "rotulo", "pronuncia", "qwen": {"temperatura", "top_p", "repeticao", "max_tokens"}}. O Qwen precisa do texto exato da referência (referencias/transcricoes.json
  ou manifesto.json → "texto"); sem ele cai em x_vector_only e fica pior.
- A síntese roda num processo à parte por motor (voz_clonada_worker.py no venv ~/.venvs/editor-gs-voz; voz_qwen_worker.py no venv ~/.venvs/editor-gs-qwen),
  carregado uma vez por sessão do MCP, descarregado depois de um tempo ocioso (a GPU de 4 GB só cabe um motor por vez).
- Os tempos por palavra vêm do faster-whisper (transcricao.transcrever) sobre o áudio gerado, no mesmo formato de palavras.json.
Regra: a voz clonada é sempre identificada como clonada ("origem": "tts-clonada", aviso na resposta); nunca é apresentada como gravação do Thiago."""
import json, os, subprocess, sys, threading, time
from pathlib import Path
from .util import caminho_saida, ErroFerramenta, FFMPEG, info_midia, rodar

_AQUI = Path(__file__).resolve().parent
WORKER = _AQUI / "voz_clonada_worker.py"
WORKER_QWEN = _AQUI / "voz_qwen_worker.py"
MOTORES = ("chatterbox", "qwen")
MOTOR_PADRAO = "chatterbox"
NOMES_MOTOR = {"chatterbox": "Chatterbox pt-BR", "qwen": "Qwen3-TTS"}
VENV_MOTOR = {"chatterbox": "~/.venvs/editor-gs-voz", "qwen": "~/.venvs/editor-gs-qwen"}
OCIOSO_S = float(os.environ.get("EDITOR_GS_VOZ_OCIOSO_S", "600"))  # descarrega o modelo (libera a VRAM) depois desse tempo sem pedido


def home_real():
    """Pasta do usuário de verdade: o MCP pode rodar com HOME temporário (Paperclip), e aí ~/.venvs e ~/.cache/huggingface sumiriam."""
    candidatos = []
    try:
        import pwd
        candidatos.append(Path(pwd.getpwuid(os.getuid()).pw_dir))
    except Exception:  # noqa
        pass
    candidatos.append(Path.home())
    for c in candidatos:
        if (c / ".venvs").exists():
            return c
    return candidatos[-1]


def python_voz(motor=MOTOR_PADRAO):
    if motor == "qwen":
        return os.environ.get("EDITOR_GS_QWEN_PYTHON") or str(home_real() / ".venvs" / "editor-gs-qwen" / "bin" / "python")
    return os.environ.get("EDITOR_GS_VOZ_PYTHON") or str(home_real() / ".venvs" / "editor-gs-voz" / "bin" / "python")


def worker_de(motor=MOTOR_PADRAO):
    return WORKER_QWEN if motor == "qwen" else WORKER


def normalizar_motor(m):
    m = (m or "").strip().lower()
    return m if m in MOTORES else MOTOR_PADRAO


def rotulo_padrao(nome, motor):
    return f"voz clonada de {nome} ({NOMES_MOTOR.get(motor, motor)}, sintética, local)"


def texto_referencia(d, ref_nome):
    """Transcrição exata do trecho de referência (obrigatória no Qwen): referencias/transcricoes.json primeiro, depois manifesto.json → texto."""
    for arq in ("transcricoes.json", "manifesto.json"):
        p = d / "referencias" / arq
        if not p.exists():
            continue
        try:
            dados = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa
            continue
        v = dados.get(ref_nome)
        t = v.get("texto") if isinstance(v, dict) else v
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None


def pasta_vozes():
    p = os.environ.get("EDITOR_GS_VOZ_DIR")
    return Path(p) if p else (_AQUI.parents[2] / "workspace" / "voz")


def listar():
    """Vozes clonadas disponíveis: {nome: {"referencia", "n_referencias", "rotulo", ...}}."""
    out = {}
    base = pasta_vozes()
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        refs = sorted((d / "referencias").glob("*.wav")) if (d / "referencias").exists() else []
        if not d.is_dir() or not refs:
            continue
        cfg = {}
        if (d / "voz.json").exists():
            try:
                cfg = json.loads((d / "voz.json").read_text(encoding="utf-8"))
            except Exception:  # noqa
                cfg = {}
        ref = d / "referencias" / cfg["referencia"] if cfg.get("referencia") else refs[0]
        if not ref.exists():
            ref = refs[0]
        motor = normalizar_motor(cfg.get("motor_escolhido"))
        q = dict(cfg.get("qwen") or {})
        out[d.name] = {"referencia": str(ref), "n_referencias": len(refs), "motor": motor, "rotulo": cfg.get("rotulo") or rotulo_padrao(d.name, motor),
                       "ref_text": texto_referencia(d, ref.name),
                       "exagero": float(cfg.get("exagero", 0.5)), "cfg": float(cfg.get("cfg", 0.5)), "temperatura": float(cfg.get("temperatura", 0.8)),
                       "pronuncia": dict(cfg.get("pronuncia") or {}),
                       "qwen": {k: q[k] for k in ("temperatura", "top_p", "repeticao", "max_tokens") if q.get(k) is not None}}
    return out


def nome_clonado(voz):
    """'thiago' ou 'clonada:thiago' → 'thiago' se existir; senão None."""
    v = (voz or "").strip().lower()
    if v.startswith("clonada:"):
        v = v.split(":", 1)[1]
    return v if v and v in listar() else None


def disponivel(motor=MOTOR_PADRAO):
    motor = normalizar_motor(motor)
    return Path(python_voz(motor)).exists() and worker_de(motor).exists()


def motores_disponiveis():
    return {m: disponivel(m) for m in MOTORES}


class _Worker:
    """Processo persistente de um motor; uma linha JSON por pedido. Reinicia sozinho se cair; descarrega depois de OCIOSO_S sem pedido."""
    def __init__(self, motor=MOTOR_PADRAO):
        self.motor = normalizar_motor(motor); self.p = None; self.info = {}; self.lock = threading.Lock(); self._timer = None; self.progresso = None

    def _subir(self, timeout=900):
        env = dict(os.environ); env.setdefault("PYTHONUNBUFFERED", "1")
        hr = home_real()
        if Path(env.get("HOME", "")) != hr:  # HOME temporário do MCP: o worker precisa do cache dos modelos e das referências do usuário real
            env["HOME"] = str(hr)
        env.setdefault("HF_HOME", str(hr / ".cache" / "huggingface"))
        self.p = subprocess.Popen([python_voz(self.motor), "-u", str(worker_de(self.motor))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
        t0 = time.time()
        while True:
            linha = self.p.stdout.readline()
            if not linha:
                raise ErroFerramenta(f"O processo da voz clonada ({NOMES_MOTOR[self.motor]}) encerrou antes de ficar pronto (veja o venv {VENV_MOTOR[self.motor]}).")
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            if d.get("pronto"):
                self.info = d; return
            if time.time() - t0 > timeout:
                raise ErroFerramenta("Tempo esgotado carregando a voz clonada.")

    def _agendar_descarga(self):
        if self._timer:
            self._timer.cancel()
        if OCIOSO_S > 0:
            self._timer = threading.Timer(OCIOSO_S, self.fechar); self._timer.daemon = True; self._timer.start()

    def pedir(self, pedido, timeout=None, ao_progresso=None):
        """timeout None = 10 min + 1 s por caractere (o Qwen leva ~0,5 s por caractere na GTX 1650). ao_progresso(dict) recebe cada {"parte","de","s_gerados"}."""
        if timeout is None:
            timeout = 600 + len(pedido.get("texto") or "")
        with self.lock:
            if self._timer:
                self._timer.cancel(); self._timer = None
            if self.p is None or self.p.poll() is not None:
                _fechar_outros(self.motor)  # a GPU só cabe um motor por vez
                self._subir()
            try:
                self.p.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n"); self.p.stdin.flush()
            except (BrokenPipeError, OSError):
                self.p = None; self._subir()
                self.p.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n"); self.p.stdin.flush()
            out = {}; self.progresso = None
            def ler():
                while True:
                    linha = self.p.stdout.readline()
                    if not linha:
                        out["linha"] = ""; return
                    try:
                        d = json.loads(linha)
                    except ValueError:
                        continue
                    if "progresso" in d:
                        self.progresso = d["progresso"]
                        if ao_progresso:
                            try:
                                ao_progresso(d["progresso"])
                            except Exception:  # noqa
                                pass
                        continue
                    if "ok" in d:
                        out["linha"] = linha; return
            t = threading.Thread(target=ler, daemon=True); t.start(); t.join(timeout)
            if t.is_alive():
                self.p.kill(); self.p = None
                raise ErroFerramenta(f"A síntese com voz clonada demorou mais de {int(timeout // 60)} min e foi interrompida (última etapa: {self.progresso}).")
            linha = out.get("linha") or ""
            if not linha:
                self.p = None
                raise ErroFerramenta("O processo da voz clonada caiu durante a síntese.")
            r = json.loads(linha)
            self._agendar_descarga()
            if not r.get("ok"):
                raise ErroFerramenta(f"Voz clonada ({NOMES_MOTOR[self.motor]}) falhou: {r.get('erro')}")
            r["motor"] = self.motor; r["device"] = self.info.get("device")
            return r

    def fechar(self):
        if self._timer:
            self._timer.cancel(); self._timer = None
        if self.p and self.p.poll() is None:
            try:
                self.p.stdin.write("sair\n"); self.p.stdin.flush(); self.p.wait(10)
            except Exception:  # noqa
                self.p.kill()
        self.p = None


_workers = {m: _Worker(m) for m in MOTORES}
_worker = _workers[MOTOR_PADRAO]  # compatibilidade


def _fechar_outros(motor):
    for m, w in _workers.items():
        if m != motor and w.p is not None:
            w.fechar()


def worker_para(motor):
    return _workers[normalizar_motor(motor)]


def montar_pedido(v, texto, saida_wav, idioma="pt", semente=None, motor=None, referencia=None, ref_text=None):
    """Pedido ao worker do motor (o do voz.json, salvo `motor` explícito). Chatterbox leva exagero/cfg/temperatura; Qwen leva ref_text e os parâmetros de geração."""
    motor = normalizar_motor(motor or v.get("motor"))
    ref = str(referencia or v["referencia"])
    pedido = {"motor": motor, "texto": texto, "saida": str(saida_wav), "ref": ref, "idioma": idioma, "pronuncia": v.get("pronuncia") or {}}
    if motor == "qwen":
        d = Path(ref).parents[1]
        rt = (ref_text or "").strip() or (v.get("ref_text") if ref == str(v["referencia"]) else None) or texto_referencia(d, Path(ref).name)
        pedido["ref_text"] = rt
        pedido.update(v.get("qwen") or {})
    else:
        pedido.update(exagero=v["exagero"], cfg=v["cfg"], temperatura=v["temperatura"])
    if semente is not None:
        pedido["semente"] = int(semente)
    return pedido


def sintetizar(texto, saida_wav, nome, idioma="pt", semente=None, _pedir=None, motor=None, referencia=None, ref_text=None, ao_progresso=None):
    """Gera saida_wav (24 kHz mono) com a voz clonada `nome` no motor do voz.json. Devolve {"duracao_s", "partes", "tempo_s", "referencia", "rotulo", "motor", "avisos"}."""
    vozes = listar()
    if nome not in vozes:
        raise ErroFerramenta(f"Voz clonada não encontrada: {nome} (disponíveis: {', '.join(vozes) or 'nenhuma'}).")
    v = vozes[nome]
    pedido = montar_pedido(v, texto, saida_wav, idioma=idioma, semente=semente, motor=motor, referencia=referencia, ref_text=ref_text)
    m = pedido["motor"]
    if not _pedir and not disponivel(m):
        raise ErroFerramenta(f"Voz clonada indisponível: falta o venv {VENV_MOTOR[m]} do motor {NOMES_MOTOR[m]} (ver docs/VOZ-CLONADA.md).")
    avisos = []
    if m == "qwen" and not pedido.get("ref_text"):
        avisos.append("referência sem transcrição (referencias/transcricoes.json): o Qwen usou só o timbre (x_vector_only), a entonação fica pior")
    r = _pedir(pedido) if _pedir else worker_para(m).pedir(pedido, ao_progresso=ao_progresso)
    r.update(referencia=pedido["ref"], rotulo=v["rotulo"], motor=m, avisos=avisos)
    return r


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t.lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return "".join(c for c in t if c.isalnum())


def alinhar_texto(ouvidas, texto, duracao_s=None):
    """Casa as palavras ouvidas pelo Whisper com o texto que foi narrado e devolve as palavras do TEXTO (grafia exata) com os tempos ouvidos.
    Trechos que o Whisper ouviu diferente recebem o intervalo do trecho dividido por igual; palavras que ele não ouviu são interpoladas entre vizinhas."""
    import difflib
    toks = texto.split()
    if not toks:
        return []
    if not ouvidas:
        d = float(duracao_s or (0.3 * len(toks))); passo = d / len(toks)
        return [{"palavra": w, "inicio": round(i * passo, 3), "fim": round((i + 1) * passo - 0.02, 3), "prob": 0.0} for i, w in enumerate(toks)]
    a = [_norm(w) for w in toks]; b = [_norm(p["palavra"]) for p in ouvidas]
    saida = [None] * len(toks)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                o = ouvidas[j1 + k]; saida[i1 + k] = {"palavra": toks[i1 + k], "inicio": o["inicio"], "fim": o["fim"], "prob": o.get("prob", 1.0)}
        elif op == "replace":
            ini, fim = ouvidas[j1]["inicio"], ouvidas[j2 - 1]["fim"]; n = i2 - i1; passo = max(0.0, fim - ini) / n
            for k in range(n):
                saida[i1 + k] = {"palavra": toks[i1 + k], "inicio": round(ini + k * passo, 3), "fim": round(ini + (k + 1) * passo, 3), "prob": 0.5}
    # palavras do texto sem tempo (insert): interpola entre a vizinha anterior e a seguinte
    i = 0
    while i < len(saida):
        if saida[i] is not None:
            i += 1; continue
        j = i
        while j < len(saida) and saida[j] is None:
            j += 1
        ini = saida[i - 1]["fim"] if i > 0 else 0.0
        fim = saida[j]["inicio"] if j < len(saida) else (duracao_s or ini + 0.3 * (j - i))
        if fim <= ini:
            fim = ini + 0.25 * (j - i)
            if j < len(saida):  # empurra a vizinha seguinte para não sobrepor
                pass
        passo = (fim - ini) / (j - i)
        for k in range(i, j):
            saida[k] = {"palavra": toks[k], "inicio": round(ini + (k - i) * passo, 3), "fim": round(ini + (k - i + 1) * passo - 0.01, 3), "prob": 0.3}
        i = j
    # monotonia
    for k in range(1, len(saida)):
        if saida[k]["inicio"] < saida[k - 1]["fim"]:
            saida[k]["inicio"] = saida[k - 1]["fim"]
        if saida[k]["fim"] < saida[k]["inicio"]:
            saida[k]["fim"] = round(saida[k]["inicio"] + 0.05, 3)
    return saida


def palavras_por_whisper(audio, texto, idioma="pt"):
    """Tempos por palavra do áudio gerado (faster-whisper em CPU) alinhados ao texto narrado: a legenda mostra o texto exato, com os tempos ouvidos."""
    from . import transcricao
    pj = Path(str(audio) + ".whisper.json")
    try:
        transcricao.transcrever(audio, pj, modelo="small", idioma=idioma, device="cpu")  # áudio curto; evita depender da CUDA do venv do app
        dados = json.loads(pj.read_text(encoding="utf-8"))
    finally:
        pj.unlink(missing_ok=True)
    ouvidas = [{"palavra": p["palavra"], "inicio": p["inicio"], "fim": p["fim"], "prob": p["prob"]} for p in dados.get("palavras", [])]
    return alinhar_texto(ouvidas, texto, duracao_s=dados.get("duracao_s"))


def narrar(texto, saida_audio, nome, idioma="pt", saida_palavras=None, semente=None, _pedir=None, _palavras=None):
    """Mesmo contrato de voz.narrar, com voz clonada. origem = tts-clonada; a resposta traz aviso explícito."""
    from .voz import _segmentos
    out = caminho_saida(saida_audio)
    bruto = out.with_suffix(".clonada.wav")
    r = sintetizar(texto, bruto, nome, idioma=idioma, semente=semente, _pedir=_pedir)
    if not bruto.exists() or bruto.stat().st_size < 1000:
        raise ErroFerramenta("A voz clonada não devolveu áudio.")
    rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", bruto, "-ar", "48000", "-ac", "2", out]); bruto.unlink(missing_ok=True)
    palavras = (_palavras or palavras_por_whisper)(out, texto, idioma)
    dur = info_midia(out)["duracao_s"]
    rot = r["rotulo"]
    d = {"arquivo": str(out), "origem": "tts-clonada", "voz": f"clonada:{nome}", "motor": r.get("motor"), "rotulo": rot, "idioma": idioma, "texto": texto, "palavras": palavras, "segmentos": _segmentos(palavras),
         "aviso": f"Áudio sintético: {rot}. Não é gravação do Thiago; informar na entrega."}
    pj = None
    if saida_palavras:
        pj = caminho_saida(saida_palavras); pj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"audio": str(out), "duracao_s": dur, "n_palavras": len(palavras), "voz": f"clonada:{nome}", "motor": r.get("motor"), "rotulo": rot, "palavras_json": str(pj) if pj else None,
            "palavras": palavras, "tempo_sintese_s": r.get("tempo_s"), "partes": r.get("partes"), "aviso": d["aviso"], "avisos": r.get("avisos") or []}
