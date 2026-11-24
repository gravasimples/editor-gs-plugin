"""Cortes de vídeo longo, extração de trecho, trilha e exportação para editores."""
import re, subprocess
from pathlib import Path
from .util import FFMPEG, caminho, caminho_saida, ler_json, salvar_json, rodar, info_midia, normalizar, ErroFerramenta

GANCHOS = ["erro", "nunca", "sempre", "segredo", "simples", "barato", "caro", "gratis", "gratuito", "dica", "truque", "como", "porque", "ninguem", "todo mundo",
           "cuidado", "para de", "pare de", "melhor", "pior", "obvio", "real", "verdade", "mentira", "diferenca", "problema", "solucao", "em 1 minuto", "em um minuto"]


EMOCAO = ["incrivel", "absurdo", "chocante", "nunca vi", "pior", "melhor", "medo", "vergonha", "errei", "aprendi", "mudou", "acredita", "serio", "pasme", "cuidado", "atencao", "finalmente", "graca", "de graca", "perdi", "ganhei"]
PARADAS = set("a o e de da do das dos em um uma que não nao com para por mais se na no os as eu ele ela isso esse essa aqui ali la lá ja já tá ta então entao mas ou como quando onde muito bem pra pro vai vou ser é e tem tinha foi ter dele dela nos nós você voce vocês voces gente tudo nada só so ainda também tambem até ate".split())


def _frases(palavras, segmentos):
    """Fronteiras de frase: fim de segmento do Whisper ou palavra terminada em . ! ? seguida de pausa > 0,25 s."""
    fins = set()
    for s in segmentos or []:
        fins.add(round(float(s.get("fim", 0)), 3))
    for i, w in enumerate(palavras):
        t = w.get("palavra", "").strip()
        if t and t[-1] in ".!?" and (i + 1 >= len(palavras) or palavras[i + 1]["inicio"] - w["fim"] > 0.25):
            fins.add(round(w["fim"], 3))
    return sorted(fins)


def _ajustar_a_frase(ini, fim, fins, palavras, tol=4.0):
    """Puxa o início para logo depois do fim de frase anterior e o fim para o fim de frase mais próximo (até tol s)."""
    ant = [f for f in fins if f <= ini + 0.05 and ini - f <= tol]
    if ant:
        f = max(ant); prox = [w["inicio"] for w in palavras if w["inicio"] >= f - 0.01]
        if prox:
            ini = max(0.0, min(prox) - 0.15)
    dep = [f for f in fins if fim - tol <= f <= fim + tol]
    if dep:
        fim = min(dep, key=lambda f: abs(f - fim)) + 0.25
    return round(ini, 3), round(fim, 3)


def _topicos(blocos, janela=3, limiar=0.18):
    """Segmentação por coesão lexical (estilo TextTiling): marca uma mudança de assunto quando a sobreposição de vocabulário
    entre a janela anterior e a seguinte cai abaixo do limiar. Devolve índices de bloco onde começa um tópico novo."""
    def bolsa(bs):
        c = {}
        for b in bs:
            for w in b:
                t = normalizar(w["palavra"]).strip(".,!?;:")
                if len(t) > 3 and t not in PARADAS:
                    c[t] = c.get(t, 0) + 1
        return c
    inicios = [0]
    janela = max(1, min(janela, len(blocos) // 2))
    for i in range(janela, len(blocos) - janela + 1):
        a, b = bolsa(blocos[i - janela:i]), bolsa(blocos[i:i + janela])
        if not a or not b:
            continue
        inter = sum(min(a[k], b[k]) for k in a if k in b); uni = (sum(a.values()) * sum(b.values())) ** 0.5
        if uni and inter / uni < limiar:
            if i - inicios[-1] >= 2:
                inicios.append(i)
    return inicios


def propor_cortes_longos(palavras_json, saida_json, n=5, min_s=20.0, max_s=75.0, pausa_bloco_s=1.2):
    """Agrupa a fala em blocos (pausa > pausa_bloco_s), junta blocos vizinhos até caber em [min_s, max_s] e pontua cada candidato.
    Pontuação: densidade de fala, palavras-gancho na abertura, presença de número, pergunta. O Editor escolhe e descreve o gancho."""
    d = ler_json(palavras_json); palavras = d["palavras"]; segmentos = d.get("segmentos", [])
    if not palavras:
        raise ErroFerramenta("Transcrição sem palavras.")
    blocos, atual = [], [palavras[0]]
    for p in palavras[1:]:
        if p["inicio"] - atual[-1]["fim"] > pausa_bloco_s:
            blocos.append(atual); atual = [p]
        else:
            atual.append(p)
    blocos.append(atual)
    fins = _frases(palavras, segmentos); topicos = set(_topicos(blocos)); spans = frases(palavras, segmentos)
    cands = []
    for i in range(len(blocos)):
        ws = []
        for j in range(i, len(blocos)):
            ws = ws + blocos[j]
            dur = ws[-1]["fim"] - ws[0]["inicio"]
            if dur > max_s:
                break
            if dur >= min_s:
                ini, fim, _ = encaixar_em_frase(ws[0]["inicio"], ws[-1]["fim"], spans, max_s=max_s)
                qual = nota_qualidade(ini, fim, palavras, spans, min_s=min_s, max_s=max_s)
                texto = " ".join(w["palavra"] for w in ws); abertura = normalizar(" ".join(w["palavra"] for w in ws[:12])); texto_n = normalizar(texto)
                fala = sum(w["fim"] - w["inicio"] for w in ws)
                det = {"densidade": round(min(1.0, fala / dur) * 2.0, 2),
                       "gancho": round(min(2.4, sum(1 for g in GANCHOS if g in abertura) * 0.8), 2),
                       "numero": 0.6 if re.search(r"\d|R\$|reais|por cento|%", texto) else 0.0,
                       "pergunta": 0.5 if "?" in texto[:160] else 0.0,
                       "emocao": round(min(1.0, sum(1 for e in EMOCAO if e in texto_n) * 0.5), 2),
                       "duracao": 0.4 if 30 <= dur <= 60 else 0.0,
                       "completude": round(qual["nota"] / 100, 2) + (0.3 if i in topicos else 0.0),
                       "topico_novo": 0.3 if i in topicos else 0.0}
                pont = round(sum(det.values()), 2)
                cands.append({"inicio": ini, "fim": fim, "duracao": round(fim - ini, 2), "pontuacao": pont, "pontuacao_detalhe": det,
                              "abertura": " ".join(w["palavra"] for w in ws[:14]), "texto": texto, "comeca_topico": i in topicos,
                              "termina_em_frase": "termina no meio de uma frase" not in qual["problemas"], "qualidade": qual})
    # remove sobreposição: ordena por pontuação, aceita se não cruza mais de 30% com um já aceito
    cands.sort(key=lambda c: -c["pontuacao"]); escolhidos = []
    for c in cands:
        ok = True
        for e in escolhidos:
            inter = max(0.0, min(c["fim"], e["fim"]) - max(c["inicio"], e["inicio"]))
            if inter > 0.3 * min(c["duracao"], e["duracao"]):
                ok = False; break
        if ok:
            escolhidos.append(c)
        if len(escolhidos) >= n:
            break
    escolhidos.sort(key=lambda c: c["inicio"])
    out = salvar_json(saida_json, {"origem": d.get("arquivo"), "duracao_s": d.get("duracao_s"), "parametros": {"n": n, "min_s": min_s, "max_s": max_s},
                                   "n_blocos": len(blocos), "n_topicos": len(topicos), "fins_de_frase": fins, "candidatos": escolhidos})
    return {"candidatos_json": out, "n_blocos": len(blocos), "n_topicos": len(topicos),
            "candidatos": [{k: c[k] for k in ("inicio", "fim", "duracao", "pontuacao", "pontuacao_detalhe", "abertura", "comeca_topico", "termina_em_frase", "qualidade")} for c in escolhidos]}


# --- borda em frase e nota de qualidade (15/11/2026, item 5; regras reimplementadas a partir do ShortsFlow, MIT) -------------------------
PAUSA_FRASE_S = 0.9      # silêncio assim entre duas palavras também separa frases (o Whisper costuma omitir a pontuação)
DESLOCA_MAX_S = 6.0      # borda anda até isso para achar a frase
DESLOCA_LONGE_S = 20.0   # frase longa sem fronteira perto: até isso, se o corte continuar dentro do tamanho
RABO_S = 0.4             # ar depois da última palavra, sem entrar na frase seguinte
CORTE_MIN_S = 8.0
MULETAS = {"e", "é", "eh", "ah", "aham", "hum", "hm", "então", "entao", "tipo", "né", "ne", "ok", "okay", "beleza", "bom", "aí", "ai", "assim", "galera",
           "gente", "pessoal", "tá", "ta"}
ABERTURA_DEPENDENTE = {"e", "mas", "porque", "que", "aí", "ai", "daí", "dai", "também", "tambem", "ou", "senão", "senao", "pois", "inclusive", "tipo",
                       "é", "eh", "ah", "hum"}
ABERTURA_MOLE = {"então", "entao", "bom", "bem", "ok", "okay", "beleza", "olha", "né", "ne", "assim", "agora"}
FIM_PENDURADO = {"a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "pra", "pro", "para", "por", "com",
                 "e", "ou", "mas", "que", "porque", "se", "como", "quando", "onde", "meu", "minha", "seu", "sua", "esse", "essa", "este", "esta"}
_FIM_RX = re.compile(r"[.!?…]+[\"')\]]*$")


def _limpa(w):
    return re.sub(r"[^\w]", "", str(w).lower())


def frases(palavras, segmentos=None):
    """[(inicio, fim, texto)]: termina em . ! ? ou numa pausa >= PAUSA_FRASE_S (o fim de segmento do Whisper sozinho não fecha frase)."""
    spans, atual = [], []
    for i, w in enumerate(palavras):
        atual.append(w)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        if prox is None or bool(_FIM_RX.search(w.get("palavra", "").strip())) or (prox["inicio"] - w["fim"] >= PAUSA_FRASE_S):
            spans.append((round(atual[0]["inicio"], 3), round(atual[-1]["fim"], 3), " ".join(x["palavra"].strip() for x in atual)))
            atual = []
    return spans


def _primeira_palavra(texto):
    m = re.match(r"\s*([^\W\d_][\w']*)(\s*[,.…]|\s|$)", texto or "")
    return (m.group(1).lower(), (m.group(2) or "").strip()) if m else ("", "")


def abertura_fraca(texto):
    """Frase que não abre um corte: começa apoiada na anterior ("E aí…", "Mas…", "Porque…") ou com muleta e vírgula ("Então, …", "Bom, …")."""
    p, sep = _primeira_palavra(texto)
    return p in ABERTURA_DEPENDENTE or (p in ABERTURA_MOLE and sep != "")


def _palavras_limpas(texto):
    return [w for w in (_limpa(x) for x in str(texto).split()) if w]


def _so_muleta(texto, max_palavras=5):
    ws = _palavras_limpas(texto)
    return 0 < len(ws) <= max_palavras and all(w in MULETAS for w in ws)


def termina_pendurado(texto):
    ws = _palavras_limpas(texto)
    return bool(ws) and ws[-1] in FIM_PENDURADO


def encaixar_em_frase(inicio, fim, spans, max_s=75.0, min_s=CORTE_MIN_S):
    """Move as bordas de um corte para fronteiras de frase: começa no início da frase mais perto (pula muleta solta e até 3 frases que se apoiam
    na anterior, sem perder mais de 40% do corte), termina no fim da frase em que o corte para (fecha o pensamento) e larga a última frase se ela
    termina pendurada ("… que") quando isso mantém 70% do corte. Devolve (inicio, fim, mudou)."""
    if not spans:
        return inicio, fim, False
    a0, z0 = float(inicio), float(fim); ini, end = a0, z0
    starts = [s for s, _, _ in spans]; ends = [e for _, e, _ in spans]
    dentro = next((i for i, (s, e, _) in enumerate(spans) if s - 0.05 <= ini < e), None)
    if dentro is not None and abs(starts[dentro] - ini) > 0.05:
        antes, depois = starts[dentro], (starts[dentro + 1] if dentro + 1 < len(spans) else None)
        c = [x for x in (antes, depois) if x is not None and abs(x - ini) <= DESLOCA_MAX_S and x < end - min_s]
        if not c:
            c = [x for x in (antes, depois) if x is not None and abs(x - ini) <= DESLOCA_LONGE_S and x < end - min_s and end - x <= max_s]
        if c:
            ini = min(c, key=lambda x: abs(x - ini))
    elif dentro is None:
        seg = [x for x in starts if x > ini]
        if seg and seg[0] - ini <= DESLOCA_MAX_S and seg[0] < end - min_s:
            ini = seg[0]
    primeira = next((i for i, s in enumerate(starts) if abs(s - ini) < 0.05), None); origem = ini
    if (primeira is not None and primeira + 1 < len(spans) and _so_muleta(spans[primeira][2]) and starts[primeira + 1] - ini <= DESLOCA_LONGE_S
            and starts[primeira + 1] < end - min_s):
        primeira += 1; ini = starts[primeira]
    for _ in range(3):
        if primeira is None or primeira + 1 >= len(spans) or not abertura_fraca(spans[primeira][2]):
            break
        c = starts[primeira + 1]
        if c - origem > DESLOCA_LONGE_S or c >= end - min_s or end - c < 0.6 * (z0 - a0):
            break
        primeira += 1; ini = c
    dentro_f = next((i for i, (s, e, _) in enumerate(spans) if s < end <= e + 0.05), None)
    if dentro_f is not None and abs(ends[dentro_f] - end) > 0.05:
        frente, tras = ends[dentro_f], (ends[dentro_f - 1] if dentro_f > 0 else None)
        c = [x for x in (frente, tras) if x is not None and abs(x - end) <= DESLOCA_MAX_S and x > ini + min_s and x - ini <= max_s]
        if not c:
            c = [x for x in (frente, tras) if x is not None and abs(x - end) <= DESLOCA_LONGE_S and x > ini + min_s and x - ini <= max_s]
        if c:
            end = frente if frente in c else min(c, key=lambda x: abs(x - end))
    elif dentro_f is None:
        prev = [e for e in ends if e <= end + 0.05]
        if prev and end - prev[-1] <= DESLOCA_MAX_S and prev[-1] > ini + min_s:
            end = prev[-1]
    ult = next((i for i, e in enumerate(ends) if abs(e - end) < 0.05), None)
    if ult is not None and ult > 0 and termina_pendurado(spans[ult][2]) and ends[ult - 1] > ini + min_s and ends[ult - 1] - ini >= 0.7 * (end - ini):
        end = ends[ult - 1]
    if end - ini > max_s:
        cabe = [e for e in ends if ini + min_s < e <= ini + max_s]
        end = cabe[-1] if cabe else ini + max_s
    prox = [s for s in starts if s >= end - 0.02]  # frase seguinte colada (Whisper encosta fim e início): o ar não entra nela
    end = max(end, min(end + RABO_S, prox[0] - 0.05) if prox else end + RABO_S)
    if end - ini < min_s <= z0 - a0:
        return round(a0, 3), round(z0, 3), False
    ini = max(0.0, ini - 0.05)
    return round(ini, 3), round(end, 3), abs(ini - a0) > 0.06 or abs(end - z0) > 0.06


def _no_corte(w, inicio, fim):
    return inicio - 0.06 <= w["inicio"] < fim


def _primeira_frase_ok(palavras, ini, fim):
    """O gancho se sustenta sozinho: a fala começa em até 1 s, a 1ª frase não se apoia na anterior nem é muleta e tem 4+ palavras (ou é pergunta)."""
    ws = [w for w in palavras if _no_corte(w, ini, fim)]
    if not ws or ws[0]["inicio"] - ini > 1.0:
        return False
    sp = frases(ws)
    t = sp[0][2] if sp else ""
    if abertura_fraca(t) or _so_muleta(t):
        return False
    return "?" in t or len(t.split()) >= 4


def nota_qualidade(inicio, fim, palavras, spans=None, gancho="", min_s=20.0, max_s=75.0):
    """Nota 0–100 de um corte, sem modelo, com o motivo de cada desconto: começa/termina em frase, gancho que se sustenta, fim pendurado,
    pausas longas (só aviso), tamanho e número do gancho que não é dito."""
    spans = spans if spans is not None else frases(palavras)
    ws = [w for w in palavras if _no_corte(w, inicio, fim)]
    probs, nota = [], 100
    if not any(abs(s - inicio) <= 0.25 for s, _, _ in spans):
        nota -= 20; probs.append("começa no meio de uma frase")
    ult = [(e, t) for s, e, t in spans if s < fim and e <= fim + 0.05]
    if not ult or any(s < fim - 0.2 and e > fim + 0.05 for s, e, _ in spans):
        nota -= 20; probs.append("termina no meio de uma frase")
    elif termina_pendurado(ult[-1][1]):
        nota -= 10; probs.append("última frase termina pendurada (\"…" + ult[-1][1].split()[-1] + "\")")
    if not _primeira_frase_ok(palavras, inicio, fim):
        nota -= 15; probs.append("abertura fraca (muleta, \"e/mas/porque…\" ou a fala demora a começar)")
    dur = fim - inicio
    morto = sum(b["inicio"] - a["fim"] for a, b in zip(ws, ws[1:]) if b["inicio"] - a["fim"] > 0.6)
    if dur > 0 and morto / dur > 0.15:  # a edição tira as pausas: só avisa quando o trecho é mais pausa que fala corrida
        probs.append(f"{morto:.1f} s de pausas longas (a edição encurta)")
    if not (min_s <= dur <= max_s):
        nota -= 10; probs.append(f"duração {dur:.0f} s fora de {min_s:.0f}–{max_s:.0f} s")
    texto = " ".join(w["palavra"] for w in ws)
    falta = [n for n in re.findall(r"\d+", gancho or "") if n not in texto]
    if falta:  # gancho é escrito pelo agente; o que não pode é número que ninguém disse
        nota -= 15; probs.append("gancho com número que não é dito no trecho: " + ", ".join(falta))
    return {"nota": max(0, nota), "problemas": probs, "pausas_longas_s": round(morto, 1)}


def conferir_cortes_longos(cortes_json, palavras_json, max_s=75.0, min_s=20.0, encaixar=True):
    """Para o cortes.json do Clipador ou do kit: encaixa cada corte em frase (guarda o original em inicio_original/fim_original), dá a nota de
    qualidade e resolve sobreposição (o corte de nota menor recua para a frase seguinte ou fica marcado para sair). Regrava o arquivo."""
    d = ler_json(cortes_json); palavras = ler_json(palavras_json)["palavras"]; spans = frases(palavras)
    cortes = d.get("cortes") or []
    for i, c in enumerate(cortes):
        c.setdefault("id", f"c{i + 1:02d}")
        a, z = float(c["inicio"]), float(c["fim"])
        if encaixar:
            na, nz, mudou = encaixar_em_frase(a, z, spans, max_s=max_s)
            if mudou:
                c.setdefault("inicio_original", a); c.setdefault("fim_original", z)
                c["inicio"], c["fim"] = na, nz
        c["duracao"] = round(c["fim"] - c["inicio"], 2)
    cortes.sort(key=lambda c: c["inicio"]); fora = []
    nota = lambda c: float(c.get("nota", 0) or 0)
    for A, B in zip(cortes, cortes[1:]):
        if A["fim"] <= B["inicio"] or A["id"] in fora or B["id"] in fora:
            continue
        if nota(B) <= nota(A):
            seg = [s for s, _, _ in spans if A["fim"] <= s <= B["fim"] - min_s]
            if seg:
                B["inicio"] = round(max(0.0, seg[0] - 0.05), 3); B["duracao"] = round(B["fim"] - B["inicio"], 2)
            else:
                fora.append(B["id"])
        else:
            fim_ok = [e for _, e, _ in spans if A["inicio"] + min_s <= e <= B["inicio"] - 0.05]
            if fim_ok:
                A["fim"] = round(min(fim_ok[-1] + RABO_S, B["inicio"] - 0.05), 3); A["duracao"] = round(A["fim"] - A["inicio"], 2)
            else:
                fora.append(A["id"])
    for c in cortes:
        c["qualidade"] = nota_qualidade(c["inicio"], c["fim"], palavras, spans, gancho=c.get("gancho", ""), min_s=min_s, max_s=max_s)
        if c["id"] in fora:
            c["qualidade"]["problemas"].append("sobrepõe um corte melhor: sugiro tirar")
    d["cortes"] = sorted(cortes, key=lambda c: (-nota(c), -c["qualidade"]["nota"]))
    d["qualidade_conjunto"] = {"cortes": len(cortes), "nota_media": round(sum(c["qualidade"]["nota"] for c in cortes) / len(cortes), 1) if cortes else None,
                               "encaixados": sum(1 for c in cortes if "inicio_original" in c), "sobrepostos": fora}
    salvar_json(cortes_json, d)
    return {"cortes_json": str(cortes_json), **d["qualidade_conjunto"],
            "cortes": [{"id": c["id"], "inicio": c["inicio"], "fim": c["fim"], "nota_qualidade": c["qualidade"]["nota"], "problemas": c["qualidade"]["problemas"]}
                       for c in d["cortes"]]}


def detectar_cenas(video, limiar=0.4, min_intervalo_s=1.0):
    """Mudanças de plano (cortes de câmera, troca de tela) pelo detector de cena do ffmpeg. Útil para não cortar no meio de um plano
    e para saber se o vídeo alterna rosto e tela. Devolve instantes em segundos."""
    v = caminho(video)
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", v, "-vf", f"select='gt(scene,{limiar})',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True)
    ts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    cenas, ult = [], -10.0
    for t in ts:
        if t - ult >= min_intervalo_s:
            cenas.append(round(t, 3)); ult = t
    return {"video": v, "n_cenas": len(cenas), "cenas": cenas, "limiar": limiar}


def extrair_trecho(video, inicio_s, fim_s, saida_video, saida_palavras=None, palavras_json=None):
    """Recorta [inicio_s, fim_s] com recodificação (corte exato) e, se houver palavras_json, grava as palavras do trecho com tempo rebaseado."""
    v = caminho(video); out = caminho_saida(saida_video)
    a, z = float(inicio_s), float(fim_s)
    if z <= a:
        raise ErroFerramenta("fim_s deve ser maior que inicio_s")
    rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-ss", str(a), "-to", str(z), "-i", v, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    res = {"video": str(out), "duracao_s": info_midia(out)["duracao_s"], "inicio_s": a, "fim_s": z}
    if palavras_json and saida_palavras:
        d = ler_json(palavras_json)
        ws = [{**p, "inicio": round(p["inicio"] - a, 3), "fim": round(p["fim"] - a, 3)} for p in d["palavras"] if a <= p["inicio"] <= z]
        segs = [{**s, "inicio": round(max(s["inicio"], a) - a, 3), "fim": round(min(s["fim"], z) - a, 3)} for s in d.get("segmentos", []) if s["fim"] > a and s["inicio"] < z]
        res["palavras_json"] = salvar_json(saida_palavras, {**d, "arquivo": str(out), "duracao_s": res["duracao_s"], "palavras": ws, "segmentos": segs,
                                                            "n_palavras": len(ws), "n_segmentos": len(segs), "origem_trecho": [a, z]})
    return res


def adicionar_trilha(video, trilha, saida_video, volume_db=-18.0, ducking=True, fade_s=1.5):
    """Mistura uma trilha por baixo da voz. ducking abaixa a trilha quando há fala (sidechain). A trilha é cortada/looped para a duração do vídeo."""
    v = caminho(video); t = caminho(trilha); out = caminho_saida(saida_video); info = info_midia(v)
    if not info["tem_audio"]:
        raise ErroFerramenta("O vídeo não tem voz para misturar.")
    dur = info["duracao_s"]
    f = (f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{dur},asetpts=PTS-STARTPTS,volume={volume_db}dB,afade=t=in:d={fade_s},afade=t=out:st={max(0, dur - fade_s)}:d={fade_s}[m];")
    if ducking:
        f += "[0:a]asplit=2[voz][sc];[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=40:release=600:makeup=1[md];[voz][md]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    else:
        f += "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v, "-i", t, "-filter_complex", f, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", out])
    return {"video": str(out), "trilha": str(t), "volume_db": volume_db, "ducking": ducking, "duracao_s": info_midia(out)["duracao_s"]}


def _tc(seg, fps):
    f = int(round(seg * fps)); h = f // (3600 * fps); m = (f // (60 * fps)) % 60; s = (f // fps) % 60; fr = f % fps
    return f"{h:02d}:{m:02d}:{s:02d}:{fr:02d}"


def exportar_edl_cmx(edl_json, saida_edl, fps=30, titulo="EDITOR GS", nome_fonte=None):
    """EDL CMX3600 (Premiere, DaVinci, FCP) com os trechos mantidos, em ordem, vídeo+áudio. O editor importa e religa ao arquivo original."""
    edl = ler_json(edl_json); out = caminho_saida(saida_edl)
    fonte = nome_fonte or Path(edl.get("origem") or "ORIGINAL").name
    reel = re.sub(r"[^A-Za-z0-9]", "", Path(fonte).stem.upper())[:8] or "AX"
    linhas = [f"TITLE: {titulo}", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for i, m in enumerate(edl["manter"], 1):
        dur = m["fim"] - m["inicio"]
        linhas.append(f"{i:03d}  {reel:<8} AA/V  C        {_tc(m['inicio'], fps)} {_tc(m['fim'], fps)} {_tc(rec, fps)} {_tc(rec + dur, fps)}")
        linhas.append(f"* FROM CLIP NAME: {fonte}")
        rec += dur
    out.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return {"edl": str(out), "n_eventos": len(edl["manter"]), "fps": fps, "duracao_s": round(rec, 3), "fonte": fonte}
