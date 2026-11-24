"""Formatos, fase 2 (03/11/2026): capítulos tirados da fala, react com trava de direitos e carrossel em vídeo. Clipes e slides sintéticos em pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_formatos_fase2.py"""
import json, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import montagem, imagem, nivel_pro as np_
from editor_video.util import FFMPEG, ErroFerramenta, info_midia

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def fala(texto, passo=0.4):
    return {"palavras": [{"palavra": w, "inicio": round(i * passo, 2), "fim": round(i * passo + 0.35, 2)} for i, w in enumerate(texto.split())]}

c = np_.capitulos_auto(fala("Olha só, três erros. Primeiro erro: o áudio baixo no OBS. Segundo erro: a luz de chapa. Terceiro erro: webcam travando."))
check([x["numero"] for x in c] == [1, 2, 3] and all(x["total"] == 3 for x in c), f"primeiro/segundo/terceiro viram 3 capítulos ({[x['texto'] for x in c]})")
check(c[0]["texto"].lower().startswith("áudio") or c[0]["texto"].lower().startswith("audio"), "rótulo pula palavras vazias e pega o conteúdo")
check(c[0]["inicio"] < c[1]["inicio"] < c[2]["inicio"], "capítulos em ordem de tempo")
c2 = np_.capitulos_auto(fala("Passo 1 abrir o OBS. Passo 2 criar a cena. Passo 3 testar o microfone."))
check(len(c2) == 3 and c2[1]["texto"].lower().startswith("criar"), "passo 1/2/3 com número também vira capítulo")
check(np_.capitulos_auto(fala("Primeiro eu abro o OBS e depois gravo a aula.")) == [], "um 'primeiro' solto não é lista")
check(np_.capitulos_auto(fala("Segundo a pesquisa, terceiro lugar no ranking.")) == [], "sequência que não começa no 1 é ignorada")
check(len(np_.capitulos_auto(fala("Dica número um: luz. Dica número dois: som."))) == 2, "dica número um/dois por extenso")

td = Path(tempfile.mkdtemp())
def clipe(nome, cor, dur=2.0, tamanho="540x960"):
    p = td / nome
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={cor}:s={tamanho}:d={dur}", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)], check=True)
    return p
ros, ref = clipe("rosto.mp4", "orange"), clipe("ref.mp4", "blue", 3.0, "1280x720")
for direitos in ("", "terceiro"):
    try:
        montagem.montar_react(ros, ref, td / "x.mp4", "@perfil", direitos); check(False, f"react recusa direitos='{direitos}'")
    except ErroFerramenta:
        check(True, f"react recusa direitos='{direitos}'")
try:
    montagem.montar_react(ros, ref, td / "x.mp4", " ", "proprio"); check(False, "react exige crédito")
except ErroFerramenta:
    check(True, "react exige crédito")
r = montagem.montar_react(ros, ref, td / "react.mp4", "@perfil", "autorizado", resolucao="720p", preset="ultrafast")
check(r["largura"] == 720 and r["altura"] == 1280 and abs(r["duracao_s"] - 2.0) < 0.15 and r["credito"] == "@perfil", f"react empilhado 9x16 com a duração da reação ({r['duracao_s']})")
r = montagem.montar_react(ros, ref, td / "react16.mp4", "@perfil", "proprio", formato="16x9", resolucao="720p", preset="ultrafast")
check(r["largura"] == 1280 and r["altura"] == 720, "react 16x9 lado a lado")
r = montagem.montar_react(ros, ref, td / "reactb.mp4", "@perfil", "licenca", layout="bolha", resolucao="720p", preset="ultrafast")
check(r["layout"] == "bolha" and info_midia(r["video"])["tem_audio"], "react em bolha com áudio")

from PIL import Image
slides = []
for i, cor in enumerate(("#000921", "#0B193D", "#F79615")):
    f = td / f"s{i}.png"; Image.new("RGB", (1080, 1350), cor).save(f); slides.append(str(f))
r = imagem.animar_carrossel(";".join(slides), td / "car.mp4", duracao_slide_s=2.0, transicao_s=0.5, formato="9x16", transicao="smoothleft")
check(r["n_slides"] == 3 and abs(r["duracao_s"] - (3 * 2.0 - 2 * 0.5)) < 0.15 and r["altura"] == 1920 and r["transicao"] == "smoothleft", f"carrossel 3 slides 4:5 em 9:16 com transição: 5 s ({r['duracao_s']})")
quadro = td / "q.png"; subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", "0.5", "-i", r["video"], "-frames:v", "1", str(quadro)], check=True)
q = Image.open(quadro).convert("RGB"); cima, meio = q.getpixel((540, 40)), q.getpixel((540, 960))
check(cima != meio and sum(abs(a - b) for a, b in zip(cima, (0, 9, 33))) < 60, "slide 4:5 não é cortado: faixa de fundo desfocado em cima, slide inteiro no meio")
(td / "pasta").mkdir()
for i, f in enumerate(slides):
    Path(f).rename(td / "pasta" / f"{i:02d}.png")
r = imagem.animar_carrossel(str(td / "pasta"), td / "car2.mp4", duracao_slide_s=1.5, formato="4x5", transicao="")
check(abs(r["duracao_s"] - 4.5) < 0.15 and r["transicao"] == "corte" and r["altura"] == 1350, f"carrossel a partir de pasta, corte seco, 4x5 ({r['duracao_s']})")
try:
    imagem.animar_carrossel(str(td / "pasta"), td / "y.mp4", transicao="explosao"); check(False, "transição inválida recusada")
except ErroFerramenta:
    check(True, "transição inválida recusada")
st = imagem.gerar_post_imagem(str(td / "st.png"), "Qual equipamento?", "equipamento", apoio="Webcam e OBS.", formato="story", fundo="papel")
im = Image.open(st["imagem"]).convert("RGB")
check(st["story_nativo"] and im.size == (1080, 1920) and im.getpixel((540, 120)) == (242, 242, 242) and im.getpixel((540, 1800)) == (242, 242, 242), "story nativo 1080x1920 em papel, faixas seguras na cor do fundo")
mar = imagem.gerar_post_imagem(str(td / "fd.png"), "Título", formato="feed", fundo="marinho")
check(Image.open(mar["imagem"]).convert("RGB").getpixel((10, 10)) == (0, 9, 33), "fundo marinho forçado no feed")
check(json.loads((RAIZ / "estilos" / "lista.json").read_text())["montagem"].get("capitulos") == "auto", "estilo lista usa capítulos da fala")
check((RAIZ / "estilos" / "pov.json").exists() and json.loads((RAIZ / "estilos" / "pov.json").read_text())["montagem"]["tela_final_cta"] is False, "estilo POV sem tela final")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
