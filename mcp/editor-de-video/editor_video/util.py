import json, os, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

try:  # Windows nativo (10/11/2026): ferramentas portáteis em ~/EditorGS/bin e DLLs CUDA do pip; fora do repositório do Editor GS o motor segue sem isso
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from servico import plataforma
    plataforma.aplicar_path(); plataforma.registrar_dlls_cuda()
except Exception:  # noqa: BLE001
    plataforma = None

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def _stdin_vazio_por_padrao():
    """11/11/2026 (GRA-66): no MCP o stdin do processo é o canal JSON-RPC com o Claude. Filho sem stdin explícito (ffmpeg sem -nostdin,
    node do Remotion) herdava esse canal no Windows: o arquivo saía em segundos e a ferramenta só voltava no tempo-limite (30 min).
    Todo Popen sem stdin passa a receber DEVNULL; quem precisa de stdin (input=, stdin=PIPE) segue igual."""
    if getattr(subprocess.Popen, "_gs_stdin_vazio", False):
        return
    original = subprocess.Popen.__init__

    def __init__(self, *a, **k):
        if k.get("stdin") is None and len(a) < 4:  # stdin é o 4º posicional de Popen; ninguém aqui passa assim
            k["stdin"] = subprocess.DEVNULL
        original(self, *a, **k)
    subprocess.Popen.__init__ = __init__
    subprocess.Popen._gs_stdin_vazio = True


_stdin_vazio_por_padrao()


class ErroFerramenta(Exception):
    pass


_GLES = None


def preparar_mediapipe():
    """O MediaPipe (tasks) exige libGLESv2.so.2, que o Ubuntu do WSL não tem: carrega a cópia que veio com as libs do Chromium (07/11/2026).
    Sem isso o detector de rosto caía em "nenhum" calado (reenquadrar no centro). Idempotente."""
    global _GLES
    if _GLES is not None:
        return _GLES
    if not sys.platform.startswith("linux"):  # Windows/macOS: a roda do MediaPipe já traz o que precisa
        _GLES = "nativo"; return _GLES
    import ctypes
    for d in (Path.home() / ".local/lib-chromium/usr/lib/x86_64-linux-gnu",):
        lib = d / "libGLESv2.so.2"
        if lib.exists():
            try:
                ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL); _GLES = str(lib); return _GLES
            except OSError:
                pass
    _GLES = ""
    return _GLES


def caminho(p, deve_existir=True):
    c = Path(p).expanduser()
    if not c.is_absolute():
        c = Path.cwd() / c
    c = c.resolve()
    if deve_existir and not c.exists():
        raise ErroFerramenta(f"Arquivo não encontrado: {p}")
    return c


def caminho_saida(p):
    c = caminho(p, deve_existir=False)
    if "entrada" in [x.name for x in c.parents] or c.parent.name == "entrada":
        raise ErroFerramenta("Não gravo dentro de entrada/: escolha uma pasta de saída.")
    c.parent.mkdir(parents=True, exist_ok=True)
    return c


CRF_PREVIA = 28  # prévia 720p (10/11/2026): mais compressão, render mais rápido; nunca é a entrega


def caminho_previa(p):
    """Mesmo arquivo com sufixo `_previa` (final_9x16.mp4 → final_9x16_previa.mp4), já validado como saída."""
    c = Path(p)
    return caminho_saida(c.with_name(c.stem + "_previa" + c.suffix))


def rodar(cmd, timeout=3600):
    r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise ErroFerramenta(f"Comando falhou ({cmd[0]}): {r.stderr.strip()[-800:]}")
    return r


def info_midia(p):
    r = rodar([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", caminho(p)])
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(d.get("format", {}).get("duration") or 0)
    fps = None
    if v and v.get("avg_frame_rate") and v["avg_frame_rate"] != "0/0":
        n, m = v["avg_frame_rate"].split("/")
        fps = round(float(n) / float(m), 3) if float(m) else None
    return {
        "arquivo": str(caminho(p)), "duracao_s": round(dur, 3),
        "largura": v.get("width") if v else None, "altura": v.get("height") if v else None,
        "fps": fps, "codec_video": v.get("codec_name") if v else None,
        "tem_audio": a is not None, "codec_audio": a.get("codec_name") if a else None,
        "tamanho_mb": round(os.path.getsize(caminho(p)) / 1e6, 1),
    }


def nivel_audio(p, limite_s=None):
    cmd = [FFMPEG, "-hide_banner", "-nostats"]
    if limite_s:
        cmd += ["-t", str(limite_s)]
    cmd += ["-i", caminho(p), "-vn", "-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
    m1 = re.search(r"mean_volume:\s*(-?[\d.]+|-inf)", r.stderr)
    m2 = re.search(r"max_volume:\s*(-?[\d.]+|-inf)", r.stderr)
    f = lambda m: (float(m.group(1)) if m and m.group(1) != "-inf" else -99.0)
    return {"medio_db": f(m1), "pico_db": f(m2)}


def ler_json(p):
    with open(caminho(p), encoding="utf-8") as f:
        return json.load(f)


def salvar_json(p, dados):
    c = caminho_saida(p)
    with open(c, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    return str(c)


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def hex_para_ass(cor, alpha="00"):
    c = cor.lstrip("#")
    if len(c) != 6:
        raise ErroFerramenta(f"Cor inválida: {cor}")
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alpha}{b}{g}{r}".upper()


# ---- Áudio final (fase A, 07/11/2026): entregas no volume de rede social, como o Máquina (−16,8 LUFS medianos, LRA ~3) ----
ALVO_LUFS, ALVO_TP = -16.0, -1.5
COMPRIMIR_ACIMA_LRA = 4.5   # só comprime voz que varia muito; abaixo disso o loudnorm sozinho basta (evita achatar, LRA alvo ~3)
CADEIA_VOZ = "highpass=f=70,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=160:makeup=1"


def _loudnorm_medir(p, cadeia, alvo_lufs, alvo_tp):
    af = ",".join(x for x in (cadeia, f"loudnorm=I={alvo_lufs}:TP={alvo_tp}:LRA=7:print_format=json") if x)
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(p), "-vn", "-af", af, "-f", "null", "-"], capture_output=True, text=True, timeout=1800)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise ErroFerramenta("Não consegui medir o volume (loudnorm).")
    return json.loads(m.group(0))


def finalizar_audio(p, alvo_lufs=ALVO_LUFS, alvo_tp=ALVO_TP, tolerancia_lu=0.7):
    """Deixa a entrega no volume de rede social: loudnorm em duas passadas (−16 LUFS, pico −1,5 dBTP), com compressão leve de voz só quando a fala varia
    muito (LRA > 4,5), vídeo copiado sem recodificar. Pula sem áudio e quando o arquivo já está no alvo (não processa duas vezes se a ferramenta seguinte
    receber um vídeo já finalizado). Devolve as medidas antes/depois."""
    c = caminho(p)
    if not info_midia(c)["tem_audio"]:
        return {"feito": False, "motivo": "sem áudio"}
    bruto = _loudnorm_medir(c, "", alvo_lufs, alvo_tp)
    i0, tp0, lra0 = float(bruto["input_i"]), float(bruto["input_tp"]), float(bruto["input_lra"])
    if i0 < -60:
        return {"feito": False, "motivo": "áudio em silêncio", "lufs": i0}
    if abs(i0 - alvo_lufs) <= tolerancia_lu and tp0 <= alvo_tp + 0.5:
        return {"feito": False, "motivo": "já no alvo", "lufs": round(i0, 1), "true_peak": round(tp0, 1)}
    cadeia = CADEIA_VOZ if lra0 > COMPRIMIR_ACIMA_LRA else "highpass=f=70"
    m = _loudnorm_medir(c, cadeia, alvo_lufs, alvo_tp)
    filtro = (f"{cadeia},loudnorm=I={alvo_lufs}:TP={alvo_tp}:LRA=7:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000")
    tmp = c.with_name(c.stem + ".audio-tmp" + c.suffix)
    try:
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", c, "-map", "0:v?", "-map", "0:a:0", "-c:v", "copy", "-af", filtro,
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", tmp])
        os.replace(tmp, c)
    finally:
        if tmp.exists():
            tmp.unlink()
    d = _loudnorm_medir(c, "", alvo_lufs, alvo_tp)
    return {"feito": True, "comprimiu": cadeia == CADEIA_VOZ,
            "antes": {"lufs": round(i0, 1), "true_peak": round(tp0, 1), "lra": round(lra0, 1)},
            "depois": {"lufs": round(float(d["input_i"]), 1), "true_peak": round(float(d["input_tp"]), 1), "lra": round(float(d["input_lra"]), 1)}}
