"""Testes isolados de montagem.montar_dividido (tela dividida rosto + tela) com clipes sintéticos do ffmpeg em pasta temporária. Não toca workspace/."""
import subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import montagem
from editor_video.util import FFMPEG, info_midia, ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def clipe(p, tam, dur, audio=True, freq=440):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={tam}:rate=30:d={dur}"]
    if audio: cmd += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}", "-shortest", "-c:a", "aac"]
    subprocess.run(cmd + ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(p)], check=True)

with tempfile.TemporaryDirectory(prefix="editor-gs-dividido-") as tmp:
    tmp = Path(tmp); clipe(tmp / "rosto.mp4", "1280x720", 3); clipe(tmp / "tela.mp4", "1920x1080", 5, freq=880); clipe(tmp / "muda.mp4", "1280x720", 5, audio=False)
    r = montagem.montar_dividido(tmp / "rosto.mp4", tmp / "tela.mp4", tmp / "saida" / "div_9x16.mp4", formato="9x16", resolucao="720p")
    i = info_midia(r["video"])
    check(i["largura"] == 720 and i["altura"] == 1280 and i["tem_audio"] and abs(i["duracao_s"] - 3) < 0.2, f"9x16 720p, áudio do rosto, duração do rosto ({i['largura']}x{i['altura']}, {i['duracao_s']} s)")
    check(r["layout"]["rosto"]["h"] == 538 and r["layout"]["tela"]["y"] == 538 and r["layout"]["tela"]["h"] == 742, f"rosto em cima com 42 % da altura, tela embaixo ({r['layout']})")
    r2 = montagem.montar_dividido(tmp / "rosto.mp4", tmp / "tela.mp4", tmp / "saida" / "div_16x9.mp4", formato="16x9", resolucao="720p", proporcao_rosto=0.4, audio="mix")
    i2 = info_midia(r2["video"])
    check(i2["largura"] == 1280 and i2["altura"] == 720 and r2["layout"]["rosto"]["w"] == 512 and r2["layout"]["tela"]["x"] == 512 and i2["tem_audio"], f"16x9: rosto à esquerda (40 %), tela à direita, áudio mixado ({r2['layout']})")
    r3 = montagem.montar_dividido(tmp / "rosto.mp4", tmp / "muda.mp4", tmp / "saida" / "div_tela.mp4", formato="1x1", resolucao="720p", audio="tela", inicio_tela_s=0.5)
    i3 = info_midia(r3["video"])
    check(i3["largura"] == 720 and i3["altura"] == 720 and i3["tem_audio"] and r3["inicio_tela_s"] == 0.5, "1x1 com tela deslocada 0,5 s; sem áudio na tela cai no áudio do rosto")
    r4 = montagem.montar_dividido(tmp / "rosto.mp4", tmp / "tela.mp4", tmp / "saida" / "div_neg.mp4", formato="9x16", resolucao="720p", inicio_tela_s=-1.0)
    check(Path(r4["video"]).exists() and abs(info_midia(r4["video"])["duracao_s"] - 3) < 0.2, "inicio_tela_s negativo pula o começo da tela e mantém a duração")
    for kw in ({"proporcao_rosto": 0.9}, {"audio": "x"}, {"formato": "4x3"}):
        try:
            montagem.montar_dividido(tmp / "rosto.mp4", tmp / "tela.mp4", tmp / "saida" / "x.mp4", **kw); check(False, f"{kw} inválido dá erro")
        except ErroFerramenta:
            check(True, f"{kw} inválido dá erro")

    # --- formatos novos (02/11/2026): PiP e antes/depois
    r5 = montagem.montar_pip(tmp / "tela.mp4", tmp / "rosto.mp4", tmp / "saida" / "pip.mp4", formato="9x16", resolucao="720p")
    i5 = info_midia(r5["video"])
    check(i5["largura"] == 720 and i5["altura"] == 1280 and i5["tem_audio"] and abs(i5["duracao_s"] - 3) < 0.2 and r5["bolha"]["diametro"] == 244 and r5["bolha"]["x"] == 720 - 244 - 28, f"pip 9x16: bolha de 34 % no canto inferior direito, duração do rosto ({r5['bolha']})")
    r6 = montagem.montar_pip(tmp / "tela.mp4", tmp / "rosto.mp4", tmp / "saida" / "pip2.mp4", formato="16x9", resolucao="720p", forma="cartao", posicao="superior-esquerda", tamanho=0.25, audio="mix")
    check(info_midia(r6["video"])["largura"] == 1280 and r6["bolha"]["forma"] == "cartao" and r6["bolha"]["x"] == 51 and r6["bolha"]["y"] == 36, f"pip 16x9 cartão no alto à esquerda, áudio mix ({r6['bolha']})")
    for kw in ({"tamanho": 0.6}, {"posicao": "meio"}, {"forma": "quadrado"}):
        try:
            montagem.montar_pip(tmp / "tela.mp4", tmp / "rosto.mp4", tmp / "saida" / "x.mp4", **kw); check(False, f"pip {kw} inválido dá erro")
        except ErroFerramenta:
            check(True, f"pip {kw} inválido dá erro")
    r7 = montagem.montar_antes_depois(tmp / "rosto.mp4", tmp / "tela.mp4", tmp / "saida" / "ad.mp4", formato="9x16", resolucao="720p")
    i7 = info_midia(r7["video"])
    check(i7["largura"] == 720 and i7["altura"] == 1280 and r7["empilhado"] and r7["layout"]["depois"]["y"] == 640 and abs(i7["duracao_s"] - 3) < 0.2 and i7["tem_audio"], f"antes/depois 9x16 empilhado, duração do mais curto ({r7['layout']})")
    r8 = montagem.montar_antes_depois(tmp / "rosto.mp4", tmp / "muda.mp4", tmp / "saida" / "ad2.mp4", formato="16x9", resolucao="720p", rotulo_antes="SEM LUZ", rotulo_depois="COM LUZ", audio="depois")
    i8 = info_midia(r8["video"])
    check(not r8["empilhado"] and r8["layout"]["depois"]["x"] == 640 and i8["tem_audio"], "antes/depois 16x9 lado a lado; 'depois' sem áudio cai no áudio do 'antes'")
    try:
        montagem.montar_antes_depois(tmp / "rosto.mp4", tmp / "tela.mp4", tmp / "saida" / "x.mp4", modo="x"); check(False, "modo inválido dá erro")
    except ErroFerramenta:
        check(True, "modo inválido dá erro")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
