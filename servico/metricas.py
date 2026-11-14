"""Aba Métricas e Automações, versão 1 (sem credencial nova): painel pelo Resultados do GSI, peças × mediana (pecas.py), pós-mortem D+7
determinístico por peça publicada e relatório semanal em Markdown. Nada aqui usa modelo de linguagem; a análise com hipóteses continua
no botão "Pedir análise ao Editor" (fluxo analise-resultados). Veredito do pós-mortem é factual (razão sobre a mediana do formato),
nunca causal; vira aprendizado proposto, validado por humano."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from servico import pecas as pcs, redes as rds

D_POSMORTEM = 7
ACIMA, ABAIXO = 1.5, 0.6


def _dia(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except Exception:  # noqa
        try:
            return date.fromisoformat(str(s)[:10])
        except Exception:  # noqa
            return None


def veredito(razao):
    if razao is None:
        return "sem mediana"
    if razao >= ACIMA:
        return "acima da mediana"
    if razao <= ABAIXO:
        return "abaixo da mediana"
    return "na média do formato"


def posmortem_de(linha, metricas, hoje=None):
    """Ficha factual de uma peça publicada há >= 7 dias com métrica: números × mediana, veredito e hipótese (uma frase, marcada como hipótese)."""
    hoje = hoje or date.today()
    m = next((x for x in metricas if x.get("views") is not None), None)
    if not m:
        return None
    pub = _dia(linha.get("publicado_em"))
    idade = (hoje - pub).days if pub else None
    et = linha.get("etiquetas") or {}
    v = veredito(m.get("ratio_vs_format_median"))
    hip = {"acima da mediana": f"repetir o que esta peça tem: gancho \"{et.get('gancho', '?')}\", formato {et.get('formato', '?')}, pilar {et.get('pilar', '?')} (hipótese, não causa)",
           "abaixo da mediana": "testar outro gancho ou outro formato para o mesmo tema antes de repetir (hipótese, não causa)",
           "na média do formato": "serve de linha de base; variar um atributo por vez para aprender", "sem mediana": "sem mediana do formato ainda; esperar mais peças"}[v]
    return {"slug": linha["slug"], "titulo": linha.get("titulo"), "codigo": linha.get("codigo"), "publicado_em": linha.get("publicado_em"), "idade_dias": idade, "gerado_em": datetime.now().isoformat(timespec="minutes"),
            "plataforma": m.get("platform"), "views": m.get("views"), "likes": m.get("likes"), "comentarios": m.get("comments"), "engajamento": m.get("engagement_rate"),
            "mediana_formato": m.get("median_views_format"), "razao": m.get("ratio_vs_format_median"), "formato_gsi": m.get("format"), "tema_gsi": m.get("theme"), "medido_em": m.get("computed_at"),
            "etiquetas": et, "veredito": v, "hipotese": hip, "status_aprendizado": "proposto"}


def pendentes(saida: Path, db: Path, cache=None, hoje=None):
    """Peças publicadas há >= D_POSMORTEM dias, com métrica e sem posmortem.json."""
    hoje = hoje or date.today(); out = []
    for l in pcs.listar(saida, db, cache):
        pub = _dia(l.get("publicado_em"))
        if not pub or (hoje - pub).days < D_POSMORTEM or l.get("views") is None:
            continue
        if (saida / l["slug"] / "posmortem.json").exists():
            continue
        out.append(l)
    return out


def feitos(saida: Path):
    out = []
    for p in sorted(saida.glob("*/posmortem.json"), key=lambda x: x.stat().st_mtime, reverse=True) if saida.exists() else []:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa
            pass
    return out


def gerar(saida: Path, db: Path, cache=None, slug=None, hoje=None):
    """Gera o pós-mortem das pendentes (ou de um slug) e grava saida/<slug>/posmortem.json. Devolve os gerados."""
    hoje = hoje or date.today(); gerados = []
    alvo = [l for l in pcs.listar(saida, db, cache) if l["slug"] == slug] if slug else pendentes(saida, db, cache, hoje)
    for l in alvo:
        f = pcs.ficha(l["slug"], saida, db, cache)
        pm = posmortem_de(l, f.get("metricas") or [], hoje)
        if not pm:
            continue
        (saida / l["slug"] / "posmortem.json").write_text(json.dumps(pm, ensure_ascii=False, indent=1), encoding="utf-8")
        gerados.append(pm)
    return gerados


def relatorio_semana(db: Path, saida: Path, pasta: Path, fim=None, cache=None):
    """Relatório da semana (7 dias até `fim`) em Markdown, sem modelo de linguagem: números do GSI, peças por etiqueta, pós-mortens, o que falta etiquetar."""
    fim = fim or date.today(); ini = fim - timedelta(days=6)
    res = {"itens": [], "total": rds._resumo([]), "anterior": rds._resumo([]), "formatos": [], "ultima_medicao": None}
    if Path(db).exists():
        con = rds._con(db); own = rds._proprios(con)
        atuais = rds._itens_desempenho(con, own, ini, fim); atuais.sort(key=lambda i: i["views"], reverse=True)
        anteriores = rds._itens_desempenho(con, own, ini - timedelta(days=7), ini - timedelta(days=1))
        ultima = con.execute("select max(computed_at) from performance_snapshots").fetchone()[0]; con.close()
        por_f = {}
        for i in atuais:
            por_f.setdefault(f"{i['plataforma']}/{i['formato'] or '?'}", []).append(i)
        res = {"itens": atuais, "total": rds._resumo(atuais), "anterior": rds._resumo(anteriores), "formatos": [{"formato": k, **rds._resumo(v)} for k, v in sorted(por_f.items())], "ultima_medicao": ultima}
    linhas = pcs.listar(saida, db, cache)
    semana = [l for l in linhas if (_dia(l.get("publicado_em")) or _dia(l.get("modificado"))) and ini <= (_dia(l.get("publicado_em")) or _dia(l.get("modificado"))) <= fim]
    pms = [p for p in feitos(saida) if (_dia(p.get("gerado_em")) or ini) >= ini]
    sem_et = [l for l in semana if not (l["etiquetas"].get("campanha") and l["etiquetas"].get("pilar"))]
    t, a = res["total"], res["anterior"]
    def var(x, y):
        return "—" if not y else f"{(x - y) / y * 100:+.0f}%"
    def conta(k):
        c = {}
        for l in semana:
            v = l["etiquetas"].get(k) or "(sem)"; c[v] = c.get(v, 0) + 1
        return ", ".join(f"{k2} {v}" for k2, v in sorted(c.items(), key=lambda x: -x[1]))
    L = [f"# Grava Simples — semana de {ini:%d/%m} a {fim:%d/%m/%Y}", "", f"Gerado em {datetime.now():%d/%m/%Y %H:%M} pelo Editor GS a partir do GSI (última medição {res['ultima_medicao'] or 'sem dados'}) e das peças do app. Números, não opinião; a análise com hipóteses é do Editor (Pedir análise).", "",
         "## Números da semana (conteúdos próprios medidos pelo GSI)", "", "| | Esta semana | Semana anterior | Variação |", "|---|---|---|---|",
         f"| Conteúdos publicados | {t['conteudos']} | {a['conteudos']} | {var(t['conteudos'], a['conteudos'])} |", f"| Views | {t['views']} | {a['views']} | {var(t['views'], a['views'])} |",
         f"| Likes | {t['likes']} | {a['likes']} | {var(t['likes'], a['likes'])} |", f"| Comentários | {t['comentarios']} | {a['comentarios']} | {var(t['comentarios'], a['comentarios'])} |",
         f"| Mediana de views | {t['views_mediana']} | {a['views_mediana']} | {var(t['views_mediana'], a['views_mediana'])} |", "",
         "## Peças do Editor GS na semana", "", f"{len(semana)} peça(s) entregues ou publicadas; {sum(1 for l in semana if l['estado'] == 'postado ou agendado')} postadas/agendadas; {len(sem_et)} sem campanha ou pilar.", "",
         f"- Por campanha: {conta('campanha') or '—'}", f"- Por pilar: {conta('pilar') or '—'}", f"- Por formato: {conta('formato') or '—'}", f"- Por voz: {conta('voz') or '—'}", "",
         "## Top 5 da semana (GSI)", ""] + ([f"{n}. [{i['titulo']}]({i['url']}) — {i['views']} views, razão {i['vs_mediana_formato'] if i['vs_mediana_formato'] is not None else '—'}× ({i['plataforma']}/{i['formato'] or '?'}, {i['publicado']})" for n, i in enumerate(res["itens"][:5], 1)] or ["Nenhum conteúdo medido no período."]) + ["",
         "## Pós-mortens fechados na semana", ""] + ([f"- **{p.get('titulo') or p['slug']}** ({p.get('plataforma')}): {p.get('views')} views, {p.get('razao') if p.get('razao') is not None else '—'}× a mediana → {p['veredito']}. {p['hipotese']}" for p in pms] or ["Nenhum pós-mortem gerado nesta semana (peças com 7 dias de publicada e métrica aparecem em Métricas → Pós-mortem)."]) + ["",
         "## Para fazer", "", *([f"- Etiquetar: {l['titulo']} ({l['codigo'] or l['slug']})" for l in sem_et[:10]] or ["- Nada pendente de etiqueta."]),
         "- Instagram: métricas oficiais só depois do app da Meta; YouTube vem da Data API pelo pulso principal do GSI.", "- Vendas: fora por decisão (Hotmart fica com comercial e suporte)."]
    pasta = Path(pasta); pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"semana-{fim:%Y-%m-%d}.md"; arq.write_text("\n".join(L), encoding="utf-8")
    return {"inicio": ini.isoformat(), "fim": fim.isoformat(), "arquivo": str(arq), "conteudo": "\n".join(L), "total": t, "pecas": len(semana), "sem_etiqueta": len(sem_et), "posmortens": len(pms)}
