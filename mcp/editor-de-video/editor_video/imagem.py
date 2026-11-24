"""Imagens da Grava Simples: editor de fotos e criador de carrosséis (Pillow), seguindo o manual de marca:
marinho #000921, cards #0B193D, branco, laranja #F79615→#E9760D (um destaque por título), papel #F2F2F2, grafite #272A33, névoa #A7ACBD;
Inter ExtraBold/Regular; cantos 20 px; carrossel 1080×1350, uma ideia por slide, até 6 linhas de apoio, CTA final. Sem logo redesenhado: o logo só entra se houver arquivo oficial."""
import json, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageEnhance
from .util import caminho, caminho_saida, ErroFerramenta

RAIZ = Path(__file__).resolve().parents[3]
FONTES = RAIZ / "fontes"
CORES = {"marinho": "#000921", "card": "#0B193D", "branco": "#FFFFFF", "laranja": "#F79615", "laranja2": "#E9760D", "azul": "#284CB8", "papel": "#F2F2F2", "grafite": "#272A33", "nevoa": "#A7ACBD"}
FORMATOS = {"carrossel": (1080, 1350), "feed": (1080, 1350), "quadrado": (1080, 1080), "story": (1080, 1920), "capa_yt": (1280, 720), "16x9": (1920, 1080), "9x16": (1080, 1920)}
RAIO = 20


def _fonte(peso="ExtraBold", tam=64):
    nome = {"ExtraBold": "Inter-ExtraBold.ttf", "Bold": "Inter-Bold.ttf", "Regular": "Inter-Regular.ttf"}.get(peso, "Inter-ExtraBold.ttf")
    return ImageFont.truetype(str(FONTES / nome), tam)


def _quebrar(d, texto, fonte, largura):
    linhas, atual = [], ""
    for p in texto.split():
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=fonte) > largura and atual:
            linhas.append(atual); atual = p
        else:
            atual = teste
    if atual:
        linhas.append(atual)
    return linhas


def _texto_destaque(d, xy, texto, fonte, cor, destaque, cor_dest, largura, entrelinha=1.15, alinhamento="esquerda"):
    """Escreve texto quebrado em linhas; a palavra `destaque` (uma só, a primeira ocorrência) sai em laranja. Devolve a altura usada."""
    x0, y = xy; usado = False
    linhas = _quebrar(d, texto, fonte, largura); alt = int(fonte.size * entrelinha)
    for linha in linhas:
        lw = d.textlength(linha, font=fonte)
        x = x0 if alinhamento == "esquerda" else x0 + (largura - lw) / 2 if alinhamento == "centro" else x0 + largura - lw
        for p in linha.split(" "):
            c = cor
            if destaque and not usado and re.sub(r"[^\wÀ-ÿ]", "", p.lower()) == re.sub(r"[^\wÀ-ÿ]", "", destaque.lower()):
                c = cor_dest; usado = True
            d.text((x, y), p, font=fonte, fill=c); x += d.textlength(p + " ", font=fonte)
        y += alt
    return len(linhas) * alt


def _gradiente_laranja(w, h):
    g = Image.new("RGB", (w, h)); px = g.load()
    a = Image.new("RGB", (1, 1), CORES["laranja"]).getpixel((0, 0)); b = Image.new("RGB", (1, 1), CORES["laranja2"]).getpixel((0, 0))
    for x in range(w):
        t = x / max(1, w - 1); c = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
        for y in range(h):
            px[x, y] = c
    return g


def _pilula(im, caixa, texto, fonte, cor_texto=CORES["marinho"], degrade=True, cor=None):
    x0, y0, x1, y1 = caixa; w, h = x1 - x0, y1 - y0
    fundo = _gradiente_laranja(w, h) if degrade else Image.new("RGB", (w, h), cor or CORES["azul"])
    mask = Image.new("L", (w, h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=255)
    im.paste(fundo, (x0, y0), mask)
    d = ImageDraw.Draw(im); tw = d.textlength(texto, font=fonte)
    d.text((x0 + (w - tw) / 2, y0 + (h - fonte.size) / 2 - fonte.size * 0.08), texto, font=fonte, fill=cor_texto)


def _selo(im, xy, texto, fonte):
    """Selo do manual: pílula azul translúcida, ponto laranja e uma palavra em caixa alta. Devolve a altura usada."""
    x0, y0 = xy; txt = texto.upper(); d0 = ImageDraw.Draw(im); tw = int(d0.textlength(txt, font=fonte)); ponto = 14; h = 56; w = tw + ponto + 70
    cam = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(cam)
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h // 2, fill=(40, 76, 184, 120))
    cy = y0 + h // 2; d.ellipse((x0 + 24, cy - ponto // 2, x0 + 24 + ponto, cy + ponto // 2), fill=CORES["laranja"])
    d.text((x0 + 24 + ponto + 16, y0 + (h - fonte.size) / 2 - fonte.size * 0.08), txt, font=fonte, fill=CORES["branco"])
    im.paste(Image.alpha_composite(im.convert("RGBA"), cam).convert("RGB")); return h


def _print_centralizado(im, p, x, y, largura, altura_max):
    """Print (imagem) inteiro, sem corte, centralizado na largura, cantos arredondados. Devolve a altura usada (0 se não couber)."""
    if altura_max < 80:
        return 0
    f = ImageOps.exif_transpose(Image.open(caminho(p))).convert("RGB")
    esc = min(largura / f.width, altura_max / f.height); f = f.resize((max(1, int(f.width * esc)), max(1, int(f.height * esc))), Image.LANCZOS)
    mask = Image.new("L", f.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, f.width - 1, f.height - 1), radius=RAIO, fill=255)
    im.paste(f, (x + (largura - f.width) // 2, y), mask); return f.height


def _foto_ajustada(p, w, h, desfoque=0):
    im = ImageOps.exif_transpose(Image.open(caminho(p))).convert("RGB")
    im = ImageOps.fit(im, (w, h), method=Image.LANCZOS, centering=(0.5, 0.4))
    if desfoque:
        im = im.filter(ImageFilter.GaussianBlur(desfoque))
    return im


def _logo(im, logo, W, margem):
    """Logo oficial no canto superior esquerdo, se existir arquivo. Nunca desenha a marca por inferência."""
    if not logo:
        return False
    p = Path(caminho(logo))
    if not p.exists():
        return False
    lg = Image.open(p).convert("RGBA"); alt = int(W * 0.05); lg = lg.resize((int(lg.width * alt / lg.height), alt), Image.LANCZOS)
    im.paste(lg, (margem, margem), lg); return True


def gerar_carrossel(slides_json, saida_dir, modelo="tipografico", logo="", foto_capa="", nome_base="slide", tamanho=None):
    """Carrossel 1080×1350. slides_json: arquivo ou lista [{"titulo","destaque","apoio":[...até 6], "foto"?, "cta"?, "tipo"?}].
    modelo: tipografico (Inter, alterna marinho/papel) | marinho (todos escuros) | historia (foto + caixa marinho no terço inferior) | tweet (capa clara, interiores marinho, números em laranja).
    "print": imagem inteira (sem corte) centralizada abaixo do texto, com cantos arredondados (depoimento, comentário, tela do OBS). "selo": pílula azul translúcida com ponto laranja.
    Último slide = CTA (botão pílula). "fundo": papel | marinho força a cor do slide (03/11/2026). `tamanho` (L, A) desenha em outra área (story nativo). Devolve a lista de PNGs."""
    slides = json.loads(Path(caminho(slides_json)).read_text(encoding="utf-8")) if isinstance(slides_json, str) and Path(caminho(slides_json)).exists() else slides_json
    if isinstance(slides, dict):
        slides = slides.get("slides", [])
    if not slides or len(slides) > 10:
        raise ErroFerramenta("Carrossel precisa de 1 a 10 slides.")
    W, H = tuple(tamanho) if tamanho else FORMATOS["carrossel"]; margem = int(W * 0.08); larg = W - 2 * margem
    esc = 1.22 if H / W > 1.29 else 1.0  # área alta (story nativo): letras maiores, o story é lido no celular a um palmo
    out_dir = Path(caminho_saida(str(Path(saida_dir) / "x"))).parent; out_dir.mkdir(parents=True, exist_ok=True)
    saidas = []; n = len(slides)
    for i, s in enumerate(slides):
        tipo = s.get("tipo") or ("capa" if i == 0 else "cta" if (i == n - 1 and (s.get("cta") or n > 1)) else "conteudo")
        claro = (modelo == "tweet" and tipo == "capa") or (modelo == "tipografico" and i % 2 == 1 and tipo != "cta")
        if s.get("fundo") in ("papel", "marinho"):
            claro = s["fundo"] == "papel"
        fundo, cor_txt, cor_apoio = (CORES["papel"], CORES["grafite"], CORES["grafite"]) if claro else (CORES["marinho"], CORES["branco"], CORES["nevoa"])
        foto = s.get("foto") or (foto_capa if tipo == "capa" else "")
        if modelo == "historia" and foto:
            im = _foto_ajustada(foto, W, H)
            d = ImageDraw.Draw(im, "RGBA"); d.rounded_rectangle((margem, int(H * 0.62), W - margem, H - margem), radius=RAIO, fill=(0, 9, 33, 235))
            fundo = CORES["marinho"]; cor_txt, cor_apoio = CORES["branco"], CORES["nevoa"]; y = int(H * 0.62) + int(W * 0.05); caixa_x = margem + int(W * 0.05); caixa_w = larg - int(W * 0.1)
        else:
            im = Image.new("RGB", (W, H), fundo); d = ImageDraw.Draw(im)
            if foto and tipo == "capa":
                f = _foto_ajustada(foto, W, int(H * 0.5)); mask = Image.new("L", f.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, f.width - 1, f.height - 1), radius=RAIO, fill=255)
                im.paste(f, (0, 0), mask)
                y = int(H * 0.5) + margem
            else:
                y = int(H * 0.16)
            caixa_x, caixa_w = margem, larg
        d = ImageDraw.Draw(im)
        _logo(im, logo, W, margem)
        # selo (uma palavra) opcional
        if s.get("selo"):
            y += _selo(im, (caixa_x, y), s["selo"], _fonte("Bold", 30)) + int(W * 0.03); d = ImageDraw.Draw(im)
        # título
        tam = int(W * (0.085 if tipo == "capa" else 0.07) * esc); f_tit = _fonte("ExtraBold", tam)
        titulo = s.get("titulo", "")
        if modelo == "tweet" and tipo != "capa":
            titulo = titulo  # números em laranja ficam pelo destaque
        y += _texto_destaque(d, (caixa_x, y), titulo, f_tit, cor_txt, s.get("destaque"), CORES["laranja"], caixa_w) + int(W * 0.035)
        # apoio
        apoio = s.get("apoio") or []
        if isinstance(apoio, str):
            apoio = [apoio]
        f_ap = _fonte("Regular", int(W * 0.04 * esc))
        for linha in apoio[:6]:
            marcador = "• " if len(apoio) > 1 and modelo != "tweet" else ""
            y += _texto_destaque(d, (caixa_x, y), marcador + linha, f_ap, cor_apoio, None, CORES["laranja"], caixa_w, entrelinha=1.3) + int(W * 0.012)
        # print inteiro (sem corte) abaixo do texto
        if s.get("print"):
            reserva = margem + int(W * 0.04) + (int(W * 0.1) + int(W * 0.04) if (tipo == "cta" or s.get("cta")) else 0)
            y += _print_centralizado(im, s["print"], caixa_x, y + int(W * 0.01), caixa_w, H - reserva - y - int(W * 0.03)) + int(W * 0.03); d = ImageDraw.Draw(im)
        # CTA
        if tipo == "cta" or s.get("cta"):
            f_cta = _fonte("Bold", int(W * 0.038 * esc)); txt = s.get("cta") or "Siga @thiago.obsstudio"
            tw = d.textlength(txt, font=f_cta); bw = int(tw) + int(W * 0.1); bh = int(W * 0.1)
            _pilula(im, (caixa_x, H - margem - bh - int(W * 0.04), caixa_x + bw, H - margem - int(W * 0.04)), txt, f_cta)
        # contador e barra (só em carrossel de verdade; post único e cena de vídeo não têm "1/1")
        if n > 1:
            f_num = _fonte("Regular", 28); d.text((W - margem - 60, H - margem - 10), f"{i + 1}/{n}", font=f_num, fill=cor_apoio)
        if tipo != "cta" and n > 1:
            d.rounded_rectangle((margem, H - margem + 18, margem + int(larg * (i + 1) / n), H - margem + 26), radius=4, fill=CORES["laranja"])
        p = out_dir / f"{nome_base}-{i + 1:02d}.png"; im.save(p, optimize=True); saidas.append(str(p))
    return {"slides": saidas, "n": n, "modelo": modelo, "largura": W, "altura": H, "logo_usado": bool(logo and Path(caminho(logo)).exists())}


def editar_foto(foto, saida, formato="feed", brilho=1.0, contraste=1.0, saturacao=1.0, nitidez=1.0, desfoque_fundo=False, texto="", destaque="", posicao="baixo", borda=0, cantos=0, logo="", escurecer=0.0):
    """Edita uma foto: enquadra no formato (feed 1080×1350 | quadrado | story | capa_yt | 16x9 | 9x16), ajusta brilho/contraste/saturação/nitidez,
    opcionalmente fundo desfocado (foto inteira dentro do quadro sem cortar), texto com uma palavra em laranja em caixa marinho (baixo | topo), borda marinho, cantos arredondados e logo."""
    if formato not in FORMATOS:
        raise ErroFerramenta(f"formato deve ser um de {sorted(FORMATOS)}")
    W, H = FORMATOS[formato]; src = ImageOps.exif_transpose(Image.open(caminho(foto))).convert("RGB")
    if desfoque_fundo:
        fundo = ImageOps.fit(src, (W, H), method=Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
        fundo = ImageEnhance.Brightness(fundo).enhance(0.6)
        fit = ImageOps.contain(src, (W - 2 * borda, H - 2 * borda), method=Image.LANCZOS)
        fundo.paste(fit, ((W - fit.width) // 2, (H - fit.height) // 2)); im = fundo
    else:
        im = ImageOps.fit(src, (W, H), method=Image.LANCZOS, centering=(0.5, 0.4))
    for cls, v in ((ImageEnhance.Brightness, brilho), (ImageEnhance.Contrast, contraste), (ImageEnhance.Color, saturacao), (ImageEnhance.Sharpness, nitidez)):
        if v != 1.0:
            im = cls(im).enhance(float(v))
    if escurecer:
        im = Image.blend(im, Image.new("RGB", im.size, CORES["marinho"]), min(0.9, max(0.0, float(escurecer))))
    if texto:
        d = ImageDraw.Draw(im, "RGBA"); margem = int(W * 0.06); f = _fonte("ExtraBold", int(W * 0.07)); larg = W - 2 * margem - int(W * 0.08)
        linhas = _quebrar(d, texto, f, larg); alt = len(linhas) * int(f.size * 1.15) + int(W * 0.08)
        y0 = H - margem - alt if posicao == "baixo" else margem
        d.rounded_rectangle((margem, y0, W - margem, y0 + alt), radius=RAIO, fill=(0, 9, 33, 225))
        _texto_destaque(d, (margem + int(W * 0.04), y0 + int(W * 0.04)), texto, f, CORES["branco"], destaque, CORES["laranja"], larg)
    if cantos:
        mask = Image.new("L", im.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=int(cantos), fill=255)
        base = Image.new("RGB", im.size, CORES["marinho"]); base.paste(im, (0, 0), mask); im = base
    if borda:
        im = ImageOps.expand(ImageOps.fit(im, (W - 2 * int(borda), H - 2 * int(borda))), border=int(borda), fill=CORES["marinho"])
    _logo(im, logo, W, int(W * 0.06))
    out = caminho_saida(saida); im.save(out, quality=92)
    return {"imagem": str(out), "largura": W, "altura": H, "formato": formato}


SEGURA_STORY = 250  # px livres em cima e embaixo no story (barra de progresso, perfil, campo de resposta do Instagram)


def gerar_post_imagem(saida, titulo, destaque="", apoio="", foto="", formato="feed", modelo="tipografico", cta="", logo="", selo="", fundo=""):
    """Post de imagem única (tipográfico, história com foto ou tweet) nos formatos feed | quadrado | story. Atalho para gerar_carrossel com um slide.
    fundo = papel | marinho (vazio = o do modelo). Story nativo (03/11/2026): o slide é desenhado na área segura 1080x1420 e fica entre as faixas
    de 250 px em cima e embaixo, na mesma cor, sem o vazio do 4:5 centralizado."""
    W, H = FORMATOS.get(formato, FORMATOS["feed"])
    slide = {"titulo": titulo, "destaque": destaque, "apoio": [apoio] if isinstance(apoio, str) and apoio else (apoio or []), "foto": foto, "cta": cta, "selo": selo, "tipo": "capa" if not cta else "cta"}
    if fundo in ("papel", "marinho"):
        slide["fundo"] = fundo
    out = Path(caminho_saida(saida))
    if formato == "story":
        r = gerar_carrossel([slide], str(out.parent), modelo=modelo, logo=logo, nome_base=out.stem, tamanho=(W, H - 2 * SEGURA_STORY))
        p = Path(r["slides"][0]); im = Image.open(p).convert("RGB")
        tela = Image.new("RGB", (W, H), im.getpixel((4, 4))); tela.paste(im, (0, SEGURA_STORY)); tela.save(p)
        if p != out:
            p.replace(out)
        return {"imagem": str(out), "largura": W, "altura": H, "modelo": modelo, "story_nativo": True, "area_segura_px": SEGURA_STORY}
    r = gerar_carrossel([slide], str(out.parent), modelo=modelo, logo=logo, nome_base=out.stem)
    p = Path(r["slides"][0])
    if (W, H) != FORMATOS["carrossel"]:
        im = Image.open(p).convert("RGB"); w0, h0 = im.size
        if abs((W / H) - (w0 / h0)) < 0.08:
            im = ImageOps.fit(im, (W, H), method=Image.LANCZOS)
        else:  # proporção diferente (story 9:16, 16:9): nada é cortado; o slide inteiro fica centralizado sobre a própria cor de fundo
            fundo = Image.new("RGB", (W, H), im.getpixel((4, 4))); esc = min(W / w0, H / h0)
            red = im.resize((max(1, int(w0 * esc)), max(1, int(h0 * esc))), Image.LANCZOS); fundo.paste(red, ((W - red.width) // 2, (H - red.height) // 2)); im = fundo
        im.save(p)
    if p != out:
        p.replace(out)
    return {"imagem": str(out), "largura": W, "altura": H, "modelo": modelo}


# --- quadros de vídeo e carrossel animado ------------------------------------------------------

def extrair_quadros(video, saida_dir, n=6, instantes=None, formato="carrossel", preferir_rosto=True):
    """Tira n quadros nítidos do vídeo para virar slides/fotos: amostra 2 por segundo, mede nitidez (variância do Laplaciano) e,
    se preferir_rosto, prioriza quadros com rosto. Ou use `instantes` (lista de segundos) para escolher à mão. Salva PNG no formato pedido."""
    import subprocess, numpy as np
    from .util import FFMPEG, info_midia
    v = caminho(video); info = info_midia(v); W, H = FORMATOS.get(formato, FORMATOS["carrossel"])
    out_dir = Path(caminho_saida(str(Path(saida_dir) / "x"))).parent; out_dir.mkdir(parents=True, exist_ok=True)
    if instantes:
        escolhidos = [float(t) for t in instantes]
    else:
        esc = 320 / info["largura"]; w, h = 320, int(round(info["altura"] * esc / 2) * 2)
        p = subprocess.Popen([FFMPEG, "-hide_banner", "-nostats", "-i", v, "-vf", f"fps=2,scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        det = None
        if preferir_rosto:
            try:
                from . import rosto as _rosto
                det, _ = _rosto._detector()
            except Exception:
                det = None
        quadros, i = [], 0
        while True:
            buf = p.stdout.read(w * h)
            if len(buf) < w * h:
                break
            g = np.frombuffer(buf, dtype=np.uint8).reshape(h, w).astype(np.float32)
            lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
            nit = float(lap.var()); t = i / 2.0; i += 1
            tem_rosto = False
            if det is not None:
                try:
                    tem_rosto = det(np.repeat(g.astype(np.uint8)[:, :, None], 3, axis=2)) is not None
                except Exception:
                    tem_rosto = False
            quadros.append((t, nit * (1.6 if tem_rosto else 1.0)))
        p.stdout.close(); p.wait()
        if not quadros:
            raise ErroFerramenta("Não li quadros do vídeo.")
        # espalha no tempo: divide em n janelas e pega o melhor de cada
        dur = info["duracao_s"]; escolhidos = []
        for k in range(n):
            a, b = dur * k / n, dur * (k + 1) / n
            cand = [q for q in quadros if a <= q[0] < b] or quadros
            escolhidos.append(max(cand, key=lambda q: q[1])[0])
    saidas = []
    for k, t in enumerate(escolhidos):
        tmp = out_dir / f"quadro-{k + 1:02d}.png"
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", v, "-frames:v", "1", str(tmp)], check=True)
        im = ImageOps.fit(Image.open(tmp).convert("RGB"), (W, H), method=Image.LANCZOS, centering=(0.5, 0.4)); im.save(tmp)
        saidas.append({"arquivo": str(tmp), "instante_s": round(t, 2)})
    return {"quadros": saidas, "n": len(saidas), "largura": W, "altura": H}


def animar_carrossel(slides, saida_video, duracao_slide_s=3.0, transicao_s=0.6, formato="4x5", zoom=1.08, fps=30, transicao="fade", audio=None):
    """Vídeo com os slides em sequência (Ken Burns leve + transição), para Reels/Story ou para um slide em vídeo no carrossel.
    slides: lista de PNG/JPG (ou pasta). formato: 4x5 (1080x1350) | 9x16 (1080x1920) | 1x1. 03/11/2026: slide de outra proporção (4:5 no 9:16) não é
    mais cortado (fica inteiro sobre ele mesmo desfocado); `transicao` = nome do xfade (fade, smoothleft, …) ou "" para corte seco; `audio` opcional
    (trilha ou narração, termina com fade)."""
    from .voz import TRANSICOES
    trans = (transicao or "").strip().lower()
    if trans and trans not in TRANSICOES:
        raise ErroFerramenta(f"transicao inválida: {transicao} (use {', '.join(sorted(TRANSICOES))} ou vazio)")
    import subprocess
    from .util import FFMPEG
    if isinstance(slides, str) and ";" in slides:
        slides = [x.strip() for x in slides.split(";") if x.strip()]
    if isinstance(slides, str):
        ps = Path(caminho(slides))
        arquivos = sorted(str(x) for x in ps.iterdir() if x.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")) if ps.is_dir() else [str(ps)]
    else:
        arquivos = [str(Path(caminho(x))) for x in slides]
    if not arquivos:
        raise ErroFerramenta("Nenhum slide para animar.")
    W, H = {"4x5": (1080, 1350), "9x16": (1080, 1920), "1x1": (1080, 1080)}.get(formato, (1080, 1350))
    n = len(arquivos); frames = int(duracao_slide_s * fps); cmd = [FFMPEG, "-y", "-hide_banner", "-nostats"]
    for a in arquivos:
        cmd += ["-framerate", str(fps), "-i", a]  # um quadro por imagem; o zoompan gera os `frames` quadros do slide
    partes = []
    for i in range(n):
        z = f"'min(zoom+{(zoom - 1) / frames:.6f},{zoom})'"
        with Image.open(arquivos[i]) as im0:
            w0, h0 = im0.size
        if abs(w0 / h0 - W / H) < 0.08:  # mesma proporção: preenche
            base = f"[{i}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2}"
        else:  # proporção diferente: slide inteiro sobre ele mesmo desfocado (nada cortado)
            base = (f"[{i}:v]split=2[b{i}][f{i}];[b{i}]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},boxblur=40:2,eq=brightness=-0.2[bg{i}];"
                    f"[f{i}]scale={W * 2}:{H * 2}:force_original_aspect_ratio=decrease[fg{i}];[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2")
        partes.append(f"{base},zoompan=z={z}:d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},format=yuv420p,setsar=1[v{i}]")
    filtro = ";".join(partes)
    if n == 1:
        filtro += ";[v0]copy[v]"
    else:
        d = transicao_s if trans else 0.0
        prev = "v0"; off = duracao_slide_s - d
        for i in range(1, n):
            nome = f"x{i}" if i < n - 1 else "v"
            filtro += (f";[{prev}][v{i}]xfade=transition={trans}:duration={d}:offset={off:.3f}[{nome}]" if trans else f";[{prev}][v{i}]concat=n=2:v=1:a=0[{nome}]")
            prev = nome; off += duracao_slide_s - d
    out = caminho_saida(saida_video)
    total = n * duracao_slide_s - (n - 1) * (transicao_s if trans else 0.0)
    if audio:
        cmd += ["-i", str(caminho(audio))]
        extra = ["-map", f"{n}:a", "-c:a", "aac", "-b:a", "160k", "-af", f"afade=t=out:st={max(0, total - 1.2):.3f}:d=1.2", "-t", f"{total:.3f}"]
    else:
        extra = []
    subprocess.run(cmd + ["-filter_complex", filtro, "-map", "[v]", *extra, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True, capture_output=True)
    from .util import info_midia
    return {"video": str(out), "n_slides": n, "duracao_s": info_midia(out)["duracao_s"], "largura": W, "altura": H, "transicao": trans or "corte", "audio": str(caminho(audio)) if audio else None}
