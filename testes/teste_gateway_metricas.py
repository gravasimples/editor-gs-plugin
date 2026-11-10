"""Testes isolados da aba Métricas e Automações v1: pós-mortem D+7 (pendentes, gerar, veredito), relatório semanal, registro de automações
(GSI lido de arquivos falsos; chaves das planejadas). Pastas temporárias, gs.db falso, sem rede."""
import json, sqlite3, sys, tempfile
from datetime import date, timedelta
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, automacoes as aut, metricas as mtr, pecas

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); hoje = date(2026, 10, 31)
    api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.GSI_DB = tmp / "gs.db"; api.GSI_RAIZ = tmp / "gsi"; api.RELATORIOS = tmp / "relatorios"
    pecas.ETIQUETAS_CFG = tmp / "etiquetas.json"; aut.REGISTRO = tmp / "automacoes.json"
    api.SAIDA.mkdir(); api.INDICE.write_text("{}"); api.TEXTOS_CACHE.write_text("{}")
    con = sqlite3.connect(api.GSI_DB)
    con.execute("create table performance_snapshots (platform, item_id, owner, horizon, computed_at, views, likes, comments, engagement_rate, format, theme, ratio_vs_format_median, median_views_format, age_days)")
    con.execute("create table sources (source_id, platform, handle, kind)"); con.execute("insert into sources values (1,'youtube','gravasimples','own')")
    con.execute("create table yt_videos (video_id, title, published_at, duration_s)"); con.execute("create table ig_posts (shortcode, caption, posted_at, product_type, post_type, url, owner_handle)")
    con.execute("insert into performance_snapshots values ('youtube','v1','gravasimples','current','2026-10-30T08:00:00Z',3000,100,10,0.04,'short','obs',2.0,1500,8)")
    con.execute("insert into performance_snapshots values ('youtube','v2','gravasimples','current','2026-10-30T08:00:00Z',400,10,1,0.03,'short','obs',0.3,1500,8)")
    con.execute("insert into yt_videos values ('v1','Vídeo bom','2026-10-22T10:00:00Z',45)"); con.execute("insert into yt_videos values ('v2','Vídeo fraco','2026-10-23T10:00:00Z',40)")
    con.commit(); con.close()
    def entrega(slug, pub_tipo, pub_id, quando, extra=None):
        d = api.SAIDA / slug; d.mkdir(); (d / "final_9x16.mp4").write_bytes(b"0")
        (d / "publicacoes.json").write_text(json.dumps([{"tipo": pub_tipo, "quando": quando, "id": pub_id}]), encoding="utf-8")
        if extra: (d / "peca.json").write_text(json.dumps({"etiquetas": extra}), encoding="utf-8")
        return d
    entrega("2026-10-22-bom", "youtube", "v1", "2026-10-22T12:00:00", {"campanha": "Orgânico", "pilar": "OBS passo a passo", "gancho": "Três cenas bastam"})
    entrega("2026-10-23-fraco", "youtube", "v2", "2026-10-23T12:00:00")
    entrega("2026-10-29-recente", "youtube", "v1", "2026-10-29T12:00:00")
    (api.SAIDA / "2026-10-30-sem-pub").mkdir(); (api.SAIDA / "2026-10-30-sem-pub" / "final_9x16.mp4").write_bytes(b"0")
    # GSI falso
    g = api.GSI_RAIZ; (g / "integracoes" / "scheduler").mkdir(parents=True); (g / "dados" / "pulsos").mkdir(parents=True); (g / "briefings" / "pulsos").mkdir(parents=True); (g / "briefings" / "radar").mkdir(parents=True)
    (g / "integracoes" / "config_pulso_conteudo.json").write_text(json.dumps({"enabled": True, "modo": "PRODUZIR"})); (g / "integracoes" / "config_radar.json").write_text(json.dumps({"enabled": True, "hora_radar": 23, "horas_aprovacoes": [11, 23], "doc": {"url": "https://x"}}))
    (g / "integracoes" / "config_editor_gs_ponte.json").write_text(json.dumps({"enabled": True, "max_por_rodada": 1, "max_por_dia": 3, "criterios": {"carrossel": {}, "reels": {}}}))
    (g / "dados" / "pulsos" / "editor_gs_ponte.json").write_text(json.dumps({"enviados": {"a": {"quando": "2026-10-29T15:40:00"}, "b": {"quando": "2026-10-30T23:05:00"}}})); (g / "dados" / "pulsos" / "fila.json").write_text(json.dumps({"x": {}, "y": {}})); (g / "dados" / "pulsos" / "estado.json").write_text(json.dumps({"lido_em": "2026-10-31T23:01:07Z"}))
    (g / "briefings" / "pulsos" / "pulso-2026-10-31-20h01.md").write_text("#"); (g / "integracoes" / "scheduler" / "KILL_SWITCH").write_text("")
    c = TestClient(api.app)

    # pós-mortem
    pend = mtr.pendentes(api.SAIDA, api.GSI_DB, {}, hoje)
    check({p["slug"] for p in pend} == {"2026-10-22-bom", "2026-10-23-fraco"}, f"pendentes: só publicadas há 7+ dias com métrica ({[p['slug'] for p in pend]})")
    ger = {g["slug"]: g for g in mtr.gerar(api.SAIDA, api.GSI_DB, {}, None, hoje)}
    check(len(ger) == 2 and ger["2026-10-22-bom"]["veredito"] == "acima da mediana" and ger["2026-10-23-fraco"]["veredito"] == "abaixo da mediana" and "Três cenas bastam" in ger["2026-10-22-bom"]["hipotese"] and ger["2026-10-22-bom"]["idade_dias"] == 9, "gerar: veredito pela razão e hipótese com o gancho")
    check((api.SAIDA / "2026-10-22-bom" / "posmortem.json").exists() and mtr.pendentes(api.SAIDA, api.GSI_DB, {}, hoje) == [] and len(mtr.feitos(api.SAIDA)) == 2, "posmortem.json gravado; pendentes zeram; feitos lista 2")
    check(mtr.veredito(1.5) == "acima da mediana" and mtr.veredito(0.6) == "abaixo da mediana" and mtr.veredito(1.0) == "na média do formato" and mtr.veredito(None) == "sem mediana", "limiares do veredito")
    r = c.post("/api/gs/metricas/posmortem", data={"slug": "2026-10-29-recente"}).json()
    check(r["n"] == 1 and r["gerados"][0]["idade_dias"] is not None and r["gerados"][0]["status_aprendizado"] == "proposto", "rota gera para um slug mesmo com menos de 7 dias (pedido explícito)")
    check(c.post("/api/gs/metricas/posmortem", data={"slug": "nao-existe"}).status_code == 404, "slug inexistente dá 404")

    # relatório semanal
    rel = mtr.relatorio_semana(api.GSI_DB, api.SAIDA, api.RELATORIOS, hoje, {})
    check(rel["inicio"] == "2026-10-25" and rel["fim"] == "2026-10-31" and Path(rel["arquivo"]).name == "semana-2026-10-31.md" and "# Grava Simples — semana de 25/10 a 31/10/2026" in rel["conteudo"], "relatório da semana gravado com o período certo")
    check(rel["posmortens"] == 3 and "acima da mediana" in rel["conteudo"] and "Vendas: fora por decisão" in rel["conteudo"], "relatório lista os pós-mortens e a decisão sobre vendas")
    r = c.get("/api/gs/metricas/relatorio-semana?fim=2026-10-31").json(); check(r["fim"] == "2026-10-31" and "Peças do Editor GS" in r["conteudo"], "rota do relatório semanal")
    check(c.get("/api/gs/metricas/relatorio-semana?fim=ontem").status_code == 400, "fim inválido dá 400")

    # automações
    lst = c.get("/api/gs/automacoes").json()["itens"]; por = {a["id"]: a for a in lst}
    check(por["gsi_pulso_conteudo"]["ligada"] and "PRODUZIR" in por["gsi_pulso_conteudo"]["detalhe"] and "2 tarefa" in por["gsi_pulso_conteudo"]["detalhe"] and por["gsi_pulso_conteudo"]["ultimo_arquivo"].endswith("pulso-2026-10-31-20h01.md"), "pulso de conteúdo lido dos arquivos do GSI")
    check(por["gsi_ponte"]["ultima"] == "2026-10-30 23:05" and "2 cartão" in por["gsi_ponte"]["detalhe"] and por["gsi_pulso_principal"]["estado"].startswith("pausado") and por["gsi_radar"]["ligada"], "ponte, pulso principal (KILL_SWITCH) e radar")
    (g / "dados" / "pulsos" / "STOP").write_text("")
    check(c.get("/api/gs/automacoes").json()["itens"][0]["estado"] == "pausada (STOP)", "STOP vira pausada")
    plan = [a for a in lst if a["grupo"] == "Planejada"]
    check(len(plan) == 1 and plan[0]["id"] == "primeiro_comentario" and not plan[0]["ligada"] and por["app_push"]["grupo"] == "Editor GS"
          and all(por[i]["grupo"] == "Editor GS" and por[i].get("existe") for i in ("stories_serie", "reel_reciclado", "posmortem", "variacao_vencedor", "alertas", "melhor_horario")),
          "só o primeiro comentário segue planejado (Meta); stories, reciclado, pós-mortem, variação, alertas e horário no grupo do app (03/11)")
    r = c.post("/api/gs/automacoes/variacao_vencedor", data={"ligada": "sim"}).json()
    check(r["ligada"] and json.loads(aut.REGISTRO.read_text())["variacao_vencedor"]["por"] == "Raphael" and {a["id"]: a for a in c.get("/api/gs/automacoes").json()["itens"]}["variacao_vencedor"]["estado"] == "ligada", "chave da variação do vencedor gravada e refletida")
    r = c.post("/api/gs/automacoes/reel_reciclado", data={"ligada": "sim"}).json()
    check(r["ligada"] and {a["id"]: a for a in c.get("/api/gs/automacoes").json()["itens"]}["reel_reciclado"]["estado"] == "ligada (só rascunho)", "chave do Reel reciclado liga a rodada periódica (só rascunho)")
    check(c.post("/api/gs/automacoes/gsi_radar", data={"ligada": "nao"}).status_code == 400, "automação do GSI não se liga pelo app")
    # painel
    r = c.get("/api/gs/metricas?dias=30").json()
    check(set(r) >= {"painel", "pecas", "posmortem", "automacoes"} and r["pecas"]["total"] == 4 and r["posmortem"]["dias"] == 7 and len(r["posmortem"]["feitos"]) == 3 and r["painel"]["dias"] == 30, "rota do painel junta tudo")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
