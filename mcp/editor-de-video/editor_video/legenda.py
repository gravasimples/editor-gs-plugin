import re
from .util import ler_json, caminho, caminho_saida, hex_para_ass, ErroFerramenta

RES = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}
MAX_CHARS = {"9x16": 22, "16x9": 38, "1x1": 26}  # caracteres por linha quando a legenda vem por bloco (SRT), não por palavra


def _linhas(palavras, max_palavras=4, max_chars=22, max_gap_s=0.6, max_dur_s=2.5):
    linhas, atual = [], []
    for p in palavras:
        if atual:
            chars = len(" ".join(x["palavra"] for x in atual + [p]))
            if (len(atual) >= max_palavras or chars > max_chars or p["inicio"] - atual[-1]["fim"] > max_gap_s
                    or p["fim"] - atual[0]["inicio"] > max_dur_s):
                linhas.append(atual); atual = []
        atual.append(p)
    if atual:
        linhas.append(atual)
    return linhas


def _t(seg):
    h = int(seg // 3600); m = int(seg % 3600 // 60); s = seg % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _estilo_ass(leg, formato="9x16", karaoke=None):
    """Cabeçalho ASS (script + estilo 'Legenda') a partir do bloco `legenda` de um estilo. Devolve (cabeçalho, info)."""
    W, H = RES.get(formato, RES["9x16"])
    tamanho = leg.get("tamanho_9x16" if formato == "9x16" else "tamanho_16x9", 64)
    fonte = leg.get("fonte", "Inter"); peso = leg.get("peso", "ExtraBold")
    nome_fonte = fonte if peso.lower() in ("regular", "normal", "") else f"{fonte} {peso}" if fonte == "Inter" else fonte
    bold = -1 if peso.lower() in ("bold", "extrabold", "black", "semibold") else 0
    if karaoke is None:
        karaoke = leg.get("modo", "karaoke") == "karaoke"
    cor_texto, cor_dest, contorno = leg.get("cor_texto", "#FFFFFF"), leg.get("cor_destaque", "#F79615"), leg.get("contorno", "#000921")
    posicao = leg.get("posicao", "baixa")
    if leg.get("altura_pct") is not None:  # altura livre na tela (% a partir de baixo), como o "altura na tela" do Máquina
        align, margem_v = 2, int(H * max(2.0, min(90.0, float(leg["altura_pct"]))) / 100)
    elif posicao == "alta":
        align, margem_v = 8, int(H * 0.22)
    elif posicao == "centro":
        align, margem_v = 5, 0
    else:
        align, margem_v = 2, int(H * 0.12)
    primaria = hex_para_ass(cor_dest if karaoke else cor_texto); secundaria = hex_para_ass(cor_texto)
    # biblioteca de legendas (03/11/2026): espessura de contorno e sombra, caixa de fundo (BorderStyle 3), espaçamento entre letras
    contorno_px = int(leg["contorno_px"]) if leg.get("contorno_px") is not None else max(2, tamanho // 14)
    sombra_px = int(leg["sombra_px"]) if leg.get("sombra_px") is not None else max(1, tamanho // 30)
    borda, cor_borda, cor_sombra = 1, hex_para_ass(contorno), hex_para_ass(contorno, '80')
    if leg.get("caixa"):
        borda = 3; cor_caixa = leg.get("cor_caixa", contorno)
        cor_borda = cor_sombra = hex_para_ass(cor_caixa, leg.get("caixa_alpha", "30"))
        contorno_px = int(leg.get("caixa_margem", max(8, tamanho // 5))); sombra_px = 0
    espaco = int(leg.get("espacamento", 0))
    pos = {2: (W // 2, H - margem_v), 8: (W // 2, margem_v), 5: (W // 2, H // 2)}[align]
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,{nome_fonte},{tamanho},{primaria},{secundaria},{cor_borda},{cor_sombra},{bold},0,0,0,100,100,{espaco},0,{borda},{contorno_px},{sombra_px},{align},60,60,{margem_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    info = {"W": W, "H": H, "karaoke": karaoke, "animacao": leg.get("animacao", "nenhuma"), "maius": leg.get("maiusculas", False),
            "nome_fonte": nome_fonte, "cor_texto": cor_texto, "cor_dest": cor_dest, "pos": pos, "align": align}
    return cab, info


def gerar_legenda(palavras_json, saida_ass, estilo, formato="9x16", saida_srt=None, max_palavras=None):
    d = ler_json(palavras_json); palavras = d["palavras"]
    if not palavras:
        raise ErroFerramenta("Sem palavras para legendar.")
    leg = estilo.get("legenda", estilo)
    cab, info = _estilo_ass(leg, formato)
    karaoke, maius, animacao = info["karaoke"], info["maius"], info["animacao"]  # animacao: nenhuma | pop | salto | subir | aparecer | zoom | digitar
    mp = max_palavras or leg.get("palavras_por_linha_max", 4)
    eventos = []
    import pysubs2
    subs = pysubs2.SSAFile()
    linhas = list(_linhas(palavras, max_palavras=mp))
    for k, linha in enumerate(linhas):
        ini = linha[0]["inicio"]; fim = linha[-1]["fim"] + 0.12
        if k + 1 < len(linhas):  # a cauda de 0,12 s nunca invade a linha seguinte (na narração sintética as palavras são contíguas e as duas linhas apareciam juntas)
            fim = max(min(fim, linhas[k + 1][0]["inicio"] - 0.01), linha[-1]["fim"], ini + 0.05)
        partes = []
        for i, p in enumerate(linha):
            prox = linha[i + 1]["inicio"] if i + 1 < len(linha) else linha[-1]["fim"]
            dur_cs = max(1, int(round((prox - p["inicio"]) * 100)))
            txt = p["palavra"].upper() if maius else p["palavra"]
            tags = f"\\k{dur_cs}" if karaoke else ""
            if animacao in ("pop", "salto"):
                t0 = int(round((p["inicio"] - ini) * 1000)); t1 = t0 + 110; t2 = t0 + 230
                if animacao == "pop":
                    tags += f"\\fscx100\\fscy100\\t({t0},{t1},\\fscx118\\fscy118)\\t({t1},{t2},\\fscx100\\fscy100)"
                else:
                    tags += f"\\fscx100\\fscy100\\t({t0},{t1},\\fscy122)\\t({t1},{t2},\\fscy100)"
            elif animacao == "digitar":  # a palavra só aparece quando é falada
                t0 = int(round((p["inicio"] - ini) * 1000))
                tags += f"\\alpha&HFF&\\t({t0},{t0 + 1},\\alpha&H00&)" if t0 > 0 else ""
            partes.append(f"{{{tags}}}{txt}" if tags else txt)
        texto = _entrada_linha(animacao, info) + " ".join(partes)
        eventos.append(f"Dialogue: 0,{_t(ini)},{_t(fim)},Legenda,,0,0,0,,{texto}")
        subs.append(pysubs2.SSAEvent(start=int(ini * 1000), end=int(fim * 1000), text=" ".join(p["palavra"] for p in linha)))
    out = caminho_saida(saida_ass)
    out.write_text(cab + "\n".join(eventos) + "\n", encoding="utf-8")
    srt = None
    if saida_srt:
        srt = str(caminho_saida(saida_srt)); subs.save(srt)
    return {"ass": str(out), "srt": srt, "n_linhas": len(eventos), "formato": formato, "fonte": info["nome_fonte"], "karaoke": karaoke, "animacao": animacao}


def _entrada_linha(animacao, info):
    """Animação de entrada da linha inteira (subir, aparecer, zoom); vazio para as animações por palavra."""
    x, y = info["pos"]
    if animacao == "subir":
        return f"{{\\an{info['align']}\\move({x},{y + 42},{x},{y},0,180)\\fad(140,60)}}"
    if animacao == "aparecer":
        return "{\\fad(180,100)}"
    if animacao == "zoom":
        return "{\\fscx72\\fscy72\\t(0,160,\\fscx100\\fscy100)\\fad(90,40)}"
    return ""


def _quebrar(texto, max_chars):
    """Quebra um bloco em até duas linhas equilibradas, sem cortar palavra. Linha única quando cabe."""
    palavras = texto.split()
    if len(texto) <= max_chars or len(palavras) < 2:
        return [texto]
    melhor = None
    for i in range(1, len(palavras)):
        a, b = " ".join(palavras[:i]), " ".join(palavras[i:])
        custo = max(len(a), len(b)) + abs(len(a) - len(b)) * 0.25
        if melhor is None or custo < melhor[0]:
            melhor = (custo, a, b)
    return [melhor[1], melhor[2]]


_MARCA = re.compile(r"\*+([^*]+?)\*+")


def legenda_de_srt(srt, saida_ass, estilo, formato="9x16", max_chars=None):
    """Legenda ASS no estilo da marca a partir de um SRT já traduzido ou revisado: um evento por bloco, sem karaokê
    (o SRT não tem tempo por palavra). `*palavra*` no SRT vira destaque na cor do estilo. Quebra em até duas linhas por bloco;
    bloco que não cabe nem em duas linhas é contado em `blocos_longos` para o Editor dividir o SRT."""
    import pysubs2
    p = caminho(srt)
    try:
        subs = pysubs2.load(str(p), encoding="utf-8")
    except Exception as e:
        raise ErroFerramenta(f"SRT inválido ({p.name}): {e}")
    blocos = [e for e in subs if not e.is_comment and e.plaintext.strip()]
    if not blocos:
        raise ErroFerramenta("SRT sem blocos de texto.")
    leg = estilo.get("legenda", estilo)
    cab, info = _estilo_ass(leg, formato, karaoke=False)
    mc = int(max_chars or leg.get(f"max_chars_{formato}") or MAX_CHARS.get(formato, 22))
    dest, normal = hex_para_ass(info["cor_dest"]), hex_para_ass(info["cor_texto"])
    anim = {"pop": "{\\fscx100\\fscy100\\t(0,110,\\fscx118\\fscy118)\\t(110,230,\\fscx100\\fscy100)}",
            "salto": "{\\fscx100\\fscy100\\t(0,110,\\fscy122)\\t(110,230,\\fscy100)}"}.get(info["animacao"], "") or _entrada_linha("aparecer" if info["animacao"] == "digitar" else info["animacao"], info)
    eventos, longos, destaques = [], 0, 0
    for e in blocos:
        txt = re.sub(r"\s+", " ", e.plaintext.replace("\n", " ")).strip()
        if info["maius"]:
            txt = txt.upper()
        linhas = _quebrar(txt, mc)
        if any(len(_MARCA.sub(r"\1", l)) > mc for l in linhas):
            longos += 1
        partes = []
        for l in linhas:
            destaques += len(_MARCA.findall(l))
            partes.append(_MARCA.sub(lambda m: f"{{\\c{dest}}}{m.group(1)}{{\\c{normal}}}", l))
        texto = "\\N".join(partes)
        eventos.append(f"Dialogue: 0,{_t(e.start / 1000)},{_t(e.end / 1000)},Legenda,,0,0,0,,{anim}{texto}")
    out = caminho_saida(saida_ass)
    out.write_text(cab + "\n".join(eventos) + "\n", encoding="utf-8")
    return {"ass": str(out), "n_blocos": len(eventos), "blocos_longos": longos, "destaques": destaques, "max_chars": mc, "formato": formato,
            "fonte": info["nome_fonte"], "karaoke": False, "animacao": info["animacao"], "duracao_s": round(blocos[-1].end / 1000, 2)}
