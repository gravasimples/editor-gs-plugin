"""Nível profissional do acabamento (02/11/2026): regras sem modelo de linguagem que escolhem o que aparece na tela e quando.
- palavras_chave_auto: palavras da fala que merecem destaque animado (números, recursos do OBS, palavras de dor/benefício), no máximo uma
  por frase e com intervalo mínimo entre elas; tempos vêm do palavras.json do vídeo cortado.
- sfx_auto: efeitos sonoros discretos (whoosh em corte, pop em palavra-chave, ding na tela final; desde 10/11/2026 também swipe na cortina,
  tick no capítulo, erro/riser/impacto por tipo de grafismo), com variações CC0 sorteadas pelo instante a partir de remotion/public/sfx/catalogo.json.
- capitulos_de / broll_de: aceitam JSON ou a forma curta "texto@segundos; texto@segundos"."""
import json, re, unicodedata
from pathlib import Path

LISTA_PADRAO = ["obs", "obs studio", "webcam", "câmera", "camera", "microfone", "mic", "áudio", "audio", "preset", "presets", "cena", "cenas", "filtro", "live", "lives", "aula", "aulas",
                "gravar", "gravação", "meet", "zoom", "tela", "luz", "iluminação", "cenário", "tripé", "celular", "notebook", "grátis", "gratuito", "de graça", "erro", "erros", "travando", "travou",
                "eco", "ruído", "chroma", "fundo", "qualidade", "profissional", "simples", "rápido", "segredo", "dica", "cuidado", "nunca", "sempre", "pronto"]
NUMERO = re.compile(r"^\d+([.,]\d+)?%?$|^(dois|duas|três|tres|quatro|cinco|seis|sete|oito|nove|dez|vinte|trinta|cem|mil)$", re.I)  # "um/uma" quase sempre é artigo ("um slide"): fora (GRA-45)


def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower()); return "".join(c for c in t if not unicodedata.combining(c)).strip(".,;:!?\"'()")


def palavras_chave_auto(palavras: dict, lista=None, max_por_min: int = 10, intervalo_min_s: float = 2.5, extra_s: float = 0.9, max_total: int = 40):
    """Escolhe palavras-chave a partir de `palavras.json` (segmentos com palavras ou lista plana de palavras). Devolve
    [{texto, inicio, fim}] em ordem; o texto é a palavra como foi dita (até 2 palavras quando a lista tem termo composto)."""
    lista = [(_norm(x), x) for x in (lista or LISTA_PADRAO)]
    normas = {n: o for n, o in lista}
    compostos = {n for n in normas if " " in n}
    itens = palavras.get("palavras") or [w for s in palavras.get("segmentos", []) for w in (s.get("palavras") or [])]
    segs = palavras.get("segmentos") or []
    def seg_de(t):
        for i, s in enumerate(segs):
            if s.get("inicio", 0) <= t <= s.get("fim", 0) + 0.05:
                return i
        return -1
    out = []; ultimo = -1e9; usados_seg = set()
    for i, w in enumerate(itens):
        txt = w.get("palavra") or w.get("texto") or ""; n = _norm(txt); ini = float(w.get("inicio", 0)); fim = float(w.get("fim", ini))
        if not n or ini - ultimo < intervalo_min_s:
            continue
        escolhido = None
        if i + 1 < len(itens):
            n2 = n + " " + _norm(itens[i + 1].get("palavra") or itens[i + 1].get("texto") or "")
            if n2 in compostos:
                escolhido = txt.strip(".,;:!?") + " " + (itens[i + 1].get("palavra") or itens[i + 1].get("texto") or "").strip(".,;:!?"); fim = float(itens[i + 1].get("fim", fim))
        if not escolhido and (n in normas or NUMERO.match(n)):
            escolhido = txt.strip(".,;:!?")
        if not escolhido:
            continue
        si = seg_de(ini)
        if si >= 0 and si in usados_seg:
            continue
        out.append({"texto": escolhido.upper() if len(escolhido) <= 3 else escolhido, "inicio": round(ini, 2), "fim": round(fim + extra_s, 2)})
        ultimo = ini; usados_seg.add(si)
        if len(out) >= max_total:
            break
    dur = float(palavras.get("duracao_s") or (itens[-1].get("fim", 0) if itens else 0) or 0)
    teto = max(4, int(max_por_min * max(dur, 6) / 60))  # vídeo curto ainda pode ter até 4
    if len(out) > teto:  # mantém os mais espalhados no tempo
        passo = len(out) / teto; out = [out[int(k * passo)] for k in range(teto)]
    for k in range(len(out) - 1):  # uma não atropela a seguinte
        out[k]["fim"] = min(out[k]["fim"], out[k + 1]["inicio"] - 0.15)
    return out


# Pacote de SFX CC0 (10/11/2026): remotion/public/sfx/catalogo.json lista as variações de cada categoria (origem e licença em LICENCA.md).
SFX_DIR = Path(__file__).resolve().parents[3] / "remotion" / "public" / "sfx"
CATEGORIAS_SFX = ("whoosh", "pop", "ding", "riser", "impacto", "swipe", "tick", "erro")
# grafismo por tipo → categoria de som (o resto dos tipos recebe pop, como a palavra-chave); "serie" nunca tem som
SFX_POR_GRAFISMO = {"riscado": "erro", "manchete": "riser", "numero": "impacto", "cta": "ding"}
ANTECIPA_S = {"riser": 0.6, "whoosh": 0.05, "swipe": 0.1, "ding": 0.2}  # quanto antes do evento o som entra
_CATALOGO = {}


def catalogo_sfx(pasta=None):
    """{categoria: [arquivos]} de catalogo.json (cache por pasta). Pasta sem catálogo → {} (nenhum som; a montagem segue sem efeito)."""
    p = Path(pasta) if pasta else SFX_DIR
    arq = p / "catalogo.json"
    try:
        chave = (str(p), arq.stat().st_mtime_ns)
    except OSError:
        chave = (str(p), None)
    if chave not in _CATALOGO:
        try:
            dados = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
        except (OSError, ValueError):
            dados = {}
        _CATALOGO[chave] = {k: [a for a in v if (p / a).exists()] for k, v in dados.items() if isinstance(v, list)}
    return _CATALOGO[chave]


def escolher_sfx(categoria, instante, catalogo=None):
    """Variação da categoria sorteada de forma determinística pelo instante (mesmo vídeo → mesma edição). None quando a categoria não tem som."""
    import zlib
    cat = catalogo if catalogo is not None else catalogo_sfx()
    lst = cat.get(categoria) or []
    if not lst:
        return None
    return lst[zlib.crc32(f"{categoria}:{float(instante):.2f}".encode()) % len(lst)]


def sfx_auto(cortes_s, palavras_chave, tela_final_inicio_s=None, v_corte=0.28, v_pop=0.3, v_final=0.35, min_gap_s=0.8,
             cortinas_s=None, capitulos=None, grafismos=None, v_extra=0.26, catalogo=None):
    """Efeitos sonoros discretos por evento: whoosh no corte, pop na palavra-chave, ding na tela final e, desde 10/11/2026, swipe na cortina
    de layout, tick no capítulo e, por tipo de grafismo, erro no `riscado`, riser antes da `manchete`, impacto no `numero`, ding no `cta`
    (demais tipos: pop). Cada categoria sorteia a variação pelo instante (escolher_sfx); categoria sem som no catálogo não gera entrada.
    Mesma categoria respeita min_gap_s. Devolve [{arquivo, inicio, volume, categoria}] em ordem."""
    cat = catalogo if catalogo is not None else catalogo_sfx()
    out = []; ult = {}

    def por(categoria, t, volume, gap=min_gap_s):
        arq = escolher_sfx(categoria, t, cat)
        if arq is None or t - ult.get(categoria, -1e9) < gap:
            return
        out.append({"arquivo": arq, "inicio": round(max(0.0, float(t) - ANTECIPA_S.get(categoria, 0.0)), 2), "volume": volume, "categoria": categoria}); ult[categoria] = t
    for c in sorted(float(x) for x in (cortes_s or [])):
        if c > 0.3:
            por("whoosh", c, v_corte)
    for c in sorted(float(x) for x in (cortinas_s or [])):
        if c > 0.3:
            por("swipe", c, v_extra)
    for k in sorted((palavras_chave or []), key=lambda k: float(k["inicio"])):
        por("pop", float(k["inicio"]), v_pop, gap=0.0)
    for c in sorted((capitulos or []), key=lambda c: float(c["inicio"])):
        por("tick", float(c["inicio"]), v_extra, gap=0.0)
    for g in sorted((grafismos or []), key=lambda g: float(g["inicio"])):
        tipo = str(g.get("tipo", ""))
        if tipo == "serie":
            continue
        por(SFX_POR_GRAFISMO.get(tipo, "pop"), float(g["inicio"]), v_extra if tipo in SFX_POR_GRAFISMO else v_pop, gap=0.0)
    if tela_final_inicio_s is not None:
        por("ding", float(tela_final_inicio_s), v_final, gap=0.0)
    return sorted(out, key=lambda e: e["inicio"])


def _lista(texto):
    if not texto:
        return []
    if isinstance(texto, list):
        return texto
    t = str(texto).strip()
    if t.startswith("["):
        return json.loads(t)
    out = []
    for parte in re.split(r"\s*;\s*", t):
        if "@" in parte:
            a, b = parte.rsplit("@", 1); out.append({"texto": a.strip(), "inicio": float(b.strip().replace(",", "."))})
    return out


def capitulos_de(texto):
    """'Áudio@0; Luz@12.5; Câmera@30' ou JSON [{texto, inicio, numero?, total?}] → lista com numero/total preenchidos."""
    lst = [dict(c) for c in _lista(texto) if c.get("texto") is not None]
    for i, c in enumerate(lst):
        c.setdefault("numero", i + 1); c.setdefault("total", len(lst)); c["inicio"] = float(c.get("inicio", 0))
    return lst


def broll_de(texto):
    """'materiais/print-obs.png@8@3' (arquivo@inicio@duracao) ou JSON [{arquivo, inicio, duracao_s, modo}] → lista normalizada."""
    if not texto:
        return []
    if isinstance(texto, list):
        raw = texto
    else:
        t = str(texto).strip()
        if t.startswith("["):
            raw = json.loads(t)
        else:
            raw = []
            for parte in re.split(r"\s*;\s*", t):
                bits = parte.split("@")
                if len(bits) >= 2:
                    raw.append({"arquivo": bits[0].strip(), "inicio": float(bits[1].replace(",", ".")), "duracao_s": float(bits[2].replace(",", ".")) if len(bits) > 2 else 3.0, "modo": bits[3].strip() if len(bits) > 3 else "janela"})
    out = []
    for b in raw:
        if not b.get("arquivo"):
            continue
        out.append({"arquivo": b["arquivo"], "inicio": float(b.get("inicio", 0)), "duracao_s": max(0.8, float(b.get("duracao_s", 3.0))), "modo": b.get("modo") if b.get("modo") in ("cheio", "janela") else "janela"})
    return out


EXTS_TRILHA = (".mp3", ".m4a", ".wav", ".ogg", ".flac")


def escolher_trilha(pasta):
    """Fase 2 (03/11/2026): primeira trilha (ordem alfabética) de `trilhas/`. None = pasta vazia: o vídeo sai só com a voz (nunca inventar arquivo)."""
    from pathlib import Path
    p = Path(pasta)
    if not p.is_dir():
        return None
    arqs = sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in EXTS_TRILHA)
    return arqs[0] if arqs else None


def broll_auto(amostras, palavras_chave=None, duracao_s=None, max_n=3, dur_b=2.5, inicio_min_s=3.0, folga_final_s=3.5, intervalo_min_s=8.0, margem_tela_s=1.5, min_amostras_tela=2):
    """Fase 2 (03/11/2026): b-roll automático a partir do próprio vídeo. `amostras` = [(t, tem_rosto)] em passo fixo.
    Trechos sem rosto = câmera mostrando a tela (OBS, celular). Cada trecho de tela vira no máximo um cutaway em janela, colocado num momento
    em que o Thiago está falando para a câmera (de preferência numa palavra-chave), longe do gancho, da tela final e dos próprios trechos de tela.
    Trecho sem rosto com menos de min_amostras_tela amostras seguidas é tratado como falha do detector (mão na frente, desfoque), não como tela.
    Devolve [{fonte_t, inicio, duracao_s, modo}] (fonte_t = instante do quadro a extrair). Vídeo todo de rosto ou todo de tela → []."""
    am = sorted((float(t), bool(r)) for t, r in amostras)
    if not am or all(r for _, r in am) or not any(r for _, r in am):
        return []
    dur = float(duracao_s) if duracao_s else am[-1][0]
    runs, atual = [], []
    for t, r in am:
        if not r:
            atual.append(t)
        elif atual:
            runs.append(atual); atual = []
    if atual:
        runs.append(atual)
    runs = [r for r in runs if len(r) >= min_amostras_tela]
    if not runs:
        return []
    runs.sort(key=len, reverse=True)  # trechos de tela mais longos primeiro (quadro mais estável)
    fontes = [r[len(r) // 2] for r in runs[:max_n]]
    def livre(t):
        if t < inicio_min_s or t + dur_b > dur - folga_final_s:
            return False
        if any(r[0] - margem_tela_s - dur_b <= t <= r[-1] + margem_tela_s for r in runs):
            return False
        dentro = [r for tt, r in am if t - 0.01 <= tt <= t + dur_b]
        return bool(dentro) and all(dentro)  # o Thiago fala para a câmera durante todo o cutaway
    cands = [float(k["inicio"]) for k in (palavras_chave or [])] + [t for t, r in am if r]
    out = []
    for fonte in fontes:
        for c in sorted(cands, key=lambda c: (c not in [float(k["inicio"]) for k in (palavras_chave or [])], abs(c - fonte))):
            if livre(c) and all(abs(c - o["inicio"]) >= intervalo_min_s for o in out):
                out.append({"fonte_t": round(fonte, 2), "inicio": round(c, 2), "duracao_s": dur_b, "modo": "janela"}); break
    return sorted(out, key=lambda b: b["inicio"])


ORDINAIS = {"primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2, "terceiro": 3, "terceira": 3, "quarto": 4, "quarta": 4, "quinto": 5, "quinta": 5,
            "sexto": 6, "sexta": 6, "setimo": 7, "setima": 7, "oitavo": 8, "oitava": 8, "nono": 9, "nona": 9, "decimo": 10, "decima": 10}
CARDINAIS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}
ROTULOS_LISTA = {"passo", "erro", "dica", "ponto", "item", "motivo", "regra", "segredo", "truque", "configuracao", "coisa", "etapa", "forma", "jeito", "ferramenta"}
VAZIAS = {"e", "o", "a", "os", "as", "que", "de", "do", "da", "dos", "das", "um", "uma", "eu", "voce", "ce", "ta", "e", "aqui", "ai", "entao", "lugar", "vai", "ser", "eh",
          "isso", "esse", "essa", "pra", "para", "com", "no", "na", "em", "se", "tem", "ele", "ela", "mais", "muito", "ja", "so", "agora", "gente", "galera", "olha", "cara"}


def capitulos_auto(palavras, max_rotulo=2):
    """Fase 2 de formatos (03/11/2026): capítulos de uma lista tirados da fala, sem modelo. Marca quando aparece "primeiro/segundo…",
    "passo/erro/dica 1, 2…" ou "número três", na ordem 1, 2, 3 (sequência quebrada = não é lista). Rótulo = 1–2 palavras de conteúdo depois do marcador.
    Menos de 2 itens → [] (não inventa capítulo)."""
    ws = palavras.get("palavras", []) if isinstance(palavras, dict) else palavras
    if ws and "palavras" in ws[0]:  # segmentos com palavras
        ws = [w for s in ws for w in s["palavras"]]
    toks = [(_norm(w.get("palavra") or w.get("word") or ""), float(w["inicio"])) for w in ws]
    achados, esperado = [], 1
    for i, (t, ini) in enumerate(toks):
        num = None; prox = i + 1
        if t in ORDINAIS:
            num = ORDINAIS[t]
            if prox < len(toks) and toks[prox][0] in ROTULOS_LISTA:
                prox += 1
        elif t in ROTULOS_LISTA or t == "numero":
            if prox < len(toks):
                n2 = toks[prox][0]
                num = int(n2) if n2.isdigit() else CARDINAIS.get(n2)
                prox += 1 if num else 0
        if num != esperado:
            continue
        rot, conteudo = [], 0  # do 1º ao último termo de conteúdo, mantendo a ligação no meio ("luz de chapa")
        for k in range(prox, min(prox + 6, len(toks))):
            t2 = toks[k][0]
            if t2 and t2 not in VAZIAS and not t2.isdigit():
                rot.append(k); conteudo += 1
            elif rot and t2 in ("de", "do", "da", "no", "na", "com"):
                rot.append(k)
            if conteudo >= max_rotulo:
                break
        while rot and toks[rot[-1]][0] in VAZIAS:
            rot.pop()
        texto = " ".join((ws[k].get("palavra") or "").strip(".,;:!?\"'") for k in rot).strip() or f"Item {num}"
        achados.append({"texto": texto[:1].upper() + texto[1:], "inicio": max(0.0, round(ini - 0.1, 2)), "numero": num}); esperado += 1
    if len(achados) < 2:
        return []
    for c in achados:
        c["total"] = len(achados)
    return achados
