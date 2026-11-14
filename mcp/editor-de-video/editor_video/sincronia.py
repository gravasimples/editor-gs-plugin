import subprocess
import numpy as np
from .util import FFMPEG, caminho, caminho_saida, rodar, info_midia, nivel_audio, ErroFerramenta

SR = 16000


def _pcm(p, limite_s):
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(p), "-t", str(limite_s), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise ErroFerramenta(f"Não li o áudio de {p}: {r.stderr.decode(errors='ignore')[-300:]}")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _envelope(x, janela=320):
    n = len(x) // janela
    e = np.sqrt(np.mean(x[: n * janela].reshape(n, janela) ** 2, axis=1))
    return (e - e.mean()) / (e.std() + 1e-9)


def estimar_deslocamento(video, audio, limite_s=180):
    """Deslocamento (s) a aplicar no áudio para alinhar com o vídeo. Positivo = áudio começa depois."""
    a = _envelope(_pcm(caminho(video), limite_s)); b = _envelope(_pcm(caminho(audio), limite_s))
    n = 1
    while n < len(a) + len(b):
        n *= 2
    corr = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    lag = int(np.argmax(corr)); pico = float(corr[lag] / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    if lag > n // 2:
        lag -= n
    return round(lag * 320 / SR, 3), round(pico, 3)


def sincronizar_audio(video, audio, saida_video, deslocamento_s=None, limite_s=180):
    v, a = caminho(video), caminho(audio)
    nivel_v = nivel_audio(v, limite_s=limite_s) if info_midia(v)["tem_audio"] else {"pico_db": -99.0}
    metodo = "informado"
    confianca = None
    if deslocamento_s is None:
        if nivel_v["pico_db"] <= -60:
            raise ErroFerramenta("O vídeo não tem áudio para alinhar por correlação. Informe deslocamento_s (segundos; positivo atrasa o áudio).")
        deslocamento_s, confianca = estimar_deslocamento(v, a, limite_s); metodo = "correlacao"
    out = caminho_saida(saida_video)
    off = float(deslocamento_s)
    cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v]
    if off >= 0:
        cmd += ["-itsoffset", f"{off}", "-i", a]
    else:
        cmd += ["-ss", f"{-off}", "-i", a]
    cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    rodar(cmd)
    return {"video": str(out), "deslocamento_s": off, "metodo": metodo, "confianca": confianca, "duracao_s": info_midia(out)["duracao_s"]}
