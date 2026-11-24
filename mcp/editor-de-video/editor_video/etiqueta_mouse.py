"""Lacuna 8 dos Criativos do Máquina (16/11/2026): etiqueta do passo junto do mouse na gravação de tela (tutorial, tela, aula).
Um balão curto ("Clique no maisinho", "Vá em Ferramentas") nasce com pop ao lado da ponta do cursor, acompanha o cursor enquanto ele anda e sai suave.

Posição do cursor: o projeto não guarda rastro do mouse (o OBS não grava e `focos_auto` descarta de propósito a mudança minúscula do cursor andando).
Por isso a posição vem de uma detecção leve, sem modelo: diferença de 3 quadros seguidos (o que mudou de f0 para f1 E de f1 para f2 é o que está em f1
e saiu de lá), em 10 quadros/s a 640 px; manchas pequenas e compactas (do tamanho de um cursor) fora da região que muda o tempo todo (webcam da prévia do OBS,
vídeo tocando). A ponta da seta é o canto de cima à esquerda da mancha. Cursor parado = vale a última posição vista. Sem cursor achado, a etiqueta ancora no
centro do foco ativo (`layouts.focos_auto`, que acha o clique pela mudança localizada); sem foco também, ela não entra (aviso).

Texto: do pedido do agente ou, em "auto", da fala: verbo de ação dito ao espectador ("você vai clicar nesse maisinho" → "Clique no maisinho"), no máximo
4 palavras. Fala sem verbo de ação não ganha etiqueta (uma por foco seria ruído, o mesmo erro dos 71 focos do item 4).
Limites: só em bloco de tela, 3 s entre etiquetas, no máximo 8 por minuto, nunca em cima de grafismo de leitura ou tela cheia; a janela de cada
etiqueta entra nas janelas de leitura (`transicoes.limitar_efeitos`: sem tremor enquanto ela está na tela). O balão fica sempre de um lado da ponta
(acima à direita; perto da borda vira), nunca em cima do ponto clicado."""
import json, re, subprocess
import numpy as np
from .util import FFMPEG, ErroFerramenta, caminho, info_midia

MAX_PALAVRAS = 4
MAX_CHARS = 26
DUR_S = 2.4           # tempo na tela (pop 0,35 s + leitura + saída 0,3 s)
GAP_S = 3.0           # entre uma etiqueta e a próxima (o mesmo respiro da câmera na tela, layouts.POSICAO_MIN_S)
POR_MIN = 8
FPS_CURSOR = 10
LARG_CURSOR = 640
ANTES_S = 1.2         # o cursor costuma chegar ao botão pouco antes de a fala dizer "clica"
VIVO_FRAC = 0.35      # pixel que muda em mais de 35% dos quadros da janela não é cursor (webcam, vídeo tocando)
VEL_MAX = 2.5         # fração da tela por segundo: mais rápido que isso não é o cursor seguido
BRANCO = 215          # a seta do Windows é branca com borda preta: a mancha precisa ter miolo branco (medidor de áudio verde e rosto não têm)
FOCO_PERTO_S = 1.5
FRESCO_S = 0.8        # posição do cursor vista há mais que isso antes do verbo já não vale (ele pode ter andado sem ser visto)
MARGEM_X, MARGEM_Y = 0.74, 0.16   # passou disso, o balão vira para a esquerda / para baixo

# verbo falado → imperativo curto na etiqueta
VERBOS = {
    "clicar": "Clique", "clica": "Clique", "clique": "Clique", "clicando": "Clique",
    "abrir": "Abra", "abre": "Abra", "abra": "Abra",
    "selecionar": "Selecione", "seleciona": "Selecione", "selecione": "Selecione",
    "escolher": "Escolha", "escolhe": "Escolha", "escolha": "Escolha",
    "marcar": "Marque", "marca": "Marque", "marque": "Marque",
    "arrastar": "Arraste", "arrasta": "Arraste", "arraste": "Arraste",
    "digitar": "Digite", "digita": "Digite", "digite": "Digite",
    "apertar": "Aperte", "aperta": "Aperte", "aperte": "Aperte",
    "copiar": "Copie", "copia": "Copie", "copie": "Copie",
    "colar": "Cole", "cola": "Cole", "cole": "Cole",
    "ativar": "Ative", "ativa": "Ative", "ative": "Ative",
    "desativar": "Desative", "desmarcar": "Desmarque",
    "fechar": "Feche", "fecha": "Feche", "feche": "Feche",
    "voltar": "Volte", "volta": "Volte", "volte": "Volte",
    "baixar": "Baixe", "baixa": "Baixe", "baixe": "Baixe",
    "salvar": "Salve", "salva": "Salve", "salve": "Salve",
    "entrar": "Entre", "entra": "Entre", "entre": "Entre",
    "va": "Vá", "vai": "Vá", "vao": "Vá", "ir": "Vá",
}
SO_COM_VOCE = {"vai", "vao", "va", "entre", "volta", "cola", "marca", "baixa", "salva", "entra", "fecha", "copia", "aperta", "ativa", "abre", "escolhe", "clica"}
PESSOA = {"voce", "voces", "cê", "ce", "a gente", "tu"}
PREPOS = {"em": "em", "no": "no", "na": "na", "nos": "nos", "nas": "nas", "nesse": "no", "nessa": "na", "neste": "no", "nesta": "na", "nisso": "nisso",
          "pro": "pro", "pra": "pra", "para": "pra", "pros": "pros", "pras": "pras", "com": "com", "o": "o", "a": "a", "os": "os", "as": "as", "de": "de", "do": "do", "da": "da"}
ARTIGOS = {"o", "a", "os", "as"}
# palavra que encerra a instrução (sujeito, negação, outro verbo): "escolher o que eu fiz", "arrastar pra ficar embaixo"
PARA = {"eu", "nem", "nao", "quando", "se", "porque", "mas", "gente", "qualquer", "nele", "nela", "neles", "nelas", "dele", "dela", "fiz", "tenho", "quero",
        "preciso", "dar", "vai", "vou", "tem", "estou", "esta", "sua", "seu", "minha", "meu"}
NOMES_EM_AR = {"celular", "lugar", "bar", "radar", "familiar", "popular", "regular", "similar", "modular", "player"}
ENCHIMENTO = {"aqui", "ai", "ali", "la", "ó", "o'", "oh", "ta", "bom", "ok", "entao", "agora", "cima", "baixo", "embaixo", "lado", "direto", "tambem", "so",
              "esse", "essa", "este", "esta", "isso", "isto", "um", "uma", "ele", "ela", "e", "que", "vou", "vamos", "pode", "voce", "voces", "beleza",
              "perfeito", "certo", "tipo", "assim", "mesmo", "depois", "primeiro"}
MINUSCULAS = {"em", "no", "na", "nos", "nas", "pro", "pra", "pros", "pras", "com", "de", "do", "da", "o", "a", "os", "as", "e", "nisso"}


def _norm(t):
    from .grafismos import _norm as n
    return n(t)


def _fecha_frase(p):
    return bool(re.search(r"[.,;:!?…]$", str(p).strip()))


# ---------- texto ----------
def frase_de_acao(ws, k):
    """Se ws[k] é um verbo de ação dito ao espectador, devolve a etiqueta curta ("Clique no maisinho"); senão None.
    ws = palavras planas [{p, i, f}] (grafismos.palavras_planas)."""
    w = _norm(ws[k]["p"])
    if w not in VERBOS:
        return None
    ant = _norm(ws[k - 1]["p"]) if k > 0 else ""
    ant2 = _norm(ws[k - 2]["p"]) if k > 1 else ""
    if w in SO_COM_VOCE and ant not in PESSOA and ant2 not in PESSOA:
        return None  # "ele vai pra pasta", "a tela fecha": não é instrução
    verbo = VERBOS[w]; j = k + 1
    if w in ("vai", "vao", "va", "ir") and j < len(ws) and _norm(ws[j]["p"]) in VERBOS and _norm(ws[j]["p"]) not in ("vai", "vao", "va", "ir"):
        verbo = VERBOS[_norm(ws[j]["p"])]; j += 1  # "vai clicar" → Clique
    if _fecha_frase(ws[j - 1]["p"]):
        return None if verbo == "Vá" else verbo
    prep, conteudo = None, []
    while j < len(ws) and j <= k + 9 and sum(1 for c in conteudo if _norm(c) not in ("de", "do", "da")) < 2:
        bruto = ws[j]["p"]; p = _norm(bruto)
        nome_de_botao = p in VERBOS and prep and not conteudo  # "clicar em abrir": o verbo depois de "em" é o nome do botão
        if p in VERBOS and p not in PREPOS and not nome_de_botao:
            break
        if p in PREPOS and not conteudo:
            if prep in ("em", "com") and p in ARTIGOS:  # "em o" → no; "com o" → com
                prep = {"o": "no", "a": "na", "os": "nos", "as": "nas"}[p] if prep == "em" else prep
            elif prep is None or p not in ARTIGOS:
                prep = PREPOS[p]  # "em cima, em ferramentas": vale a última
        elif p in PREPOS and conteudo:
            if PREPOS[p] in ("de", "do", "da"):
                conteudo.append(PREPOS[p])
            else:
                break
        elif not nome_de_botao and p in PARA or (not nome_de_botao and p not in NOMES_EM_AR and len(p) > 4 and (re.search(r"(ar|er|ir)$", p) or p.endswith("ndo"))):
            break  # outro verbo (infinitivo ou gerúndio) ou sujeito: a instrução acabou
        elif p and p not in ENCHIMENTO:
            conteudo.append(re.sub(r"[.,;:!?…\"']+$", "", bruto.strip()))
        if _fecha_frase(bruto) and conteudo:
            break
        j += 1
    while conteudo and _norm(conteudo[-1]) in ("de", "do", "da"):
        conteudo.pop()
    if not conteudo:
        return None if verbo == "Vá" else verbo
    if verbo == "Vá" and prep in (None, "o", "a", "os", "as"):
        prep = "em"
    if verbo in ("Clique", "Selecione", "Marque", "Aperte") and prep in ("o", "a", "os", "as"):
        prep = {"o": "no", "a": "na", "os": "nos", "as": "nas"}[prep]
    if 1 + bool(prep) + len(conteudo) > MAX_PALAVRAS and any(_norm(c) in ("de", "do", "da") for c in conteudo):
        k_de = max(i for i, c in enumerate(conteudo) if _norm(c) in ("de", "do", "da"))
        conteudo = conteudo[k_de + 1:] or conteudo  # "pasta de downloads" → Downloads
    partes = [verbo] + ([prep] if prep else []) + conteudo
    return curto(" ".join(partes))


def curto(texto):
    """No máximo 4 palavras e ~26 letras; substantivo com maiúscula ("Vá em Ferramentas"), preposição em minúscula."""
    ps = str(texto or "").split()[:MAX_PALAVRAS]
    while len(" ".join(ps)) > MAX_CHARS and len(ps) > 1:
        ps = ps[:-1]
    while len(ps) > 1 and _norm(ps[-1]) in MINUSCULAS:
        ps = ps[:-1]
    out = []
    for i, p in enumerate(ps):
        if i == 0 or (_norm(p) not in MINUSCULAS and p[:1].islower() and len(p) > 2):
            p = p[:1].upper() + p[1:]
        out.append(p)
    return " ".join(out)


def acoes_da_fala(pal):
    """[{inicio, texto, palavra}] das instruções faladas (verbo de ação dito ao espectador), na ordem do tempo."""
    from .grafismos import palavras_planas
    ws = palavras_planas(pal) if isinstance(pal, dict) else (pal or [])
    out = []
    for k in range(len(ws)):
        tx = frase_de_acao(ws, k)
        if tx and len(tx.split()) >= 2 and not (out and out[-1]["texto"] == tx and abs(ws[k]["i"] - out[-1]["inicio"]) < 2.0):  # "Clique" sozinho não ensina nada; "vai clicar" conta uma vez
            kv = k + 1 if _norm(ws[k]["p"]) in ("vai", "vao") and k + 1 < len(ws) and _norm(ws[k + 1]["p"]) in VERBOS else k  # "vai clicar": entra no "clicar"
            out.append({"inicio": round(ws[kv]["i"], 3), "texto": tx, "palavra": ws[kv]["p"]})
    return out


# ---------- cursor ----------
def _quadros_cinza(video, ini, dur, fps=FPS_CURSOR, largura=LARG_CURSOR):
    info = info_midia(caminho(video))
    H = int(round(info["altura"] * largura / info["largura"] / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-ss", f"{max(0.0, ini):.3f}", "-i", str(caminho(video)), "-t", f"{dur:.3f}",
           "-vf", f"fps={fps},scale={largura}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    n = largura * H; buf = r.stdout
    qs = [np.frombuffer(buf[i * n:(i + 1) * n], dtype=np.uint8).reshape(H, largura) for i in range(len(buf) // n)]
    return qs, largura, H


def rastro_cursor(video, ini, fim, fps=FPS_CURSOR, largura=LARG_CURSOR):
    """[(t, x, y)] da ponta do cursor (frações da tela) nos instantes em que ele andou, entre ini e fim. Detecção leve por diferença de 3 quadros.
    Lista vazia = cursor não visto (parado o tempo todo, ou tela sem cursor)."""
    import cv2
    qs, W, H = _quadros_cinza(video, ini, max(0.3, fim - ini), fps, largura)
    if len(qs) < 3:
        return []
    difs = [cv2.absdiff(b, a) > 24 for a, b in zip(qs, qs[1:])]
    vivo = (np.mean(difs, axis=0) > VIVO_FRAC) if len(difs) >= 6 else np.zeros((H, W), bool)  # muda o tempo todo: webcam, medidor de áudio, vídeo tocando
    vivo = cv2.dilate(vivo.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    a_max = (W / 640) ** 2 * 900; a_min = (W / 640) ** 2 * 6; lado_max = 46 * W / 640
    out, ultimo = [], None
    for i in range(1, len(qs) - 1):
        m = (difs[i - 1] & difs[i] & ~vivo).astype(np.uint8)
        n, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        f1 = qs[i]

        def seta(c):
            x, y, w, h, a = st[c]
            if not (a_min <= a <= a_max and w <= lado_max and h <= lado_max):
                return False
            claro = int(np.count_nonzero(f1[y:y + h, x:x + w] >= BRANCO)); escuro = int(np.count_nonzero(f1[y:y + h, x:x + w] <= 60))
            return claro >= 3 and escuro >= 2 and claro <= 0.75 * w * h
        cand = [st[c] for c in range(1, n) if seta(c)]
        grandes = sum(1 for c in range(1, n) if st[c][4] > a_max)
        if not cand or len(cand) > 3 or grandes > 2:  # nada pequeno, ou muita coisa mudando junto (rolagem, janela abrindo)
            continue
        if ultimo is not None and len(cand) > 1:
            cand.sort(key=lambda s: abs(s[0] / W - ultimo[0]) + abs(s[1] / H - ultimo[1]))
        else:
            cand.sort(key=lambda s: -s[4])
        x0, y0 = cand[0][0], cand[0][1]
        novo = (float(x0) / W, float(y0) / H)
        if out and ultimo is not None and max(abs(novo[0] - ultimo[0]), abs(novo[1] - ultimo[1])) > VEL_MAX * (ini + i / fps - out[-1][0]):
            continue  # salto impossível para a mão: outra coisa mudou (zoom da própria gravação, notificação)
        ultimo = novo
        out.append((round(ini + i / fps, 3), round(ultimo[0], 4), round(ultimo[1], 4)))
    return out


def _sem_saltos(rastro, janela_s=0.25, perto=0.1):
    """Tira do rastro a posição isolada (sem vizinha perto no tempo e no espaço): cursor andando dá várias detecções seguidas; um ponto só é outra coisa."""
    return [r for k, r in enumerate(rastro) if any(j != k and abs(q[0] - r[0]) <= janela_s and max(abs(q[1] - r[1]), abs(q[2] - r[2])) < perto
                                               for j, q in enumerate(rastro))]


def _foco_em(focos, t):
    ativo = [f for f in focos or [] if f["inicio"] <= t < f["fim"]]
    if ativo:
        return ativo[-1]
    perto = [f for f in focos or [] if f["inicio"] - FOCO_PERTO_S <= t <= f["fim"]]  # o foco que começa logo depois (o clique vem pouco depois da fala)
    return min(perto, key=lambda f: abs(f["inicio"] - t)) if perto else None


def lado_de(x, y):
    """Para onde o balão abre a partir da ponta: acima à direita por padrão; perto da borda direita vira para a esquerda, perto do topo vai para baixo
    (e mais afastado, para não cair na seta do cursor)."""
    return ("esq" if x > MARGEM_X else "dir"), ("baixo" if y < MARGEM_Y else "cima")


# ---------- normalização ----------
def separar_do_plano(plano):
    """Tira do plano de grafismos os itens `etiqueta_mouse` (eles vivem na camada da tela, não no quadro). Devolve (plano_sem_eles, etiquetas)."""
    if not plano or str(plano).strip().lower() == "auto":
        return plano, []
    if isinstance(plano, str) and not plano.strip().startswith(("{", "[")):
        from .util import ler_json
        dados = ler_json(plano)
    elif isinstance(plano, str):
        dados = json.loads(plano)
    else:
        dados = plano
    itens = dados.get("itens", []) if isinstance(dados, dict) else list(dados or [])
    etq = [dict(g) for g in itens if str(g.get("tipo", "")).strip().lower() == "etiqueta_mouse"]
    if not etq:
        return plano, []
    resto = [g for g in itens if str(g.get("tipo", "")).strip().lower() != "etiqueta_mouse"]
    return ({**dados, "itens": resto} if isinstance(dados, dict) else resto), etq


def etiquetas_de(etiquetas, pal=None, duracao_s=None, tela=None, focos=None, blocos=None, grafismos=None):
    """Normaliza as etiquetas do mouse: "auto" (instruções da fala), "Clique aqui@12; Abra Configurações@20" ou JSON [{texto, inicio|palavra, fim?, x?, y?}].
    Devolve (lista para o Remotion [{inicio, fim, texto, x, y, lado, vert, origem, rastro?}], resumo)."""
    from .grafismos import ancorar, palavras_planas
    from .layouts import PRECISA_TELA, _lista_texto
    from .transicoes import LEITURA
    ws = palavras_planas(pal) if isinstance(pal, dict) else []
    avisos = []
    if isinstance(etiquetas, str) and etiquetas.strip().lower() == "auto":
        brutos = acoes_da_fala(pal or {}); origem_txt = "fala"
    elif isinstance(etiquetas, str):
        s = etiquetas.strip()
        brutos = json.loads(s) if s.startswith("[") else [{"texto": p["_nome"], "inicio": p["inicio"]} for p in _lista_texto(s)]
        origem_txt = "agente"
    else:
        brutos = list(etiquetas or []); origem_txt = "agente"
    pedidos = []
    for e in brutos:
        texto = str(e.get("texto") or "").strip()
        if not texto:
            avisos.append("etiqueta sem texto: ignorada"); continue
        ini = e.get("inicio")
        if e.get("palavra") and ws and origem_txt == "agente":
            a = ancorar(e["palavra"], ws, float(ini) if ini is not None else None)
            if a is None:
                avisos.append(f"etiqueta '{texto}': palavra '{e['palavra']}' não foi dita perto de {ini}")
            ini = a if a is not None else ini
        if ini is None:
            avisos.append(f"etiqueta '{texto}' sem início: ignorada"); continue
        if len(texto.split()) > MAX_PALAVRAS or len(texto) > MAX_CHARS:
            avisos.append(f"etiqueta '{texto}': mais de {MAX_PALAVRAS} palavras; ficou '{curto(texto)}'")
        pedidos.append({**e, "texto": curto(texto), "inicio": float(ini)})
    pedidos.sort(key=lambda e: e["inicio"])
    na_tela = [(b["inicio"], b["fim"]) for b in blocos or [] if b.get("modo") in PRECISA_TELA] if blocos is not None else [(0.0, float(duracao_s or 1e9))]
    leitura = [(float(g["inicio"]), float(g["fim"])) for g in grafismos or [] if g.get("tela_cheia") or g.get("tipo") in LEITURA]
    out, pulos = [], {"fora_da_tela": 0, "perto_da_anterior": 0, "teto_por_minuto": 0, "em_cima_de_texto": 0, "sem_posicao": 0}
    for e in pedidos:
        ini = round(max(0.0, e["inicio"]), 3)
        fim = round(float(e.get("fim") or ini + DUR_S), 3)
        if duracao_s:
            fim = min(fim, float(duracao_s))
        if fim - ini < 1.0:
            continue
        if not any(a <= ini and fim <= b + 0.3 for a, b in na_tela):
            pulos["fora_da_tela"] += 1; continue
        if out and ini - out[-1]["inicio"] < GAP_S and e.get("forcar") is not True:
            pulos["perto_da_anterior"] += 1; continue
        if sum(1 for o in out if ini - o["inicio"] < 60.0) >= POR_MIN:
            pulos["teto_por_minuto"] += 1; continue
        if any(a < fim and ini < b for a, b in leitura):
            pulos["em_cima_de_texto"] += 1; continue
        x, y, rastro, origem = e.get("x"), e.get("y"), [], "agente"
        if x is None or y is None:
            if tela:
                try:
                    rastro = rastro_cursor(tela, ini - ANTES_S, fim)
                except Exception as ex:  # noqa: BLE001
                    avisos.append(f"cursor: não li a tela ({ex})"); rastro = []
            rastro = _sem_saltos(rastro)
            antes = [r for r in rastro if ini - FRESCO_S <= r[0] <= ini + 0.05]  # onde a ponta estava quando a fala disse o verbo; depois, o rastro conduz
            logo = [r for r in rastro if ini < r[0] <= ini + 0.6]
            f = _foco_em(focos, ini)
            if antes or logo:
                _, x, y = (antes[-1] if antes else logo[0]); origem = "cursor"
            elif f:  # cursor parado há muito tempo (ou a própria gravação dando zoom): a última posição vista já não vale, o foco sim
                x, y, origem = f["x"], f["y"], "foco"
            elif rastro:
                _, x, y = rastro[-1] if rastro[0][0] <= ini else rastro[0]; origem = "cursor"
            rastro = [r for r in rastro if r[0] > ini]
            if origem == "foco" and rastro and max(abs(rastro[0][1] - x), abs(rastro[0][2] - y)) > 0.15:
                rastro = []  # o rastro não começa perto do foco: seguir daria um pulo
        if x is None or y is None:
            pulos["sem_posicao"] += 1; avisos.append(f"etiqueta '{e['texto']}' em {ini}: cursor não visto e sem foco perto; ficou fora"); continue
        x, y = float(x), float(y)
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ErroFerramenta("etiquetas: x e y vão de 0 a 1 (fração da largura e da altura da tela)")
        lado, vert = lado_de(x, y)
        item = {"inicio": ini, "fim": fim, "texto": e["texto"], "x": round(x, 4), "y": round(y, 4), "lado": lado, "vert": vert, "origem": origem}
        if len(rastro) >= 2:
            item["rastro"] = [[round(t, 2), xx, yy] for t, xx, yy in rastro]
        out.append(item)
    for a, b in zip(out, out[1:]):
        if a["fim"] > b["inicio"] - 0.2:
            a["fim"] = round(max(a["inicio"] + 1.0, b["inicio"] - 0.2), 3)
    resumo = {"n": len(out), "origem_texto": origem_txt, "posicao": {k: sum(1 for o in out if o["origem"] == k) for k in ("cursor", "foco", "agente")},
              "textos": [o["texto"] for o in out], "puladas": {k: v for k, v in pulos.items() if v}, "avisos": avisos}
    return out, resumo


def ajustar_focos(focos, etiquetas, margem=0.1):
    """A câmera virtual não pode deixar a ponta do cursor fora do quadro enquanto a etiqueta está na tela: o foco que cobre a etiqueta anda (ou abre o zoom)
    até a ponta e o rastro caberem com folga. Devolve quantos focos mudaram."""
    n = 0
    for e in etiquetas or []:
        pts = [(e["x"], e["y"])] + [(r[1], r[2]) for r in e.get("rastro", [])]
        for f in focos or []:
            if f["fim"] + 0.55 < e["inicio"] or f["inicio"] > e["fim"]:
                continue
            antes = (f["x"], f["y"], f["zoom"])
            for k, ix in (("x", 0), ("y", 1)):
                lo, hi = min(p[ix] for p in pts), max(p[ix] for p in pts)
                meia = 0.5 / f["zoom"]
                if hi - lo + 2 * margem > 2 * meia:
                    f["zoom"] = round(max(1.0, min(f["zoom"], 1.0 / (hi - lo + 2 * margem))), 2); meia = 0.5 / f["zoom"]
                f[k] = round(min(max(f[k], hi + margem - meia), lo - margem + meia), 4)
            n += (f["x"], f["y"], f["zoom"]) != antes
    return n
