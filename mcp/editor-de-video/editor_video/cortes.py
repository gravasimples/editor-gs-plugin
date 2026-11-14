import difflib
from .util import ler_json, salvar_json, normalizar, info_midia, caminho, caminho_saida, rodar, FFMPEG, ErroFerramenta

# 13/11/2026: "e", "então" e "aí" saíram da lista. Isolados entre duas ideias são ligação ("E aí, o que acontece?"); cortados, a fala
# ficava desconexa. Só os enchimentos puros saem sozinhos; conectivo sobrando o agente tira à mão (ajustar_edl) lendo o texto.
VICIOS = {"ne", "tipo", "hum", "ahn", "eh", "humm", "hmm"}
FADE_CORTE_S = 0.008  # fade nas bordas de cada trecho mantido (tira o estalo da emenda)
# pausa máxima que fica dentro da fala, medida no áudio (08/11): o Whisper estica a palavra por cima do silêncio,
# e o GRA-49 saiu com pausas de 1 a 1,8 s que a EDL não via. O Máquina fica em ~0,36 s.
PAUSA_MAX_AUDIO = {"normal": 0.5, "dinamico": 0.3, "bem_dinamico": 0.22}
RESPIRO_S = 0.08  # silêncio que fica antes da fala quando a pausa é encurtada
# 13/11/2026: depois da fala fica mais. O limiar do silêncio (chão + 30% até a fala) lê consoante final fraca ("s", "f", "x") como silêncio,
# e com 0,06 s o corte comia o fim da palavra. Referência da skill shorts: fim = última voz + fricativa (até 180 ms) + 80 ms.
RESPIRO_FIM_S = 0.16


def _silencios_audio(arquivo, limite_s, quadro_s=0.02):
    """Trechos de silêncio real no áudio com mais de limite_s. Limiar relativo à própria gravação
    (chão de ruído + 30% da distância até a fala, nunca abaixo de fala − 24 dB: com noise gate o chão é silêncio digital
    e o limiar ficaria fundo demais), então funciona com microfone baixo ou alto."""
    import numpy as np, subprocess
    sr = 16000
    try:
        pcm = subprocess.run([FFMPEG, "-v", "error", "-i", str(arquivo), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                             capture_output=True, timeout=600).stdout
    except Exception:  # noqa
        return []
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(sr * quadro_s)
    if len(a) < n * 10:
        return []
    q = a[: len(a) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((q ** 2).mean(axis=1)) + 1e-9)
    chao, fala = np.percentile(db, 10), np.percentile(db, 90)
    if fala - chao < 12:  # sem contraste (música, ruído contínuo): não arrisca
        return []
    mudo = db < max(chao + 0.3 * (fala - chao), fala - 24)
    out, ini = [], None
    for i, m in enumerate(np.append(mudo, False)):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            if (i - ini) * quadro_s > limite_s:
                out.append((round(ini * quadro_s, 3), round(i * quadro_s, 3)))
            ini = None
    return out


def _encurtar_pausas(manter, silencios, limite_s, respiro_s=RESPIRO_S, respiro_fim_s=RESPIRO_FIM_S):
    """Tira de dentro dos trechos mantidos o miolo das pausas longas (fica respiro_fim_s depois da fala e respiro_s antes da próxima)."""
    tirar = [(s + respiro_fim_s, e - respiro_s) for s, e in silencios if e - s > max(limite_s, respiro_s + respiro_fim_s + 0.05)]
    novos, cortado = [], 0.0
    for x, y in manter:
        pedacos = [(x, y)]
        for a, z in tirar:
            prox = []
            for u, w in pedacos:
                if z <= u or a >= w:
                    prox.append((u, w)); continue
                if a > u: prox.append((u, a))
                if z < w: prox.append((z, w))
                cortado += min(z, w) - max(a, u)
            pedacos = prox
        novos += [list(p) for p in pedacos if p[1] - p[0] >= 0.12]
    return novos, round(cortado, 2)


def _blocos_de_fala(palavras, min_pausa_s):
    blocos = []
    for p in palavras:
        if blocos and p["inicio"] - blocos[-1]["fim"] <= min_pausa_s:
            blocos[-1]["fim"] = max(blocos[-1]["fim"], p["fim"]); blocos[-1]["palavras"].append(p)
        else:
            blocos.append({"inicio": p["inicio"], "fim": p["fim"], "palavras": [p]})
    for b in blocos:
        b["texto"] = " ".join(x["palavra"] for x in b["palavras"])
    return blocos


def _repeticoes(segmentos, janela_s, similaridade=0.72, n_abertura=4, similaridade_com_abertura=0.55):
    """Devolve índices de segmentos a remover (a tomada anterior quando a frase se repete).
    13/11/2026: abertura igual sozinha não basta ("você precisa de luz…" / "você precisa de um microfone…" são frases diferentes e a
    primeira sumia): com a mesma abertura a frase inteira ainda precisa de similaridade >= 0,55. Quando a versão que fica é bem mais curta
    que a tirada, marca `conferir` (pode ser o take abandonado no lugar do bom)."""
    remover = {}
    for i, s in enumerate(segmentos):
        ni = normalizar(s["texto"]); ab_i = " ".join(ni.split()[:n_abertura])
        if len(ni.split()) < 3:
            continue
        for j in range(i - 1, -1, -1):
            t = segmentos[j]
            if s["inicio"] - t["fim"] > janela_s:
                break
            if j in remover:
                continue
            nj = normalizar(t["texto"]); ab_j = " ".join(nj.split()[:n_abertura])
            if len(nj.split()) < 3:
                continue
            r = difflib.SequenceMatcher(None, ni, nj).ratio()
            if r >= similaridade or (ab_i == ab_j and r >= similaridade_com_abertura):
                info = {"motivo": "refação (frase repetida)", "parecida_com": i, "similaridade": round(r, 2)}
                if len(ni.split()) < 0.7 * len(nj.split()):
                    info["conferir"] = "a versão que fica é bem mais curta que a tirada: confira se o take bom não é o anterior"
                remover[j] = info
                break
    return remover


# Fase E (08/11/2026): recomeço dentro da frase. O Revisor do GRA-49 achou "agora vai depender… agora vai depender", "é basicamente… é basicamente"
# e "e vou procurar… vou procurar" que a EDL deixou: o Whisper junta a tomada repetida numa palavra só (ou num buraco de 1–3 s), e a
# comparação por segmento não via. Agora: (1) retranscrição literal só dos trechos suspeitos; (2) detector de recomeço palavra a palavra.
COMUNS = {"e", "o", "a", "os", "as", "de", "do", "da", "dos", "das", "que", "um", "uma", "eu", "voce", "ce", "pra", "no", "na", "se", "ele", "ela",
          "isso", "esse", "essa", "ai", "tipo", "entao", "ne", "so", "mais", "mas", "com", "por", "em", "ja", "tem", "vai", "eh", "e", "ta", "aqui"}
PROMPT_LITERAL = "Então, é, é basicamente, tipo, é... é que, é que eu, repetindo as palavras exatamente como faladas."
_MODELO_LITERAL = {}


def _reinicios(palavras, max_n=6, max_meio=6, janela_s=5.0):
    """Recomeços: uma sequência de 2 a max_n palavras (não só palavras comuns) que se repete logo depois, com até max_meio palavras abandonadas no meio.
    Devolve [(inicio, fim, texto)] da tomada que sai (da primeira palavra da sequência até a palavra antes da repetição)."""
    tok = [normalizar(p["palavra"]) for p in palavras]
    out, i = [], 0
    while i < len(tok):
        achou = None
        for n in range(max_n, 1, -1):
            seq = tok[i:i + n]
            if len(seq) < n or not all(seq) or all(w in COMUNS for w in seq):
                continue
            for meio in range(0, max_meio + 1):
                j = i + n + meio
                if tok[j:j + n] == seq and palavras[j]["inicio"] - palavras[i + n - 1]["fim"] < janela_s:
                    achou = (n, j); break
            if achou:
                break
        if achou:
            n, j = achou
            out.append((palavras[i]["inicio"], palavras[j]["inicio"], " ".join(p["palavra"] for p in palavras[i:j + n])))
            i = j
        else:
            i += 1
    return out


def _fala_em(silencios, a, b):
    """Segundos com som de fala entre a e b (o que não é silêncio)."""
    mudo = sum(max(0.0, min(b, e) - max(a, s)) for s, e in silencios)
    return max(0.0, (b - a) - mudo)


def janelas_suspeitas(palavras, silencios, buraco_s=0.7, palavra_longa_s=1.0, fala_min_s=0.35, folga_s=1.5):
    """Trechos onde o áudio tem fala que a transcrição não mostra: buraco entre palavras ou palavra esticada, com som de fala dentro."""
    js = []
    for k, p in enumerate(palavras):
        if p["fim"] - p["inicio"] > palavra_longa_s and _fala_em(silencios, p["inicio"], p["fim"]) > palavra_longa_s * 0.6:
            js.append([p["inicio"], p["fim"]])
        if k + 1 < len(palavras):
            a, b = p["fim"], palavras[k + 1]["inicio"]
            if b - a > buraco_s and _fala_em(silencios, a, b) >= fala_min_s:
                js.append([a, b])
    js = sorted([max(0.0, a - folga_s), b + folga_s] for a, b in js)
    juntas = []
    for a, b in js:
        if juntas and a <= juntas[-1][1]:
            juntas[-1][1] = max(juntas[-1][1], b)
        else:
            juntas.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in juntas]


def _transcrever_literal(arquivo, a, b, modelo="small"):
    """Palavras do trecho [a, b] transcritas sem condicionamento e com prompt de fala literal (o Whisper mostra a repetição)."""
    import subprocess, tempfile, os
    from faster_whisper import WhisperModel
    if modelo not in _MODELO_LITERAL:
        _MODELO_LITERAL[modelo] = WhisperModel(modelo, device="cpu", compute_type="int8")
    fd, wav = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    try:
        subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", str(arquivo), "-ac", "1", "-ar", "16000", wav], check=True, timeout=120)
        segs, _ = _MODELO_LITERAL[modelo].transcribe(wav, language="pt", word_timestamps=True, vad_filter=False, condition_on_previous_text=False, initial_prompt=PROMPT_LITERAL)
        return [{"palavra": w.word.strip(), "inicio": round(float(a + w.start), 3), "fim": round(float(a + w.end), 3), "prob": round(float(w.probability), 3), "literal": True}
                for sg in segs for w in (sg.words or []) if w.word.strip()]
    finally:
        os.unlink(wav)


def refinar_literal(palavras, arquivo, silencios, transcrever=None, borda_s=0.4, max_janelas=40):
    """Troca as palavras de cada janela suspeita pela retranscrição literal (só o miolo, longe das bordas, para não duplicar palavra).
    Devolve (palavras novas, resumo)."""
    transcrever = transcrever or _transcrever_literal
    js = janelas_suspeitas(palavras, silencios)[:max_janelas]
    novas = list(palavras); trocas = []
    for a, b in js:
        try:
            lit = transcrever(arquivo, a, b)
        except Exception as e:  # noqa
            trocas.append({"janela": [a, b], "erro": str(e)[:120]}); continue
        lo, hi = a + borda_s, b - borda_s
        miolo = [w for w in lit if lo <= w["inicio"] < hi]
        antes = [w for w in novas if lo <= w["inicio"] < hi]
        if len(miolo) <= len(antes):  # a literal não achou nada a mais
            continue
        novas = sorted([w for w in novas if not (lo <= w["inicio"] < hi)] + miolo, key=lambda w: w["inicio"])
        trocas.append({"janela": [a, b], "antes": " ".join(w["palavra"] for w in antes), "literal": " ".join(w["palavra"] for w in miolo)})
    return novas, {"janelas": len(js), "trocas": [t for t in trocas if "literal" in t], "erros": [t for t in trocas if "erro" in t]}


def propor_cortes(palavras_json, saida_edl, min_pausa_s=0.3, margem_s=0.08, max_remocao=0.25,
                  remover_repeticoes=True, janela_repeticao_s=15.0, remover_vicios=True, modo="normal", pausa_max_audio_s=None, literal=True, _transcrever=None):
    d = ler_json(palavras_json)
    palavras, segmentos = d["palavras"], d.get("segmentos", [])
    dur = float(d.get("duracao_s") or (palavras[-1]["fim"] if palavras else 0))
    if not palavras:
        raise ErroFerramenta("Transcrição sem palavras: não há o que cortar.")
    # 13/11/2026: margens antigas (0,05 s no dinâmico, 0,03 s no bem dinâmico) comiam sílaba: o Whisper adianta o fim da palavra.
    # O ritmo vem de tirar pausa, não de apertar a borda da fala. Fim da fala com folga maior que o começo.
    if modo == "dinamico":
        min_pausa_s = min(min_pausa_s, 0.25); margem_s = min(margem_s, 0.07)
    elif modo == "bem_dinamico":
        min_pausa_s = min(min_pausa_s, 0.18); margem_s = min(margem_s, 0.06)
    margem_fim_s = max(margem_s + 0.04, 0.10)

    removidos = []
    excluir = []  # intervalos [inicio, fim] de fala que saem
    lit_info = None
    if remover_repeticoes and literal and d.get("arquivo"):
        try:
            sil_fino = _silencios_audio(caminho(d["arquivo"]), 0.04)
            palavras, lit_info = refinar_literal(palavras, caminho(d["arquivo"]), sil_fino, transcrever=_transcrever)
        except Exception as e:  # noqa
            lit_info = {"erro": str(e)[:160]}
    if remover_repeticoes:
        for a, z, texto in _reinicios(palavras):
            excluir.append((a, z))
            removidos.append({"inicio": round(a, 3), "fim": round(z, 3), "motivo": "recomeço (tomada abandonada)", "texto": texto})
    if remover_repeticoes and segmentos:
        for j, info in _repeticoes(segmentos, janela_repeticao_s).items():
            s = segmentos[j]
            excluir.append((s["inicio"], s["fim"]))
            fica = segmentos[info["parecida_com"]]
            removidos.append({"inicio": s["inicio"], "fim": s["fim"], "motivo": info["motivo"], "texto": s["texto"], "similaridade": info["similaridade"],
                              "fica_a_versao": fica["texto"], "fica_inicio": fica["inicio"], "fica_fim": fica["fim"],
                              **({"conferir": info["conferir"]} if info.get("conferir") else {})})

    blocos = _blocos_de_fala(palavras, min_pausa_s)
    manter = []
    for b in blocos:
        if remover_vicios and len(b["palavras"]) <= 2 and all(normalizar(p["palavra"]) in VICIOS for p in b["palavras"]):
            removidos.append({"inicio": b["inicio"], "fim": b["fim"], "motivo": "vício de linguagem isolado", "texto": b["texto"]}); continue
        ini, fim = b["inicio"], b["fim"]
        pedacos = [(ini, fim)]
        for (a, z) in excluir:  # recorta trechos excluídos de dentro do bloco
            novos = []
            for (x, y) in pedacos:
                if z <= x or a >= y:
                    novos.append((x, y)); continue
                if a > x: novos.append((x, a))
                if z < y: novos.append((z, y))
            pedacos = novos
        for (x, y) in pedacos:
            if y - x >= 0.2:
                manter.append([max(0.0, x - margem_s), min(dur, y + margem_fim_s)])
    # junta trechos que encostam
    manter.sort(); juntos = []
    for x, y in manter:
        if juntos and x - juntos[-1][1] <= 0.15:
            juntos[-1][1] = max(juntos[-1][1], y)
        else:
            juntos.append([x, y])
    # pausas longas que o Whisper escondeu dentro das palavras: confere no áudio
    limite = pausa_max_audio_s if pausa_max_audio_s is not None else PAUSA_MAX_AUDIO.get(modo, 0.5)
    pausas_audio = 0.0; arq = d.get("arquivo")
    if limite and limite > 0 and arq:
        try:
            juntos, pausas_audio = _encurtar_pausas(juntos, _silencios_audio(caminho(arq), limite), limite)
        except Exception:  # noqa
            pausas_audio = 0.0
    # pausas removidas (para o relatório)
    cursor = 0.0
    for x, y in juntos:
        if x - cursor >= min(min_pausa_s, limite or min_pausa_s):
            removidos.append({"inicio": round(cursor, 3), "fim": round(x, 3), "motivo": "pausa", "texto": ""})
        cursor = y
    if dur - cursor >= min_pausa_s:
        removidos.append({"inicio": round(cursor, 3), "fim": round(dur, 3), "motivo": "pausa", "texto": ""})
    final = round(sum(y - x for x, y in juntos), 3)
    fracao = round(1 - final / dur, 3) if dur else 0.0
    edl = {
        "origem": d.get("arquivo"), "palavras_json": str(caminho(palavras_json)),
        "parametros": {"min_pausa_s": min_pausa_s, "margem_s": margem_s, "margem_fim_s": margem_fim_s, "modo": modo, "max_remocao": max_remocao,
                       "pausa_max_audio_s": limite, "pausas_encurtadas_no_audio_s": pausas_audio},
        "literal": lit_info,
        "duracao_original_s": round(dur, 3), "duracao_final_s": final, "fracao_removida": fracao,
        "precisa_aprovacao": fracao > max_remocao,
        "resumo_motivos": {m: round(sum(r["fim"] - r["inicio"] for r in removidos if r["motivo"] == m), 2)
                           for m in sorted({r["motivo"] for r in removidos})},
        "manter": [{"inicio": round(x, 3), "fim": round(y, 3)} for x, y in juntos],
        "removidos": sorted(removidos, key=lambda r: r["inicio"]),
    }
    out = salvar_json(saida_edl, edl)
    return {"edl_json": out, "duracao_original_s": edl["duracao_original_s"], "duracao_final_s": final,
            "fracao_removida": fracao, "precisa_aprovacao": edl["precisa_aprovacao"], "n_trechos_mantidos": len(juntos),
            "n_removidos": len(removidos), "resumo_motivos": edl["resumo_motivos"],
            "conferir_takes": [{"inicio": r["inicio"], "tirado": r["texto"][:80], "fica": r["fica_a_versao"][:80], "motivo": r["conferir"]} for r in edl["removidos"] if r.get("conferir")],
            "literal": {"janelas": lit_info.get("janelas"), "trocas": len(lit_info.get("trocas", []))} if lit_info and "janelas" in lit_info else lit_info}


def aplicar_cortes(video, edl_json, saida_video, saida_palavras=None, crf=18, preset="veryfast"):
    v = caminho(video); edl = ler_json(edl_json); segs = edl["manter"]
    if not segs:
        raise ErroFerramenta("EDL sem trechos a manter.")
    info = info_midia(v)
    out = caminho_saida(saida_video)
    partes_v, partes_a, fc = [], [], []
    for i, s in enumerate(segs):
        fc.append(f"[0:v]trim=start={s['inicio']}:end={s['fim']},setpts=PTS-STARTPTS[v{i}]"); partes_v.append(f"[v{i}]")
        if info["tem_audio"]:
            # fade curto nas bordas de cada trecho (07/11, fase D): a emenda seca estalava no corte; a duração não muda
            d = max(0.0, s["fim"] - s["inicio"]); f = min(FADE_CORTE_S, d / 4)
            fades = f",afade=t=in:d={f:.3f},afade=t=out:st={max(0.0, d - f):.3f}:d={f:.3f}" if f > 0.001 else ""
            fc.append(f"[0:a]atrim=start={s['inicio']}:end={s['fim']},asetpts=PTS-STARTPTS{fades}[a{i}]"); partes_a.append(f"[a{i}]")
    n = len(segs)
    if info["tem_audio"]:
        fc.append("".join(f"{a}{b}" for a, b in zip(partes_v, partes_a)) + f"concat=n={n}:v=1:a=1[v][a]")
        mapas = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    else:
        fc.append("".join(partes_v) + f"concat=n={n}:v=1:a=0[v]"); mapas = ["-map", "[v]"]
    rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v, "-filter_complex", ";".join(fc)] + mapas +
          ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    res = {"video": str(out), "duracao_s": info_midia(out)["duracao_s"], "n_trechos": n}
    if saida_palavras:
        d = ler_json(edl["palavras_json"]); novas = []; deslocs = []; acc = 0.0
        for s in segs:
            deslocs.append((s["inicio"], s["fim"], acc)); acc += s["fim"] - s["inicio"]
        def remap(t):
            for a, z, off in deslocs:
                if a <= t <= z:
                    return round(off + (t - a), 3)
            return None
        for p in d["palavras"]:
            ni, nf = remap(p["inicio"]), remap(p["fim"])
            if ni is None and nf is None:
                continue
            if ni is None: ni = nf
            if nf is None: nf = ni
            novas.append({**p, "inicio": ni, "fim": max(ni, nf)})
        segmentos = []
        for s in d.get("segmentos", []):
            ws = [p for p in novas if any(a <= p["inicio"] <= z for a, z, _ in deslocs)]
            ni, nf = remap(s["inicio"]), remap(s["fim"])
            if ni is None and nf is None:
                continue
            segmentos.append({"inicio": ni if ni is not None else nf, "fim": nf if nf is not None else ni, "texto": s["texto"]})
        res["palavras_json"] = salvar_json(saida_palavras, {**d, "arquivo": str(out), "duracao_s": res["duracao_s"],
                                                           "origem_edl": str(caminho(edl_json)), "palavras": novas, "segmentos": segmentos,
                                                           "n_palavras": len(novas), "n_segmentos": len(segmentos)})
        res["n_palavras"] = len(novas)
    return res


def ajustar_edl(edl_json, saida_edl, manter_extra=None, remover_extra=None, motivo="ajuste do editor"):
    """Ajusta uma EDL: manter_extra devolve trechos (lista de [inicio, fim] no tempo ORIGINAL) que tinham sido removidos;
    remover_extra tira trechos (idem) que estavam mantidos. Recalcula duração, fração e lista de removidos."""
    edl = ler_json(edl_json); dur = float(edl["duracao_original_s"])
    manter = [[m["inicio"], m["fim"]] for m in edl["manter"]]
    for a, z in (manter_extra or []):
        manter.append([max(0.0, float(a)), min(dur, float(z))])
    novos = []
    for a, z in sorted(manter):
        if novos and a <= novos[-1][1] + 0.01:
            novos[-1][1] = max(novos[-1][1], z)
        else:
            novos.append([a, z])
    manter = novos
    removidos = [r for r in edl["removidos"] if r.get("motivo") != motivo]
    for a, z in (remover_extra or []):
        a, z = float(a), float(z); cortados = []
        for x, y in manter:
            if z <= x or a >= y:
                cortados.append([x, y]); continue
            if a > x: cortados.append([x, a])
            if z < y: cortados.append([z, y])
        manter = [c for c in cortados if c[1] - c[0] >= 0.1]
        removidos.append({"inicio": round(a, 3), "fim": round(z, 3), "motivo": motivo, "texto": ""})
    # pausas recomputadas: remove 'pausa' antigas e recalcula a partir dos buracos
    removidos = [r for r in removidos if r.get("motivo") != "pausa"]
    cursor = 0.0
    for x, y in manter:
        if x - cursor >= 0.2:
            removidos.append({"inicio": round(cursor, 3), "fim": round(x, 3), "motivo": "pausa", "texto": ""})
        cursor = y
    if dur - cursor >= 0.2:
        removidos.append({"inicio": round(cursor, 3), "fim": round(dur, 3), "motivo": "pausa", "texto": ""})
    # trechos devolvidos saem da lista de removidos
    if manter_extra:
        def coberto(r):
            return any(float(a) <= r["inicio"] and r["fim"] <= float(z) for a, z in manter_extra)
        removidos = [r for r in removidos if not coberto(r)]
    final = round(sum(y - x for x, y in manter), 3); fracao = round(1 - final / dur, 3) if dur else 0.0
    edl.update({"manter": [{"inicio": round(x, 3), "fim": round(y, 3)} for x, y in manter], "removidos": sorted(removidos, key=lambda r: r["inicio"]),
                "duracao_final_s": final, "fracao_removida": fracao, "precisa_aprovacao": fracao > edl["parametros"].get("max_remocao", 0.25),
                "ajustes": edl.get("ajustes", []) + [{"manter_extra": manter_extra or [], "remover_extra": remover_extra or [], "motivo": motivo}]})
    out = salvar_json(saida_edl, edl)
    return {"edl_json": out, "duracao_final_s": final, "fracao_removida": fracao, "precisa_aprovacao": edl["precisa_aprovacao"], "n_trechos_mantidos": len(manter)}


# 11/11/2026 (GRA-66): cortar + remapear palavras + legenda numa chamada só, sem o agente escrever script na hora.
# O remapeamento antigo (dentro de aplicar_cortes) usava as durações nominais da EDL, descartava palavra esticada pelo Whisper por cima do corte
# e acumulava drift (0,27 s no fim do GRA-66). Aqui: durações reais de cada trecho (quadros do vídeo, áudio com pausa preenchida) e regra de fronteira.
MIN_SOBREPOSICAO_S = 0.15  # palavra com ao menos isto de fala dentro do trecho mantido fica (o Whisper estica a palavra por cima do silêncio cortado)
PALAVRA_MIN_S = 0.04


def duracoes_reais(manter, fps):
    """Duração de cada trecho mantido como o ffmpeg (trim + atrim + concat) realmente grava: o vídeo vira número inteiro de quadros
    (quadros com pts em [inicio, fim)); o áudio é exato e o concat completa o lado mais curto, então vale o maior dos dois."""
    import math
    out = []
    for s in manter:
        nominal = float(s["fim"]) - float(s["inicio"])
        if fps:
            n = math.ceil(float(s["fim"]) * fps - 1e-6) - math.ceil(float(s["inicio"]) * fps - 1e-6)
            out.append(max(nominal, n / fps))
        else:
            out.append(nominal)
    return out


def remapear_palavras(palavras, manter, duracoes=None, segmentos=None):
    """Palavras (tempo do trecho original) → tempo do vídeo cortado. Cada palavra vai para o trecho mantido onde tem mais fala:
    fica se tiver >= 50% da duração ou >= MIN_SOBREPOSICAO_S dentro dele (recortada ao trecho); some só quando caiu em trecho cortado.
    Devolve (palavras, segmentos, descartadas, n_recortadas_na_borda). Sem retranscrição: o tempo vem só da EDL."""
    duracoes = duracoes or [float(s["fim"]) - float(s["inicio"]) for s in manter]
    deslocs, acc = [], 0.0
    for s, d in zip(manter, duracoes):
        deslocs.append((float(s["inicio"]), float(s["fim"]), acc)); acc += d

    def melhor(i, f):
        best, bo = None, 0.0
        for k, (a, z, _) in enumerate(deslocs):
            o = min(f, z) - max(i, a)
            if o > bo:
                best, bo = k, o
        return best, bo

    novas, descartadas, bordas = [], [], 0
    for p in palavras:
        i, f = float(p["inicio"]), float(p["fim"])
        k, o = melhor(i, f)
        dur = f - i
        if k is None and dur <= 0.001:  # palavra de duração zero: vale se cair dentro de um trecho
            k = next((j for j, (a, z, _) in enumerate(deslocs) if a <= i <= z), None); o = dur
        if k is None or not (o >= 0.5 * dur or o >= MIN_SOBREPOSICAO_S):
            descartadas.append(p); continue
        a, z, off = deslocs[k]
        ci, cf = max(i, a), min(f, z)
        if cf - ci < dur - 0.001:
            bordas += 1
        ni, nf = round(off + (ci - a), 3), round(off + (cf - a), 3)
        if nf - ni < PALAVRA_MIN_S:
            nf = ni + PALAVRA_MIN_S
        novas.append({**p, "inicio": ni, "fim": nf})
    # palavra de borda nunca atravessa para a seguinte: mantém a ordem sem sobreposição
    for x, y in zip(novas, novas[1:]):
        if y["inicio"] < x["fim"]:
            x["fim"] = max(x["inicio"], y["inicio"])
    segs = []
    for s in (segmentos or []):
        k, o = melhor(float(s["inicio"]), float(s["fim"]))
        if k is None:
            continue
        a, z, off = deslocs[k]
        segs.append({"inicio": round(off + max(float(s["inicio"]), a) - a, 3), "fim": round(off + min(float(s["fim"]), z) - a, 3), "texto": s["texto"]})
    return novas, segs, descartadas, bordas


def cortar_e_legendar(video, palavras_json, edl_json, saida_video, saida_palavras, formatos="9x16", estilo=None, saida_ass_prefixo=None,
                      crf=18, preset="veryfast", saida_srt=False):
    """Aplica a EDL (aplicar_cortes), remapeia as palavras pelos trechos mantidos e gera a legenda ASS de cada formato.
    `estilo`: dict de estilo já carregado (o servidor resolve o nome); None = padrão do gerar_legenda. formatos: "9x16,16x9" ou "" para não gerar legenda."""
    from . import legenda as _leg
    if estilo is None:
        from pathlib import Path as _P
        estilo = ler_json(_P(__file__).resolve().parents[3] / "estilos" / "padrao.json")
    edl = ler_json(edl_json); manter = edl["manter"]
    d = ler_json(palavras_json)
    v = caminho(video)
    res_c = aplicar_cortes(video, edl_json, saida_video, saida_palavras=None, crf=crf, preset=preset)
    out = res_c["video"]; info = info_midia(out); fps = info_midia(v)["fps"]
    durs = duracoes_reais(manter, fps)
    esperado = round(sum(durs), 3); nominal = round(sum(float(s["fim"]) - float(s["inicio"]) for s in manter), 3)
    real = info["duracao_s"]; drift = round(real - esperado, 3)
    quadro = (1.0 / fps) if fps else 0.04
    avisos = []
    if abs(drift) > quadro:  # o modelo de quadros não explicou o arquivo: reparte o resíduo por duração (não acumula no fim)
        k = real / esperado if esperado else 1.0
        durs = [x * k for x in durs]
        avisos.append(f"drift de {drift:+.3f} s entre o esperado ({esperado} s) e o arquivo ({real} s): tempos reescalados por trecho")
    novas, segs, descartadas, bordas = remapear_palavras(d["palavras"], manter, durs, d.get("segmentos"))
    fim_palavras = novas[-1]["fim"] if novas else 0.0
    if fim_palavras > real + 0.05:
        avisos.append(f"última palavra termina em {fim_palavras} s, depois do fim do vídeo ({real} s)")
    if descartadas:
        avisos.append(f"{len(descartadas)} palavra(s) caíram em trecho cortado: " + " ".join(p["palavra"] for p in descartadas[:12]) + (" …" if len(descartadas) > 12 else ""))
    pj = salvar_json(saida_palavras, {**d, "arquivo": str(out), "duracao_s": real, "origem_edl": str(caminho(edl_json)), "palavras": novas, "segmentos": segs,
                                      "n_palavras": len(novas), "n_segmentos": len(segs)})
    legendas = {}
    fmts = [f.strip() for f in str(formatos or "").split(",") if f.strip()]
    if fmts and not novas:
        avisos.append("nenhuma palavra sobrou: legenda não gerada"); fmts = []
    prefixo = saida_ass_prefixo or str(caminho_saida(saida_palavras).with_suffix("")) + "_legenda"
    for fm in fmts:
        r = _leg.gerar_legenda(pj, f"{prefixo}_{fm}.ass", estilo, formato=fm, saida_srt=(f"{prefixo}_{fm}.srt" if saida_srt else None))
        legendas[fm] = {"ass": r["ass"], "srt": r.get("srt"), "n_linhas": r["n_linhas"]}
    return {"video": str(out), "palavras_json": pj, "legendas": legendas, "n_trechos": len(manter),
            "palavras_mantidas": len(novas), "palavras_descartadas": len(descartadas), "palavras_recortadas_na_borda": bordas,
            "duracao_nominal_s": nominal, "duracao_esperada_s": esperado, "duracao_real_s": real, "drift_s": drift,
            "drift_quadros": round(drift / quadro, 2), "avisos": avisos}


# ----------------------------------------------------------------------------------------------------------------- conferir emendas
# 13/11/2026: nenhuma ferramenta mostrava cada emenda como texto. O agente cortava, olhava só drift e avisos, e falas desconexas
# ("…pra você | não precisa…" com a frase do meio tirada) ou palavra pela metade só apareciam no Revisor, quando apareciam.
CONECTIVOS_SOLTOS = {"e", "mas", "porque", "entao", "que", "ai", "pois", "tambem", "so", "ou"}
FIM_DE_FRASE = (".", "!", "?", "…", ":")


def conferir_emendas(edl_json, palavras_json, contexto=5, max_texto=8000):
    """Lê a EDL contra a transcrição ORIGINAL e devolve, por emenda: instante no vídeo cortado, últimas palavras antes e primeiras depois,
    o que foi tirado no meio e alertas (palavra cortada pela metade, frase interrompida, conectivo solto, palavra repetida na emenda).
    Também devolve o texto final inteiro, para ler de ponta a ponta antes de renderizar. Não muda nada."""
    edl = ler_json(edl_json); d = ler_json(palavras_json)
    manter = [(float(s["inicio"]), float(s["fim"])) for s in edl.get("manter", [])]
    pals = d.get("palavras", [])
    if not manter or not pals:
        raise ErroFerramenta("EDL ou transcrição vazia.")

    def dentro(p, a, z):
        i, f = float(p["inicio"]), float(p["fim"]); dur = max(f - i, 1e-3)
        return max(0.0, min(f, z) - max(i, a)) / dur

    por_trecho = [[p for p in pals if dentro(p, a, z) >= 0.5] for a, z in manter]
    texto_final = " ".join(p["palavra"].strip() for t in por_trecho for p in t)
    emendas, acc = [], 0.0
    for k in range(len(manter) - 1):
        (a, z), (a2, z2) = manter[k], manter[k + 1]
        acc += z - a
        antes, depois = por_trecho[k][-contexto:], por_trecho[k + 1][:contexto]
        tirado = [p for p in pals if float(p["inicio"]) >= z - 0.02 and float(p["fim"]) <= a2 + 0.02 and dentro(p, a, z) < 0.5 and dentro(p, a2, z2) < 0.5]
        alertas = []
        for p in pals:
            for borda, (x, y), lado in ((z, (a, z), "fim"), (a2, (a2, z2), "começo")):
                fr = dentro(p, x, y)
                if float(p["inicio"]) < borda < float(p["fim"]) and 0.15 < fr < 0.85:
                    alertas.append(f"palavra cortada no {lado}: '{p['palavra'].strip()}' ({round(fr * 100)}% fica)")
        ult = antes[-1]["palavra"].strip() if antes else ""; pri = depois[0]["palavra"].strip() if depois else ""
        if tirado and ult and not ult.endswith(FIM_DE_FRASE):
            alertas.append("frase interrompida: o trecho antes não fecha a frase e há fala tirada no meio; leia se faz sentido")
        if tirado and normalizar(pri) in CONECTIVOS_SOLTOS:
            alertas.append(f"começa em conectivo ('{pri}') depois de fala tirada: confira se liga com o que vem antes")
        if ult and pri and normalizar(ult) == normalizar(pri):
            alertas.append(f"palavra repetida na emenda ('{pri}')")
        emendas.append({"n": k + 1, "instante_s": round(acc, 2), "origem_s": [round(z, 2), round(a2, 2)],
                        "antes": " ".join(p["palavra"].strip() for p in antes), "depois": " ".join(p["palavra"].strip() for p in depois),
                        "tirado": " ".join(p["palavra"].strip() for p in tirado)[:200], "tirado_s": round(a2 - z, 2), "alertas": alertas})
    com = [e for e in emendas if e["alertas"]]
    return {"n_emendas": len(emendas), "n_com_alerta": len(com), "emendas": emendas,
            "resumo": [f"{e['instante_s']}s: …{e['antes'][-40:]} | {e['depois'][:40]}… → {'; '.join(e['alertas'])}" for e in com][:20],
            "texto_final": texto_final[:max_texto] + (" …" if len(texto_final) > max_texto else ""),
            "duracao_final_s": round(sum(z - a for a, z in manter), 2)}
