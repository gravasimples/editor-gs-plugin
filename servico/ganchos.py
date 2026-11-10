"""Biblioteca de ganchos com desempenho (01/11/2026): todo gancho que a Grava Simples já usou, com a razão sobre a mediana do formato
quando houver medição. Fontes, só leitura: (1) peças do Editor GS (etiqueta `gancho`, inferida da seção `## Gancho` ou escolhida à mão;
métrica pelas publicações casadas com o GSI); (2) experimentos "mesma peça, outro gancho" (`experimento.json`: gancho original e novo);
(3) conteúdos próprios medidos pelo GSI (título do vídeo/Short no YouTube, primeira linha da legenda do Reel no Instagram: o que a
pessoa lê antes de decidir). Nada aqui é claim: razão × mediana é o que o GSI mediu no último snapshot."""
import json, re, sqlite3
from pathlib import Path


def _limpa(t: str, n=140):
    t = re.sub(r"\*+|__|`", "", t or ""); t = re.sub(r"\s+", " ", t).strip(" -\"“”'")
    return t[:n]


def _primeira_linha(t: str):
    for l in (t or "").splitlines():
        l = _limpa(l)
        if l and not l.startswith("#") and not l.startswith("@"):
            return l
    return ""


def do_app(saida: Path, db: Path, cache_textos: dict = None):
    from servico import pecas as pcs
    out = []
    for l in pcs.listar(Path(saida), db, cache_textos or {}):
        g = (l.get("etiquetas") or {}).get("gancho")
        if not g:
            continue
        out.append({"gancho": _limpa(g), "origem": "app", "plataforma": l.get("plataforma") or "app", "formato": (l.get("etiquetas") or {}).get("formato"), "fonte": l.get("titulo"), "codigo": l.get("codigo"), "slug": l["slug"],
                    "url": None, "data": (l.get("publicado_em") or l.get("modificado") or "")[:10], "views": l.get("views"), "razao": (round(float(l["vs_mediana"]), 2) if l.get("vs_mediana") is not None else None),
                    "estado": l.get("estado"), "pilar": (l.get("etiquetas") or {}).get("pilar"), "campanha": (l.get("etiquetas") or {}).get("campanha")})
    return out


def de_experimentos(saida: Path):
    out = []
    for p in sorted(Path(saida).glob("*/experimento.json")) if Path(saida).exists() else []:
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa
            continue
        o = e.get("original") or {}
        if e.get("gancho_original"):
            out.append({"gancho": _limpa(e["gancho_original"]), "origem": "experimento", "plataforma": o.get("plataforma"), "formato": "reel", "fonte": f"original de {e.get('codigo') or p.parent.name}: {o.get('titulo') or ''}"[:120], "codigo": e.get("codigo"), "slug": p.parent.name,
                        "url": o.get("url"), "data": (o.get("publicado") or "")[:10], "views": o.get("views"), "razao": o.get("razao"), "estado": "original do experimento", "papel": "gancho original"})
        if e.get("gancho_novo"):
            out.append({"gancho": _limpa(e["gancho_novo"]), "origem": "experimento", "plataforma": o.get("plataforma"), "formato": "reel", "fonte": f"{e.get('codigo') or p.parent.name} (mesma peça, outro gancho)"[:120], "codigo": e.get("codigo"), "slug": p.parent.name,
                        "url": None, "data": (e.get("quando") or "")[:10], "views": (e.get("resultado") or {}).get("views_nova"), "razao": (e.get("resultado") or {}).get("razao_nova"), "estado": f"experimento {e.get('status', 'aberto')}", "papel": "gancho novo"})
    return out


def do_gsi(db: Path, minimo: float = 0.0, limite: int = 300):
    """Títulos (YouTube) e primeiras linhas de legenda (Instagram) dos conteúdos próprios, com a razão do último snapshot."""
    if not Path(db).exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    try:
        tabelas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        if "performance_snapshots" not in tabelas:
            return []
        donos = [r["handle"] for r in con.execute("select handle from sources where kind='own'")] if "sources" in tabelas else []
        q = f"""select s.platform, s.item_id, s.views, s.ratio_vs_format_median, s.format from performance_snapshots s join (select platform u_p, item_id u_i, max(computed_at) u_m from performance_snapshots where horizon='current' group by 1, 2) u on u.u_p=s.platform and u.u_i=s.item_id where s.horizon='current'
                {('and s.owner in (' + ','.join('?' * len(donos)) + ')') if donos else ''}
                and s.computed_at = u.u_m  -- 03/11/2026: máximo agrupado (era subconsulta por linha, lenta)"""
        out = []
        for s in con.execute(q, donos):
            raz = s["ratio_vs_format_median"]
            if raz is None or float(raz) < minimo:
                continue
            if s["platform"] == "youtube" and "yt_videos" in tabelas:
                v = con.execute("select title, published_at from yt_videos where video_id=?", (s["item_id"],)).fetchone()
                if not v or not v["title"]:
                    continue
                out.append({"gancho": _limpa(v["title"]), "origem": "youtube", "plataforma": "youtube", "formato": s["format"], "fonte": "título do vídeo", "codigo": None, "slug": None, "url": f"https://youtu.be/{s['item_id']}", "data": str(v["published_at"] or "")[:10], "views": s["views"], "razao": round(float(raz), 2), "estado": "publicado"})
            elif s["platform"] == "instagram" and "ig_posts" in tabelas:
                p = con.execute("select caption, posted_at, url, is_paid from ig_posts where shortcode=?", (s["item_id"],)).fetchone()
                if not p or p["is_paid"]:
                    continue
                g = _primeira_linha(p["caption"] or "")
                if len(g) < 8:
                    continue
                out.append({"gancho": g, "origem": "instagram", "plataforma": "instagram", "formato": s["format"], "fonte": "primeira linha da legenda", "codigo": None, "slug": None, "url": p["url"] or f"https://www.instagram.com/p/{s['item_id']}/", "data": str(p["posted_at"] or "")[:10], "views": s["views"], "razao": round(float(raz), 2), "estado": "publicado"})
        out.sort(key=lambda x: (x["razao"] or 0), reverse=True)
        return out[:limite]
    finally:
        con.close()


# Fase 2 (03/11/2026): tipo do gancho por regras (sem modelo). Ordem = prioridade quando o gancho cabe em mais de um tipo.
TIPOS = [
    ("pergunta", "Pergunta", r"\?|^(por que|porque|qual|quais|quanto|quem|onde|sera|voce sabia|ja pensou|sabia que)\b"),
    ("erro", "Erro / alerta", r"\b(erro|erros|errad\w*|nunca|pare de|para de|cuidado|nao faca|evite|ninguem faz|problema|travou|travando|ruim)\b"),
    ("numero", "Número / lista", r"(^|\s)\d+[\s%x]|\b(dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+(\w+\s+)?(erros|passos|dicas|formas|jeitos|coisas|motivos|configurac\w*|truques|ferramentas)\b"),
    ("contraste", "Contraste / antes e depois", r"\b(antes|depois|vs|versus|em vez de|ao inves|mas|todo mundo|ninguem|mito|verdade|diferenca|caro|barato|celular x)\b"),
    ("segredo", "Segredo / curiosidade", r"\b(segredo|truque|ninguem te conta|descobri|escondid\w*|pouca gente|pasme|e serio)\b"),
    ("novidade", "Novidade", r"\b(novo|nova|novidade|chegou|lancou|atualizac\w*|update|agora (o|a) \w+ tem)\b"),
    ("como", "Como fazer / promessa", r"\b(como|passo a passo|aprenda|jeito|tutorial|em \d+ (minutos|segundos)|sem gastar|de graca|gratis|facil|simples)\b"),
    ("historia", "História / POV", r"\b(pov|quando eu|minha|meu|eu \w+ei|historia|bastidor)\b"),
]


def _sem_acento(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").lower()); return "".join(c for c in t if not unicodedata.combining(c))


def tipo_gancho(texto: str):
    t = _sem_acento(texto)
    for tid, _, rx in TIPOS:
        if re.search(rx, t):
            return tid
    return "outro"


def por_tipo(itens):
    """Desempenho por tipo: quantos, quantos medidos, razão média e mediana, e o melhor exemplo medido. Mediana manda (a média puxa com um viral)."""
    import statistics
    rot = dict((a, b) for a, b, _ in TIPOS) | {"outro": "Outros"}; out = []
    for tid in [t for t, _, _ in TIPOS] + ["outro"]:
        grupo = [i for i in itens if i.get("tipo") == tid]
        if not grupo:
            continue
        med = [i["razao"] for i in grupo if i.get("razao") is not None]
        melhor = max((i for i in grupo if i.get("razao") is not None), key=lambda i: i["razao"], default=None)
        out.append({"tipo": tid, "rotulo": rot[tid], "n": len(grupo), "medidos": len(med), "razao_media": round(statistics.mean(med), 2) if med else None,
                    "razao_mediana": round(statistics.median(med), 2) if med else None, "melhor": melhor["gancho"] if melhor else None, "melhor_razao": melhor["razao"] if melhor else None,
                    "pouca_amostra": len(med) < 5})
    out.sort(key=lambda x: (x["razao_mediana"] if x["razao_mediana"] is not None else -1), reverse=True)
    return out


def listar(saida: Path, db: Path, cache_textos: dict = None, origem: str = "tudo", so_medidos: bool = False, q: str = "", minimo: float = 0.0, tipo: str = ""):
    itens = do_app(saida, db, cache_textos) + de_experimentos(saida) + do_gsi(db, minimo)
    for i in itens:
        i["tipo"] = tipo_gancho(i["gancho"])
    if tipo:
        itens = [i for i in itens if i["tipo"] == tipo]
    if origem and origem != "tudo":
        itens = [i for i in itens if i["origem"] == origem]
    if so_medidos:
        itens = [i for i in itens if i.get("razao") is not None]
    if q:
        qn = q.lower(); itens = [i for i in itens if qn in f"{i['gancho']} {i.get('fonte') or ''}".lower()]
    itens.sort(key=lambda i: ((i.get("razao") if i.get("razao") is not None else -1), i.get("data") or ""), reverse=True)
    return itens


def resumo(itens):
    med = [i for i in itens if i.get("razao") is not None]
    return {"total": len(itens), "medidos": len(med), "acima": sum(1 for i in med if i["razao"] >= 1.5), "abaixo": sum(1 for i in med if i["razao"] <= 0.6),
            "por_origem": {o: sum(1 for i in itens if i["origem"] == o) for o in ("app", "experimento", "youtube", "instagram")}}


def texto_pedido(item: dict):
    """Linha pronta para o Novo pedido: usar este gancho como frase de impacto, com a prova (razão) sem virar claim."""
    prova = f" (rendeu {item['razao']}× a mediana do formato {item.get('formato') or ''} em {item.get('data') or '?'}; número do GSI, não claim)" if item.get("razao") is not None else ""
    return f"Use este gancho como frase de impacto (adapte, não copie): \"{item['gancho']}\"{prova}. Fonte: {item.get('fonte') or item.get('origem')}."
