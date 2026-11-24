"""Cena ruim de propósito (15/11/2026, visto nos Criativos do Máquina: "Meet e Zoom"). Para mostrar o PROBLEMA antes da solução,
um trecho do vídeo cortado fica feio de propósito: som de rádio ou microfone ruim, webcam pixelada, preto e branco com vinheta
para a dúvida ou a citação. Só ffmpeg, com o filtro ligado por tempo (enable=between), o resto do vídeo passa igual.
Rodar no vídeo CORTADO, antes do montar_remotion (os tempos são os do cortado). Efeito sem motivo na fala não entra."""
from .util import FFMPEG, ErroFerramenta, caminho, caminho_saida, info_midia, rodar

# efeito → (filtros de vídeo, filtros de áudio); {e} vira o enable do trecho; {px}/{px2} = bloco proporcional à largura (rosto ainda reconhecível)
EFEITOS = {
    "radio": ([], ["highpass=f=450:enable='{e}'", "lowpass=f=2600:enable='{e}'", "acrusher=bits=10:mix=0.35:enable='{e}'"]),
    "mic_ruim": ([], ["highpass=f=250:enable='{e}'", "lowpass=f=1800:enable='{e}'", "acrusher=bits=6:mix=0.25:enable='{e}'"]),
    "pixelado": (["pixelize=w={px}:h={px}:enable='{e}'", "noise=alls=14:allf=t:enable='{e}'"], []),
    "webcam_ruim": (["gblur=sigma=2:enable='{e}'", "pixelize=w={px2}:h={px2}:enable='{e}'", "eq=saturation=0.7:contrast=0.85:brightness=-0.04:enable='{e}'", "noise=alls=18:allf=t:enable='{e}'"],
                    ["highpass=f=300:enable='{e}'", "lowpass=f=3000:enable='{e}'"]),
    "drama": (["eq=saturation=0:contrast=1.3:enable='{e}'", "vignette=angle=PI/3.2:enable='{e}'"], []),
}
DESCRICAO = {
    "radio": "som de rádio/telefone (corta grave e agudo)",
    "mic_ruim": "microfone ruim de notebook (abafado e áspero)",
    "pixelado": "imagem pixelada com chiado (internet ruim)",
    "webcam_ruim": "webcam barata: borrada, pixelada, apagada, com som de notebook",
    "drama": "preto e branco contrastado com vinheta (dúvida, citação, 'antes')",
}
MAX_TRECHO_S = 8.0


def aplicar(video, saida, trechos):
    """trechos = [{efeito, inicio, fim}] em segundos do vídeo de entrada. Recodifica o vídeo uma vez; devolve o que aplicou e avisos."""
    if isinstance(trechos, dict):
        trechos = [trechos]
    ent = caminho(video); out = caminho_saida(saida); info = info_midia(ent); dur = info["duracao_s"]
    vf, af, aplicados, avisos = [], [], [], []
    for n, t in enumerate(trechos or [], 1):
        ef = str(t.get("efeito", "")).strip().lower()
        if ef not in EFEITOS:
            raise ErroFerramenta(f"trecho {n}: efeito '{ef}' não existe (use {', '.join(EFEITOS)})")
        a, b = max(0.0, float(t["inicio"])), min(dur, float(t["fim"]))
        if b - a < 0.3:
            avisos.append(f"trecho {n}: curto demais ({a:.2f}–{b:.2f}); ignorado"); continue
        if b - a > MAX_TRECHO_S:
            avisos.append(f"trecho {n}: {b - a:.1f} s de cena ruim cansa; cortei em {MAX_TRECHO_S:.0f} s"); b = a + MAX_TRECHO_S
        e = f"between(t,{a:.3f},{b:.3f})"
        v, s = EFEITOS[ef]
        larg = info["largura"] or 1080
        vf += [x.format(e=e, px=max(4, round(larg / 120)), px2=max(3, round(larg / 200))) for x in v]
        if s and not info["tem_audio"]:
            avisos.append(f"trecho {n}: '{ef}' mexe no som, mas o vídeo não tem áudio")
        af += [x.format(e=e) for x in s] if info["tem_audio"] else []
        aplicados.append({"efeito": ef, "inicio": round(a, 2), "fim": round(b, 2)})
    if not aplicados:
        raise ErroFerramenta("nenhum trecho válido para aplicar")
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", ent]
    cmd += ["-vf", ",".join(vf), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"] if vf else ["-c:v", "copy"]
    if info["tem_audio"]:
        cmd += ["-af", ",".join(af), "-c:a", "aac", "-b:a", "192k"] if af else ["-c:a", "copy"]
    cmd += ["-movflags", "+faststart", out]
    rodar(cmd)
    return {"arquivo": str(out), "aplicados": aplicados, "avisos": avisos}
