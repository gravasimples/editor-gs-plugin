"""Testes das ferramentas de imagem (carrossel, foto, post). Tudo em pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_imagem.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import imagem
from editor_video.util import ErroFerramenta
from PIL import Image

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def cor_mais_comum(p):
    im = Image.open(p).convert("RGB").resize((54, 68)); return max(im.getcolors(54 * 68), key=lambda c: c[0])[1]

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); foto = tmp / "foto.jpg"; Image.new("RGB", (1600, 900), (120, 60, 20)).save(foto)
    logo = tmp / "logo.png"; Image.new("RGBA", (400, 100), (255, 255, 255, 255)).save(logo)
    slides = [{"titulo": "Sua webcam está no automático", "destaque": "automático", "apoio": ["Por isso a imagem muda de cor."], "selo": "OBS"},
              {"titulo": "Tire do automático em 3 cliques", "destaque": "3", "apoio": ["Exposição", "Obturador", "ISO", "Balanço", "Ganho", "Foco", "sétima linha não entra"]},
              {"titulo": "Olha a diferença", "destaque": "diferença", "foto": str(foto)},
              {"titulo": "Salve para testar no OBS", "cta": "Siga @thiago.obsstudio"}]
    sj = tmp / "slides.json"; sj.write_text(json.dumps(slides, ensure_ascii=False))
    r = imagem.gerar_carrossel(str(sj), str(tmp / "tip"), modelo="tipografico")
    check(r["n"] == 4 and len(r["slides"]) == 4 and all(Image.open(p).size == (1080, 1350) for p in r["slides"]), "tipográfico: 4 slides 1080x1350")
    check(cor_mais_comum(r["slides"][0]) == (0, 9, 33) and cor_mais_comum(r["slides"][1]) == (242, 242, 242), "alterna marinho e papel")
    check(not r["logo_usado"], "sem logo quando não há arquivo")
    r2 = imagem.gerar_carrossel(slides, str(tmp / "hist"), modelo="historia", foto_capa=str(foto), logo=str(logo))
    check(r2["logo_usado"] and Image.open(r2["slides"][2]).size == (1080, 1350), "história com foto e logo oficial")
    r3 = imagem.gerar_carrossel(slides, str(tmp / "tw"), modelo="tweet")
    check(cor_mais_comum(r3["slides"][0]) == (242, 242, 242) and cor_mais_comum(r3["slides"][1]) == (0, 9, 33), "tweet: capa clara, interior marinho")
    try:
        imagem.gerar_carrossel([], str(tmp / "v")); check(False, "carrossel vazio deveria falhar")
    except ErroFerramenta:
        check(True, "carrossel vazio recusado")
    # 29/10: modelo marinho (todos escuros), selo translúcido com ponto laranja, campo print (imagem inteira sem corte)
    pr = tmp / "print.png"; Image.new("RGB", (1200, 400), (10, 200, 10)).save(pr)
    sl5 = [{"titulo": "Quem grava simples aprova", "destaque": "aprova", "selo": "depoimento", "print": str(pr)},
           {"titulo": "Olha o que a aluna disse", "apoio": ["Chegou por direct"], "print": str(pr)},
           {"titulo": "O próximo pode ser o seu", "cta": "Comenta DESCOMPLICA", "print": str(pr)}]
    r5 = imagem.gerar_carrossel(sl5, str(tmp / "mar"), modelo="marinho")
    check(all(cor_mais_comum(p) == (0, 9, 33) for p in r5["slides"]), "marinho: todos os slides escuros")
    im5 = Image.open(r5["slides"][0]).convert("RGB"); px = im5.getpixel((int(1080 * 0.08) + 8, int(1350 * 0.16) + 28))
    check(px != (40, 76, 184) and px[2] > px[0] and px != (0, 9, 33), f"selo azul translúcido (mistura com o fundo): {px}")
    faixa = [im5.getpixel((int(1080 * 0.08) + 24 + x, int(1350 * 0.16) + 28)) for x in range(0, 14)]
    check(any(p[0] > 200 and p[2] < 80 for p in faixa), "selo tem o ponto laranja")
    verdes = [dict(Image.open(p).convert("RGB").resize((108, 135)).getcolors(108 * 135) and [(c, n) for n, c in Image.open(p).convert("RGB").resize((108, 135), Image.NEAREST).getcolors(108 * 135)]).get((10, 200, 10), 0) for p in r5["slides"]]
    check(all(v > 1500 for v in verdes), f"print inteiro (1200x400 → ~907x302) aparece nos três slides, inclusive o CTA: {verdes} px numa miniatura 108x135")
    r4 = imagem.editar_foto(str(foto), str(tmp / "ed.png"), formato="story", desfoque_fundo=True, texto="Pronto, tá gravando", destaque="gravando", cantos=20, borda=12)
    check(Image.open(r4["imagem"]).size == (1080, 1920), "editar_foto story 1080x1920 com fundo desfocado, texto, cantos e borda")
    r5 = imagem.editar_foto(str(foto), str(tmp / "ed2.png"), formato="capa_yt", contraste=1.2, saturacao=0.9, texto="Topo", posicao="topo", logo=str(logo))
    check(Image.open(r5["imagem"]).size == (1280, 720), "editar_foto capa_yt 1280x720")
    try:
        imagem.editar_foto(str(foto), str(tmp / "x.png"), formato="gigante"); check(False, "formato inválido deveria falhar")
    except ErroFerramenta:
        check(True, "formato inválido recusado")
    r6 = imagem.gerar_post_imagem(str(tmp / "post.png"), "O óbvio precisa ser dito", destaque="óbvio", apoio="parte 3", formato="quadrado", cta="Siga para a parte 4")
    check(Image.open(r6["imagem"]).size == (1080, 1080) and (tmp / "post.png").exists(), "post único quadrado 1080x1080")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
