"""Redes no app: calendário, comentários e resultados. Tudo só leitura: gs.db do GSI (coletas do YouTube e do Instagram,
snapshots de desempenho), `publicacoes.json` das entregas (Publora) e o Notion Mídias (datas de publicação, lido pelo gateway).
Nada aqui publica, responde ou escreve fora de `workspace/relatorios/`."""
import json, sqlite3, statistics
from datetime import date, datetime, timedelta
from pathlib import Path


def _con(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    return con


def _rows(con, q, args=()):
    return [dict(r) for r in con.execute(q, args)]


def _proprios(con):
    """source_id e handle das contas próprias (kind='own') por plataforma."""
    return {r["platform"]: {"source_id": r["source_id"], "handle": r["handle"]} for r in _rows(con, "select platform, source_id, handle from sources where kind='own'")}


def _dia(iso):
    try:
        return date.fromisoformat(str(iso)[:10])
    except Exception:
        return None


def _hora(iso):
    s = str(iso or "")
    return s[11:16] if len(s) >= 16 and s[10] == "T" else None


# --- calendário -----------------------------------------------------------------------------------

def calendario(db, saida, notion_itens=(), antes=14, depois=28, hoje=None):
    """Itens por dia: agendados/rascunhos da Publora (entregas), postados de verdade (gs.db) e cartões do Notion com Data de publicação."""
    hoje = hoje or date.today(); ini = hoje - timedelta(days=antes); fim = hoje + timedelta(days=depois)
    itens = []
    for arq in sorted(Path(saida).glob("*/publicacoes.json")) if Path(saida).exists() else []:
        try:
            lista = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in lista:
            if it.get("tipo") != "publora":
                continue
            q = it.get("scheduledTime") or it.get("quando"); d = _dia(q)
            if d and ini <= d <= fim:
                st = it.get("status") or "draft"
                itens.append({"dia": d.isoformat(), "hora": _hora(q), "tipo": {"scheduled": "agendado", "draft": "rascunho", "published": "postado"}.get(st, st), "titulo": arq.parent.name, "slug": arq.parent.name,
                              "plataformas": sorted({p.split("-")[0] for p in it.get("plataformas", [])}), "origem": "publora", "status": st, "arquivo": it.get("arquivo")})
    if Path(db).exists():
        con = _con(db); own = _proprios(con)
        if "youtube" in own:
            for r in _rows(con, "select video_id, title, published_at, format from yt_videos where source_id=? and substr(published_at,1,10) between ? and ?", (own["youtube"]["source_id"], ini.isoformat(), fim.isoformat())):
                itens.append({"dia": r["published_at"][:10], "hora": _hora(r["published_at"]), "tipo": "postado", "titulo": r["title"], "plataformas": ["youtube"], "origem": "youtube", "url": f"https://youtu.be/{r['video_id']}", "formato": r["format"]})
        if "instagram" in own:
            for r in _rows(con, "select shortcode, caption, posted_at, product_type, post_type, url from ig_posts where source_id=? and substr(posted_at,1,10) between ? and ?", (own["instagram"]["source_id"], ini.isoformat(), fim.isoformat())):
                titulo = ((r["caption"] or "").strip().splitlines() or [""])[0][:80] or r["shortcode"]
                itens.append({"dia": r["posted_at"][:10], "hora": _hora(r["posted_at"]), "tipo": "postado", "titulo": titulo, "plataformas": ["instagram"], "origem": "instagram", "url": r["url"] or f"https://www.instagram.com/p/{r['shortcode']}/", "formato": r["product_type"] or r["post_type"]})
        con.close()
    for n in notion_itens:
        d = _dia(n.get("dia"))
        if d and ini <= d <= fim:
            itens.append({**n, "dia": d.isoformat(), "tipo": "recorrente" if n.get("recorrente") else "postado" if n.get("postado") else "planejado", "origem": "notion", "plataformas": n.get("plataformas") or ["instagram"]})
    itens.sort(key=lambda x: (x["dia"], x.get("hora") or "", x["origem"]))
    return {"hoje": hoje.isoformat(), "inicio": ini.isoformat(), "fim": fim.isoformat(), "itens": itens, "n": len(itens)}


# --- comentários ----------------------------------------------------------------------------------

def comentarios(db, dias=30, todos=False, limite=200):
    """Comentários de leitores nos conteúdos próprios (YouTube e Instagram). Autor pseudonimizado (hash curto). `respondido` = já tem resposta do dono."""
    if not Path(db).exists():
        return {"itens": [], "n": 0, "sem_resposta": 0, "aviso": "banco do GSI não encontrado"}
    con = _con(db); own = _proprios(con); desde = (date.today() - timedelta(days=dias)).isoformat(); itens = []
    if "youtube" in own:
        itens += _rows(con, """select c.comment_id as id, 'youtube' as plataforma, c.text as texto, substr(coalesce(c.author_hash,''),1,6) as autor, coalesce(c.likes,0) as likes, c.posted_at as quando,
            v.title as conteudo, v.video_id as item_id, 'https://youtu.be/' || v.video_id as url,
            exists(select 1 from yt_comments r where r.parent_id=c.comment_id and r.is_owner=1) as respondido
            from yt_comments c join yt_videos v using(video_id) where v.source_id=? and c.parent_id is null and coalesce(c.is_owner,0)=0 and substr(c.posted_at,1,10) >= ?""", (own["youtube"]["source_id"], desde))
    if "instagram" in own:
        itens += _rows(con, """select c.comment_id as id, 'instagram' as plataforma, c.text as texto, substr(coalesce(c.author_hash,''),1,6) as autor, coalesce(c.likes,0) as likes, c.posted_at as quando,
            substr(coalesce(p.caption,''),1,80) as conteudo, p.shortcode as item_id, coalesce(p.url, 'https://www.instagram.com/p/' || p.shortcode || '/') as url,
            exists(select 1 from ig_comments r where r.parent_id=c.comment_id and r.is_owner=1) as respondido
            from ig_comments c join ig_posts p using(shortcode) where p.source_id=? and c.parent_id is null and coalesce(c.is_owner,0)=0 and substr(c.posted_at,1,10) >= ?""", (own["instagram"]["source_id"], desde))
    con.close()
    for it in itens:
        it["respondido"] = bool(it["respondido"]); it["texto"] = (it["texto"] or "").strip()
    sem = [i for i in itens if not i["respondido"]]
    lista = itens if todos else sem
    lista.sort(key=lambda x: x["quando"] or "", reverse=True)
    return {"itens": lista[:limite], "n": len(itens), "sem_resposta": len(sem), "dias": dias}


def pedido_respostas(itens):
    linhas = ["Rascunhe uma resposta curta, na voz do Thiago, para cada comentário abaixo (fluxo respostas-comentarios). Não publique nada: entregue as respostas na mensagem final, seção `## Respostas`, um bloco por comentário (plataforma, conteúdo, o comentário e a resposta sugerida); nenhum arquivo. Dúvida técnica → resposta direta e, se couber, convite para ver o vídeo certo; elogio → agradecer sem exagero; pergunta sobre curso, preço ou vaga → responder que o link vai na DM e marcar como [HUMANO] para o Thiago decidir. Sem número de alunos, preço ou promessa de resultado.", "", "COMENTÁRIOS:"]
    for i, it in enumerate(itens, 1):
        linhas.append(f"{i}. [{it['plataforma']}] em \"{(it.get('conteudo') or '')[:70]}\" ({it.get('url') or ''}) — autor {it.get('autor') or 'anônimo'}, {str(it.get('quando') or '')[:10]}:\n   \"{(it.get('texto') or '')[:500]}\"")
    return "\n".join(linhas)


# --- resultados -----------------------------------------------------------------------------------

def _itens_desempenho(con, own, ini, fim):
    """Último snapshot `current` de cada conteúdo próprio publicado no período, com título e data."""
    donos = [v["handle"] for v in own.values()]
    if not donos:
        return []
    q = f"""select s.platform, s.item_id, s.views, s.likes, s.comments, s.engagement_rate, s.format, s.theme, s.ratio_vs_format_median, s.computed_at
            from performance_snapshots s join (select platform, item_id, max(computed_at) m from performance_snapshots where horizon='current' group by 1, 2) u
              on u.platform=s.platform and u.item_id=s.item_id and u.m=s.computed_at
            where s.horizon='current' and s.owner in ({','.join('?' * len(donos))})"""  # 03/11/2026: junção com o máximo agrupado no lugar da subconsulta por linha (28 s → <1 s)
    snaps = _rows(con, q, donos)
    yt = {r["video_id"]: r for r in _rows(con, "select video_id, title, published_at, duration_s from yt_videos")}
    ig = {r["shortcode"]: r for r in _rows(con, "select shortcode, caption, posted_at, product_type, post_type, url from ig_posts")}
    out = []
    for s in snaps:
        if s["platform"] == "youtube" and s["item_id"] in yt:
            v = yt[s["item_id"]]; pub, titulo, url = v["published_at"], v["title"], f"https://youtu.be/{s['item_id']}"
        elif s["platform"] == "instagram" and s["item_id"] in ig:
            p = ig[s["item_id"]]; pub = p["posted_at"]; titulo = ((p["caption"] or "").strip().splitlines() or [""])[0][:80] or s["item_id"]; url = p["url"] or f"https://www.instagram.com/p/{s['item_id']}/"
        else:
            continue
        d = _dia(pub)
        if not d or not (ini <= d <= fim):
            continue
        out.append({"plataforma": s["platform"], "id": s["item_id"], "titulo": titulo, "url": url, "publicado": d.isoformat(), "views": s["views"] or 0, "likes": s["likes"] or 0, "comentarios": s["comments"] or 0,
                    "engajamento": s["engagement_rate"], "formato": s["format"], "tema": s["theme"], "vs_mediana_formato": s["ratio_vs_format_median"], "medido_em": s["computed_at"]})
    return out


def _resumo(itens):
    views = [i["views"] for i in itens]; eng = [i["engajamento"] for i in itens if i["engajamento"] is not None]
    return {"conteudos": len(itens), "views": sum(views), "likes": sum(i["likes"] for i in itens), "comentarios": sum(i["comentarios"] for i in itens),
            "views_mediana": int(statistics.median(views)) if views else 0, "engajamento_medio": round(statistics.mean(eng), 4) if eng else None}


def resultados(db, dias=30, hoje=None):
    """Desempenho dos conteúdos próprios publicados nos últimos `dias` (último snapshot de cada um) e comparação com o período anterior."""
    if not Path(db).exists():
        return {"itens": [], "aviso": "banco do GSI não encontrado"}
    hoje = hoje or date.today(); ini = hoje - timedelta(days=dias); ini_ant = ini - timedelta(days=dias)
    con = _con(db); own = _proprios(con)
    atuais = _itens_desempenho(con, own, ini, hoje); anteriores = _itens_desempenho(con, own, ini_ant, ini - timedelta(days=1))
    ultima = con.execute("select max(computed_at) from performance_snapshots").fetchone()[0]
    con.close()
    atuais.sort(key=lambda i: i["views"], reverse=True)
    por_formato = {}
    for i in atuais:
        k = f"{i['plataforma']}/{i['formato'] or '?'}"; por_formato.setdefault(k, []).append(i)
    formatos = [{"formato": k, **_resumo(v)} for k, v in sorted(por_formato.items())]
    por_plat = {}
    for i in atuais:
        por_plat.setdefault(i["plataforma"], []).append(i)
    return {"dias": dias, "inicio": ini.isoformat(), "fim": hoje.isoformat(), "ultima_medicao": ultima, "total": _resumo(atuais), "anterior": _resumo(anteriores),
            "plataformas": {k: _resumo(v) for k, v in por_plat.items()}, "formatos": formatos, "top": atuais[:5], "piores": atuais[-3:][::-1] if len(atuais) > 5 else [], "itens": atuais,
            "nota": "Números do último snapshot do GSI (não são tempo real). Instagram depende da coleta oficial da Meta (pendente); YouTube vem da Data API."}


def pedido_analise(res):
    t, a = res["total"], res["anterior"]
    linhas = [f"Analise os resultados dos últimos {res['dias']} dias (fluxo analise-resultados) e entregue na mensagem final, seção `## Análise` (nenhum arquivo): o que funcionou, o que não, hipóteses explicadas em linguagem simples e 3 sugestões de próximo conteúdo (cada uma com formato e gancho). Não invente métrica; use só os números abaixo e marque como hipótese o que for inferência. Sem número de alunos, preço ou promessa.", "",
              f"PERÍODO {res['inicio']} a {res['fim']} (última medição {res['ultima_medicao']}): {t['conteudos']} conteúdos, {t['views']} views, {t['likes']} likes, {t['comentarios']} comentários, mediana {t['views_mediana']} views, engajamento médio {t['engajamento_medio']}.",
              f"PERÍODO ANTERIOR: {a['conteudos']} conteúdos, {a['views']} views, {a['likes']} likes, {a['comentarios']} comentários, mediana {a['views_mediana']} views.", "", "POR FORMATO:"]
    linhas += [f"- {f['formato']}: {f['conteudos']} conteúdos, {f['views']} views, mediana {f['views_mediana']}, engajamento {f['engajamento_medio']}" for f in res["formatos"]]
    linhas += ["", "CONTEÚDOS (views, likes, comentários, razão vs. mediana do formato):"]
    linhas += [f"- [{i['plataforma']}/{i['formato'] or '?'}] {i['publicado']} \"{i['titulo'][:70]}\": {i['views']} views, {i['likes']} likes, {i['comentarios']} com., razão {i['vs_mediana_formato']} ({i['url']})" for i in res["itens"][:40]]
    return "\n".join(linhas)


def relatorio_mes(db, mes, pasta):
    """Relatório do mês (AAAA-MM) em Markdown, sem modelo de linguagem: números do GSI, top conteúdos, comentários. Grava em `pasta/relatorio-AAAA-MM.md`."""
    try:
        ano, m = (int(x) for x in mes.split("-"))
        ini = date(ano, m, 1)
    except Exception:
        raise ValueError("mes deve ser AAAA-MM")
    fim = (date(ano + (m == 12), (m % 12) + 1, 1) - timedelta(days=1))
    res = {"itens": [], "total": _resumo([]), "anterior": _resumo([]), "formatos": [], "ultima_medicao": None}
    com = {"n": 0, "sem_resposta": 0}
    if Path(db).exists():
        con = _con(db); own = _proprios(con)
        atuais = _itens_desempenho(con, own, ini, fim); atuais.sort(key=lambda i: i["views"], reverse=True)
        ini_ant = (ini - timedelta(days=1)).replace(day=1); anteriores = _itens_desempenho(con, own, ini_ant, ini - timedelta(days=1))
        ultima = con.execute("select max(computed_at) from performance_snapshots").fetchone()[0]
        por_formato = {}
        for i in atuais:
            por_formato.setdefault(f"{i['plataforma']}/{i['formato'] or '?'}", []).append(i)
        res = {"itens": atuais, "total": _resumo(atuais), "anterior": _resumo(anteriores), "formatos": [{"formato": k, **_resumo(v)} for k, v in sorted(por_formato.items())], "ultima_medicao": ultima}
        con.close()
        c = comentarios(db, dias=(date.today() - ini).days + 1, todos=True, limite=100000)
        no_mes = [x for x in c["itens"] if ini.isoformat() <= str(x["quando"] or "")[:10] <= fim.isoformat()]
        com = {"n": len(no_mes), "sem_resposta": sum(1 for x in no_mes if not x["respondido"])}
    t, a = res["total"], res["anterior"]
    def var(x, y):
        return "—" if not y else f"{(x - y) / y * 100:+.0f}%"
    L = [f"# Grava Simples — resultados de {ini:%m/%Y}", "", f"Gerado em {datetime.now():%d/%m/%Y %H:%M} pelo Editor GS a partir do banco do GSI (última medição: {res['ultima_medicao'] or 'sem dados'}). Números de coleta, não auditados; sem Instagram oficial até a Meta ser conectada.", "",
         "## Resumo", "", "| | Este mês | Mês anterior | Variação |", "|---|---|---|---|",
         f"| Conteúdos publicados | {t['conteudos']} | {a['conteudos']} | {var(t['conteudos'], a['conteudos'])} |", f"| Views | {t['views']} | {a['views']} | {var(t['views'], a['views'])} |",
         f"| Likes | {t['likes']} | {a['likes']} | {var(t['likes'], a['likes'])} |", f"| Comentários nos conteúdos | {t['comentarios']} | {a['comentarios']} | {var(t['comentarios'], a['comentarios'])} |",
         f"| Mediana de views | {t['views_mediana']} | {a['views_mediana']} | {var(t['views_mediana'], a['views_mediana'])} |", f"| Engajamento médio | {t['engajamento_medio'] if t['engajamento_medio'] is not None else '—'} | {a['engajamento_medio'] if a['engajamento_medio'] is not None else '—'} | |", "",
         "## Por formato", ""] + ([f"- **{f['formato']}**: {f['conteudos']} conteúdos, {f['views']} views (mediana {f['views_mediana']}), engajamento {f['engajamento_medio'] if f['engajamento_medio'] is not None else '—'}" for f in res["formatos"]] or ["Sem conteúdo medido neste mês."]) + ["",
         "## Top 5 do mês", ""] + ([f"{n}. [{i['titulo']}]({i['url']}) — {i['views']} views, {i['likes']} likes, {i['comentarios']} comentários ({i['plataforma']}/{i['formato'] or '?'}, {i['publicado']})" for n, i in enumerate(res["itens"][:5], 1)] or ["Sem dados."]) + ["",
         "## Comentários recebidos", "", f"{com['n']} comentários de leitores no mês, {com['sem_resposta']} ainda sem resposta do canal.", "",
         "## Pendências", "", "- Instagram: métricas oficiais só depois do app da Meta (hoje o que existe é a coleta antiga).", "- Este relatório não substitui a análise do performance-analyst do GSI; peça a análise do Editor para hipóteses."]
    pasta = Path(pasta); pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"relatorio-{ini:%Y-%m}.md"; arq.write_text("\n".join(L), encoding="utf-8")
    return {"mes": f"{ini:%Y-%m}", "arquivo": str(arq), "conteudo": "\n".join(L), "total": t, "comentarios": com}


# --- concorrentes: vídeos que deram certo (YouTube) -----------------------------------------------

def destaques_concorrentes(db, dias=120, minimo=1.6, limite=30, hoje=None):
    """Vídeos dos canais acompanhados (kind != own) publicados nos últimos `dias` cujas views passam de `minimo` × a mediana do próprio canal
    no período. Só leitura do gs.db (coleta do YouTube do GSI); Instagram só depois da Meta. Não é claim de viralidade: é razão sobre a mediana."""
    hoje = hoje or date.today(); ini = (hoje - timedelta(days=dias)).isoformat()
    con = _con(db)
    try:
        linhas = _rows(con, """select v.video_id, v.source_id, v.title, v.published_at, v.duration_s, v.format, s.handle, s.display_name, s.kind, s.category,
                                  (select m.views from yt_video_metrics m where m.video_id = v.video_id order by m.captured_at desc limit 1) as views
                               from yt_videos v join sources s on s.source_id = v.source_id
                               where s.platform = 'youtube' and s.kind != 'own' and v.published_at >= ? order by v.published_at desc""", (ini,))
    finally:
        con.close()
    por_canal = {}
    for l in linhas:
        if l["views"] is not None:
            por_canal.setdefault(l["source_id"], []).append(l["views"])
    medianas = {k: statistics.median(v) for k, v in por_canal.items() if len(v) >= 3}
    out, canais = [], {}
    for l in linhas:
        med = medianas.get(l["source_id"])
        canais.setdefault(l["source_id"], {"handle": l["handle"], "nome": l["display_name"] or l["handle"], "tipo": l["kind"], "videos": 0, "mediana": med})
        canais[l["source_id"]]["videos"] += 1
        if not med or l["views"] is None:
            continue
        razao = l["views"] / med if med else None
        if razao is not None and razao >= minimo:
            out.append({"video_id": l["video_id"], "titulo": l["title"], "url": f"https://www.youtube.com/watch?v={l['video_id']}", "canal": l["display_name"] or l["handle"], "handle": l["handle"],
                        "tipo_fonte": l["kind"], "categoria": l["category"], "publicado": (l["published_at"] or "")[:10], "duracao_s": l["duration_s"], "formato": l["format"],
                        "views": l["views"], "mediana_canal": round(med), "razao": round(razao, 1)})
    out.sort(key=lambda x: x["razao"], reverse=True)
    return {"dias": dias, "minimo": minimo, "itens": out[:limite], "canais": list(canais.values()),
            "nota": "YouTube pela coleta do GSI (views mais recentes de cada vídeo ÷ mediana do canal no período). Instagram entra quando a Meta estiver conectada."}
