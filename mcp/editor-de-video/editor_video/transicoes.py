"""Fase E (08/11/2026): gramática de corte. Cada emenda do vídeo cortado ganha um tratamento escolhido pelo contexto,
em vez do mesmo clarão + zoom 1,00↔1,08 em todas (crítica do Raphael ao GRA-49: "transições iguais, pouco dinâmicas, sem fluxo").

Regras (do jeito de editor de Reels):
- Dentro do mesmo assunto, a maioria das emendas é corte seco com troca de enquadramento (aberto/médio/fechado, nunca o mesmo duas vezes:
  jump cut sem mudança de pelo menos ~8% parece erro).
- Palavra de ênfase logo depois da emenda = punch-in (fechado) e, às vezes, um tremor curto.
- Troca de assunto (capítulo, tela cheia, troca de bloco) = transição forte do repertório: zoom com desfoque, deslize (whip),
  luz laranja, giro. Clarão branco só nas viradas grandes, no máximo 2 por vídeo.
- Nunca o mesmo tratamento forte duas vezes seguidas; forte no máximo um a cada ~5 s.
- A câmera nunca fica parada: cada plano anda devagar (aproxima ou afasta), alternando, e o ritmo vem da energia.
- Plano longo demais ganha troca de enquadramento sem corte no começo de frase (pattern interrupt).
Saída: lista de planos para o Remotion (Montagem.tsx lê `camera`).

Recalibração pelo repertório (08/11/2026): a fase E saiu com 75% de emendas secas contra 39% no Máquina (fala com tela: seco 9, punch 8,
deslize 7, zoom_blur 1). Com `receita` (pesos por tipo, padrão = fala_tela lida do repertório; `receita_de(formato)` lê o repertório), as emendas que
não são ênfase nem troca de assunto escolhem o tipo que está mais abaixo da proporção da receita, e tipo com peso zero (giro, luz) só entra
forçado. Deslize vira transição de ritmo (pode repetir com ~1,5 s de folga); as outras fortes mantêm o intervalo da energia.

13/11/2026 (curadoria das instruções): transição forte só com motivo — troca de assunto (capítulo, tela cheia, bloco novo) ou o agente mandar
pelo `transicoes='{"seg": "tipo"}'`. Emenda sem motivo usa a receita só entre seco e punch. A receita do repertório decide QUAL forte entra numa
troca de assunto, não QUANTAS fortes o vídeo tem."""
import random

FORTES = ("zoom_blur", "deslize", "luz", "giro")
LEVES = ("seco", "punch", "tremor")
TIPOS = FORTES + LEVES + ("flash",)
# enquadramentos (escala sobre o quadro que já cobre a tela)
ENQ = {"aberto": 1.0, "medio": 1.1, "fechado": 1.22}
ENERGIA = {  # deriva por segundo, duração das transições fortes, chance de tremor no punch, intervalo mínimo entre fortes
    "calmo": {"seco": 1.5, "deriva": 0.006, "dur_forte": 0.32, "tremor": 0.0, "gap_forte": 7.0, "ritmo": 6.0},
    "normal": {"seco": 1.15, "deriva": 0.010, "dur_forte": 0.28, "tremor": 0.25, "gap_forte": 5.0, "ritmo": 4.5},
    "dinamico": {"seco": 1.0, "deriva": 0.014, "dur_forte": 0.24, "tremor": 0.4, "gap_forte": 4.0, "ritmo": 3.5},
    "bem_dinamico": {"seco": 0.8, "deriva": 0.018, "dur_forte": 0.2, "tremor": 0.55, "gap_forte": 3.0, "ritmo": 2.6},
}
SFX = {"zoom_blur": ("whoosh", 0.3), "deslize": ("swipe", 0.32), "luz": ("riser", 0.22), "giro": ("swipe", 0.28),
       "flash": ("impacto", 0.3), "punch": ("tick", 0.18), "tremor": ("impacto", 0.22)}  # entrada → (categoria do catálogo de SFX, volume)


# reserva quando o repertório não tem fichas: fala_tela do Máquina em 09/11 (4 fichas decupadas, 37 emendas; "nenhuma" conta como seco, cortina é do layout)
RECEITA_PADRAO = {"seco": 0.51, "punch": 0.24, "deslize": 0.22, "zoom_blur": 0.03}
GAP_DESLIZE = 1.5
GAP_SOM = {"punch": 5.0, "deslize": 3.0}
# 15/11/2026 (item 3, efeitos com limite; números do 2BFT/shorts em docs/maquina/ANALISE-SKILLS-2026-11-13.md): teto e espaçamento,
# nunca cota mínima. Efeito pedido pelo agente (forcar) passa sempre e ocupa a vaga; o automático que estoura vira seco (o enquadramento muda igual).
PUNCH_GAP_S = 8.0          # zoom de impacto: no mínimo 8 s entre um e outro
PUNCH_POR_MIN = 6          # e no máximo 6 em qualquer janela de 60 s
TREMOR_GAP_S = 3.0         # tremor: 3 s de qualquer outro impacto (tremor ou zoom de impacto)
TREMOR_VISIVEL_S = 0.3     # tremor de 0,16 s com a escala voltando: ~0,3 s de imagem mexendo
TREMOR_FRACAO = (0.10, 0.05)  # tremor visível: até 10% de um Reels, até 5% de vídeo longo (acima de 90 s)
LONGO_S = 90.0
LEITURA = {"manchete", "checklist", "pilulas", "fluxo", "cartoes", "numero", "riscado", "cta", "celular", "comentario", "historia", "grade"}  # texto que se lê: nunca treme
GAP_MOVIMENTO_S = 5.0      # whoosh/swipe (som de movimento): no máximo 1 a cada 5 s


def receita_de(formato="fala_tela", n=10):
    """Pesos de transição a partir das fichas decupadas do repertório; None se o formato não tiver decupagem."""
    try:
        from . import repertorio
        tr = (repertorio.consultar(formato, n=n).get("padroes") or {}).get("transicoes") or {}
    except Exception:
        return None
    pesos = {}
    for t, q in tr.items():
        t = "seco" if t == "nenhuma" else t
        if t in TIPOS:
            pesos[t] = pesos.get(t, 0) + q
    tot = sum(pesos.values())
    return {t: round(q / tot, 3) for t, q in pesos.items()} if tot >= 5 else None


def _perto(t, lista, antes=0.35, depois=0.8):
    return any(t - antes <= x <= t + depois for x in lista)


def _virtuais(cortes, segmentos, duracao_s, ritmo_s):
    """Começos de frase dentro de planos mais longos que ritmo_s viram trocas de enquadramento sem corte."""
    pontos = sorted({0.0, *cortes, duracao_s})
    novos = []
    for a, b in zip(pontos, pontos[1:]):
        if b - a <= ritmo_s * 1.4:
            continue
        ult, aqui = a, []
        for s in segmentos:
            x = float(s["inicio"])
            if x - ult >= ritmo_s * 0.8 and b - x >= 1.2 and a < x < b:
                aqui.append(round(x, 3)); ult = x
        if not aqui:  # sem frase no meio: divide pelo tempo
            k = int((b - a) // ritmo_s)
            aqui = [round(a + i * (b - a) / (k + 1), 3) for i in range(1, k + 1)]
        novos += aqui
    return sorted(set(novos) - set(cortes))


def janelas_de_leitura(grafismos=None, blocos=None):
    """Trechos com texto sendo lido (grafismo de leitura ou em tela cheia, bloco de layout com tela/UI): o tremor não entra neles."""
    from .layouts import PRECISA_TELA
    out = [(float(g["inicio"]), float(g["fim"])) for g in grafismos or [] if g.get("tela_cheia") or g.get("tipo") in LEITURA]
    out += [(float(b["inicio"]), float(b["fim"])) for b in blocos or [] if b.get("modo") in PRECISA_TELA and "fim" in b]
    return sorted(out)


def limitar_efeitos(planos, duracao_s, leitura=None):
    """Aplica os tetos de zoom de impacto (punch) e tremor nos planos, na ordem do tempo, com os pedidos do agente na frente.
    Tremor que não cabe tenta virar punch; punch que não cabe vira seco. Devolve (planos, {"punch": n, "tremor": n} rebaixados)."""
    leitura = leitura or []
    teto_tremor = int((TREMOR_FRACAO[1] if duracao_s > LONGO_S else TREMOR_FRACAO[0]) * duracao_s / TREMOR_VISIVEL_S)
    punches, tremores = [], []
    rebaixou = {"punch": 0, "tremor": 0}

    def cabe_punch(t):
        if any(abs(t - x) < PUNCH_GAP_S for x in punches) or any(abs(t - x) < TREMOR_GAP_S for x in tremores):
            return False
        lst = sorted(punches + [t])
        return all(sum(1 for y in lst if x <= y < x + 60.0) <= PUNCH_POR_MIN for x in lst)

    def cabe_tremor(t):
        return (len(tremores) < teto_tremor and all(abs(t - x) >= TREMOR_GAP_S for x in punches + tremores)
                and not any(a - 0.2 <= t <= b for a, b in leitura))
    ordem = sorted(range(1, len(planos)), key=lambda i: (not planos[i].get("forcado"), planos[i]["inicio"]))
    for i in ordem:
        p = planos[i]; t = p["inicio"]; e = p["entrada"]
        if e not in ("punch", "tremor"):
            continue
        if p.get("forcado"):
            (punches if e == "punch" else tremores).append(t); continue
        if e == "tremor":
            if cabe_tremor(t):
                tremores.append(t); continue
            rebaixou["tremor"] += 1
            if cabe_punch(t):
                p.update(entrada="punch", dur=0.08); punches.append(t); continue
        elif cabe_punch(t):
            punches.append(t); continue
        else:
            rebaixou["punch"] += 1
        p.update(entrada="seco", dur=0.0)
    for p in planos:
        p.pop("forcado", None)
    return planos, rebaixou


def planejar(cortes_s, duracao_s, enfases=None, mudancas=None, segmentos=None, energia="normal", semente=7, forcar=None, sem_zoom=False, sem_flash=False, receita=None,
             leitura=None):
    """cortes_s: instantes das emendas (vídeo cortado); enfases: instantes de palavras de ênfase (grafismos/palavras-chave);
    mudancas: instantes de troca de assunto (capítulos, tela cheia, troca de bloco); forcar: {instante: tipo} vindo do agente.
    receita: {tipo: peso} (None = fala_tela do repertório, ou RECEITA_PADRAO sem fichas; {} = regras antigas, sem receita).
    leitura: [(inicio, fim)] com texto sendo lido (janelas_de_leitura); os tetos de efeito (limitar_efeitos) valem sempre.
    Devolve {"planos": [...], "resumo": {...}}; cada plano = {inicio, fim, z0, z1, entrada, dur, intensidade, virtual}."""
    cfg = ENERGIA.get(energia, ENERGIA["normal"])
    if receita is None:  # padrão: fala_tela lida do repertório na hora (cresce com as fichas novas)
        receita = receita_de("fala_tela") or RECEITA_PADRAO
    rec = {t: float(w) for t, w in receita.items() if t in TIPOS and float(w) > 0}
    if sem_flash:
        rec.pop("flash", None)
    if "seco" in rec:  # energia mexe na proporção de seco da receita (calmo = mais seco, bem dinâmico = menos)
        rec["seco"] *= cfg["seco"]
        tot = sum(rec.values()); rec = {t: round(w / tot, 3) for t, w in rec.items()}
    rnd = random.Random(semente)
    enfases = sorted(float(x) for x in (enfases or []))
    mudancas = sorted(float(x) for x in (mudancas or []))
    forcar = {round(float(k), 2): v for k, v in (forcar or {}).items() if v in TIPOS and not (sem_flash and v == "flash")}
    cortes = sorted({round(float(c), 3) for c in (cortes_s or []) if 0.2 < float(c) < duracao_s - 0.2})
    virt = set(_virtuais(cortes, segmentos or [], duracao_s, cfg["ritmo"]))
    pontos = sorted(set(cortes) | virt)
    bordas = [0.0, *pontos, float(duracao_s)]
    planos, ult_forte_t, ult_forte_tipo, flashes = [], -99.0, None, 0
    ult_efeito_t, ult_tremor_t = -99.0, -99.0  # efeito colado no outro polui: ~1,2 s entre efeitos e um tremor a cada ~6 s
    enq_atual = "aberto"; sentido = 1
    contagem = {}

    def pode(t, a, b, virtual):
        if t in FORTES or t == "flash":
            if virtual or t == ult_forte_tipo and t != "deslize":
                return False
            gap = GAP_DESLIZE if t == "deslize" else cfg["gap_forte"]
            return a - ult_forte_t >= gap and a - ult_efeito_t >= 0.8 and b - a > 0.6 and (t != "flash" or flashes < 2)
        if t in ("punch", "tremor"):
            return a - ult_efeito_t >= (0.6 if t == "punch" else 1.2) and (t != "tremor" or a - ult_tremor_t >= 6.0)
        return True

    def pela_receita(a, b, virtual, candidatos=None):
        """Tipo mais abaixo da proporção alvo entre os permitidos agora (seco sempre pode)."""
        feitos = sum(contagem.values()) + 1
        ops = [t for t in (candidatos or rec) if t in rec and pode(t, a, b, virtual)] or ["seco"]
        return max(ops, key=lambda t: (rec.get(t, 0) - contagem.get(t, 0) / feitos, rnd.random()))

    for i, (a, b) in enumerate(zip(bordas, bordas[1:])):
        virtual = a in virt
        entrada, dur, inten = "seco", 0.0, 1.0
        forcado = False
        if i == 0:
            enq = "medio"  # abre perto, no gancho
        else:
            forc = next((v for k, v in forcar.items() if abs(k - a) <= 0.15), None)
            mud = _perto(a, mudancas, 0.6, 0.6)
            enf = _perto(a, enfases, 0.15, 0.8)
            if forc:
                entrada = forc
                forcado = True
            elif rec:
                fortes_rec = [t for t in rec if t in FORTES or t == "flash"]
                if mud and not virtual and fortes_rec and any(pode(t, a, b, False) for t in fortes_rec):
                    entrada = pela_receita(a, b, False, fortes_rec)
                elif enf and pode("punch", a, b, virtual) and "punch" in rec:
                    entrada = "tremor" if not virtual and pode("tremor", a, b, False) and rnd.random() < cfg["tremor"] * 0.5 else "punch"
                else:  # 13/11/2026: emenda sem motivo (nem troca de assunto nem ênfase) fica no leve; deslize por cota parecia efeito sem sentido
                    entrada = pela_receita(a, b, virtual, [t for t in rec if t in ("seco", "punch")])
            elif mud and not virtual and a - ult_forte_t >= cfg["gap_forte"] * 0.6 and a - ult_efeito_t >= 0.8:
                if not sem_flash and flashes < 2 and a > duracao_s * 0.15 and rnd.random() < 0.18:
                    entrada = "flash"
                else:
                    opcoes = [f for f in FORTES if f != ult_forte_tipo]
                    entrada = min(opcoes, key=lambda f: (contagem.get(f, 0), rnd.random()))
            elif enf and a - ult_efeito_t >= 1.2:
                entrada = "tremor" if (not virtual and a - ult_tremor_t >= 6.0 and rnd.random() < cfg["tremor"]) else "punch"
            elif not virtual and a - ult_forte_t >= cfg["gap_forte"] * 2.2 and b - a > 1.0 and rnd.random() < 0.3:
                entrada = min([f for f in FORTES if f != ult_forte_tipo], key=lambda f: (contagem.get(f, 0), rnd.random()))
            # enquadramento novo, sempre diferente do anterior
            if entrada in ("punch", "tremor"):
                enq = "fechado" if enq_atual != "fechado" else "medio"
            elif entrada in FORTES or entrada == "flash":
                enq = "aberto" if enq_atual != "aberto" else "medio"
            else:
                enq = rnd.choice([e for e in ENQ if e != enq_atual])
            if entrada in FORTES or entrada == "flash":
                dur = cfg["dur_forte"] if entrada != "luz" else cfg["dur_forte"] + 0.18
                ult_forte_t, ult_forte_tipo = a, entrada
                flashes += entrada == "flash"
            elif entrada == "tremor":
                dur = 0.16
            elif entrada == "punch":
                dur = 0.08
            if entrada != "seco":
                ult_efeito_t = a
            if entrada == "tremor":
                ult_tremor_t = a
            inten = round(0.8 + 0.4 * rnd.random(), 2)
            contagem[entrada] = contagem.get(entrada, 0) + 1
        sent = -1 if enq == "fechado" else 1 if enq == "aberto" else sentido  # fechado só afasta (não corta cabeça); aberto só aproxima (abaixo de 1 aparece a borda)
        z0 = 1.0 if sem_zoom else ENQ[enq]
        z1 = z0 if sem_zoom else round(z0 * (1 + sent * min(0.05, cfg["deriva"] * (b - a))), 4)  # câmera viva: anda devagar dentro do plano
        sentido = -sentido
        planos.append({"inicio": round(a, 3), "fim": round(b, 3), "z0": z0, "z1": z1, "entrada": entrada, "dur": round(dur, 3),
                       "intensidade": inten, "virtual": virtual, "enquadramento": enq, **({"forcado": True} if forcado else {})})
        enq_atual = enq
    planos, rebaixados = limitar_efeitos(planos, float(duracao_s), leitura)
    tipos = [p["entrada"] for p in planos[1:]]
    resumo = {"planos": len(planos), "cortes": len(cortes), "trocas_sem_corte": len(virt), "energia": energia, "receita": rec or None,
              "por_tipo": {t: tipos.count(t) for t in sorted(set(tipos))}, "limites": {"rebaixados": rebaixados}}
    return {"planos": planos, "resumo": resumo}


def sfx_dos_planos(planos, min_gap_s=1.5):
    """Som de cada transição (forte = whoosh/swipe/riser; punch = tick discreto; seco = nada), respeitando um intervalo mínimo.
    A variação vem do catálogo CC0 (nivel_pro.escolher_sfx, sorteio determinístico pelo instante); categoria sem som não entra."""
    from .nivel_pro import escolher_sfx, antecipa_movimento, MOVIMENTO
    out, ult, ult_tipo, ult_mov = [], -9.0, {}, -99.0
    for p in planos[1:]:
        s = SFX.get(p["entrada"])
        # com a receita há mais punch e deslize: um som a cada 1,5 s no mínimo e o mesmo no máximo a cada 3–5 s, senão vira ruído
        if not s or p["inicio"] - ult < min_gap_s or p["inicio"] - ult_tipo.get(p["entrada"], -9.0) < GAP_SOM.get(p["entrada"], 0):
            continue
        if s[0] in MOVIMENTO and p["inicio"] - ult_mov < GAP_MOVIMENTO_S:
            continue
        arq = escolher_sfx(s[0], p["inicio"])
        if arq is None:
            continue
        ult_tipo[p["entrada"]] = p["inicio"]
        if s[0] in MOVIMENTO:  # 15/11: o pico do whoosh cai no primeiro quadro do plano novo (entra 150–300 ms antes)
            adiant = antecipa_movimento(arq); ult_mov = p["inicio"]
        else:
            adiant = 0.35 if p["entrada"] == "luz" else 0.0
        out.append({"arquivo": arq, "inicio": round(max(0.0, p["inicio"] - adiant), 2), "volume": s[1], "categoria": s[0]}); ult = p["inicio"]
    return out


def mudancas_de(grafismos=None, capitulos=None, cortinas=None):
    """Instantes de troca de assunto a partir do que o plano já sabe: capítulo, entrada/saída de tela cheia, kicker de seção ('1 · …'), troca de bloco."""
    m = [float(c["inicio"]) for c in (capitulos or [])]
    for g in grafismos or []:
        if g.get("tela_cheia"):
            m += [float(g["inicio"]), float(g["fim"])]
        elif g.get("tipo") == "kicker" and any(ch.isdigit() for ch in str(g.get("texto", ""))[:3]):
            m.append(float(g["inicio"]))
    m += [float(x) for x in (cortinas or [])]
    return sorted(set(round(x, 2) for x in m if x > 0.3))


ENFATICOS = {"manchete", "numero", "riscado", "pilula", "cta", "logos"}


def enfases_de(grafismos=None, palavras_chave=None):
    return sorted({round(float(g["inicio"]), 2) for g in (grafismos or []) if g.get("tipo") in ENFATICOS and not g.get("tela_cheia")}
                  | {round(float(k["inicio"]), 2) for k in (palavras_chave or [])})
