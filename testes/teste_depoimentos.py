"""Testes do carrossel semanal de depoimentos (molde fixo + cartões 3D). Tudo em pasta temporária; lê só o molde de estilos/.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_depoimentos.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import depoimentos
from editor_video.util import ErroFerramenta
from PIL import Image, ImageDraw
from pptx import Presentation

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def cor_mais_comum(p):
    im = Image.open(p).convert("RGB").resize((54, 68)); return max(im.getcolors(54 * 68), key=lambda c: c[0])[1]

def print_falso(p, w, h, cor):
    im = Image.new("RGB", (w, h), cor); d = ImageDraw.Draw(im)
    d.rounded_rectangle((30, 30, w - 30, h - 30), radius=18, outline=(0, 120, 255), width=10)
    d.text((60, 60), "depoimento", fill=(255 - cor[0], 255 - cor[1], 255 - cor[2])); im.save(p); return str(p)

MOLDE = RAIZ / "estilos" / "depoimentos-semanais"
check(all((MOLDE / f).exists() for f in ("fundo.png", "fundo-ultimo.png", "tela-cta.png")), "molde fixo presente em estilos/depoimentos-semanais")

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    formas = [(1080, 500, (255, 255, 255)), (800, 300, (30, 30, 30)), (1200, 900, (236, 229, 221)), (1080, 2340, (255, 255, 255)), (600, 200, (255, 255, 255)), (900, 400, (20, 20, 20)), (1000, 350, (255, 255, 255))]
    prints = [print_falso(tmp / f"p{i}.png", w, h, c) for i, (w, h, c) in enumerate(formas)]

    r = depoimentos.gerar_carrossel_depoimentos(prints, str(tmp / "saida"))
    check(r["n_telas"] == 4 and len(r["telas"]) == 4 and all(Image.open(t).size == (1080, 1350) for t in r["telas"]), "7 prints → 3 telas de prints + CTA, todas 1080×1350")
    check(all(Path(t).name == f"final_tela-{i:02d}.png" for i, t in enumerate(r["telas"], 1)), "nomes final_tela-01..04 (aparecem como principais no cartão)")
    check(cor_mais_comum(r["telas"][3]) == cor_mais_comum(MOLDE / "tela-cta.png"), "última tela é a tela CTA do molde, sem alteração")
    check(not [a for a in r["avisos"] if "cobre" in a], f"nenhum cartão cobre outro print (avisos: {r['avisos']})")
    check(all(c["face_top"] >= 300 and c["face_bot"] <= 1010 for t in json.loads(Path(r["posicoes"]).read_text()) for c in t["cartoes"]), "todos os cartões dentro da faixa entre título e selo")
    check([p["tela"] for p in r["prints"]] == [1, 1, 1, 2, 2, 2, 3] and r["prints"][0]["nome"] == "p0", "ordem de leitura respeitada (3 por tela, sobra na última)")
    check(any("2340" in str(p) or p["escala"] < 0.45 for p in r["prints"] if p["nome"] == "p3") and any("p3" in a for a in r["avisos"]), "print alto sem corte gera aviso de tamanho")
    prs = Presentation(r["pptx"])
    check(len(prs.slides) == 4 and sum(len(s.shapes) for s in prs.slides) == 7 + 4, "PPTX com 4 páginas e uma camada por fundo e por print")
    check(Path(r["pdf"]).exists() and Path(r["pdf"]).stat().st_size > 10000, "PDF gerado")
    check(Path(r["camadas"]).name == "depoimentos" and Path(r["camadas"]).parent.name == "_trabalho" and len(list(Path(r["camadas"]).glob("tela-*-cartao-*.png"))) == 7, "camadas em _trabalho/depoimentos (escondidas do cartão)")

    # corte, nome e 1 print só
    pj = tmp / "prints.json"; pj.write_text(json.dumps([{"arquivo": prints[3], "nome": "Aluna X", "corte": [0, 0, 1080, 400]}]), encoding="utf-8")
    r2 = depoimentos.gerar_carrossel_depoimentos(str(pj), str(tmp / "s2"))
    check(r2["n_telas"] == 2 and r2["prints"][0]["nome"] == "Aluna X" and r2["prints"][0]["corte"] == [0, 0, 1080, 400] and r2["prints"][0]["escala"] > 0.5, "JSON com corte e nome: 1 print grande + CTA")

    # 2 prints e pasta como entrada
    pasta = tmp / "pasta"; pasta.mkdir(); print_falso(pasta / "a.jpg", 900, 300, (255, 255, 255)); print_falso(pasta / "b.png", 700, 500, (255, 255, 255))
    r3 = depoimentos.gerar_carrossel_depoimentos(str(pasta), str(tmp / "s3"), nome_base="tela")
    check(r3["n_telas"] == 2 and r3["n_prints"] == 2 and Path(r3["telas"][0]).name == "tela-01.png", "pasta com 2 prints → 1 tela dupla + CTA, nome_base respeitado")

    # erros
    for args, msg in (([], "sem print"), (prints * 2, "13 prints")):
        try:
            depoimentos.gerar_carrossel_depoimentos(args, str(tmp / "err")); check(False, f"{msg} deveria falhar")
        except ErroFerramenta:
            check(True, f"{msg} recusado")
    try:
        depoimentos.gerar_carrossel_depoimentos([{"arquivo": prints[0], "corte": [10, 10, 5, 5]}], str(tmp / "err")); check(False, "corte inválido deveria falhar")
    except ErroFerramenta:
        check(True, "corte inválido recusado")
    try:
        depoimentos.gerar_carrossel_depoimentos(prints[:1], str(tmp / "err"), molde_dir=str(tmp / "nao-existe")); check(False, "molde ausente deveria falhar")
    except ErroFerramenta:
        check(True, "molde ausente recusado")
    entrada = tmp / "entrada"; entrada.mkdir()
    try:
        depoimentos.gerar_carrossel_depoimentos(prints[:1], str(entrada / "x")); check(False, "gravar em entrada/ deveria falhar")
    except ErroFerramenta:
        check(True, "não grava dentro de entrada/")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
