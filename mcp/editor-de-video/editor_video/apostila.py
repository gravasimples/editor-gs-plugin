"""Apostila (A4) ou slides (16:9) em PDF no manual da marca, com reportlab e Inter embutida. O Editor escreve o conteúdo em JSON;
a ferramenta diagrama: capa, seções, parágrafos, listas, passo a passo, dica/atenção, imagens (prints reais) e rodapé com página.
Sem preço, oferta ou número de alunos no conteúdo (responsabilidade do Editor); a ferramenta só diagrama."""
import json
from pathlib import Path
from .util import caminho, caminho_saida, ErroFerramenta
from .imagem import CORES, FONTES

A4 = (595.28, 841.89)
SLIDE = (960.0, 540.0)


def _fontes():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for nome, arq in (("Inter-ExtraBold", "Inter-ExtraBold.ttf"), ("Inter-Bold", "Inter-Bold.ttf"), ("Inter-Regular", "Inter-Regular.ttf")):
        if nome not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nome, str(FONTES / arq)))


def _ler(conteudo):
    if isinstance(conteudo, (str, Path)):
        p = Path(caminho(conteudo)); d = json.loads(p.read_text(encoding="utf-8"))
    else:
        d = conteudo
    if not isinstance(d, dict) or not d.get("secoes"):
        raise ErroFerramenta("Conteúdo precisa ser um objeto com `titulo` e `secoes` (lista).")
    return d


def _estilos():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    base = dict(fontName="Inter-Regular", textColor=HexColor(CORES["grafite"]), leading=16, fontSize=11, alignment=TA_LEFT)
    return {
        "corpo": ParagraphStyle("corpo", **base),
        "secao": ParagraphStyle("secao", fontName="Inter-ExtraBold", fontSize=22, leading=27, textColor=HexColor(CORES["marinho"]), spaceBefore=18, spaceAfter=8),
        "sub": ParagraphStyle("sub", fontName="Inter-Bold", fontSize=14, leading=18, textColor=HexColor(CORES["marinho"]), spaceBefore=10, spaceAfter=4),
        "item": ParagraphStyle("item", **{**base, "leftIndent": 14, "bulletIndent": 2}),
        "passo": ParagraphStyle("passo", **{**base, "leftIndent": 26, "bulletIndent": 2, "bulletFontName": "Inter-Bold", "bulletColor": HexColor(CORES["laranja"])}),
        "caixa": ParagraphStyle("caixa", **{**base, "textColor": HexColor(CORES["branco"])}),
        "legenda": ParagraphStyle("legenda", **{**base, "fontSize": 9, "leading": 12, "textColor": HexColor(CORES["nevoa"])}),
        "capa_tit": ParagraphStyle("capa_tit", fontName="Inter-ExtraBold", fontSize=34, leading=40, textColor=HexColor(CORES["branco"])),
        "capa_sub": ParagraphStyle("capa_sub", fontName="Inter-Regular", fontSize=15, leading=21, textColor=HexColor(CORES["nevoa"])),
    }


def _esc(t):
    return str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _destacar(texto, destaque):
    """Uma palavra em laranja (um destaque por título, como manda o manual)."""
    t = _esc(texto)
    if destaque:
        d = _esc(destaque)
        if d and d in t:
            t = t.replace(d, f'<font color="{CORES["laranja"]}">{d}</font>', 1)
    return t


def _imagem(bloco, largura_max, altura_max):
    from reportlab.platypus import Image as RLImage
    from PIL import Image as PILImage
    p = caminho(bloco["imagem"]); w, h = PILImage.open(p).size
    esc = min(largura_max / w, altura_max / h, 1.0 if w < largura_max else largura_max / w)
    return RLImage(str(p), width=w * esc, height=h * esc)


def _blocos_secao(sec, est, largura, altura_img):
    from reportlab.platypus import Paragraph, Spacer, ListFlowable, ListItem, Table, TableStyle, KeepTogether
    from reportlab.lib.colors import HexColor
    out = []
    for b in sec.get("blocos", []):
        if isinstance(b, str):
            b = {"paragrafo": b}
        if "paragrafo" in b:
            out.append(Paragraph(_esc(b["paragrafo"]), est["corpo"])); out.append(Spacer(1, 6))
        elif "subtitulo" in b:
            out.append(Paragraph(_esc(b["subtitulo"]), est["sub"]))
        elif "lista" in b:
            out.append(ListFlowable([ListItem(Paragraph(_esc(x), est["item"]), value="•") for x in b["lista"]], bulletType="bullet", bulletFontName="Inter-Bold", bulletColor=HexColor(CORES["laranja"]), leftIndent=14)); out.append(Spacer(1, 6))
        elif "passos" in b:
            out.append(ListFlowable([ListItem(Paragraph(_esc(x), est["passo"])) for x in b["passos"]], bulletType="1", bulletFontName="Inter-Bold", bulletColor=HexColor(CORES["laranja"]), leftIndent=26, bulletFormat="%s.")); out.append(Spacer(1, 6))
        elif "dica" in b or "atencao" in b:
            txt = b.get("dica") or b.get("atencao"); rot = "DICA" if "dica" in b else "ATENÇÃO"
            cor = CORES["card"] if "dica" in b else CORES["laranja2"]
            t = Table([[Paragraph(f'<font name="Inter-Bold" size="9">{rot}</font><br/>{_esc(txt)}', est["caixa"])]], colWidths=[largura])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor(cor)), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("ROUNDEDCORNERS", [8, 8, 8, 8])]))
            out.append(KeepTogether([t, Spacer(1, 8)]))
        elif "imagem" in b:
            try:
                img = _imagem(b, largura, altura_img)
            except Exception as e:
                raise ErroFerramenta(f"Imagem inválida em '{sec.get('titulo', '')}': {e}")
            itens = [img]
            if b.get("legenda"):
                itens += [Spacer(1, 3), Paragraph(_esc(b["legenda"]), est["legenda"])]
            out.append(KeepTogether(itens + [Spacer(1, 8)]))
        elif "tabela" in b:
            linhas = [[Paragraph(_esc(c), est["corpo"]) for c in l] for l in b["tabela"]]
            t = Table(linhas, colWidths=[largura / max(1, len(linhas[0]))] * len(linhas[0]))
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), HexColor(CORES["papel"])), ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(CORES["nevoa"])), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            out.append(t); out.append(Spacer(1, 8))
    return out


def gerar_apostila(conteudo_json, saida_pdf, formato="apostila", logo=""):
    """formato apostila (A4, corrido, com capa e sumário simples) ou slides (16:9, uma seção por página, texto grande)."""
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, NextPageTemplate, KeepTogether
    from reportlab.lib.colors import HexColor
    _fontes(); d = _ler(conteudo_json); est = _estilos()
    out = caminho_saida(saida_pdf)
    titulo, subtitulo, autor = d.get("titulo", "Apostila"), d.get("subtitulo", ""), d.get("autor", "Grava Simples")
    secoes = d["secoes"]; lg = Path(caminho(logo)) if logo else None
    if lg is not None and not lg.exists():
        lg = None
    W, H = A4 if formato == "apostila" else SLIDE
    margem = 48 if formato == "apostila" else 44

    def capa(c, doc):
        c.saveState(); c.setFillColor(HexColor(CORES["marinho"])); c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(HexColor(CORES["laranja"])); c.rect(margem, H * 0.36 - 6, 72, 6, fill=1, stroke=0)
        if lg:
            c.drawImage(str(lg), margem, H - margem - 36, height=36, width=144, preserveAspectRatio=True, mask="auto", anchor="nw")
        c.setFillColor(HexColor(CORES["nevoa"])); c.setFont("Inter-Regular", 10); c.drawString(margem, margem, f"{autor} · {d.get('data', '')}".strip(" ·"))
        c.restoreState()

    def normal(c, doc):
        c.saveState(); c.setFillColor(HexColor(CORES["marinho"])); c.rect(0, H - 8, W, 8, fill=1, stroke=0)
        c.setFillColor(HexColor(CORES["nevoa"])); c.setFont("Inter-Regular", 8.5)
        c.drawString(margem, 22, f"{titulo} · {autor}"); c.drawRightString(W - margem, 22, str(doc.page))
        c.restoreState()

    def slide_fundo(c, doc):
        c.saveState(); c.setFillColor(HexColor(CORES["marinho"] if doc.page % 2 else CORES["papel"])); c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(HexColor(CORES["laranja"])); c.rect(0, 0, W * doc.page / max(1, len(secoes) + 1), 5, fill=1, stroke=0)
        c.setFillColor(HexColor(CORES["nevoa"])); c.setFont("Inter-Regular", 9); c.drawRightString(W - margem, 14, f"{doc.page}")
        c.restoreState()

    doc = BaseDocTemplate(str(out), pagesize=(W, H), leftMargin=margem, rightMargin=margem, topMargin=margem, bottomMargin=margem + 6, title=titulo, author=autor)
    largura = W - 2 * margem
    if formato == "apostila":
        fr_capa = Frame(margem, margem, largura, H * 0.62 - margem, id="capa", showBoundary=0)
        fr = Frame(margem, margem + 16, largura, H - 2 * margem - 16, id="normal")
        doc.addPageTemplates([PageTemplate(id="capa", frames=[fr_capa], onPage=capa), PageTemplate(id="normal", frames=[fr], onPage=normal)])
        hist = [Spacer(1, H * 0.1), Paragraph(_destacar(titulo, d.get("destaque")), est["capa_tit"]), Spacer(1, 10)]
        if subtitulo:
            hist.append(Paragraph(_esc(subtitulo), est["capa_sub"]))
        hist += [NextPageTemplate("normal"), PageBreak()]
        if len(secoes) > 2:
            hist.append(Paragraph("Neste material", est["secao"]))
            for i, s in enumerate(secoes, 1):
                hist.append(Paragraph(f'<font color="{CORES["laranja"]}">{i}.</font> {_esc(s.get("titulo", ""))}', est["corpo"]))
            hist.append(Spacer(1, 14))
        for i, s in enumerate(secoes, 1):
            hist.append(KeepTogether([Paragraph(_destacar(s.get("titulo", ""), s.get("destaque")), est["secao"])]))
            hist += _blocos_secao(s, est, largura, H * 0.42)
        if d.get("cta"):
            hist += [Spacer(1, 18), Paragraph(_esc(d["cta"]), est["sub"])]
    else:
        est["secao"].fontSize, est["secao"].leading = 30, 36
        est["corpo"].fontSize, est["corpo"].leading = 16, 23
        est["item"].fontSize, est["item"].leading, est["passo"].fontSize, est["passo"].leading = 16, 23, 16, 23
        fr = Frame(margem, margem, largura, H - 2 * margem, id="slide")
        doc.addPageTemplates([PageTemplate(id="slide", frames=[fr], onPage=slide_fundo)])
        hist = [Spacer(1, H * 0.28), Paragraph(_destacar(titulo, d.get("destaque")), est["capa_tit"]), Spacer(1, 8)]
        if subtitulo:
            hist.append(Paragraph(_esc(subtitulo), est["capa_sub"]))
        hist.append(PageBreak())
        for i, s in enumerate(secoes, 1):
            claro = (i + 1) % 2 == 0  # página 2, 4… clara (slide_fundo usa doc.page)
            est_sec = est["secao"].clone(f"sec{i}", textColor=HexColor(CORES["marinho"] if claro else CORES["branco"]))
            est_corpo = est["corpo"].clone(f"corpo{i}", textColor=HexColor(CORES["grafite"] if claro else CORES["branco"]))
            est_item = est["item"].clone(f"item{i}", textColor=est_corpo.textColor); est_passo = est["passo"].clone(f"passo{i}", textColor=est_corpo.textColor)
            e2 = {**est, "secao": est_sec, "corpo": est_corpo, "item": est_item, "passo": est_passo, "sub": est["sub"].clone(f"sub{i}", textColor=est_sec.textColor)}
            hist.append(Paragraph(_destacar(s.get("titulo", ""), s.get("destaque")), est_sec)); hist.append(Spacer(1, 6))
            hist += _blocos_secao(s, e2, largura, H * 0.30)
            if i < len(secoes):
                hist.append(PageBreak())
    try:
        doc.build(hist)
    except Exception as e:
        raise ErroFerramenta(f"Falha ao diagramar o PDF: {type(e).__name__}: {str(e)[:200]}")
    from pypdf import PdfReader
    try:
        n = len(PdfReader(str(out)).pages)
    except Exception:
        n = None
    return {"pdf": str(out), "formato": formato, "paginas": n, "secoes": len(secoes), "tamanho_kb": round(out.stat().st_size / 1024), "fontes_embutidas": ["Inter-ExtraBold", "Inter-Bold", "Inter-Regular"]}
