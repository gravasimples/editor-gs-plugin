"""Testes isolados da Automação 1 (Série de Stories): escolha da dúvida no banco de teste, texto do pedido, agenda semanal,
rodada no gateway com Paperclip falso e Publora por MockTransport. Sem rede, sem gs.db real, pastas temporárias.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_automacoes.py"""
import json, os, sqlite3, sys, tempfile
from datetime import datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import httpx
from fastapi.testclient import TestClient
from servico import api, automacoes as aut, publicar as pub

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def banco(p: Path):
    con = sqlite3.connect(p)
    con.executescript("""
    create table yt_comments(comment_id text, video_id text, parent_id text, text text, author_hash text, is_owner int, likes int, reply_count int, posted_at text);
    create table ig_comments(comment_id text, shortcode text, parent_id text, text text, author_hash text, is_owner int, likes int, replies_count int, posted_at text);
    create table comment_classifications(class_id int, platform text, comment_id text, classification text, classification_confidence real, classifier_version text, needs_review int, topics_json text, secondary_json text, rationale text, is_current int, classified_at text);
    create table yt_videos(video_id text, title text);
    """)
    linhas = [("y1", "v1", None, "Tem como gravar no formato do reels e do youtube ao mesmo tempo? Uso só um notebook.", "h1", 0, 1, 0, "2026-03-19T11:22:24Z"),
              ("y2", "v1", None, "CADE OS LINKS??", "h2", 0, 5, 0, "2026-10-07T00:33:09Z"),  # curto demais
              ("y3", "v2", None, "Thiago, me chama no zap 11 99999-8888 ou no email fulano@gmail.com? Preciso saber como gravar a tela com a webcam ao mesmo tempo no OBS, dá?", "h3", 0, 9, 0, "2026-09-01T00:00:00Z"),  # PII removida, continua válido
              ("y4", "v2", None, "Respondendo aqui: dá sim, usa a cena com duas fontes?", "h0", 1, 0, 0, "2026-09-02T00:00:00Z"),  # dono do canal
              ("y5", "v2", "y3", "Também quero saber como gravar a tela com a webcam junto no OBS, alguém sabe?", "h5", 0, 20, 0, "2026-09-03T00:00:00Z"),  # resposta a outro comentário
              ("y6", "v3", None, "Qual microfone barato você indica para gravar aula no quarto sem eco? Tenho medo de comprar errado.", "h6", 0, 3, 0, "2026-08-01T00:00:00Z")]
    con.executemany("insert into yt_comments values (?,?,?,?,?,?,?,?,?)", linhas)
    con.execute("insert into ig_comments values ('i1','s1',NULL,'@thiago.obsstudio como faço pra live no instagram sair sem travar pelo OBS?','h9',0,4,0,'2026-10-01T00:00:00Z')")
    cls = [("youtube", "y1", "QUESTION", '["dois_formatos"]'), ("youtube", "y2", "QUESTION", '["links"]'), ("youtube", "y3", "QUESTION", "[]"), ("youtube", "y4", "QUESTION", "[]"),
           ("youtube", "y5", "QUESTION", '["webcam_camera"]'), ("youtube", "y6", "QUESTION", '["audio"]'), ("instagram", "i1", "QUESTION", '["live"]')]
    con.executemany("insert into comment_classifications values (?,?,?,?,0.6,'rules-v2',0,?,'[]','',1,'2026-09-30')", [(i + 1, p, c, k, t) for i, (p, c, k, t) in enumerate(cls)])
    con.execute("insert into comment_classifications values (99,'youtube','y6','QUESTION',0.6,'rules-v2',0,'[]','[]','',0,'2026-09-01')")  # classificação antiga, não corrente
    con.execute("insert into yt_videos values ('v1','Como gravar em dois formatos no OBS'),('v3','Microfone para aula')")
    con.commit(); con.close()

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    db = tmp / "gs.db"; banco(db)
    aut.REGISTRO = tmp / "automacoes.json"; aut.RODADAS = tmp / "rodadas.json"
    cfg = aut.stories_config()
    # 1. escolha da fonte: tópico > likes > recente; filtros
    f = aut.stories_fonte(db, set(), cfg)
    check(f and f["id"] == "i1" and f["topicos"] == ["live"] and "@" not in f["texto"] and f["contexto"] is None, f"escolhe a dúvida com tópico e mais likes e tira o @ ({f and f['id']}: {f and f['texto'][:40]})")
    f2 = aut.stories_fonte(db, {"instagram:i1"}, cfg)
    check(f2 and f2["id"] == "y6" and f2["contexto"] == 'vídeo "Microfone para aula"', f"segunda rodada pula a usada e traz o contexto do vídeo ({f2 and f2['id']})")
    f3 = aut.stories_fonte(db, {"youtube:y6", "instagram:i1", "youtube:y1"}, cfg)
    check(f3 and f3["id"] == "y3" and "99999" not in f3["texto"] and "gmail" not in f3["texto"], f"dado pessoal sai do texto; dono do canal, resposta e comentário curto ficam de fora ({f3 and f3['id']})")
    check(aut.stories_fonte(db, {"youtube:y6", "instagram:i1", "youtube:y1", "youtube:y3"}, cfg) is None, "sem candidato válido devolve None")
    check(aut.stories_fonte(tmp / "nao-existe.db", set(), cfg) is None, "banco ausente: None, sem exceção")
    ped = aut.stories_pedido(f2, cfg)
    check("fluxos/stories-serie.md" in ped and f2["texto"] in ped and "Microfone para aula" in ped and "h6" not in ped and "rascunho" in ped and "Não escreva no Notion" in ped, "pedido cita fluxo, dúvida, contexto, rascunho e proíbe Notion; sem autor")
    # 2. agenda semanal
    reg = {"stories_serie": {"ligada": True}}
    ter = datetime(2026, 11, 3, 10, 5)  # terça
    check(aut.stories_devida(ter, reg, [], cfg) == (True, "na hora"), "terça 10h05 com a chave ligada: devida")
    check(not aut.stories_devida(datetime(2026, 11, 3, 9, 59), reg, [], cfg)[0] and not aut.stories_devida(datetime(2026, 11, 4, 12), reg, [], cfg)[0], "antes da hora ou em outro dia: não")
    check(not aut.stories_devida(ter, {"stories_serie": {"ligada": False}}, [], cfg)[0], "chave desligada: não roda")
    check(not aut.stories_devida(ter, reg, [{"automacao": "stories_serie", "semana": "2026-W45"}], cfg)[0], "já rodou nesta semana: não repete")
    check(aut.stories_proxima(datetime(2026, 11, 1, 12), cfg, []).startswith("03/11 10h"), f"próxima rodada calculada ({aut.stories_proxima(datetime(2026, 11, 1, 12), cfg, [])})")
    c2 = aut.stories_configurar({"dia_semana": "4", "hora": "18", "plataformas": "instagram,tiktok"})
    check(c2["dia_semana"] == 4 and c2["hora"] == 18 and c2["plataformas"] == ["instagram"] and aut.stories_config()["hora"] == 18, "configurar grava dia/hora e ignora plataforma desconhecida")
    aut.stories_configurar({"dia_semana": "1", "hora": "10", "plataformas": "youtube,instagram"})
    aut.alternar("stories_serie", True)
    item = next(x for x in aut.planejadas() if x["id"] == "stories_serie")
    check(item["grupo"] == "Editor GS" and item["ligada"] and item["existe"] and "0 rodada" in item["detalhe"], "lista mostra a série como automação do app, ligada, 0 rodadas")

    # 3. gateway: rodada cria o pedido; entrega vira rascunho de Story na Publora
    api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.GSI_DB = db; api.ENTRADA.mkdir(); api.SAIDA.mkdir()
    criadas, status, comentarios = [], {}, {}
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            criadas.append(kw["json"]); return {"id": f"issue-{len(criadas)}", "identifier": f"GRA-{len(criadas)}", **kw["json"]}
        if metodo == "GET" and url.endswith("/comments"):
            return comentarios.get(url.split("/")[-2], [])
        if metodo == "GET" and "/issues/issue-" in url:
            iid = url.rsplit("/", 1)[-1]; return {"id": iid, "status": status.get(iid, "todo"), "description": next((c["description"] for i, c in enumerate(criadas) if f"issue-{i+1}" == iid), "")}
        return []
    api._pc = pc_falso
    async def sem_sinc(forcar=False): return []
    api._sincronizar_instrucoes = sem_sinc
    avisos = []
    api.pushn.enviar = lambda t, c="", u="/", tag="", **k: avisos.append((t, u)) or {"ok": True}
    CH = []
    def publora_falsa(req: httpx.Request):
        CH.append((req.method, req.url.path, req.content if req.url.host != "s3.falso" else b""))
        p = req.url.path
        if req.url.host == "s3.falso": return httpx.Response(200)
        if p.endswith("/platform-connections"): return httpx.Response(200, json={"connections": [{"platformId": "instagram-111", "username": "thiago", "connectionStatus": "active"}, {"platformId": "youtube-1", "connectionStatus": "active"}]})
        if p.endswith("/create-post"): return httpx.Response(200, json={"postGroupId": "pgS"})
        if p.endswith("/get-upload-url"): return httpx.Response(200, json={"uploadUrl": "https://s3.falso/up", "mediaId": "m1"})
        if "/complete-media/" in p: return httpx.Response(404)
        if "/get-post/" in p: return httpx.Response(200, json={"postGroupId": "pgS", "status": "draft", "posts": [{"platform": "instagram", "status": "draft"}]})
        return httpx.Response(404, json={"error": p})
    _orig = pub.Publora.__init__
    pub.Publora.__init__ = lambda self, chave=None, transport=None: _orig(self, chave, httpx.MockTransport(publora_falsa))
    c = TestClient(api.app)

    r = c.get("/api/gs/automacoes/rodadas")
    check(r.status_code == 200 and r.json()["rodadas"] == [] and r.json()["config"]["dia_semana"] == 1 and "proxima" in r.json(), "rodadas: vazio, config e próxima")
    r = c.post("/api/gs/automacoes/stories_serie/rodar")
    rod = r.json()
    check(r.status_code == 200 and rod["estado"] == "pedido_aberto" and rod["codigo"] == "GRA-1" and rod["fonte"]["id"] == "i1" and rod["por"] == "Raphael", f"rodar agora abre o pedido com a dúvida escolhida ({r.status_code} {str(rod)[:80]})")
    check(criadas[0]["title"].startswith("Dúvida da semana:") and "fluxos/stories-serie.md" in criadas[0]["description"] and "h9" not in criadas[0]["description"] and "@thiago" not in criadas[0]["description"], "issue do Editor com o fluxo e sem autor")
    idx = json.loads(api.INDICE.read_text()); ent = idx["issue-1"]
    check(ent["origem"] == "automacao" and ent["pasta"] == "Automações" and ent["fluxo"] == "stories-serie", "índice guarda origem automacao, pasta Automações e fluxo")
    check(len(aut.rodadas()) == 1 and aut.stories_fontes_usadas() == {"instagram:i1"}, "rodada registrada e fonte marcada como usada")
    # ainda em andamento: nada muda
    r = c.post("/api/gs/automacoes/stories_serie/concluir"); check(r.json()["feitas"] == [], "pedido ainda aberto: concluir não faz nada")
    # entrega sem vídeo
    status["issue-1"] = "done"; slug = ent["slug"]
    r = c.post("/api/gs/automacoes/stories_serie/concluir")
    check(r.json()["feitas"][0]["estado"] == "entregue_sem_video" and avisos and "sem vídeo" in avisos[-1][0], "concluído sem o mp4: registra e avisa")
    # segunda rodada, com entrega completa; sem chave da Publora
    r = c.post("/api/gs/automacoes/stories_serie/rodar"); rod2 = r.json()
    check(rod2["fonte"]["id"] == "y6" and rod2["codigo"] == "GRA-2", "segunda rodada pega a próxima dúvida")
    slug2 = json.loads(api.INDICE.read_text())["issue-2"]["slug"]; pasta2 = api.SAIDA / slug2; pasta2.mkdir(parents=True)
    (pasta2 / "final_stories_9x16.mp4").write_bytes(b"\x00" * 4000)
    comentarios["issue-2"] = [{"id": "m1", "authorAgentId": "ag", "body": "## Resumo\nfeito\n\n## Roteiro\nTela 1: ...\n\n## Legenda do post\nDúvida da semana: live no Instagram sem travar pelo OBS. Manda a sua!\n\n## Hashtags\n#obs #live #gravasimples", "createdAt": "2026-11-01T10:00:00Z"}]
    status["issue-2"] = "done"; os.environ.pop("PUBLORA_API_KEY", None)
    r = c.post("/api/gs/automacoes/stories_serie/concluir"); f2r = r.json()["feitas"]
    check(len(f2r) == 1 and f2r[0]["estado"] == "entregue_sem_publora" and "live no Instagram" in f2r[0]["legenda"] and "#obs" in f2r[0]["legenda"], f"sem PUBLORA_API_KEY: entregue, legenda montada das seções ({f2r and f2r[0]['estado']})")
    check(not any("/create-post" in x[1] for x in CH), "sem chave não chama a Publora")
    # terceira rodada: com chave → rascunho STORIES, sem agendar
    os.environ["PUBLORA_API_KEY"] = "sk_teste"
    r = c.post("/api/gs/automacoes/stories_serie/rodar"); rod3 = r.json(); check(rod3.get("fonte") and rod3["fonte"]["id"] == "y1", f"terceira rodada: próxima dúvida ({rod3.get('estado')} {str(rod3.get('fonte'))[:80]})")
    slug3 = json.loads(api.INDICE.read_text())["issue-3"]["slug"]; pasta3 = api.SAIDA / slug3; pasta3.mkdir(parents=True)
    (pasta3 / "final_stories_9x16.mp4").write_bytes(b"\x00" * 4000)
    comentarios["issue-3"] = [{"id": "m1", "authorAgentId": "ag", "body": "## Legenda do post\nDá pra gravar nos dois formatos de uma vez. Olha só.\n\n## Hashtags\n#obs", "createdAt": "2026-11-01T10:00:00Z"}]
    status["issue-3"] = "done"; CH.clear()
    r = c.post("/api/gs/automacoes/stories_serie/concluir"); f3r = r.json()["feitas"]
    check(len(f3r) == 1 and f3r[0]["estado"] == "rascunho_publora" and f3r[0]["publora"]["postGroupId"] == "pgS" and f3r[0]["publora"]["contas"] == ["instagram-111"], f"com chave: rascunho na Publora na conta do Instagram ({f3r and f3r[0]['estado']})")
    corpo = json.loads(next(x[2] for x in CH if x[1].endswith("/create-post")))
    check(corpo["platformSettings"]["instagram"]["videoType"] == "STORIES" and corpo["platforms"] == ["instagram-111"], "create-post com videoType STORIES")
    check(not any("/update-post" in x[1] for x in CH), "nunca agenda (sem update-post)")
    reg = json.loads((pasta3 / "publicacoes.json").read_text())
    check(reg[0]["tipo_instagram"] == "STORIES" and reg[0]["automacao"] == "stories_serie" and reg[0]["postGroupId"] == "pgS", "publicacoes.json registra o rascunho da automação")
    check(avisos[-1][0].startswith("Stories da semana: rascunho") and avisos[-1][1] == "/c/issue-3", "push avisa o rascunho com o link da conversa")
    # revisor de marca segura preço
    r = c.post("/api/gs/automacoes/stories_serie/rodar"); rod4 = r.json(); check(rod4["fonte"]["id"] == "y3", "quarta rodada: última dúvida válida")
    slug4 = json.loads(api.INDICE.read_text())["issue-4"]["slug"]; pasta4 = api.SAIDA / slug4; pasta4.mkdir(parents=True); (pasta4 / "final_stories_9x16.mp4").write_bytes(b"\x00" * 4000)
    comentarios["issue-4"] = [{"id": "m1", "authorAgentId": "ag", "body": "## Legenda do post\nCurso por R$ 297, últimas vagas hoje! Link na bio.\n", "createdAt": "2026-11-01T10:00:00Z"}]
    status["issue-4"] = "done"; CH.clear()
    r = c.post("/api/gs/automacoes/stories_serie/concluir"); f4r = r.json()["feitas"]
    check(len(f4r) == 1 and f4r[0]["estado"] == "bloqueado_revisor" and not any("/create-post" in x[1] for x in CH), f"legenda com preço/escassez: revisor segura, nada vai à Publora ({f4r and f4r[0]['estado']})")
    # sem fonte
    r = c.post("/api/gs/automacoes/stories_serie/rodar"); check(r.json()["estado"] == "sem_fonte" and len(criadas) == 4, "sem dúvida nova: rodada sem_fonte e nenhum pedido novo")
    r = c.get("/api/gs/automacoes/rodadas"); check(len(r.json()["rodadas"]) == 5 and r.json()["rodadas"][0]["estado"] == "sem_fonte", "rodadas listadas, mais recente primeiro")
    r = c.get("/api/gs/automacoes"); it = next(x for x in r.json()["itens"] if x["id"] == "stories_serie")
    check("5 rodada(s)" in it["detalhe"] and it["ultima"], "aba Automações mostra o resumo da série")
    # cancelamento
    status["issue-1"] = "cancelled"
    rods = aut.rodadas(); r1 = next(x for x in rods if x["issue"] == "issue-1"); r1["estado"] = "pedido_aberto"; aut.rodada_gravar(r1)
    r = c.post("/api/gs/automacoes/stories_serie/concluir"); check(any(x["estado"] == "cancelado" for x in r.json()["feitas"]), "pedido cancelado no Editor vira rodada cancelada")


    # ---- Automação 2 · Reel reciclado com gancho novo ---------------------------------------------------------------
    def banco2(p: Path):
        con = sqlite3.connect(p)
        con.executescript("""
        create table sources(source_id int, platform text, handle text, kind text);
        create table performance_snapshots(snapshot_id int, platform text, item_id text, owner text, horizon text, computed_at text, views int, likes int, comments int, engagement_rate real, format text, theme text, median_views_format real, ratio_vs_format_median real, age_days int);
        create table ig_posts(shortcode text, caption text, posted_at text, video_duration_s real, is_paid int, url text);
        create table yt_videos(video_id text, title text, description text, published_at text, duration_s int);
        """)
        con.executemany("insert into sources values (?,?,?,?)", [(1, "youtube", "gravasimples", "own"), (2, "instagram", "thiago.obsstudio", "own"), (3, "youtube", "concorrente", "competitor")])
        snaps = [("instagram", "R1", "thiago.obsstudio", "2026-10-28T08:00:00Z", 60000, 12.0, "reel"), ("instagram", "R1", "thiago.obsstudio", "2026-09-01T08:00:00Z", 50000, 10.0, "reel"),  # snapshot antigo não conta
                 ("instagram", "R2", "thiago.obsstudio", "2026-10-28T08:00:00Z", 250000, 50.0, "reel"), ("instagram", "R3", "thiago.obsstudio", "2026-10-28T08:00:00Z", 15000, 3.0, "reel"),
                 ("instagram", "R4", "thiago.obsstudio", "2026-10-28T08:00:00Z", 10000, 2.0, "reel"), ("instagram", "R5", "thiago.obsstudio", "2026-10-28T08:00:00Z", 10000, 2.0, "reel"),
                 ("instagram", "R6", "thiago.obsstudio", "2026-10-28T08:00:00Z", 6000, 1.2, "reel"),
                 ("youtube", "S1", "gravasimples", "2026-10-28T08:00:00Z", 8000, 5.0, "short"), ("youtube", "L1", "gravasimples", "2026-10-28T08:00:00Z", 12000, 9.0, "long"),
                 ("youtube", "X1", "concorrente", "2026-10-28T08:00:00Z", 900000, 100.0, "short")]
        con.executemany("insert into performance_snapshots values (?,?,?,?,'current',?,?,0,0,0.1,?,'',5000,?,10)", [(i, a, b, c, d, e, g, f) for i, (a, b, c, d, e, f, g) in enumerate(snaps)])
        posts = [("R1", "Como gravar a tela e a webcam juntas no OBS. Olha só.", "2026-02-10T10:00:00Z", 58.0, 0, "https://www.instagram.com/reel/R1/"),
                 ("R2", "Preset novo do OBS pra live", "2026-10-25T10:00:00Z", 40.0, 0, "https://www.instagram.com/reel/R2/"),  # recente demais
                 ("R3", "Dia de kart com a família", "2026-01-10T10:00:00Z", 30.0, 0, "https://www.instagram.com/reel/R3/"),  # sem tema
                 ("R4", "Como gravar aula no OBS com luz boa", "2026-01-10T10:00:00Z", 30.0, 1, "https://www.instagram.com/reel/R4/"),  # pago
                 ("R5", "Gravar no OBS em 4 segundos", "2026-01-10T10:00:00Z", 4.0, 0, "https://www.instagram.com/reel/R5/"),  # curto demais
                 ("R6", "Microfone pra gravar aula", "2026-01-10T10:00:00Z", 30.0, 0, "https://www.instagram.com/reel/R6/")]  # razão baixa
        con.executemany("insert into ig_posts values (?,?,?,?,?,?)", posts)
        con.executemany("insert into yt_videos values (?,?,?,?,?)", [("S1", "3 funções do OBS para quem grava aula", "", "2024-09-12T12:00:00Z", 34), ("L1", "Tutorial completo do OBS", "", "2024-09-12T12:00:00Z", 900), ("X1", "OBS do concorrente", "", "2024-01-01T00:00:00Z", 30)])
        con.commit(); con.close()
    db2 = tmp / "gs2.db"; banco2(db2); api.GSI_DB = db2
    hoje = datetime(2026, 11, 1, 12, 0)
    rcfg = aut.reciclado_config()
    cands = aut.reciclado_candidatos(db2, api.SAIDA, set(), rcfg, hoje)
    check([c["id"] for c in cands] == ["R1", "S1"], f"candidatos: só evergreens próprios com tema, não pagos, 45+ dias, 12–90 s, razão ≥ 1,5, Reel/Short; ordem por razão ({[c['id'] for c in cands]})")
    c1 = cands[0]
    check(c1["origem"] == "gsi" and c1["url"] == "https://www.instagram.com/reel/R1/" and c1["razao"] == 12.0 and c1["duracao_s"] == 58 and c1["idade_dias"] > 200 and "webcam" in c1["legenda"], "candidato traz link, razão, duração, idade e legenda")
    check([c["id"] for c in aut.reciclado_candidatos(db2, api.SAIDA, {"instagram:R1"}, rcfg, hoje)] == ["S1"], "original já reciclado sai da lista")
    check(aut.reciclado_candidatos(db2, api.SAIDA, set(), {**rcfg, "plataformas": ["youtube"]}, hoje)[0]["id"] == "S1" and aut.reciclado_candidatos(tmp / "nada.db", None, set(), rcfg, hoje) == [], "filtro de plataforma; banco ausente: lista vazia")
    # peça do app publicada e medida, com arquivo local, entra primeiro
    pa = api.SAIDA / "2026-08-01-peca-app"; pa.mkdir(parents=True); (pa / "final_9x16.mp4").write_bytes(b"\x00" * 100)
    (pa / "publicacoes.json").write_text(json.dumps([{"tipo": "publora", "quando": "2026-08-01T10:00:00", "posts": [{"permalink": "https://www.instagram.com/reel/R1/"}]}]), encoding="utf-8")
    cands2 = aut.reciclado_candidatos(db2, api.SAIDA, set(), rcfg, hoje, {"x": {"slug": "2026-08-01-peca-app", "titulo": "Peça do app", "codigo": "GRA-0", "secoes": [{"chave": "gancho", "conteudo": "Grava tela e webcam juntas"}]}})
    check(cands2[0]["origem"] == "app" and cands2[0]["arquivo"] == "saida/2026-08-01-peca-app/final_9x16.mp4" and cands2[0]["gancho"] == "Grava tela e webcam juntas" and cands2[0]["id"] == "R1" and len(cands2) == 2, f"peça do app com arquivo local vem primeiro e substitui o mesmo id do GSI ({cands2[0]['origem']} {len(cands2)})")
    import shutil as _sh; _sh.rmtree(pa)
    # pedido
    ped = aut.reciclado_pedido(c1, "entrada/_reciclagem/instagram-R1/origem.mp4", rcfg)
    check(ped.startswith("Reel reciclado: Como gravar a tela") and "fluxos/reel-reciclado.md" in ped and "`entrada/_reciclagem/instagram-R1/origem.mp4`" in ped and "MESMO corte" in ped and "## Abertura original" in ped and "voz clonada não entra" in ped and "rascunho de Reels" in ped and "Não escreva no Notion" in ped, "pedido cita fluxo, arquivo, regra do experimento, seções e proíbe Notion")
    check("Pode regravar só a abertura com a voz clonada" in aut.reciclado_pedido(c1, "x.mp4", {**rcfg, "voz_clonada": True}), "com voz_clonada ligada o pedido libera só a abertura, rotulada")
    # agenda
    regr = {"reel_reciclado": {"ligada": True}}
    check(aut.reciclado_devida(datetime(2026, 11, 1, 9, 5), regr, [], rcfg) == (True, "na hora"), "ligada, 9h05, sem rodada: devida")
    check(not aut.reciclado_devida(datetime(2026, 11, 1, 8, 59), regr, [], rcfg)[0] and not aut.reciclado_devida(datetime(2026, 11, 1, 9, 5), {}, [], rcfg)[0], "antes da hora ou desligada: não")
    check(not aut.reciclado_devida(datetime(2026, 11, 5, 10), regr, [{"automacao": "reel_reciclado", "quando": "2026-11-01T09:10:00", "estado": "pedido_aberto"}], rcfg)[0], "última rodada há 4 dias com cada_dias=7: não")
    check(aut.reciclado_devida(datetime(2026, 11, 8, 10), regr, [{"automacao": "reel_reciclado", "quando": "2026-11-01T09:10:00", "estado": "pedido_aberto"}], rcfg)[0], "7 dias depois: devida")
    check(aut.reciclado_devida(datetime(2026, 11, 8, 10), regr, [{"automacao": "reel_reciclado", "quando": "2026-11-01T09:10:00", "estado": "sem_fonte"}], rcfg)[0], "rodada sem_fonte não conta no intervalo")
    check(aut.reciclado_proxima(datetime(2026, 11, 1, 12), rcfg, [{"automacao": "reel_reciclado", "quando": "2026-11-01T09:10:00", "estado": "pedido_aberto"}]).startswith("08/11 09h"), f"próxima = última + 7 dias ({aut.reciclado_proxima(datetime(2026, 11, 1, 12), rcfg, [{'automacao': 'reel_reciclado', 'quando': '2026-11-01T09:10:00', 'estado': 'pedido_aberto'}])})")
    rc2 = aut.reciclado_configurar({"cada_dias": "3", "min_razao": "2,5", "min_idade_dias": "-1", "voz_clonada": "sim", "plataformas": "instagram"})
    check(rc2["cada_dias"] == 3 and rc2["min_razao"] == 2.5 and rc2["min_idade_dias"] == 45 and rc2["voz_clonada"] and rc2["plataformas"] == ["instagram"], "configurar grava e ignora valor inválido")
    aut.reciclado_configurar({"cada_dias": "7", "min_razao": "1.5", "voz_clonada": "nao", "plataformas": "instagram,youtube"})
    # gateway: rodada baixa o original (falso) e abre o pedido
    baixados = []
    def baixar_falso(fonte, entrada):
        pasta = Path(entrada) / "_reciclagem" / f"{fonte['plataforma']}-{fonte['id']}"; pasta.mkdir(parents=True, exist_ok=True); (pasta / "origem.mp4").write_bytes(b"\x00" * 2000)
        baixados.append(fonte["id"]); return f"entrada/_reciclagem/{pasta.name}/origem.mp4"
    aut.reciclado_baixar = baixar_falso
    def publora_falsa2(req: httpx.Request):
        p = req.url.path
        if p.endswith("/upload-instagram-cover"): CH.append((req.method, p, b"")); return httpx.Response(200, json={"cover": {"url": "https://cdn.falso/capa.jpg"}})
        if "/update-post/" in p: CH.append((req.method, p, req.content)); return httpx.Response(200, json={"ok": True})
        return publora_falsa(req)
    pub.Publora.__init__ = lambda self, chave=None, transport=None: _orig(self, chave, httpx.MockTransport(publora_falsa2))
    r = c.get("/api/gs/automacoes/rodadas"); rj = r.json()
    check(r.status_code == 200 and [x["id"] for x in rj["reciclado"]["candidatos"]] == ["R1", "S1"] and rj["reciclado"]["config"]["cada_dias"] == 7 and "proxima" in rj["reciclado"], "rodadas traz os candidatos e a config da reciclagem")
    n_antes = len(criadas)
    r = c.post("/api/gs/automacoes/reel_reciclado/rodar"); rod = r.json()
    check(r.status_code == 200 and rod["estado"] == "pedido_aberto" and rod["automacao"] == "reel_reciclado" and rod["fonte"]["id"] == "R1" and rod["arquivo"] == "entrada/_reciclagem/instagram-R1/origem.mp4" and baixados == ["R1"], f"rodar agora baixa o original e abre o pedido ({rod.get('estado')} {rod.get('fonte', {}) and rod['fonte'].get('id')})")
    issue_r = criadas[-1]; iid = f"issue-{len(criadas)}"
    check(issue_r["title"].startswith("Reel reciclado:") and "fluxos/reel-reciclado.md" in issue_r["description"] and "Fluxo: `fluxos/reel-reciclado.md`" in issue_r["description"], "issue do Editor com o fluxo reel-reciclado")
    ent_r = json.loads(api.INDICE.read_text())[iid]
    check(ent_r["origem"] == "automacao" and ent_r["pasta"] == "Automações" and ent_r["fluxo"] == "reel-reciclado", "índice: origem automacao, pasta Automações, fluxo reel-reciclado")
    check(aut.reciclado_usados() == {"instagram:R1"} and [x["id"] for x in aut.reciclado_candidatos(db2, api.SAIDA, aut.reciclado_usados(), rcfg, hoje)] == ["S1"], "R1 vira usado; próximo candidato é S1")
    r = c.post("/api/gs/automacoes/reel_reciclado/concluir"); check(r.json()["feitas"] == [], "pedido aberto: concluir não faz nada")
    # entrega → rascunho de Reels com capa + experimento.json
    slug_r = ent_r["slug"]; pasta_r = api.SAIDA / slug_r; pasta_r.mkdir(parents=True)
    (pasta_r / "final_9x16.mp4").write_bytes(b"\x00" * 4000); (pasta_r / "capa.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
    comentarios[iid] = [{"id": "m1", "authorAgentId": "ag", "body": "## Resumo\nmesmo corte\n\n## Gancho\nVocê grava a tela e a webcam separadas? Olha o erro.\n\n## Abertura original\nComo gravar a tela e a webcam juntas no OBS\n\n## Legenda do post\nTela e webcam no mesmo vídeo, sem programa extra. Salva pra testar depois.\n\n## Hashtags\n#obs #webcam #gravasimples", "createdAt": "2026-11-01T12:00:00Z"}]
    status[iid] = "done"; CH.clear(); os.environ["PUBLORA_API_KEY"] = "sk_teste"
    r = c.post("/api/gs/automacoes/reel_reciclado/concluir"); fr = r.json()["feitas"]
    check(len(fr) == 1 and fr[0]["estado"] == "rascunho_publora" and fr[0]["publora"]["postGroupId"] == "pgS" and fr[0]["gancho_novo"].startswith("Você grava a tela") and fr[0]["gancho_original"].startswith("Como gravar a tela"), f"entrega vira rascunho de Reels e a rodada guarda gancho novo e original ({fr and fr[0]['estado']})")
    corpo = json.loads(next(x[2] for x in CH if x[1].endswith("/create-post")))
    check(corpo["platformSettings"]["instagram"]["videoType"] == "REELS" and corpo["platforms"] == ["instagram-111"] and "#obs" in corpo["content"], "create-post com videoType REELS, conta do Instagram e legenda nova")
    check(any(x[1].endswith("/upload-instagram-cover") for x in CH) and not any(b"scheduled" in (x[2] or b"") for x in CH if "/update-post/" in x[1]), "capa enviada; nunca agenda (update-post só da capa)")
    exp = json.loads((pasta_r / "experimento.json").read_text())
    check(exp["tipo"] == "mesma peça, outro gancho" and exp["original"]["id"] == "R1" and exp["original"]["razao"] == 12.0 and exp["gancho_novo"].startswith("Você grava") and exp["gancho_original"].startswith("Como gravar") and exp["publora"]["postGroupId"] == "pgS" and exp["status"] == "aberto", "experimento.json registra original, ganchos, Publora e como ler")
    from servico import pecas as pcs
    fich = pcs.ficha(slug_r, api.SAIDA, db2, {iid: {"slug": slug_r, "pasta": "Automações", "codigo": "GRA-r", "secoes": []}})
    check(fich["experimento"]["gancho_novo"] == exp["gancho_novo"] and fich["etiquetas"].get("origem") == "automacao", "ficha da peça mostra o experimento e a origem automacao")
    check(avisos[-1][0] == "Reel reciclado: rascunho na Publora" and avisos[-1][1] == f"/c/{iid}", "push avisa o rascunho de Reels")
    it = next(x for x in c.get("/api/gs/automacoes").json()["itens"] if x["id"] == "reel_reciclado")
    check(it["grupo"] == "Editor GS" and it["existe"] and "1 rodada(s)" in it["detalhe"] and "rascunho de Reels" in it["detalhe"], "aba Automações mostra o Reel reciclado como automação do app")
    # revisor segura; download que falha; sem fonte
    r = c.post("/api/gs/automacoes/reel_reciclado/rodar"); rod2 = r.json(); iid2 = f"issue-{len(criadas)}"
    check(rod2["fonte"]["id"] == "S1" and rod2["arquivo"].endswith("youtube-S1/origem.mp4"), "segunda rodada pega o Short")
    slug2r = json.loads(api.INDICE.read_text())[iid2]["slug"]; p2 = api.SAIDA / slug2r; p2.mkdir(parents=True); (p2 / "final_9x16.mp4").write_bytes(b"\x00" * 4000)
    comentarios[iid2] = [{"id": "m1", "authorAgentId": "ag", "body": "## Gancho\nMais de 20 mil alunos já fizeram isso\n\n## Legenda do post\nÚltimas vagas por R$ 297, link na bio.", "createdAt": "2026-11-01T12:00:00Z"}]
    status[iid2] = "done"; CH.clear()
    r = c.post("/api/gs/automacoes/reel_reciclado/concluir"); f2r = r.json()["feitas"]
    check(len(f2r) == 1 and f2r[0]["estado"] == "bloqueado_revisor" and not any("/create-post" in x[1] for x in CH) and not (p2 / "experimento.json").exists(), f"preço/escassez na legenda: revisor segura, nada vai à Publora, sem experimento ({f2r and f2r[0]['estado']})")
    def baixar_falha(fonte, entrada): raise aut.ErroReciclagem("Instagram pediu login")
    aut.reciclado_baixar = baixar_falha
    aut.reciclado_configurar({"min_razao": "1.1"})  # R6 (1,2×) vira candidato
    n_antes = len(criadas); r = c.post("/api/gs/automacoes/reel_reciclado/rodar"); rod3 = r.json()
    check(rod3["estado"] == "sem_video_origem" and "login" in rod3["historico"][-1]["nota"] and len(criadas) == n_antes and avisos[-1][0].startswith("Reel reciclado: original não baixou"), f"download falha: rodada sem_video_origem, nenhum pedido, push ({rod3.get('estado')})")
    aut.reciclado_baixar = baixar_falso; aut.reciclado_configurar({"min_razao": "1.5"})
    r = c.post("/api/gs/automacoes/reel_reciclado/rodar"); check(r.json()["estado"] == "sem_fonte" and len(criadas) == n_antes, "todos reciclados: sem_fonte e nenhum pedido novo")
    rj = c.get("/api/gs/automacoes/rodadas").json()
    check(rj["rodadas"][0]["automacao"] == "reel_reciclado" and sum(1 for x in rj["rodadas"] if x["automacao"] == "stories_serie") == 5 and sum(1 for x in rj["rodadas"] if x["automacao"] == "reel_reciclado") == 4, "as duas automações convivem na mesma lista de rodadas")

    # ---- fechamento do experimento no D+7 --------------------------------------------------------------------------
    from datetime import date as _date
    pasta_r2 = api.SAIDA / slug_r
    (pasta_r2 / "publicacoes.json").write_text(json.dumps([{"tipo": "publora", "quando": "2026-10-20T10:00:00", "posts": [{"permalink": "https://www.instagram.com/reel/NOVA1/"}]}]), encoding="utf-8")
    con = sqlite3.connect(db2); con.execute("insert into performance_snapshots values (99,'instagram','NOVA1','thiago.obsstudio','current','2026-10-28T08:00:00Z',90000,0,0,0.1,'reel','',5000,18.0,8)"); con.commit(); con.close()
    check(aut.experimentos_fechar(api.SAIDA, db2, {}, hoje=_date(2026, 10, 24)) == [], "antes de 7 dias publicada: não fecha")
    fech = aut.experimentos_fechar(api.SAIDA, db2, {}, hoje=_date(2026, 10, 28))
    check(len(fech) == 1 and fech[0]["status"] == "ganhou" and fech[0]["resultado"]["razao_nova"] == 18.0 and fech[0]["resultado"]["razao_original"] == 12.0 and fech[0]["resultado"]["dias"] == 8, f"7+ dias e métrica: fecha como ganhou (18 vs 12) ({fech and fech[0]['status']})")
    check(json.loads((pasta_r2 / "experimento.json").read_text())["status"] == "ganhou" and aut.experimentos_fechar(api.SAIDA, db2, {}, hoje=_date(2026, 11, 5)) == [], "gravado no arquivo; não reabre")
    check(aut.experimento_veredito(9.0, 12.0) == "perdeu" and aut.experimento_veredito(13.0, 12.0) == "empate" and aut.experimento_veredito(None, 12.0) is None and aut.experimento_veredito(1.0, 0) is None, "veredito: perdeu ≤ 0,8×, empate no meio, sem dado = None")
    r = c.get("/api/gs/automacoes/experimentos"); je = r.json()
    check(r.status_code == 200 and je["ganhou"] == 1 and je["itens"][0]["slug"] == slug_r and "regra" in je, "endpoint lista os experimentos com o status")
    from servico import ganchos as _g
    gn = next(i for i in _g.de_experimentos(api.SAIDA) if i["papel"] == "gancho novo")
    check(gn["razao"] == 18.0 and gn["estado"] == "experimento ganhou", "biblioteca de ganchos mostra a razão da peça nova depois do fechamento")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
