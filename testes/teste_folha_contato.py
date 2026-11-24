"""Folha de contato (10/11/2026): vídeo sintético com 3 cores trocando → acha ≥ 2 cenas, tira quadros iguais, grava o PNG com os instantes.
Também o trecho do revisor (inicio_s/fim_s → start_offset/end_offset), sem rede. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_folha_contato.py"""
import os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import folha_contato as fc, revisao
from editor_video.util import FFMPEG, ErroFerramenta
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def video_cores(pasta, dur_cena=2.0):
    """Três cores chapadas em sequência (escuro, branco, cinza), 2 s cada, 640x360. O filtro scene do ffmpeg olha a luma: cores com o mesmo brilho não contam."""
    out = pasta / "cores.mp4"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"color=c=0x202020:s=640x360:r=25:d={dur_cena}",
                    "-f", "lavfi", "-i", f"color=c=white:s=640x360:r=25:d={dur_cena}",
                    "-f", "lavfi", "-i", f"color=c=0x808080:s=640x360:r=25:d={dur_cena}",
                    "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out

with tempfile.TemporaryDirectory(prefix="gs-teste-folha-", ignore_cleanup_errors=True) as tmp:
    pasta = Path(tmp); os.chdir(pasta)
    v = video_cores(pasta)
    cenas = fc.cenas_ffmpeg(v, 0.3)
    check(len(cenas) >= 2 and abs(cenas[0] - 2.0) < 0.15 and abs(cenas[1] - 4.0) < 0.15, f"cenas pelo ffmpeg: {cenas}")
    r = fc.folha_contato(v, pasta / "_trabalho" / "folha.png", max_quadros=16)
    check(Path(r["folha"]).exists() and Path(r["folha"]).stat().st_size > 5000, f"PNG gravado: {r['folha']} ({r['largura']}x{r['altura']}, grade {r['grade']})")
    check(r["cenas_detectadas"] >= 2, f"cenas detectadas: {r['cenas_detectadas']} ({r['origem']})")
    check(3 <= r["n"] <= 4, f"quadros na folha: {r['n']} (3 cores + amostra uniforme, sem repetidos)")
    inst = [q["instante_s"] for q in r["quadros"]]
    check(inst == sorted(inst) and inst[0] == 0.0 and any(1.9 < t < 2.3 for t in inst) and any(3.9 < t < 4.3 for t in inst), f"instantes escolhidos: {inst}")
    check(all(q["mmss"].count(":") == 1 and q["coluna"] >= 1 and q["linha"] >= 1 for q in r["quadros"]), f"rótulos m:ss e posição na grade: {r['quadros'][:2]}")
    # a cor dos quadros na folha (canto superior direito, longe do rótulo): o primeiro é escuro, o da cena 2 (≈2 s) é branco
    from PIL import Image
    im = Image.open(r["folha"]).convert("RGB"); q1 = next(q for q in r["quadros"] if 1.9 < q["instante_s"] < 2.3)
    cw = (r["largura"] - 6) // int(r["grade"].split("x")[0]) - 6
    px0 = im.getpixel((6 + cw - 10, 6 + 10)); px1 = im.getpixel((6 + (q1["coluna"] - 1) * (cw + 6) + cw - 10, 6 + (q1["linha"] - 1) * (cw * 360 // 640 + 6) + 10))
    check(max(px0) < 60 and min(px1) > 200, f"quadro 1 escuro {px0}, quadro da cena 2 branco {px1}")
    # amostra uniforme e limite de quadros
    r2 = fc.folha_contato(v, pasta / "_trabalho" / "folha2.png", max_quadros=4, por_cena=False)
    check(r2["n"] <= 4 and r2["origem"] == "amostra uniforme" and r2["grade"] in ("2x2", "2x1", "1x1"), f"por_cena=False: {r2['n']} quadros, grade {r2['grade']}")
    # quadros iguais saem: vídeo de uma cor só amostrado 8× vira 1 quadro
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=25:d=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(pasta / "azul.mp4")], check=True)
    im.close()
    r3 = fc.folha_contato(pasta / "azul.mp4", pasta / "_trabalho" / "folha3.png", max_quadros=8, por_cena=False)
    check(r3["n"] == 1 and r3["descartados_iguais"] == 7, f"deduplicação: {r3['n']} quadro, {r3['descartados_iguais']} iguais descartados")
    # trecho
    r4 = fc.folha_contato(v, pasta / "_trabalho" / "folha4.png", max_quadros=8, inicio_s=3.0, fim_s=6.0)
    check(all(3.0 <= q["instante_s"] < 6.0 for q in r4["quadros"]) and r4["trecho"] == {"inicio_s": 3.0, "fim_s": 6.0}, f"trecho 3–6 s: {[q['instante_s'] for q in r4['quadros']]}")
    try:
        fc.folha_contato(v, pasta / "_trabalho" / "x.png", inicio_s=5, fim_s=2); check(False, "deveria recusar trecho invertido")
    except ErroFerramenta as e:
        check("trecho inválido" in str(e), f"trecho invertido recusa: {e}")
    # pelo servidor (negativo = sem trecho) e recusa em entrada/
    s = servidor.folha_contato(str(v), str(pasta / "_trabalho" / "folha5.png"), max_quadros=6)
    check("erro" not in s and s["n"] >= 3, f"servidor.folha_contato: {s.get('n')} quadros")
    (pasta / "entrada").mkdir()
    s2 = servidor.folha_contato(str(v), str(pasta / "entrada" / "folha.png"))
    check("erro" in s2 and "entrada" in s2["erro"], f"servidor recusa gravar em entrada/: {s2}")
    # revisor: trecho vira video_metadata, sem chamar a rede
    meta, txt = revisao.trecho_video(12.5, 30, 60)
    check(meta == {"start_offset": "12.500s", "end_offset": "30.000s"} and "12.5 s a 30.0 s" in txt, f"trecho do revisor: {meta}")
    meta, txt = revisao.trecho_video(None, None, 60)
    check(meta is None and txt == "", "sem inicio/fim o revisor segue como antes (vídeo inteiro)")
    meta, _ = revisao.trecho_video(50, 999, 60)
    check(meta["end_offset"] == "60.000s", "fim_s acima da duração é limitado")
    try:
        revisao.trecho_video(30, 10, 60); check(False, "deveria recusar fim antes do início")
    except ErroFerramenta as e:
        check("trecho inválido" in str(e), f"revisor recusa trecho invertido: {e}")
    import inspect
    sig = inspect.signature(servidor.revisar_video).parameters
    check("inicio_s" in sig and "fim_s" in sig and sig["inicio_s"].default == -1.0, "servidor.revisar_video expõe inicio_s/fim_s (negativo = inteiro)")
os.chdir(RAIZ)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
