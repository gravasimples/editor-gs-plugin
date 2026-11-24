"""Voz clonada no app (página Voz): lista as vozes de workspace/voz/<nome>/ com referências (trechos originais) e amostras (sintéticas)
para o Raphael ouvir dentro do Editor GS, grava a decisão dele em voz.json (motor escolhido, referência padrão, aprovação, uso por padrão na locução,
exagero/cfg do Chatterbox, parâmetros do Qwen) e gera amostra nova pelo mesmo processo do MCP (voz_qwen_worker.py no venv do Qwen ou
voz_clonada_worker.py no venv do Chatterbox), uma por vez. Motor padrão da voz: voz.json → motor_escolhido (Qwen desde 31/10/2026 15h30).
Regra: a voz clonada é sempre sintética e identificada como tal; esta página não publica nada e não muda os fluxos sozinha."""
import json, os, re, subprocess, threading, time, wave
from datetime import datetime
from pathlib import Path
from servico import plataforma

RAIZ = Path(__file__).resolve().parents[1]
WORKER = RAIZ / "mcp" / "editor-de-video" / "editor_video" / "voz_clonada_worker.py"
WORKER_QWEN = RAIZ / "mcp" / "editor-de-video" / "editor_video" / "voz_qwen_worker.py"
MOTORES = ("chatterbox", "qwen")
NOMES_MOTOR = {"chatterbox": "Chatterbox pt-BR", "qwen": "Qwen3-TTS"}
VENV_MOTOR = {"chatterbox": "~/.venvs/editor-gs-voz", "qwen": "~/.venvs/editor-gs-qwen"}
MODELO_ROTULO = {"chatterbox": "clone (Chatterbox pt-BR)", "qwen": "clone (Qwen3-TTS 0.6B Base)"}
QWEN_PADRAO = {"temperatura": 0.9, "top_p": 0.9, "repeticao": 1.05}
QWEN_LIMITES = {"temperatura": (0.1, 1.5), "top_p": (0.1, 1.0), "repeticao": (1.0, 1.5)}
from servico import caminhos as _cam
VOZ_DIR = _cam.WORKSPACE / "voz"
NOME_RE = re.compile(r"^[a-z0-9_\-]{1,40}$")
ARQ_RE = re.compile(r"^[\w\-. ]{1,120}\.(wav|mp3|m4a|ogg)$")  # \w aceita acento (ex.: aula_de_gravação)
LIMITES = {"exagero": (0.0, 1.0), "cfg": (0.0, 1.0), "temperatura": (0.1, 1.5)}
TEXTO_PADRAO = ("Ó, olha só. Muita gente acha que precisa de um estúdio caro pra gravar aula. A real é que não precisa. "
                "Com o OBS e a webcam que você já tem, dá pra deixar a imagem profissional em uma tarde. Vamos testar na prática.")

# geração em andamento (uma por vez; o worker ocupa a GPU inteira)
GERACAO = {"status": "parado", "voz": None, "inicio": None, "fim": None, "amostra": None, "erro": None, "etapa": None}
_LOCK = threading.Lock()


def home_real():
    try:
        import pwd
        h = Path(pwd.getpwuid(os.getuid()).pw_dir)
        if (h / ".venvs").exists():
            return h
    except Exception:  # noqa
        pass
    return Path.home()


def python_voz():
    return os.environ.get("EDITOR_GS_VOZ_PYTHON") or str(plataforma.python_venv(home_real() / ".venvs" / "editor-gs-voz"))


def python_qwen():
    return os.environ.get("EDITOR_GS_QWEN_PYTHON") or str(plataforma.python_venv(home_real() / ".venvs" / "editor-gs-qwen"))


def normalizar_motor(m):
    m = (m or "").strip().lower()
    return m if m in MOTORES else "chatterbox"


def python_motor(motor):
    return python_qwen() if normalizar_motor(motor) == "qwen" else python_voz()


def worker_motor(motor):
    return WORKER_QWEN if normalizar_motor(motor) == "qwen" else WORKER


def disponivel(motor="chatterbox"):
    return Path(python_motor(motor)).exists() and worker_motor(motor).exists()


def motores():
    return {m: disponivel(m) for m in MOTORES}


def texto_referencia(d: Path, ref_nome):
    """Transcrição exata da referência (o Qwen precisa dela): referencias/transcricoes.json, depois manifesto.json → texto."""
    for arq in ("transcricoes.json", "manifesto.json"):
        dados = _json(d / "referencias" / arq)
        v = dados.get(ref_nome) if isinstance(dados, dict) else None
        t = v.get("texto") if isinstance(v, dict) else v
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None


# cache da duração por (caminho, mtime, tamanho): o ffprobe por .wav a cada GET /api/gs/voz levava 4–5 s (11/11/2026)
_DURACOES = {}


def duracao_s(p: Path):
    """Duração do áudio com cache em memória por (caminho, mtime, tamanho); o arquivo mudou → mede de novo."""
    try:
        st = p.stat()
        chave = (str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if chave in _DURACOES:
        return _DURACOES[chave]
    v = _medir_duracao(p)
    if v is not None:
        _DURACOES[chave] = v
    return v


def _medir_duracao(p: Path):
    """Duração do áudio: wave (stdlib) para .wav; ffprobe para o resto. None se não der."""
    if p.suffix.lower() == ".wav":
        try:  # PCM comum; WAV float/extensível (torchaudio) cai no ffprobe
            with wave.open(str(p), "rb") as w:
                return round(w.getnframes() / float(w.getframerate() or 1), 2)
        except Exception:  # noqa
            pass
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=20)
        return round(float(r.stdout.strip()), 2) if r.returncode == 0 and r.stdout.strip() else None
    except Exception:  # noqa
        return None


def _json(p: Path, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return padrao if padrao is not None else {}


def _pasta(nome, voz_dir=None):
    if not NOME_RE.match(nome or ""):
        raise ValueError("Nome de voz inválido.")
    d = (voz_dir or VOZ_DIR) / nome
    if not d.is_dir():
        raise FileNotFoundError(f"Voz não encontrada: {nome}")
    return d


def referencias(d: Path):
    man = _json(d / "referencias" / "manifesto.json")
    out = []
    for p in sorted((d / "referencias").glob("*.wav")) if (d / "referencias").exists() else []:
        m = man.get(p.name) or {}
        out.append({"nome": p.name, "url": f"/voz-arquivos/{d.name}/referencias/{p.name}", "duracao_s": duracao_s(p), "origem": m.get("origem"),
                    "texto": m.get("texto"), "nivel_db": m.get("mean_db"), "cobertura": m.get("cobertura_transcricao")})
    return out


def amostras(d: Path):
    """Amostras sintéticas em <voz>/amostras/: cada áudio pode ter um .json ao lado {texto, referencia, modelo, quando, duracao_s, tempo_s, origem}."""
    out = []
    pasta = d / "amostras"
    if not pasta.exists():
        return out
    for p in sorted(pasta.iterdir(), key=lambda x: x.stat().st_mtime):
        if not ARQ_RE.match(p.name) or p.suffix.lower() == ".json":
            continue
        meta = _json(p.with_suffix(p.suffix + ".json"))
        out.append({"nome": p.name, "url": f"/voz-arquivos/{d.name}/amostras/{p.name}", "duracao_s": meta.get("duracao_s") or duracao_s(p),
                    "texto": meta.get("texto"), "referencia": meta.get("referencia"), "motor": meta.get("motor") or ("qwen" if "qwen" in (meta.get("modelo") or p.name).lower() else "chatterbox"),
                    "modelo": meta.get("modelo") or "clone (Chatterbox pt-BR)",
                    "quando": meta.get("quando") or datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes"),
                    "tempo_s": meta.get("tempo_s"), "origem": meta.get("origem") or "piloto", "nota": meta.get("nota"), "medidas": meta.get("medidas")})
    out.reverse()
    return out


def config(d: Path):
    c = _json(d / "voz.json")
    refs = sorted(p.name for p in (d / "referencias").glob("*.wav")) if (d / "referencias").exists() else []
    ref = c.get("referencia") if c.get("referencia") in refs else (refs[0] if refs else None)
    motor = normalizar_motor(c.get("motor_escolhido"))
    q = dict(QWEN_PADRAO); q.update({k: float(v) for k, v in (c.get("qwen") or {}).items() if k in QWEN_PADRAO and v is not None})
    return {"referencia": ref, "motor": motor, "motor_nome": NOMES_MOTOR[motor], "exagero": float(c.get("exagero", 0.5)), "cfg": float(c.get("cfg", 0.5)), "temperatura": float(c.get("temperatura", 0.8)),
            "qwen": q, "ref_text": texto_referencia(d, ref) if ref else None,
            "rotulo": c.get("rotulo") or f"voz clonada de {d.name} ({NOMES_MOTOR[motor]}, sintética, local)", "aprovada": bool(c.get("aprovada", False)),
            "padrao_locucao": bool(c.get("padrao_locucao", False)), "nota": c.get("nota") or "", "decidido_em": c.get("decidido_em"), "pronuncia": dict(c.get("pronuncia") or {})}


def listar(voz_dir=None):
    base = voz_dir or VOZ_DIR
    out = []
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        if not d.is_dir() or not NOME_RE.match(d.name):
            continue
        refs = referencias(d)
        if not refs:
            continue
        cfg = config(d)
        out.append({"nome": d.name, **cfg, "referencias": refs, "amostras": amostras(d), "disponivel": disponivel(cfg["motor"])})
    return out


def resumo(voz_dir=None):
    """Versão leve de listar() para a tela Início: só nome, padrão de locução e motor disponível, sem medir áudio (11/11/2026)."""
    base = voz_dir or VOZ_DIR
    out = []
    if not base.exists():
        return out
    for d in sorted(base.iterdir()):
        if not d.is_dir() or not NOME_RE.match(d.name) or not (d / "referencias").exists() or not any((d / "referencias").glob("*.wav")):
            continue
        c = _json(d / "voz.json")
        motor = normalizar_motor(c.get("motor_escolhido"))
        out.append({"nome": d.name, "motor": motor, "padrao_locucao": bool(c.get("padrao_locucao", False)), "aprovada": bool(c.get("aprovada", False)), "disponivel": disponivel(motor)})
    return out


def decidir(nome, referencia=None, exagero=None, cfg=None, temperatura=None, aprovada=None, padrao_locucao=None, nota=None, voz_dir=None, motor=None, qwen=None):
    """Grava a decisão humana em voz.json (só os campos enviados). A referência precisa existir em referencias/. motor: qwen | chatterbox; qwen: {temperatura, top_p, repeticao}."""
    d = _pasta(nome, voz_dir)
    c = _json(d / "voz.json")
    if motor is not None:
        if motor not in MOTORES:
            raise ValueError(f"Motor desconhecido: {motor} (use qwen ou chatterbox).")
        c["motor_escolhido"] = motor
        c["rotulo"] = f"voz clonada do Thiago ({NOMES_MOTOR[motor]}, sintética, local; autorizada em 31/10/2026)" if nome == "thiago" else f"voz clonada de {nome} ({NOMES_MOTOR[motor]}, sintética, local)"
    if qwen:
        atual = dict(c.get("qwen") or {})
        for campo, valor in qwen.items():
            if campo not in QWEN_LIMITES or valor is None:
                continue
            lo, hi = QWEN_LIMITES[campo]; v = float(valor)
            if not (lo <= v <= hi):
                raise ValueError(f"qwen.{campo} fora do intervalo {lo}–{hi}.")
            atual[campo] = v
        c["qwen"] = atual
    if referencia is not None:
        if not (d / "referencias" / referencia).exists() or "/" in referencia or ".." in referencia:
            raise ValueError(f"Referência não encontrada: {referencia}")
        c["referencia"] = referencia
    for campo, valor in (("exagero", exagero), ("cfg", cfg), ("temperatura", temperatura)):
        if valor is not None:
            lo, hi = LIMITES[campo]
            v = float(valor)
            if not (lo <= v <= hi):
                raise ValueError(f"{campo} fora do intervalo {lo}–{hi}.")
            c[campo] = v
    if aprovada is not None:
        c["aprovada"] = bool(aprovada)
    if padrao_locucao is not None:
        c["padrao_locucao"] = bool(padrao_locucao)
    if nota is not None:
        c["nota"] = str(nota).strip()[:1000]
    c.setdefault("rotulo", f"voz clonada de {nome} ({NOMES_MOTOR[normalizar_motor(c.get('motor_escolhido'))]}, sintética, local)")
    c["decidido_em"] = datetime.now().isoformat(timespec="minutes"); c["decidido_por"] = "Raphael (página Voz do Editor GS)"
    (d / "voz.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    return config(d)


def _sintetizar_processo(pedido, timeout_carga=900, timeout_sintese=1800):
    """Sobe o worker do motor do pedido num processo próprio, manda um pedido e encerra (libera a GPU no fim). Devolve o JSON de resposta."""
    motor = normalizar_motor(pedido.get("motor"))
    env = dict(os.environ); env.setdefault("PYTHONUNBUFFERED", "1")
    hr = home_real()
    if Path(env.get("HOME", "")) != hr:
        env["HOME"] = str(hr)
    env.setdefault("HF_HOME", str(hr / ".cache" / "huggingface"))
    p = subprocess.Popen([python_motor(motor), "-u", str(worker_motor(motor))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
    try:
        t0 = time.time(); pronto = None
        while True:
            linha = p.stdout.readline()
            if not linha:
                raise RuntimeError(f"O processo da voz clonada ({NOMES_MOTOR[motor]}) encerrou antes de ficar pronto (veja o venv {VENV_MOTOR[motor]}).")
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            if d.get("pronto"):
                pronto = d; break
            if time.time() - t0 > timeout_carga:
                raise RuntimeError("Tempo esgotado carregando a voz clonada.")
        GERACAO["etapa"] = f"{NOMES_MOTOR[motor]} carregado em {pronto.get('tempo_carga_s', '?')} s ({pronto.get('device', '?')}); sintetizando…"
        p.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n"); p.stdin.flush()
        out = {}
        def ler():
            while True:
                linha = p.stdout.readline()
                if not linha:
                    out["linha"] = ""; return
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if "progresso" in d:
                    pr = d["progresso"]
                    GERACAO["etapa"] = f"{NOMES_MOTOR[motor]} sintetizando a frase {pr.get('parte')}/{pr.get('de')} ({pr.get('s_gerados', 0)} s de fala prontos)…"
                    continue
                if "ok" in d:
                    out["linha"] = linha; return
        t = threading.Thread(target=ler, daemon=True); t.start(); t.join(timeout_sintese)
        if t.is_alive():
            raise RuntimeError("A síntese demorou demais e foi interrompida.")
        linha = out.get("linha") or ""
        if not linha:
            raise RuntimeError("O processo da voz clonada caiu durante a síntese.")
        r = json.loads(linha)
        if not r.get("ok"):
            raise RuntimeError(f"Voz clonada falhou: {r.get('erro')}")
        r["device"] = pronto.get("device"); r["tempo_carga_s"] = pronto.get("tempo_carga_s"); r["motor"] = motor
        return r
    finally:
        try:
            if p.poll() is None:
                p.stdin.write("sair\n"); p.stdin.flush(); p.wait(10)
        except Exception:  # noqa
            pass
        if p.poll() is None:
            p.kill()


def gerar_amostra(nome, texto, referencia=None, exagero=None, cfg=None, voz_dir=None, _sint=None, _em_thread=True, motor=None, ref_text=None, semente=None, qwen=None, idioma="pt"):
    """Gera uma amostra nova em <voz>/amostras/ com a referência pedida (ou a padrão) no motor pedido (ou o do voz.json). Roda em thread; estado em GERACAO.
    ref_text (Qwen) substitui a transcrição da referência; qwen = {temperatura, top_p, repeticao} só para esta amostra. `_sint(pedido) -> dict` substitui o processo real nos testes."""
    d = _pasta(nome, voz_dir)
    texto = (texto or "").strip()
    if len(texto) < 10 or len(texto) > 700:
        raise ValueError("Escreva de 10 a 700 caracteres para a amostra.")
    c = config(d)
    ref = referencia or c["referencia"]
    if not ref or not (d / "referencias" / ref).exists() or "/" in ref or ".." in ref:
        raise ValueError(f"Referência não encontrada: {ref}")
    if motor is not None and motor not in MOTORES:
        raise ValueError(f"Motor desconhecido: {motor} (use qwen ou chatterbox).")
    motor = motor or c["motor"]
    q = dict(c["qwen"]); q.update({k: float(v) for k, v in (qwen or {}).items() if k in QWEN_PADRAO and v is not None})
    for k, (lo, hi) in QWEN_LIMITES.items():  # validar ANTES de marcar a geração como em andamento
        if not (lo <= q[k] <= hi):
            raise ValueError(f"qwen.{k} fora do intervalo {lo}–{hi}.")
    if not _sint and not disponivel(motor):
        raise RuntimeError(f"Voz clonada indisponível neste computador: falta o venv {VENV_MOTOR[motor]} do motor {NOMES_MOTOR[motor]} (docs/VOZ-CLONADA.md).")
    with _LOCK:
        if GERACAO["status"] == "rodando":
            raise RuntimeError("Já tem uma amostra sendo gerada; espere terminar (a GPU só cabe uma por vez).")
        GERACAO.update(status="rodando", voz=nome, inicio=datetime.now().isoformat(timespec="seconds"), fim=None, amostra=None, erro=None,
                       etapa=f"carregando o {NOMES_MOTOR[motor]} ({'~2 min' if motor == 'qwen' else '~40 s'})…")
    pasta = d / "amostras"; pasta.mkdir(exist_ok=True)
    base = f"{datetime.now():%Y-%m-%d-%H%M%S}-{'qwen' if motor == 'qwen' else 'cb'}-{Path(ref).stem}"
    saida = pasta / f"{base}.wav"
    pedido = {"motor": motor, "texto": texto, "saida": str(saida), "ref": (d / "referencias" / ref).as_posix(), "idioma": idioma, "pronuncia": c.get("pronuncia") or {}}
    if motor == "qwen":
        rt = (ref_text or "").strip() or texto_referencia(d, ref)
        pedido["ref_text"] = rt
        pedido.update(q)
    else:
        pedido.update(exagero=float(c["exagero"] if exagero is None else exagero), cfg=float(c["cfg"] if cfg is None else cfg), temperatura=c["temperatura"])
    if semente is not None:
        pedido["semente"] = int(semente)

    def rodar():
        t0 = time.time()
        try:
            r = (_sint or _sintetizar_processo)(pedido)
            if not saida.exists() or saida.stat().st_size < 1000:
                raise RuntimeError("A voz clonada não devolveu áudio.")
            meta = {"texto": texto, "referencia": ref, "motor": motor, "modelo": MODELO_ROTULO[motor], "quando": datetime.now().isoformat(timespec="minutes"),
                    "duracao_s": r.get("duracao_s") or duracao_s(saida), "tempo_s": round(time.time() - t0, 1), "tempo_sintese_s": r.get("tempo_s"), "origem": "pagina-voz",
                    "exagero": pedido.get("exagero"), "cfg": pedido.get("cfg"), "semente": pedido.get("semente"), "device": r.get("device"), "partes": r.get("partes")}
            if motor == "qwen":
                meta.update(qwen={k: pedido[k] for k in QWEN_PADRAO}, ref_text=bool(pedido.get("ref_text")), modo=r.get("modo"))
                if not pedido.get("ref_text"):
                    meta["nota"] = "referência sem transcrição: o Qwen usou só o timbre (x_vector_only)"
            saida.with_suffix(".wav.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            GERACAO.update(status="pronto", fim=datetime.now().isoformat(timespec="seconds"), etapa=None,
                           amostra={"nome": saida.name, "url": f"/voz-arquivos/{nome}/amostras/{saida.name}", **meta})
        except Exception as e:  # noqa
            saida.unlink(missing_ok=True)
            GERACAO.update(status="erro", fim=datetime.now().isoformat(timespec="seconds"), erro=str(e), etapa=None)

    if _em_thread:
        threading.Thread(target=rodar, daemon=True).start()
    else:
        rodar()
    return {"status": GERACAO["status"], "arquivo": saida.name, "referencia": ref, "texto": texto, "motor": motor}


def apagar_amostra(nome, arquivo, voz_dir=None):
    d = _pasta(nome, voz_dir)
    if not ARQ_RE.match(arquivo or "") or "/" in arquivo or ".." in arquivo:
        raise ValueError("Arquivo inválido.")
    p = d / "amostras" / arquivo
    if not p.exists():
        raise FileNotFoundError("Amostra não encontrada.")
    p.unlink(); p.with_suffix(p.suffix + ".json").unlink(missing_ok=True)
    return {"apagada": arquivo}


def estado():
    return dict(GERACAO)
