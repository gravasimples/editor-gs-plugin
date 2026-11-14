"""Teste do editável para o Canva (PPTX) a partir de slides.json. Pasta temporária."""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import canva
from pptx import Presentation
from PIL import Image
FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); foto = tmp / "f.jpg"; Image.new("RGB", (1200, 800), (90, 40, 10)).save(foto); logo = tmp / "logo.png"; Image.new("RGBA", (300, 80), (255, 255, 255, 255)).save(logo)
    slides = [{"titulo": "Sua webcam está no automático", "destaque": "automático", "apoio": ["Por isso muda de cor."], "selo": "OBS", "foto": str(foto)},
              {"titulo": "Três ajustes", "destaque": "Três", "apoio": ["Exposição", "Obturador", "ISO"]}, {"titulo": "Salve para testar", "cta": "Siga @thiago.obsstudio"}]
    sj = tmp / "slides.json"; sj.write_text(json.dumps(slides, ensure_ascii=False))
    r = canva.exportar_canva(str(sj), str(tmp / "c.pptx"), modelo="tipografico", logo=str(logo))
    prs = Presentation(r["pptx"])
    check(len(prs.slides) == 3 and round(prs.slide_width / 9525) == 1080 and round(prs.slide_height / 9525) == 1350, "3 slides de 1080x1350")
    textos = [sh.text_frame.text for sh in prs.slides[0].shapes if sh.has_text_frame]
    check(any("automático" in t for t in textos) and any(t == "OBS" for t in textos), "título e selo como texto editável")
    from pptx.oxml.ns import qn
    alphas = [a.get("val") for sl in prs.slides for sh in sl.shapes for a in sh._element.iter(qn("a:alpha"))]
    check("47000" in alphas, f"selo do PPTX é translúcido (alpha 47 %): {alphas}")
    runs = [run for sh in prs.slides[0].shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for run in p.runs]
    dest = [run for run in runs if run.text.strip() == "automático"]
    check(dest and str(dest[0].font.color.rgb) == "F79615" and dest[0].font.name == "Inter" and dest[0].font.bold, "palavra de destaque em laranja, Inter, negrito")
    check(sum(1 for sh in prs.slides[0].shapes if sh.shape_type == 13) == 2, "foto da capa e logo como imagens")
    cta = [sh for sh in prs.slides[2].shapes if sh.has_text_frame and "Siga" in sh.text_frame.text]
    check(len(cta) == 1 and any(sh.shape_type == 1 for sh in prs.slides[2].shapes), "CTA como texto sobre forma pílula")
    r2 = canva.exportar_canva(slides, str(tmp / "h.pptx"), modelo="historia")
    check(len(Presentation(r2["pptx"]).slides) == 3, "modelo história também exporta")
    try:
        canva.exportar_canva([], str(tmp / "v.pptx")); check(False, "vazio deveria falhar")
    except Exception:
        check(True, "slides vazios recusados")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
