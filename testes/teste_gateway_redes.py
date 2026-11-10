"""Testes isolados da página Redes (calendário, comentários, resultados, relatório do mês): gs.db falso em pasta temporária,
Notion e Paperclip por dublê, nada de rede. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_redes.py"""
import json, sqlite3, sys, tempfile
from datetime import date, timedelta
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, redes

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

H = date.today(); D = lambda n: (H - timedelta(days=n)).isoformat()

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.WORKSPACE = tmp / "ws"; api.SAIDA = api.WORKSPACE / "saida"; api.ENTRADA = api.WORKSPACE / "entrada"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.SAIDA.mkdir(parents=True); api.ENTRADA.mkdir(); api.GSI_DB = tmp / "gs.db"
    con = sqlite3.connect(api.GSI_DB)
    con.executescript("""
    create table sources(source_id integer, platform text, handle text, kind text);
    create table yt_videos(video_id text, source_id integer, title text, published_at text, duration_s real, format text);
    create table yt_comments(comment_id text, video_id text, parent_id text, text text, author_hash text, is_owner integer, likes integer, posted_at text);
    create table ig_posts(shortcode text, source_id integer, caption text, posted_at text, product_type text, post_type text, url text);
    create table ig_comments(comment_id text, shortcode text, parent_id text, text text, author_hash text, is_owner integer, likes integer, posted_at text);
    create table performance_snapshots(platform text, item_id text, owner text, horizon text, computed_at text, views integer, likes integer, comments integer, engagement_rate real, format text, theme text, ratio_vs_format_median real);
    """)
    con.executemany("insert into sources values(?,?,?,?)", [(1, "youtube", "gravasimples", "own"), (2, "instagram", "thiago.obsstudio", "own"), (9, "youtube", "concorrente", "competitor")])
    con.executemany("insert into yt_videos values(?,?,?,?,?,?)", [("v1", 1, "Webcam no automático", D(3) + "T15:00:00Z", 400, "short"), ("v2", 1, "Áudio limpo no OBS", D(20) + "T15:00:00Z", 600, "long"), ("v3", 1, "Vídeo velho", D(45) + "T15:00:00Z", 600, "long"), ("vx", 9, "Do concorrente", D(2) + "T15:00:00Z", 60, "short")])
    con.executemany("insert into yt_comments values(?,?,?,?,?,?,?,?)", [
        ("c1", "v1", None, "Como faz pra tirar o ruído?", "abcdef123456", 0, 3, D(2) + "T10:00:00Z"),
        ("c2", "v1", None, "Excelente!", "zzzzzz999999", 0, 0, D(1) + "T10:00:00Z"), ("c2r", "v1", "c2", "Valeu!", "dono", 1, 0, D(1) + "T11:00:00Z"),
        ("c3", "v3", None, "antigo", "qqq", 0, 0, D(44) + "T10:00:00Z"), ("cx", "vx", None, "no concorrente", "k", 0, 0, D(1) + "T10:00:00Z")])
    con.executemany("insert into ig_posts values(?,?,?,?,?,?,?)", [("p1", 2, "Pronto, tá gravando\nmais texto", D(5) + "T18:00:00Z", "clips", "Video", None), ("p2", 2, "Carrossel de presets", D(40) + "T18:00:00Z", "feed", "Sidecar", "https://ig/p2")])
    con.executemany("insert into ig_comments values(?,?,?,?,?,?,?,?)", [("i1", "p1", None, "Qual mic você usa?", "hhhhhh777777", 0, 1, D(4) + "T10:00:00Z")])
    snaps = []
    for item, plat, owner, views, likes, com, fmt, ratio in [("v1", "youtube", "gravasimples", 1200, 80, 2, "short", 1.4), ("v2", "youtube", "gravasimples", 300, 20, 1, "long", 0.6), ("v3", "youtube", "gravasimples", 900, 50, 1, "long", 1.0), ("p1", "instagram", "thiago.obsstudio", 5000, 300, 1, "reel", 2.0), ("p2", "instagram", "thiago.obsstudio", 700, 40, 0, "carousel", 0.8)]:
        snaps += [(plat, item, owner, "current", D(1) + "T08:00:00Z", views, likes, com, round((likes + com) / views, 4), fmt, "t", ratio), (plat, item, owner, "current", D(3) + "T08:00:00Z", views // 2, likes // 2, 0, 0.01, fmt, "t", 0.5), (plat, item, owner, "D+7", D(1) + "T08:00:00Z", None, None, None, None, fmt, "t", None)]
    con.executemany("insert into performance_snapshots values(?,?,?,?,?,?,?,?,?,?,?,?)", snaps); con.commit(); con.close()
    # publicações das entregas
    (api.SAIDA / "s1").mkdir(); (api.SAIDA / "s1" / "publicacoes.json").write_text(json.dumps([{"quando": D(1) + "T10:00:00", "tipo": "publora", "arquivo": "final_9x16.mp4", "plataformas": ["instagram-111"], "status": "scheduled", "scheduledTime": (H + timedelta(days=2)).isoformat() + "T14:00:00.000Z"},
                                                                                              {"quando": D(1) + "T10:05:00", "tipo": "publora", "arquivo": "final_9x16.mp4", "plataformas": ["youtube-UC"], "status": "draft", "scheduledTime": None}, {"quando": D(1) + "T10:06:00", "tipo": "drive", "destino": "gs:x"}]))
    # Notion e Paperclip por dublê
    api._notion_calendario = lambda ini, fim: [{"dia": (H + timedelta(days=5)).isoformat(), "titulo": "Reels: presets", "status": "Aprovado", "formato": ["Reels"], "fila": [], "material": "✅ Pronto", "notion_url": "https://notion/x", "recorrente": False, "postado": False}, {"dia": "2020-01-01", "titulo": "fora", "status": "Ideias", "formato": [], "fila": [], "material": None, "notion_url": None, "recorrente": False, "postado": False}, {"dia": (H + timedelta(days=1)).isoformat(), "titulo": "Acordei vencendo", "status": "🔁 Recorrente", "formato": ["Stories"], "fila": [], "material": None, "notion_url": "https://notion/r", "recorrente": True, "postado": False}]
    CRIADAS = []
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            d = kw["json"]; CRIADAS.append(d); return {"id": f"i{len(CRIADAS)}", "identifier": f"GRA-{len(CRIADAS)}", "title": d["title"], "description": d["description"], "status": "todo", "createdAt": "2026-10-29T00:00:00Z", "updatedAt": "2026-10-29T00:00:00Z"}
        return []
    api._pc = pc_falso
    c = TestClient(api.app)

    # calendário
    r = c.get("/api/gs/redes/calendario"); j = r.json()
    check(r.status_code == 200 and j["hoje"] == H.isoformat(), "calendário responde")
    origens = sorted(i["origem"] for i in j["itens"])
    check(origens == ["instagram", "notion", "notion", "publora", "publora", "youtube"], f"calendário junta Publora (2), YouTube (1, só próprio e na janela), Instagram (1) e Notion (2 na janela): {origens}")
    check(next(i for i in j["itens"] if i["titulo"] == "Acordei vencendo")["tipo"] == "recorrente", "modelo 🔁 Recorrente do Notion vira tipo 'recorrente' (filtrável)")
    ag = next(i for i in j["itens"] if i["origem"] == "publora" and i["tipo"] == "agendado"); check(ag["dia"] == (H + timedelta(days=2)).isoformat() and ag["plataformas"] == ["instagram"], "agendado da Publora no dia do scheduledTime")
    check(any(i["tipo"] == "rascunho" for i in j["itens"]) and all(j["itens"][k]["dia"] <= j["itens"][k + 1]["dia"] for k in range(len(j["itens"]) - 1)), "rascunho aparece e itens vêm por dia")
    nt = next(i for i in j["itens"] if i["origem"] == "notion" and i["tipo"] == "planejado"); check(nt["tipo"] == "planejado" and nt["status"] == "Aprovado" and nt["notion_url"], "cartão do Notion vira 'planejado' com status e link")
    def quebra(ini, fim): raise RuntimeError("sem token")
    api._notion_calendario = quebra; j2 = c.get("/api/gs/redes/calendario").json()
    check("Notion" in (j2["aviso"] or "") and len(j2["itens"]) == 4, "Notion fora do ar vira aviso, resto continua")

    # comentários
    r = c.get("/api/gs/redes/comentarios"); j = r.json()
    check(r.status_code == 200 and j["n"] == 3 and j["sem_resposta"] == 2 and [x["id"] for x in j["itens"]] == ["c1", "i1"], f"3 comentários próprios em 30 dias, 2 sem resposta (do mais novo): {[x['id'] for x in j['itens']]}")
    check(all(len(x["autor"]) == 6 and x["autor"] not in x["texto"] for x in j["itens"]) and j["itens"][0]["plataforma"] == "youtube" and j["itens"][1]["plataforma"] == "instagram", "autor pseudonimizado (6 caracteres); YouTube e Instagram")
    jt = c.get("/api/gs/redes/comentarios?todos=1").json(); check(len(jt["itens"]) == 3 and next(x for x in jt["itens"] if x["id"] == "c2")["respondido"] is True, "todos=1 inclui o respondido pelo dono")
    r = c.post("/api/gs/redes/comentarios/rascunhar", data={"ids": "c1"})
    check(r.status_code == 200 and r.json()["codigo"] == "GRA-1" and "respostas-comentarios" in CRIADAS[-1]["description"] and "tirar o ruído" in CRIADAS[-1]["description"] and "Excelente" not in CRIADAS[-1]["description"], "rascunhar cria pedido com o fluxo e só o comentário escolhido")
    r = c.post("/api/gs/redes/comentarios/rascunhar", data={"ids": ""}); check(r.status_code == 200 and "Qual mic" in CRIADAS[-1]["description"] and "tirar o ruído" in CRIADAS[-1]["description"], "sem ids: todos os sem resposta (até 20)")
    check(c.post("/api/gs/redes/comentarios/rascunhar", data={"ids": "nao-existe"}).status_code == 400, "id inexistente dá 400")

    # resultados
    r = c.get("/api/gs/redes/resultados?dias=30"); j = r.json()
    check(r.status_code == 200 and j["total"]["conteudos"] == 3 and j["total"]["views"] == 1200 + 300 + 5000 and j["anterior"]["conteudos"] == 2 and j["anterior"]["views"] == 900 + 700, f"30 dias: 3 conteúdos (último snapshot current), anterior 2: {j['total']} / {j['anterior']}")
    check(j["top"][0]["id"] == "p1" and j["top"][0]["vs_mediana_formato"] == 2.0 and j["itens"][-1]["id"] == "v2", "ordenado por views com razão sobre a mediana")
    check(sorted(f["formato"] for f in j["formatos"]) == ["instagram/reel", "youtube/long", "youtube/short"], "resumo por plataforma/formato")
    check(c.get("/api/gs/redes/resultados?dias=7").json()["total"]["conteudos"] == 2 and c.get("/api/gs/redes/resultados?dias=10").status_code == 400, "7 dias filtra; 10 dias é recusado")
    r = c.post("/api/gs/redes/resultados/analisar", data={"dias": 30})
    check(r.status_code == 200 and "analise-resultados" in CRIADAS[-1]["description"] and "6500 views" in CRIADAS[-1]["description"] and "Webcam no automático" in CRIADAS[-1]["description"], "pedido de análise leva os números e o fluxo")

    # relatório do mês
    mes = (H - timedelta(days=4)).strftime("%Y-%m"); r = c.get(f"/api/gs/redes/relatorio-mes?mes={mes}"); j = r.json()  # mês do comentário da fixture (no dia 1 o mês corrente ainda não o tem)
    check(r.status_code == 200 and (api.WORKSPACE / "relatorios" / f"relatorio-{mes}.md").exists() and "| Views |" in j["conteudo"] and "## Top 5 do mês" in j["conteudo"], "relatório do mês gravado em workspace/relatorios com tabela e top 5")
    check(j["comentarios"]["n"] >= 1 and "Comentários recebidos" in j["conteudo"], "relatório conta comentários do mês")
    check(c.get(f"/api/gs/redes/relatorio-mes/arquivo?mes={mes}").status_code == 200 and c.get("/api/gs/redes/relatorio-mes?mes=2026-13").status_code == 400 and c.get("/api/gs/redes/relatorio-mes/arquivo?mes=2000-01").status_code == 404, "download do .md; mês inválido 400; não gerado 404")

    # sem banco: nada quebra
    api.GSI_DB = tmp / "nao.db"
    check(c.get("/api/gs/redes/comentarios").json()["itens"] == [] and c.get("/api/gs/redes/resultados").json()["itens"] == [] and c.get("/api/gs/redes/calendario").status_code == 200, "sem gs.db: respostas vazias com aviso, sem erro")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
