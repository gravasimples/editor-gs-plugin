"""Perfil do Thiago: padrões dos posts já publicados (Instagram e YouTube) lidos do gs.db do GSI, só leitura.
Serve de referência de estilo para o Editor (quais formatos, durações, ganchos e hashtags mais rendem)."""
import collections, json, re, sqlite3, unicodedata
from datetime import datetime
from pathlib import Path


def _con(db: Path):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def calcular(db: Path, proprio_ig=2, proprio_yt=1):
    if not db.exists():
        return {"erro": f"banco do GSI não encontrado: {db}"}
    con = _con(db); con.row_factory = sqlite3.Row
    try:
        ig = con.execute("""select p.shortcode, p.post_type, p.product_type, p.posted_at, p.video_duration_s, p.caption, p.hashtags_json, p.url, p.is_pinned,
            (select max(likes) from ig_post_metrics m where m.shortcode=p.shortcode) likes, (select max(comments) from ig_post_metrics m where m.shortcode=p.shortcode) comments,
            (select max(coalesce(plays,views)) from ig_post_metrics m where m.shortcode=p.shortcode) plays
            from ig_posts p where p.source_id=? order by p.posted_at desc""", (proprio_ig,)).fetchall()
        yt = con.execute("""select v.video_id, v.title, v.published_at, v.duration_s, v.format,
            (select max(views) from yt_video_metrics m where m.video_id=v.video_id) views, (select max(likes) from yt_video_metrics m where m.video_id=v.video_id) likes,
            (select max(comments) from yt_video_metrics m where m.video_id=v.video_id) comments, (select max(avg_view_percentage) from yt_video_metrics m where m.video_id=v.video_id) retencao
            from yt_videos v where v.source_id=? order by v.published_at desc""", (proprio_yt,)).fetchall()
        perfil = con.execute("select captured_on, followers, posts_count from profile_metrics where source_id=? order by captured_at desc limit 1", (proprio_ig,)).fetchone()
        coment = con.execute("""select c.text, c.likes, p.caption from ig_comments c join ig_posts p on p.shortcode=c.shortcode where p.source_id=? and c.is_owner=0 order by c.likes desc limit 12""", (proprio_ig,)).fetchall()
    finally:
        con.close()
    def tipo(r):
        return {"Video": "reels", "Sidecar": "carrossel", "Image": "imagem"}.get(r["post_type"], r["post_type"] or "?")
    posts = []
    for r in ig:
        cap = (r["caption"] or "").strip(); primeira = re.split(r"[\n.!?]", cap, 1)[0][:90]
        posts.append({"shortcode": r["shortcode"], "tipo": tipo(r), "data": (r["posted_at"] or "")[:10], "duracao_s": r["video_duration_s"], "gancho": primeira, "legenda": cap[:300],
                      "hashtags": json.loads(r["hashtags_json"] or "[]"), "url": r["url"], "fixado": bool(r["is_pinned"]), "plays": r["plays"], "likes": r["likes"], "comentarios": r["comments"],
                      "cta_comentario": bool(re.search(r"coment[ae]\s+[\"“”']", cap, re.I))})
    por_tipo = collections.defaultdict(list)
    for p in posts:
        por_tipo[p["tipo"]].append(p)
    def mediana(xs):
        xs = sorted(x for x in xs if x is not None); return xs[len(xs) // 2] if xs else None
    resumo_tipos = {t: {"n": len(ps), "mediana_plays": mediana([p["plays"] for p in ps]), "mediana_likes": mediana([p["likes"] for p in ps]), "mediana_comentarios": mediana([p["comentarios"] for p in ps]),
                        "mediana_duracao_s": mediana([p["duracao_s"] for p in ps])} for t, ps in por_tipo.items()}
    hashtags = collections.Counter(h.lower() for p in posts for h in p["hashtags"])
    dias = collections.Counter(); horas = collections.Counter()
    for r in ig:
        try:
            d = datetime.fromisoformat((r["posted_at"] or "").replace("Z", "+00:00")); dias[d.strftime("%a")] += 1; horas[d.hour] += 1
        except Exception:
            pass
    faixa = collections.Counter()
    for p in por_tipo.get("reels", []):
        if p["duracao_s"]:
            faixa["até 15 s" if p["duracao_s"] <= 15 else "16–30 s" if p["duracao_s"] <= 30 else "31–60 s" if p["duracao_s"] <= 60 else "61–90 s" if p["duracao_s"] <= 90 else "mais de 90 s"] += 1
    def top(ps, chave, n=8):
        return sorted([p for p in ps if p.get(chave) is not None], key=lambda p: -p[chave])[:n]
    top_plays = top(posts, "plays"); top_coment = top(posts, "comentarios"); top_likes = top(posts, "likes")
    # taxa: likes por mil plays em reels
    taxas = [1000 * p["likes"] / p["plays"] for p in por_tipo.get("reels", []) if p["plays"] and p["likes"]]
    ytv = [{"video_id": r["video_id"], "titulo": r["title"], "data": (r["published_at"] or "")[:10], "duracao_s": r["duration_s"], "formato": r["format"], "views": r["views"], "likes": r["likes"], "comentarios": r["comments"], "retencao": r["retencao"]} for r in yt]
    return {"gerado_em": datetime.now().isoformat(timespec="seconds"), "fonte": str(db), "perfil": dict(perfil) if perfil else None, "n_posts": len(posts), "periodo": [posts[-1]["data"], posts[0]["data"]] if posts else None,
            "por_tipo": resumo_tipos, "faixas_duracao_reels": dict(faixa), "likes_por_mil_plays_mediana": round(mediana(taxas), 1) if taxas else None,
            "hashtags_top": hashtags.most_common(15), "dias_semana": dict(dias), "horas": dict(sorted(horas.items())),
            "top_plays": top_plays, "top_comentarios": top_coment, "top_likes": top_likes, "recentes": posts[:10], "carrosseis": por_tipo.get("carrossel", []),
            "comentarios_top": [{"texto": (c["text"] or "")[:160], "likes": c["likes"], "post": (c["caption"] or "")[:60]} for c in coment],
            "youtube": {"n": len(ytv), "top_views": sorted([v for v in ytv if v["views"]], key=lambda v: -v["views"])[:8], "recentes": ytv[:8], "mediana_duracao_s": mediana([v["duracao_s"] for v in ytv])}}


def markdown(d: dict):
    if d.get("erro"):
        return f"# Perfil do Thiago\n\n{d['erro']}\n"
    L = [f"# Perfil do Thiago — padrões dos posts publicados", "", f"Gerado em {d['gerado_em']} a partir do gs.db do GSI (só leitura). Números são os últimos capturados pelo GSI, não auditados; o período coberto é {d['periodo'][0]} a {d['periodo'][1]} ({d['n_posts']} posts do Instagram)."]
    if d.get("perfil"):
        L.append(f"Seguidores em {d['perfil']['captured_on']}: {d['perfil']['followers']:,} · posts na conta: {d['perfil']['posts_count']}".replace(",", "."))
    L += ["", "## Formatos", "", "| Tipo | Posts | Mediana de plays | Mediana de likes | Mediana de comentários | Duração mediana |", "|---|---|---|---|---|---|"]
    for t, r in d["por_tipo"].items():
        L.append(f"| {t} | {r['n']} | {r['mediana_plays'] or '-'} | {r['mediana_likes'] or '-'} | {r['mediana_comentarios'] or '-'} | {r['mediana_duracao_s'] or '-'} |")
    L += ["", f"Faixas de duração dos Reels: {d['faixas_duracao_reels']}", f"Likes por mil plays (mediana dos Reels): {d['likes_por_mil_plays_mediana']}", f"Dias da semana: {d['dias_semana']} · horas (UTC): {d['horas']}", "",
          "## Reels com mais plays", "", "| Data | Dur. | Plays | Likes | Coment. | Gancho (primeira frase da legenda) |", "|---|---|---|---|---|---|"]
    for p in d["top_plays"]:
        L.append(f"| {p['data']} | {p['duracao_s'] or '-'} | {p['plays']} | {p['likes']} | {p['comentarios']} | {p['gancho']} |")
    L += ["", "## Posts com mais comentários", "", "| Data | Tipo | Coment. | Likes | CTA de comentário? | Gancho |", "|---|---|---|---|---|---|"]
    for p in d["top_comentarios"]:
        L.append(f"| {p['data']} | {p['tipo']} | {p['comentarios']} | {p['likes']} | {'sim' if p['cta_comentario'] else 'não'} | {p['gancho']} |")
    L += ["", "## Carrosséis publicados", "", "| Data | Likes | Coment. | Primeira frase |", "|---|---|---|---|"]
    for p in d["carrosseis"]:
        L.append(f"| {p['data']} | {p['likes'] or '-'} | {p['comentarios'] or '-'} | {p['gancho']} |")
    L += ["", "## Hashtags mais usadas", "", ", ".join(f"#{h} ({n})" for h, n in d["hashtags_top"]), "", "## Comentários da audiência com mais likes", ""]
    for c in d["comentarios_top"][:8]:
        L.append(f"- ({c['likes']} likes) {c['texto']}")
    L += ["", "## YouTube", "", f"{d['youtube']['n']} vídeos; duração mediana {d['youtube']['mediana_duracao_s']} s.", "", "| Data | Views | Retenção % | Dur. | Título |", "|---|---|---|---|---|"]
    for v in d["youtube"]["top_views"]:
        L.append(f"| {v['data']} | {v['views']} | {v['retencao'] or '-'} | {v['duracao_s']} | {v['titulo']} |")
    L += ["", "## Como usar", "", "- Referência de ritmo e formato, não de claims: números históricos, não auditados.", "- Ganchos acima são as primeiras frases das legendas; os ganchos falados ficam nos vídeos (baixar como referência quando houver cookies do Instagram).",
          "- Não copiar legendas antigas; usar para calibrar duração, tipo de abertura, uso de CTA de comentário e hashtags."]
    return "\n".join(L) + "\n"


# --- Perfil vivo (03/11/2026): "o que rende" para o Thiago, recalculado sozinho uma vez por dia e lido pelo Editor antes de cada pedido.
# Usa a razão sobre a mediana do formato (performance_snapshots do GSI, último snapshot `current` de cada peça própria), a duração,
# o tipo de gancho (servico/ganchos.py) e o melhor horário (automação 7). Faixa com menos de 5 peças é marcada como pouca amostra:
# é pista, não regra.
FAIXAS_CURTO = [("até 15 s", 0, 15), ("16–30 s", 15, 30), ("31–60 s", 30, 60), ("61–90 s", 60, 90), ("mais de 90 s", 90, 10 ** 9)]
FAIXAS_LONGO = [("até 5 min", 0, 300), ("5–10 min", 300, 600), ("10–20 min", 600, 1200), ("mais de 20 min", 1200, 10 ** 9)]
NOME_REDE = {"instagram": "Instagram", "youtube": "YouTube"}
ROTULO_FORMATO = {"reel": "Reels", "carrossel": "Carrossel", "imagem": "Imagem", "short": "Shorts", "long": "Vídeo longo", "live": "Live", "live_or_premiere": "Live/estreia"}


def _mediana(xs):
    import statistics
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def _faixas(itens, faixas, min_n=3):
    out = []
    for nome, a, b in faixas:
        g = [i for i in itens if i.get("duracao_s") and a < i["duracao_s"] <= b and i.get("razao") is not None]
        if g:
            out.append({"faixa": nome, "n": len(g), "mediana": _mediana([i["razao"] for i in g]), "pouca_amostra": len(g) < 5})
    return out


def rende(db: Path, ganchos_tipos: list | None = None, horario: dict | None = None, hoje: datetime | None = None):
    """O que rende para o Thiago, pelos números do GSI (só leitura). Sem modelo de linguagem."""
    if not Path(db).exists():
        return {"erro": f"banco do GSI não encontrado: {db}"}
    con = _con(db); con.row_factory = sqlite3.Row
    try:
        rows = con.execute("""select ps.platform, ps.item_id, ps.format, ps.views, ps.ratio_vs_format_median razao, ps.computed_at,
               (select p.video_duration_s from ig_posts p where p.shortcode=ps.item_id) dur_ig, (select v.duration_s from yt_videos v where v.video_id=ps.item_id) dur_yt
            from performance_snapshots ps join (select platform, item_id, max(computed_at) m from performance_snapshots where horizon='current' group by 1, 2) u
              on u.platform=ps.platform and u.item_id=ps.item_id and u.m=ps.computed_at
            where ps.horizon='current' and ps.owner in (select handle from sources where kind='own')""").fetchall()
        coleta = {"instagram": con.execute("select max(captured_at) from ig_post_metrics").fetchone()[0], "youtube": con.execute("select max(captured_at) from yt_video_metrics").fetchone()[0]}
    finally:
        con.close()
    itens = [{"plataforma": r["platform"], "formato": r["format"], "views": r["views"], "razao": r["razao"], "duracao_s": r["dur_ig"] or r["dur_yt"], "quando": r["computed_at"]} for r in rows]
    formatos = []
    for f in sorted({i["formato"] for i in itens if i["formato"]}):
        g = [i for i in itens if i["formato"] == f]; med = [i["razao"] for i in g if i["razao"] is not None]
        formatos.append({"formato": f, "rotulo": ROTULO_FORMATO.get(f, f), "plataforma": g[0]["plataforma"], "n": len(g), "medidos": len(med), "mediana_views": _mediana([i["views"] for i in g])})
    curtos = [i for i in itens if i["formato"] in ("reel", "short")]
    dur = {"reels": _faixas([i for i in curtos if i["formato"] == "reel"], FAIXAS_CURTO), "shorts": _faixas([i for i in curtos if i["formato"] == "short"], FAIXAS_CURTO),
           "youtube_longo": _faixas([i for i in itens if i["formato"] == "long"], FAIXAS_LONGO)}
    ultimo = coleta  # última coleta de métricas de cada rede (o snapshot é recalculado todo dia mesmo sem coleta nova)
    agora = hoje or datetime.now()
    def velho(q):
        try:
            return (agora - datetime.fromisoformat(q.replace("Z", "+00:00")).replace(tzinfo=None)).days
        except Exception:  # noqa
            return None
    pistas = []
    for chave, rot in (("reels", "Reels"), ("shorts", "Shorts"), ("youtube_longo", "vídeo longo do YouTube")):
        firmes = [x for x in dur[chave] if not x["pouca_amostra"]]
        if len(firmes) >= 2:
            m, p = max(firmes, key=lambda x: x["mediana"]), min(firmes, key=lambda x: x["mediana"])
            if m["mediana"] - p["mediana"] >= 0.2:
                pistas.append(f"{rot}: {m['faixa']} rendem mais ({m['mediana']}× a mediana, {m['n']} peças) que {p['faixa']} ({p['mediana']}×, {p['n']}).")
    tipos = [t for t in (ganchos_tipos or []) if t.get("razao_mediana") is not None]
    if len(tipos) >= 2:
        a, b = tipos[0], tipos[-1]
        pistas.append(f"Gancho de {a['rotulo'].lower()} tem a melhor mediana ({a['razao_mediana']}×, {a['medidos']} medidos{', pouca amostra' if a['pouca_amostra'] else ''}); {b['rotulo'].lower()} a pior ({b['razao_mediana']}×).")
    for rede, r in ((horario or {}).get("redes") or {}).items():
        if r.get("melhores") and (r["melhores"][0].get("mediana") or 0) >= 1:  # melhor faixa abaixo da média não é pista
            f = r["melhores"][0]; pistas.append(f"{NOME_REDE.get(rede, rede)}: {f['dia']} · {f['faixa']} é o melhor horário ({f['mediana']}×, {f['n']} posts).")
    avisos = [f"Métricas do {NOME_REDE[p]} paradas há {velho(q)} dias (última coleta {q[:10]}); as pistas dessa rede são do retrato antigo." for p, q in ultimo.items() if q and (velho(q) or 0) > 5]
    return {"gerado_em": datetime.now().isoformat(timespec="minutes"), "n_pecas": len(itens), "formatos": formatos, "duracao": dur, "ganchos": tipos, "horario": horario,
            "pistas": pistas, "avisos": avisos, "ultimo_calculo": ultimo,
            "nota": "Razão = views da peça ÷ mediana do formato na conta (1,0× = na média). Faixa com menos de 5 peças é pista, não regra. Números do GSI, não auditados."}


def rende_markdown(r: dict):
    if r.get("erro"):
        return ""
    L = ["", "## O que rende (atualizado sozinho todo dia)", "", f"Calculado em {r['gerado_em']} sobre {r['n_pecas']} peças próprias. {r['nota']}", ""]
    L += [f"- {a}" for a in r["avisos"]]
    if r["pistas"]:
        L += ["", "Pistas para calibrar o pedido (não são regra; o pedido e o manual vencem):", ""] + [f"- {p}" for p in r["pistas"]]
    for chave, rot in (("reels", "Reels por duração"), ("shorts", "Shorts por duração"), ("youtube_longo", "YouTube longo por duração")):
        if r["duracao"][chave]:
            L += ["", f"### {rot}", "", "| Faixa | Peças | Mediana da razão |", "|---|---|---|"] + [f"| {x['faixa']} | {x['n']} | {x['mediana']}×{' (pouca amostra)' if x['pouca_amostra'] else ''} |" for x in r["duracao"][chave]]
    if r["ganchos"]:
        L += ["", "### Ganchos por tipo", "", "| Tipo | Medidos | Mediana | Melhor exemplo |", "|---|---|---|---|"] + [f"| {t['rotulo']} | {t['medidos']} | {t['razao_mediana']}× | {(t.get('melhor') or '')[:70]} |" for t in r["ganchos"]]
    return "\n".join(L) + "\n"
