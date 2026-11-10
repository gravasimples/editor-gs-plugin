import re, subprocess
from .util import FFMPEG, caminho, info_midia, nivel_audio


def detectar_silencios(midia, limiar_db=-35.0, min_s=0.35):
    m = caminho(midia)
    info = info_midia(m)
    if not info["tem_audio"]:
        return {"arquivo": str(m), "duracao_s": info["duracao_s"], "silencios": [], "aviso": "sem faixa de áudio"}
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(m), "-vn", "-af", f"silencedetect=noise={limiar_db}dB:d={min_s}", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    sil, inicio = [], None
    for linha in r.stderr.splitlines():
        a = re.search(r"silence_start:\s*(-?[\d.]+)", linha)
        b = re.search(r"silence_end:\s*(-?[\d.]+)", linha)
        if a:
            inicio = max(0.0, float(a.group(1)))
        elif b and inicio is not None:
            fim = float(b.group(1)); sil.append({"inicio": round(inicio, 3), "fim": round(fim, 3), "duracao": round(fim - inicio, 3)}); inicio = None
    if inicio is not None:
        sil.append({"inicio": round(inicio, 3), "fim": info["duracao_s"], "duracao": round(info["duracao_s"] - inicio, 3)})
    total = round(sum(s["duracao"] for s in sil), 2)
    return {"arquivo": str(m), "duracao_s": info["duracao_s"], "limiar_db": limiar_db, "min_s": min_s,
            "nivel_audio": nivel_audio(m), "n_silencios": len(sil), "silencio_total_s": total,
            "fracao_silencio": round(total / info["duracao_s"], 3) if info["duracao_s"] else 0, "silencios": sil}
