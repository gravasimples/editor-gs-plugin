"""Cena ruim de propósito (15/11/2026): filtro só no trecho, resto igual, limites e erros. Vídeo sintético em pasta temporária.
Rodar: python -X utf8 -I testes/teste_cena_ruim.py"""
import subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import cena_ruim as c
from editor_video.util import ErroFerramenta, info_midia

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-cena-ruim-"))
src = tmp / "src.mp4"
subprocess.run([c.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=12:r=30", "-f", "lavfi", "-i", "sine=f=440:d=12",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)], check=True)

r = c.aplicar(src, tmp / "out" / "a.mp4", [{"efeito": "webcam_ruim", "inicio": 1, "fim": 3}, {"efeito": "drama", "inicio": 5, "fim": 6}])
i = info_midia(r["arquivo"])
check(abs(i["duracao_s"] - 12) < 0.2 and i["tem_audio"], "duração e áudio preservados")
check([a["efeito"] for a in r["aplicados"]] == ["webcam_ruim", "drama"], "aplica os dois trechos na ordem")

def quadro(arq, t):
    return subprocess.run([c.FFMPEG, "-loglevel", "error", "-ss", str(t), "-i", str(arq), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "36x64", "-"], capture_output=True).stdout
dif = lambda x, y: sum(abs(p - q) for p, q in zip(x, y)) / max(1, len(x))
check(dif(quadro(src, 2), quadro(r["arquivo"], 2)) > 3, "dentro do trecho a imagem muda")
check(dif(quadro(src, 9), quadro(r["arquivo"], 9)) < 3, "fora do trecho a imagem fica igual")

r = c.aplicar(src, tmp / "out" / "b.mp4", [{"efeito": "radio", "inicio": 2, "fim": 11.9}, {"efeito": "pixelado", "inicio": 0, "fim": 0.1}])
check(r["aplicados"][0]["fim"] == 10.0 and any("cansa" in a for a in r["avisos"]), "trecho acima de 8 s é encurtado com aviso")
check(len(r["aplicados"]) == 1 and any("curto demais" in a for a in r["avisos"]), "trecho curto demais é ignorado")
try:
    c.aplicar(src, tmp / "out" / "c.mp4", [{"efeito": "sepia", "inicio": 1, "fim": 2}]); ok = False
except ErroFerramenta as e:
    ok = "radio" in str(e)
check(ok, "efeito desconhecido dá erro com a lista")
check(set(c.EFEITOS) == set(c.DESCRICAO), "todo efeito tem descrição")
srv = (RAIZ / "mcp" / "editor-de-video" / "servidor.py").read_text(encoding="utf-8")
check("def efeito_no_trecho" in srv and all(e in srv.split("def efeito_no_trecho")[1][:900] for e in c.EFEITOS), "ferramenta MCP lista todos os efeitos")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
