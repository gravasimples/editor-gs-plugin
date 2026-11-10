"""Editável do carrossel para o Canva: PPTX 1080×1350 com camadas reais (fundo, selo, título com destaque, apoio, CTA, foto, barra, contador).
O Canva importa PPTX com texto editável e fontes por nome (Inter). Não depende da 'camada mágica'."""
import json
from pathlib import Path
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from .util import caminho, caminho_saida, ErroFerramenta
from .imagem import CORES, FORMATOS, _quebrar, _fonte
from PIL import ImageDraw, Image

PX = 9525  # EMU por pixel


def _rgb(h):
    h = h.lstrip("#"); return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _caixa(slide, x, y, w, h, texto, tam_px, cor, negrito=True, destaque=None, cor_dest=None, fonte="Inter", alinhamento=PP_ALIGN.LEFT, entrelinha=1.12):
    tb = slide.shapes.add_textbox(Emu(x * PX), Emu(y * PX), Emu(w * PX), Emu(h * PX)); tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]; p.alignment = alinhamento; p.line_spacing = entrelinha
    usado = False
    for i, palavra in enumerate(texto.split(" ")):
        r = p.add_run(); r.text = palavra + (" " if i < len(texto.split(" ")) - 1 else "")
        f = r.font; f.name = fonte; f.size = Pt(tam_px * 0.75); f.bold = negrito
        chave = "".join(c for c in palavra.lower() if c.isalnum())
        if destaque and not usado and chave == "".join(c for c in destaque.lower() if c.isalnum()):
            f.color.rgb = _rgb(cor_dest or CORES["laranja"]); usado = True
        else:
            f.color.rgb = _rgb(cor)
    return tb


def _retangulo(slide, x, y, w, h, cor, cantos_px=0, pilula=False, alpha=None, oval=False):
    """alpha (0 a 1) deixa o preenchimento translúcido (selo do manual: azul a 47 %); oval=True desenha uma elipse (ponto laranja do selo)."""
    forma = MSO_SHAPE.OVAL if oval else MSO_SHAPE.ROUNDED_RECTANGLE if (cantos_px or pilula) else MSO_SHAPE.RECTANGLE
    s = slide.shapes.add_shape(forma, Emu(x * PX), Emu(y * PX), Emu(w * PX), Emu(h * PX))
    s.fill.solid(); s.fill.fore_color.rgb = _rgb(cor); s.line.fill.background()
    if alpha is not None:
        from pptx.oxml.ns import qn
        srgb = s._element.spPr.find(".//" + qn("a:srgbClr"))
        if srgb is not None:
            a = srgb.makeelement(qn("a:alpha"), {"val": str(int(max(0.0, min(1.0, alpha)) * 100000))}); srgb.append(a)
    if forma == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.5 if pilula else min(0.5, cantos_px / min(w, h))
    return s


def _altura_texto(texto, tam_px, largura, entrelinha=1.15):
    im = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(im); f = _fonte("ExtraBold", tam_px)
    return len(_quebrar(d, texto, f, largura)) * int(tam_px * entrelinha)


def exportar_canva(slides_json, saida_pptx, modelo="tipografico", logo="", foto_capa="", nome="Carrossel Grava Simples"):
    """Gera o PPTX editável do carrossel (mesma composição do gerar_carrossel). Devolve caminho, nº de slides e instruções de importação."""
    if isinstance(slides_json, (str, Path)):
        p = Path(caminho(slides_json))
        slides = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    else:
        slides = slides_json
    if isinstance(slides, dict):
        slides = slides.get("slides", [])
    if not slides:
        raise ErroFerramenta("slides.json vazio.")
    W, H = FORMATOS["carrossel"]; margem = int(W * 0.08); larg = W - 2 * margem
    prs = Presentation(); prs.slide_width = Emu(W * PX); prs.slide_height = Emu(H * PX)
    branco = prs.slide_layouts[6]; n = len(slides); lg = Path(caminho(logo)) if logo else None
    for i, s in enumerate(slides):
        tipo = s.get("tipo") or ("capa" if i == 0 else "cta" if (i == n - 1 and (s.get("cta") or n > 1)) else "conteudo")
        claro = (modelo == "tweet" and tipo == "capa") or (modelo == "tipografico" and i % 2 == 1 and tipo != "cta")
        fundo, cor_txt, cor_apoio = (CORES["papel"], CORES["grafite"], CORES["grafite"]) if claro else (CORES["marinho"], CORES["branco"], CORES["nevoa"])
        sl = prs.slides.add_slide(branco); sl.background.fill.solid(); sl.background.fill.fore_color.rgb = _rgb(fundo)
        foto = s.get("foto") or (foto_capa if tipo == "capa" else "")
        caixa_x, caixa_w = margem, larg
        if modelo == "historia" and foto and Path(caminho(foto)).exists():
            sl.shapes.add_picture(str(caminho(foto)), 0, 0, Emu(W * PX), Emu(H * PX))
            _retangulo(sl, margem, int(H * 0.62), larg, H - margem - int(H * 0.62), CORES["marinho"], cantos_px=20)
            y = int(H * 0.62) + int(W * 0.05); caixa_x = margem + int(W * 0.05); caixa_w = larg - int(W * 0.1)
            cor_txt, cor_apoio = CORES["branco"], CORES["nevoa"]
        elif foto and tipo == "capa" and Path(caminho(foto)).exists():
            sl.shapes.add_picture(str(caminho(foto)), 0, 0, Emu(W * PX), Emu(int(H * 0.5) * PX)); y = int(H * 0.5) + margem
        else:
            y = int(H * 0.16)
        if lg and lg.exists():
            sl.shapes.add_picture(str(lg), Emu(margem * PX), Emu(margem * PX), height=Emu(int(W * 0.05) * PX))
        if s.get("selo"):
            tw = int(len(s["selo"]) * 18) + 90
            _retangulo(sl, caixa_x, y, tw, 56, CORES["azul"], pilula=True, alpha=0.47)  # pílula azul translúcida do manual
            _retangulo(sl, caixa_x + 24, y + 21, 14, 14, CORES["laranja"], oval=True)  # ponto laranja
            _caixa(sl, caixa_x + 48, y + 12, tw - 48, 40, s["selo"].upper(), 30, CORES["branco"], alinhamento=PP_ALIGN.LEFT)
            y += 56 + int(W * 0.03)
        tam = int(W * (0.085 if tipo == "capa" else 0.07)); titulo = s.get("titulo", "")
        alt = _altura_texto(titulo, tam, caixa_w)
        _caixa(sl, caixa_x, y, caixa_w, alt + 10, titulo, tam, cor_txt, True, s.get("destaque"), CORES["laranja"])
        y += alt + int(W * 0.035)
        apoio = s.get("apoio") or []
        apoio = [apoio] if isinstance(apoio, str) else apoio
        if apoio:
            tam_ap = int(W * 0.04); linhas = [(("• " if len(apoio) > 1 and modelo != "tweet" else "") + a) for a in apoio[:6]]
            texto = "\n".join(linhas); alt_ap = sum(_altura_texto(l, tam_ap, caixa_w, 1.3) + int(W * 0.012) for l in linhas)
            tb = sl.shapes.add_textbox(Emu(caixa_x * PX), Emu(y * PX), Emu(caixa_w * PX), Emu((alt_ap + 10) * PX)); tf = tb.text_frame; tf.word_wrap = True
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            for k, l in enumerate(linhas):
                par = tf.paragraphs[0] if k == 0 else tf.add_paragraph(); par.line_spacing = 1.3; par.space_after = Pt(int(W * 0.012) * 0.75)
                r = par.add_run(); r.text = l; r.font.name = "Inter"; r.font.size = Pt(tam_ap * 0.75); r.font.bold = False; r.font.color.rgb = _rgb(cor_apoio)
            y += alt_ap
        if tipo == "cta" or s.get("cta"):
            txt = s.get("cta") or "Siga @thiago.obsstudio"; tam_c = int(W * 0.038); bw = int(len(txt) * tam_c * 0.55) + int(W * 0.1); bh = int(W * 0.1)
            by = H - margem - bh - int(W * 0.04)
            _retangulo(sl, caixa_x, by, bw, bh, CORES["laranja"], pilula=True)
            _caixa(sl, caixa_x, by + int(bh * 0.28), bw, bh, txt, tam_c, CORES["marinho"], True, alinhamento=PP_ALIGN.CENTER)
        _caixa(sl, W - margem - 80, H - margem - 10, 80, 34, f"{i + 1}/{n}", 28, cor_apoio, False, alinhamento=PP_ALIGN.RIGHT)
        if tipo != "cta":
            _retangulo(sl, margem, H - margem + 18, int(larg * (i + 1) / n), 8, CORES["laranja"], cantos_px=4)
    out = caminho_saida(saida_pptx); prs.save(str(out))
    return {"pptx": str(out), "n_slides": n, "largura": W, "altura": H, "fonte": "Inter (ExtraBold nos títulos; o Canva mapeia pelo nome)",
            "como_abrir_no_canva": "Canva → Criar design → Importar arquivo (ou arraste o .pptx na página inicial). Cada slide vira uma página 1080×1350 com texto, selo, botão e foto como camadas separadas."}


# --- variante PDF (texto real com Inter embutida; o Canva converte em elementos editáveis) ----------------

def exportar_canva_pdf(slides_json, saida_pdf, modelo="tipografico", logo="", foto_capa=""):
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    from .imagem import FONTES
    for nome, arq in (("Inter-ExtraBold", "Inter-ExtraBold.ttf"), ("Inter-Bold", "Inter-Bold.ttf"), ("Inter-Regular", "Inter-Regular.ttf")):
        if nome not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nome, str(FONTES / arq)))
    if isinstance(slides_json, (str, Path)):
        p = Path(caminho(slides_json)); slides = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    else:
        slides = slides_json
    if isinstance(slides, dict):
        slides = slides.get("slides", [])
    if not slides:
        raise ErroFerramenta("slides.json vazio.")
    W, H = FORMATOS["carrossel"]; margem = int(W * 0.08); larg = W - 2 * margem; n = len(slides)
    out = caminho_saida(saida_pdf); c = rl_canvas.Canvas(str(out), pagesize=(W, H))
    def Y(y_topo, alt=0):  # converte y medido do topo (como nas imagens) para o eixo do PDF
        return H - y_topo - alt
    def texto_destaque(x, y, texto, tam, cor, destaque, largura, fonte="Inter-ExtraBold", entrelinha=1.15, centro=False):
        c.setFont(fonte, tam); usado = False; linhas, atual = [], ""
        for w in texto.split():
            t = (atual + " " + w).strip()
            if pdfmetrics.stringWidth(t, fonte, tam) > largura and atual:
                linhas.append(atual); atual = w
            else:
                atual = t
        if atual: linhas.append(atual)
        yy = y
        for linha in linhas:
            lw = pdfmetrics.stringWidth(linha, fonte, tam); xx = x + (largura - lw) / 2 if centro else x
            for w in linha.split(" "):
                chave = "".join(ch for ch in w.lower() if ch.isalnum())
                if destaque and not usado and chave == "".join(ch for ch in destaque.lower() if ch.isalnum()):
                    c.setFillColor(HexColor(CORES["laranja"])); usado = True
                else:
                    c.setFillColor(HexColor(cor))
                c.drawString(xx, Y(yy + tam), w); xx += pdfmetrics.stringWidth(w + " ", fonte, tam)
            yy += int(tam * entrelinha)
        return yy - y
    for i, s in enumerate(slides):
        tipo = s.get("tipo") or ("capa" if i == 0 else "cta" if (i == n - 1 and (s.get("cta") or n > 1)) else "conteudo")
        claro = (modelo == "tweet" and tipo == "capa") or (modelo == "tipografico" and i % 2 == 1 and tipo != "cta")
        fundo, cor_txt, cor_apoio = (CORES["papel"], CORES["grafite"], CORES["grafite"]) if claro else (CORES["marinho"], CORES["branco"], CORES["nevoa"])
        c.setFillColor(HexColor(fundo)); c.rect(0, 0, W, H, fill=1, stroke=0)
        foto = s.get("foto") or (foto_capa if tipo == "capa" else ""); caixa_x, caixa_w = margem, larg
        if modelo == "historia" and foto and Path(caminho(foto)).exists():
            c.drawImage(str(caminho(foto)), 0, 0, W, H, preserveAspectRatio=True, mask="auto")
            c.setFillColor(HexColor(CORES["marinho"])); c.roundRect(margem, Y(int(H * 0.62), H - margem - int(H * 0.62)), larg, H - margem - int(H * 0.62), 20, fill=1, stroke=0)
            y = int(H * 0.62) + int(W * 0.05); caixa_x = margem + int(W * 0.05); caixa_w = larg - int(W * 0.1); cor_txt, cor_apoio = CORES["branco"], CORES["nevoa"]
        elif foto and tipo == "capa" and Path(caminho(foto)).exists():
            c.drawImage(str(caminho(foto)), 0, Y(0, int(H * 0.5)), W, int(H * 0.5), preserveAspectRatio=True, mask="auto"); y = int(H * 0.5) + margem
        else:
            y = int(H * 0.16)
        lg = Path(caminho(logo)) if logo else None
        if lg and lg.exists():
            c.drawImage(str(lg), margem, Y(margem, int(W * 0.05)), height=int(W * 0.05), width=int(W * 0.05) * 4, preserveAspectRatio=True, mask="auto", anchor="nw")
        if s.get("selo"):
            tw = pdfmetrics.stringWidth(s["selo"].upper(), "Inter-Bold", 30) + 90
            c.setFillColor(HexColor(CORES["azul"])); c.setFillAlpha(0.47); c.roundRect(caixa_x, Y(y, 56), tw, 56, 28, fill=1, stroke=0); c.setFillAlpha(1)
            c.setFillColor(HexColor(CORES["laranja"])); c.circle(caixa_x + 31, Y(y + 28), 7, fill=1, stroke=0)
            c.setFont("Inter-Bold", 30); c.setFillColor(HexColor(CORES["branco"])); c.drawString(caixa_x + 48, Y(y + 40), s["selo"].upper()); y += 56 + int(W * 0.03)
        tam = int(W * (0.085 if tipo == "capa" else 0.07))
        y += texto_destaque(caixa_x, y, s.get("titulo", ""), tam, cor_txt, s.get("destaque"), caixa_w) + int(W * 0.035)
        apoio = s.get("apoio") or []; apoio = [apoio] if isinstance(apoio, str) else apoio
        for linha in apoio[:6]:
            marcador = "• " if len(apoio) > 1 and modelo != "tweet" else ""
            y += texto_destaque(caixa_x, y, marcador + linha, int(W * 0.04), cor_apoio, None, caixa_w, fonte="Inter-Regular", entrelinha=1.3) + int(W * 0.012)
        if tipo == "cta" or s.get("cta"):
            txt = s.get("cta") or "Siga @thiago.obsstudio"; tam_c = int(W * 0.038); bw = pdfmetrics.stringWidth(txt, "Inter-Bold", tam_c) + int(W * 0.1); bh = int(W * 0.1)
            by = H - margem - bh - int(W * 0.04)
            c.setFillColor(HexColor(CORES["laranja"])); c.roundRect(caixa_x, Y(by, bh), bw, bh, bh / 2, fill=1, stroke=0)
            c.setFont("Inter-Bold", tam_c); c.setFillColor(HexColor(CORES["marinho"])); c.drawString(caixa_x + int(W * 0.05), Y(by + bh / 2 + tam_c * 0.35), txt)
        c.setFont("Inter-Regular", 28); c.setFillColor(HexColor(cor_apoio)); c.drawRightString(W - margem, Y(H - margem + 18), f"{i + 1}/{n}")
        if tipo != "cta":
            c.setFillColor(HexColor(CORES["laranja"])); c.roundRect(margem, Y(H - margem + 18, 8), int(larg * (i + 1) / n), 8, 4, fill=1, stroke=0)
        c.showPage()
    c.save()
    return {"pdf": str(out), "n_slides": n, "largura": W, "altura": H, "fontes_embutidas": ["Inter-ExtraBold", "Inter-Bold", "Inter-Regular"],
            "como_abrir_no_canva": "Canva → Importar arquivo (PDF): textos e formas viram elementos editáveis; fontes Inter embutidas."}
