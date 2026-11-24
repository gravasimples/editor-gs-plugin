"""Produto recortado (15/11/2026): PNG com transparência aparado no objeto, avisos de recorte duvidoso, quadro de vídeo, grafismo `recorte`.
O modelo é trocado por uma máscara sintética (o teste não baixa os 178 MB). Rodar: python -X utf8 -I testes/teste_recorte.py"""
import os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-recorte-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from PIL import Image, ImageDraw
from editor_video import recorte as rc, grafismos as g
from editor_video.util import ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def mascara_do_quadrado(img):  # objeto = quadrado escuro no meio (como faria o modelo)
    m = Image.new("L", img.size, 0); w, h = img.size
    ImageDraw.Draw(m).rectangle([w * 0.3, h * 0.3, w * 0.7, h * 0.7], fill=255); return m
rc._rodar = mascara_do_quadrado

foto = tmp / "foto.jpg"
im = Image.new("RGB", (400, 400), "white"); ImageDraw.Draw(im).rectangle([120, 120, 280, 280], fill="black"); im.save(foto)
r = rc.recortar(foto, tmp / "out" / "obj.png")
png = Image.open(r["arquivo"])
check(png.mode == "RGBA", "saída tem transparência")
check(abs(r["largura"] - 193) <= 2 and abs(r["altura"] - 193) <= 2, f"aparado no objeto com margem ({r['largura']}x{r['altura']})")
check(png.getpixel((2, 2))[3] == 0 and png.getpixel((88, 88))[3] == 255, "fundo transparente, objeto opaco")
check(r["avisos"] == [] and 0.1 < r["cobertura"] < 0.3, "recorte normal sem aviso")

rc._rodar = lambda img: Image.new("L", img.size, 255)
check(any("quase a imagem toda" in a for a in rc.recortar(foto, tmp / "out" / "tudo.png")["avisos"]), "máscara cheia avisa que o fundo pode não ter saído")
rc._rodar = lambda img: Image.new("L", img.size, 0)
try:
    rc.recortar(foto, tmp / "out" / "nada.png"); ok = False
except ErroFerramenta:
    ok = True
check(ok, "sem objeto dá erro claro")
try:
    rc.recortar(foto, tmp / "out" / "x.jpg"); ok = False
except ErroFerramenta as e:
    ok = ".png" in str(e)
check(ok, "saída que não é PNG é recusada")

rc._rodar = mascara_do_quadrado
vid = tmp / "v.mp4"
subprocess.run([rc.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=3:r=25", "-pix_fmt", "yuv420p", str(vid)], check=True)
check(Image.open(rc.recortar(vid, tmp / "out" / "q.png", instante_s=1.0)["arquivo"]).mode == "RGBA", "recorta de um quadro do vídeo")
try:
    rc.recortar(vid, tmp / "out" / "q2.png"); ok = False
except ErroFerramenta as e:
    ok = "instante_s" in str(e)
check(ok, "vídeo sem instante pede o instante")

# grafismo recorte
its, av = g.normalizar({"itens": [{"tipo": "recorte", "inicio": 1, "itens": [{"imagem": r["arquivo"], "texto": "C922"}, {"texto": "sem imagem"}]}]}, duracao_s=10)
check(len(its) == 1 and len(its[0]["itens"]) == 1 and its[0]["itens"][0]["midia"]["tipo"] == "img", "recorte guarda só os subitens com imagem")
check(any("sem `imagem`" in a for a in av), "subitem sem imagem avisa para rodar recortar_objeto")
tsx = (RAIZ / "remotion" / "src" / "Grafismos.tsx").read_text(encoding="utf-8")
check("case 'recorte'" in tsx and "drop-shadow" in tsx, "Remotion desenha o recorte com borda")
srv = (RAIZ / "mcp" / "editor-de-video" / "servidor.py").read_text(encoding="utf-8")
check("def recortar_objeto" in srv, "ferramenta MCP recortar_objeto existe")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
