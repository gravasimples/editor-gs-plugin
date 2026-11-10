"""Testes isolados: YouTube direto (OAuth, upload resumable, capa, status) com httpx.MockTransport, e destaques de concorrentes com gs.db falso.
Token em pasta temporária; nada toca servico/youtube_token.json, a rede nem o gs.db real."""
import json, sqlite3, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import httpx
from fastapi.testclient import TestClient
from servico import api, youtube as yt, redes, publicar as pub

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

chamadas = []
def servidor_falso(req: httpx.Request):
    chamadas.append((req.method, req.url.path, dict(req.headers)))
    u = req.url
    if u.host == "oauth2.googleapis.com":
        body = dict(x.split("=", 1) for x in req.content.decode().split("&"))
        if body.get("grant_type") == "authorization_code":
            return httpx.Response(200, json={"access_token": "A1", "refresh_token": "R1", "expires_in": 3600})
        return httpx.Response(200, json={"access_token": "A2", "expires_in": 3600})
    if u.path == "/youtube/v3/channels":
        return httpx.Response(200, json={"items": [{"id": "UC1", "snippet": {"title": "Grava Simples", "customUrl": "@gravasimples"}, "statistics": {"subscriberCount": "1234"}}]})
    if u.path == "/upload/youtube/v3/videos" and req.method == "POST":
        return httpx.Response(200, headers={"Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=X"}, json={})
    if "upload_id=X" in str(u):
        rng = req.headers.get("Content-Range", "")
        if rng.endswith("/30000000") and not rng.startswith("bytes 25165824"):
            return httpx.Response(308, headers={"Range": rng.split(" ")[1].split("/")[0]})
        return httpx.Response(200, json={"id": "vid123", "status": {"uploadStatus": "uploaded", "privacyStatus": "private"}})
    if u.path == "/upload/youtube/v3/thumbnails/set":
        return httpx.Response(403, json={"error": {"message": "The authenticated user doesn't have permissions to upload and set custom video thumbnails."}})
    if u.path == "/youtube/v3/videos":
        return httpx.Response(200, json={"items": [{"status": {"privacyStatus": "private", "publishAt": "2026-11-01T12:00:00Z", "uploadStatus": "processed"}, "statistics": {"viewCount": "7"}, "snippet": {"title": "T"}}]})
    return httpx.Response(404, json={"error": {"message": "rota falsa não existe: " + str(u)}})
transport = httpx.MockTransport(servidor_falso)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    yt.ARQ_TOKEN = tmp / "youtube_token.json"
    import os
    os.environ["YT_CLIENT_ID"] = "cid.apps"; os.environ["YT_CLIENT_SECRET"] = "sec"
    e = yt.estado("https://x/cb"); check(e["configurado"] and not e["conectado"] and e["canal"] is None, "estado: configurado, ainda não conectado")
    url = yt.url_autorizacao("https://x/cb"); state = url.split("state=")[1].split("&")[0]
    check("accounts.google.com" in url and "access_type=offline" in url and "youtube.upload" in url, "URL de autorização com offline e escopos")
    try:
        yt.trocar_codigo("c", "errado", "https://x/cb", transport); check(False, "state errado é recusado")
    except yt.ErroYouTube:
        check(True, "state errado é recusado")
    tok = yt.trocar_codigo("codigo", state, "https://x/cb", transport)
    check(tok["refresh_token"] == "R1" and tok["canal"]["titulo"] == "Grava Simples" and yt.ARQ_TOKEN.exists(), "troca do código grava o token e lê o canal")
    check(yt.estado("https://x/cb")["conectado"] and yt.estado("https://x/cb")["canal"]["handle"] == "@gravasimples", "estado conectado mostra o canal")
    # token vencido → refresh mantém o refresh_token antigo
    d = json.loads(yt.ARQ_TOKEN.read_text()); d["obtido_em"] = 0; yt.ARQ_TOKEN.write_text(json.dumps(d))
    check(yt.token_valido(transport) == "A2" and json.loads(yt.ARQ_TOKEN.read_text())["refresh_token"] == "R1", "refresh renova o access e preserva o refresh_token")

    video = tmp / "final_16x9.mp4"; video.write_bytes(b"\x00" * 30_000_000); capa = tmp / "capa.png"; capa.write_bytes(b"\x89PNG" + b"\x00" * 100)
    chamadas.clear()
    r = yt.publicar(video, "Título do vídeo", "descrição", ["obs", "webcam"], "public", publicar_em="2026-11-01T12:00:00Z", capa=capa, transport=transport)
    inicio = next(c for c in chamadas if c[1] == "/upload/youtube/v3/videos" and c[0] == "POST")
    puts = [c for c in chamadas if c[0] == "PUT"]
    check(r["video_id"] == "vid123" and r["url"] == "https://youtu.be/vid123" and inicio[2].get("x-upload-content-length") == "30000000", "upload resumable começa com o tamanho e devolve o id")
    check(len(puts) == 4 and puts[0][2]["content-range"] == "bytes 0-8388607/30000000" and puts[-1][2]["content-range"].endswith("29999999/30000000"), f"arquivo sobe em pedaços de 8 MB ({len(puts)} PUTs)")
    check(r["privacidade"] == "private" and r["publishAt"] == "2026-11-01T12:00:00Z", "agendado sobe privado com publishAt")
    check(r["capa"] is None and "capa_erro" in r, "capa recusada pelo YouTube vira aviso, não erro")
    try:
        yt.publicar(video, "", transport=transport); check(False, "sem título dá erro")
    except yt.ErroYouTube:
        check(True, "sem título dá erro")
    try:
        yt.publicar(video, "t", privacidade="segredo", transport=transport); check(False, "privacidade inválida dá erro")
    except yt.ErroYouTube:
        check(True, "privacidade inválida dá erro")
    s = yt.estado_video("vid123", transport); check(s["status"] == "agendado" and s["views"] == "7", "estado do vídeo: agendado com views")

    # rotas do gateway
    api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"; api.SAIDA = tmp / "saida"; api.ENTRADA = tmp / "entrada"
    (api.SAIDA / "s1").mkdir(parents=True); api.ENTRADA.mkdir(); (api.SAIDA / "s1" / "final_16x9.mp4").write_bytes(b"\x00" * 1000)
    api.INDICE.write_text(json.dumps({"i1": {"slug": "s1"}}))
    async def pc_falso(metodo, url, **kw): return []
    api._pc = pc_falso
    c = TestClient(api.app)
    est = c.get("/api/gs/youtube/estado").json(); check(est["conectado"] and est["redirect_uri"].endswith("/api/gs/youtube/callback"), "rota de estado")
    r = c.get("/api/gs/youtube/conectar", follow_redirects=False); check(r.status_code == 302 and "accounts.google.com" in r.headers["location"], "conectar redireciona ao Google")
    check(c.get("/api/gs/youtube/callback?error=access_denied", follow_redirects=False).status_code == 400, "callback com erro dá 400")
    yt_pub = yt.publicar
    yt.publicar = lambda *a, **k: yt_pub(*a, **{**k, "transport": transport})
    r = c.post("/api/gs/conversas/i1/youtube", data={"arquivo": "final_16x9.mp4", "titulo": "T", "descricao": "d", "tags": "#obs, webcam\nmeet", "privacidade": "unlisted"})
    check(r.status_code == 200 and r.json()["video_id"] == "vid123" and r.json()["privacidade"] == "unlisted", "rota de publicar sobe o vídeo da entrega")
    hist = pub.registros(api.SAIDA / "s1"); check(len(hist) == 1 and hist[0]["tipo"] == "youtube" and hist[0]["url"] == "https://youtu.be/vid123", "publicação registrada em publicacoes.json")
    check(c.post("/api/gs/conversas/i1/youtube", data={"arquivo": "../x.mp4", "titulo": "T"}).status_code == 400, "arquivo com barra é recusado")
    check(c.post("/api/gs/conversas/i1/youtube", data={"arquivo": "nao.mp4", "titulo": "T"}).status_code == 400, "arquivo inexistente dá 400")
    yt_est = yt.estado_video; yt.estado_video = lambda vid, transport=None: yt_est(vid, transport=transport or globals()["transport"])
    h = c.get("/api/gs/conversas/i1/publicacoes?atualizar=1").json(); check(h[0].get("status") == "agendado" and h[0].get("views") == "7", "atualizar status consulta o YouTube")
    check(c.get("/api/gs/publicar/estado").json()["youtube"]["conectado"], "estado de publicar inclui o YouTube")

    # destaques de concorrentes com gs.db falso
    db = tmp / "gs.db"; con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE sources (source_id INTEGER PRIMARY KEY, platform TEXT, handle TEXT, display_name TEXT, kind TEXT, category TEXT);
    CREATE TABLE yt_videos (video_id TEXT PRIMARY KEY, source_id INTEGER, title TEXT, published_at TEXT, duration_s INTEGER, format TEXT);
    CREATE TABLE yt_video_metrics (video_id TEXT, captured_at TEXT, views INTEGER);
    INSERT INTO sources VALUES (1,'youtube','gravasimples','GS','own',NULL),(2,'youtube','rival','Rival','competitor','direto'),(3,'youtube','novo','Novo','reference',NULL);""")
    import datetime
    hoje = datetime.date(2026, 10, 30)
    for i, v in enumerate([100, 120, 110, 900, 130]):
        con.execute("insert into yt_videos values (?,?,?,?,?,?)", (f"r{i}", 2, f"Vídeo {i}", (hoje - datetime.timedelta(days=10 + i)).isoformat() + "T10:00:00Z", 300, "long"))
        con.execute("insert into yt_video_metrics values (?,?,?)", (f"r{i}", "2026-10-01T00:00:00Z", 1)); con.execute("insert into yt_video_metrics values (?,?,?)", (f"r{i}", "2026-10-29T00:00:00Z", v))
    con.execute("insert into yt_videos values ('o1',1,'Próprio','2026-10-20T10:00:00Z',300,'long')"); con.execute("insert into yt_video_metrics values ('o1','2026-10-29T00:00:00Z',99999)")
    con.execute("insert into yt_videos values ('n1',3,'Só um','2026-10-20T10:00:00Z',300,'short')"); con.execute("insert into yt_video_metrics values ('n1','2026-10-29T00:00:00Z',5000)")
    con.execute("insert into yt_videos values ('velho',2,'Antigo','2025-01-01T10:00:00Z',300,'long')"); con.execute("insert into yt_video_metrics values ('velho','2026-10-29T00:00:00Z',99999)")
    con.commit(); con.close()
    d = redes.destaques_concorrentes(db, dias=120, hoje=hoje)
    check([x["video_id"] for x in d["itens"]] == ["r3"] and d["itens"][0]["razao"] == 7.5 and d["itens"][0]["mediana_canal"] == 120, f"só o vídeo acima de 1,6× a mediana do canal entra ({[x['video_id'] for x in d['itens']]})")
    check(all(x["handle"] != "gravasimples" for x in d["itens"]) and "velho" not in json.dumps(d), "canal próprio e vídeo fora da janela ficam de fora")
    check(any(c_["handle"] == "novo" and c_["mediana"] is None for c_ in d["canais"]), "canal com menos de 3 vídeos aparece sem mediana")
    api.GSI_DB = db
    r = c.get("/api/gs/referencias/concorrentes/destaques?dias=120").json(); check(len(r["itens"]) == 1 and r["itens"][0]["url"].endswith("r3"), "rota de destaques")
    api.GSI_DB = tmp / "nao.db"; check(c.get("/api/gs/referencias/concorrentes/destaques").json()["itens"] == [], "sem gs.db devolve vazio")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
