"""Automações 3, 5, 6 e 7 da proposta de 31/10 (03/11/2026), sem modelo de linguagem e sem credencial nova:
- 5 · Pós-mortem D+7 automático: uma vez por dia gera a ficha das peças publicadas há 7+ dias (o motor é metricas.gerar, o mesmo do botão).
- 3 · Variação do vencedor: peça cujo pós-mortem fechou ≥ min_razao × a mediana vira UM pedido no Editor com duas variações (outro ângulo e outro
  formato), a partir do material da própria peça. No máximo `max_por_semana`; cada peça só uma vez.
- 6 · Alertas de tração e risco: pelo último snapshot do GSI (diário; com a Meta fica mais frequente), push quando um post próprio recente foge da
  mediana para cima ou para baixo, ou quando comentários de objeção/problema técnico se acumulam. Cada alerta sai uma vez.
- 7 · Melhor horário por rede: dia da semana × faixa do dia (horário de Brasília) dos posts próprios, mediana da razão × mediana do formato;
  faixa com pouca amostra fica marcada. Recalcula uma vez por semana.
Tudo lê o gs.db do GSI só para leitura; nada publica, nada escreve no Notion nem no GSI. Números do GSI, não claim; horário é correlação, não causa."""
import json, re, sqlite3, statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
ESTADO = _cam.estado("automacoes_estado.json")
BRT = timezone(timedelta(hours=-3))
PADRAO = {
    "posmortem": {"hora": 8},
    "variacao_vencedor": {"min_razao": 1.5, "max_por_semana": 2},
    "alertas": {"tracao": 2.5, "queda": 0.4, "min_idade_dias": 2, "max_idade_dias": 14, "negativos_min": 3, "negativos_dias": 7},
    "melhor_horario": {"dias": 365, "min_n": 3, "cada_dias": 7},
}
NEGATIVOS = ("OBJECTION", "TECHNICAL_PROBLEM", "VERSION_PROBLEM")
FAIXAS = [("madrugada", 0, 6), ("manhã", 6, 11), ("almoço", 11, 14), ("tarde", 14, 18), ("noite", 18, 22), ("fim da noite", 22, 24)]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _ler(p: Path, padrao):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return padrao


def estado(arq: Path = None):
    d = _ler(arq or ESTADO, {})
    return d if isinstance(d, dict) else {}


def gravar(d: dict, arq: Path = None):
    (arq or ESTADO).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def config(id_: str, reg: dict = None):
    return {**PADRAO[id_], **{k: v for k, v in (((reg or {}).get(id_) or {}).get("config") or {}).items() if k in PADRAO[id_]}}


def _con(db: Path):
    if not Path(db).exists():
        return None
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    return c


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


# --- 5 · pós-mortem automático ---------------------------------------------------------------------------------------------------
def posmortem_devido(agora: datetime, est: dict, cfg: dict):
    ult = (est.get("posmortem") or {}).get("ultimo_dia")
    return ult != agora.date().isoformat() and agora.hour >= int(cfg.get("hora", 8))


# --- 3 · variação do vencedor ----------------------------------------------------------------------------------------------------
def variacao_candidatos(feitos: list, est: dict, cfg: dict, agora: datetime):
    """Pós-mortens acima de min_razao, de peças ainda não variadas, maior razão primeiro; respeita o teto da semana."""
    vs = est.get("variacoes") or {}
    semana = [v for v in vs.values() if (_dt(v.get("quando")) or datetime.min.replace(tzinfo=BRT)) > agora.astimezone(BRT) - timedelta(days=7)]
    if len(semana) >= int(cfg.get("max_por_semana", 2)):
        return []
    c = [p for p in feitos if p.get("razao") is not None and float(p["razao"]) >= float(cfg.get("min_razao", 1.5)) and p.get("slug") not in vs]
    return sorted(c, key=lambda p: float(p["razao"]), reverse=True)


def material_da_peca(saida: Path, entrada: Path, slug: str):
    """Melhor fonte para variar: o bruto em entrada/<slug>/ (vídeo mais longo) ou, sem ele, o final entregue."""
    vids = sorted((p for p in (Path(entrada) / slug).glob("*") if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")), key=lambda p: p.stat().st_size, reverse=True) if (Path(entrada) / slug).is_dir() else []
    if vids:
        return f"entrada/{slug}/{vids[0].name}"
    for n in ("final_9x16.mp4", "final_16x9.mp4"):
        if (Path(saida) / slug / n).exists():
            return f"saida/{slug}/{n}"
    return None


def variacao_pedido(pm: dict, material: str):
    et = pm.get("etiquetas") or {}
    return "\n".join([
        f"Variação do vencedor: {(pm.get('titulo') or pm['slug'])[:70]}",
        "",
        "Variação do vencedor (Automação 3 do Editor GS). Fluxo: `fluxos/reels-padrao.md`.",
        f"A peça {pm.get('codigo') or pm['slug']} fechou o D+7 com {pm['razao']}× a mediana do formato ({pm.get('views')} views, {pm.get('plataforma') or '?'}). Número do GSI, não claim; não cite na peça.",
        f"O que ela tem (etiquetas): gancho \"{et.get('gancho', '?')}\", formato {et.get('formato', '?')}, pilar {et.get('pilar', '?')}. Hipótese: {pm.get('hipotese', '')}",
        f"Material: `{material}`.",
        "",
        "Entregue DUAS variações, cada uma mudando UM atributo (para o pós-mortem dizer o que pesou):",
        "1. `final_variacao_angulo_9x16.mp4`: mesmo formato, outro ângulo de gancho (pergunta, número, erro comum ou contraste; diferente do original).",
        "2. `final_variacao_formato_9x16.mp4`: mesmo gancho, outro formato de edição (ex.: lista com capítulos, PiP, antes e depois ou nível profissional, o que o material permitir).",
        "Capa para cada uma. Na mensagem final: `## Resumo` (o que mudou em cada uma), `## Gancho` (da variação 1), `## Legenda do post` (uma por variação), `## Pendências`, `## Arquivos`.",
        "Sem preço, oferta, número de alunos ou link. Não publique nem agende. Não altere `entrada/` nem a pasta da peça original.",
        "Modo automático: poste o plano e monte direto, sem pedir aprovação."])


# --- 6 · alertas ------------------------------------------------------------------------------------------------------------------
def _titulos(con, tabelas):
    t = {}
    if "yt_videos" in tabelas:
        for r in con.execute("select video_id, title from yt_videos"):
            t[("youtube", r["video_id"])] = r["title"] or r["video_id"]
    if "ig_posts" in tabelas:
        for r in con.execute("select shortcode, caption, url from ig_posts"):
            linha = next((l.strip() for l in (r["caption"] or "").splitlines() if l.strip()), r["shortcode"])
            t[("instagram", r["shortcode"])] = linha[:90]
    return t


def _url(plat, iid):
    return f"https://youtu.be/{iid}" if plat == "youtube" else f"https://www.instagram.com/p/{iid}/"


def alertas(db: Path, est: dict, cfg: dict, agora: datetime = None):
    """Alertas novos (ainda não enviados). Tipos: tracao (razão ≥ tracao), queda (razão ≤ queda, com min_idade_dias), risco (comentários negativos)."""
    agora = agora or datetime.now(timezone.utc)
    con = _con(db)
    if not con:
        return []
    enviados = set(est.get("alertas_enviados") or []); out = []
    try:
        tabelas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        donos = [r["handle"] for r in con.execute("select handle from sources where kind='own'")] if "sources" in tabelas else []
        if "performance_snapshots" not in tabelas or not donos:
            return []
        tit = _titulos(con, tabelas)
        q = f"""select s.platform, s.item_id, s.views, s.ratio_vs_format_median r, s.age_days, s.format, s.computed_at from performance_snapshots s join (select platform u_p, item_id u_i, max(computed_at) u_m from performance_snapshots where horizon='current' group by 1, 2) u on u.u_p=s.platform and u.u_i=s.item_id
                where s.horizon='current' and s.owner in ({','.join('?' * len(donos))})
                and s.computed_at = u.u_m  -- 03/11/2026: máximo agrupado (era subconsulta por linha, lenta)"""
        for s in con.execute(q, donos):
            idade = s["age_days"]; r = s["r"]
            if r is None or idade is None or idade > float(cfg["max_idade_dias"]):
                continue
            tipo = "tracao" if r >= float(cfg["tracao"]) else ("queda" if r <= float(cfg["queda"]) and idade >= float(cfg["min_idade_dias"]) else None)
            if not tipo:
                continue
            chave = f"{tipo}:{s['platform']}:{s['item_id']}"
            if chave in enviados:
                continue
            out.append({"chave": chave, "tipo": tipo, "plataforma": s["platform"], "item": s["item_id"], "titulo": tit.get((s["platform"], s["item_id"]), s["item_id"]),
                        "razao": round(float(r), 2), "views": s["views"], "idade_dias": round(float(idade), 1), "formato": s["format"], "medido_em": s["computed_at"], "url": _url(s["platform"], s["item_id"])})
        if "comment_classifications" in tabelas:
            desde = (agora - timedelta(days=int(cfg["negativos_dias"]))).strftime("%Y-%m-%dT%H:%M:%S")
            for plat, tab, col in (("instagram", "ig_comments", "shortcode"), ("youtube", "yt_comments", "video_id")):
                if tab not in tabelas:
                    continue
                q = f"""select c.{col} item, count(*) n from comment_classifications k join {tab} c on c.comment_id=k.comment_id
                        where k.platform=? and k.is_current=1 and k.classification in ({','.join('?' * len(NEGATIVOS))}) and c.posted_at >= ? and coalesce(c.is_owner,0)=0 group by c.{col}"""
                for row in con.execute(q, (plat, *NEGATIVOS, desde)):
                    if row["n"] < int(cfg["negativos_min"]):
                        continue
                    chave = f"risco:{plat}:{row['item']}:{agora.date().isocalendar()[1]}"  # no máximo um por semana por post
                    if chave in enviados:
                        continue
                    out.append({"chave": chave, "tipo": "risco", "plataforma": plat, "item": row["item"], "titulo": tit.get((plat, row["item"]), row["item"]), "negativos": row["n"],
                                "url": _url(plat, row["item"])})
    finally:
        con.close()
    return out


def texto_alerta(a: dict):
    if a["tipo"] == "tracao":
        return f"Tração: {a['razao']}× a mediana", f"{a['titulo'][:60]} ({a['plataforma']}, {a['views']} views em {a['idade_dias']} dias). Vale um Reel reciclado ou uma variação."
    if a["tipo"] == "queda":
        return f"Abaixo da mediana: {a['razao']}×", f"{a['titulo'][:60]} ({a['plataforma']}, {a['idade_dias']} dias). Teste outro gancho antes de repetir o tema."
    return f"Comentários de problema: {a['negativos']}", f"{a['titulo'][:60]} ({a['plataforma']}): objeções ou problemas técnicos nos últimos dias. Vale responder."


# --- 7 · melhor horário -----------------------------------------------------------------------------------------------------------
def _faixa(h):
    return next(n for n, a, b in FAIXAS if a <= h < b)


def melhor_horario(db: Path, cfg: dict = None, agora: datetime = None):
    cfg = cfg or PADRAO["melhor_horario"]; agora = agora or datetime.now(timezone.utc)
    con = _con(db)
    if not con:
        return None
    try:
        tabelas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        donos = [r["handle"] for r in con.execute("select handle from sources where kind='own'")] if "sources" in tabelas else []
        if "performance_snapshots" not in tabelas or not donos:
            return None
        pub = {}
        if "yt_videos" in tabelas:
            for r in con.execute("select y.video_id, y.published_at from yt_videos y join sources s on s.source_id=y.source_id where s.kind='own'"):
                pub[("youtube", r["video_id"])] = r["published_at"]
        if "ig_posts" in tabelas:
            for r in con.execute(f"select shortcode, posted_at from ig_posts where owner_handle in ({','.join('?' * len(donos))}) and coalesce(is_paid,0)=0", donos):
                pub[("instagram", r["shortcode"])] = r["posted_at"]
        q = f"""select s.platform, s.item_id, s.ratio_vs_format_median r from performance_snapshots s join (select platform u_p, item_id u_i, max(computed_at) u_m from performance_snapshots where horizon='current' group by 1, 2) u on u.u_p=s.platform and u.u_i=s.item_id where s.horizon='current' and s.owner in ({','.join('?' * len(donos))})
                and s.computed_at = u.u_m  -- 03/11/2026: máximo agrupado (era subconsulta por linha, lenta)"""
        grupos = {}
        limite = agora - timedelta(days=int(cfg["dias"]))
        for s in con.execute(q, donos):
            d = _dt(pub.get((s["platform"], s["item_id"])))
            if s["r"] is None or not d or d < limite:
                continue
            local = d.astimezone(BRT)
            grupos.setdefault(s["platform"], {}).setdefault((local.weekday(), _faixa(local.hour)), []).append(float(s["r"]))
    finally:
        con.close()
    out = {"calculado_em": agora.astimezone(BRT).isoformat(timespec="minutes"), "janela_dias": int(cfg["dias"]), "min_n": int(cfg["min_n"]), "redes": {}}
    for plat, gs in grupos.items():
        linhas = [{"dia": DIAS[d], "faixa": f, "n": len(v), "mediana": round(statistics.median(v), 2), "pouca_amostra": len(v) < int(cfg["min_n"])} for (d, f), v in gs.items()]
        linhas.sort(key=lambda x: (not x["pouca_amostra"], x["mediana"]), reverse=True)
        firmes = [x for x in linhas if not x["pouca_amostra"]]
        out["redes"][plat] = {"posts": sum(x["n"] for x in linhas), "melhores": firmes[:3], "piores": sorted(firmes, key=lambda x: x["mediana"])[:2], "todas": linhas,
                              "nota": "poucos posts por faixa: trate como pista" if len(firmes) < 3 else "correlação com o histórico, não causa"}
    return out


def melhor_horario_devido(agora: datetime, est: dict, cfg: dict):
    ult = _dt((est.get("melhor_horario") or {}).get("calculado_em"))
    return not ult or agora.astimezone(BRT) - ult >= timedelta(days=int(cfg.get("cada_dias", 7)))
