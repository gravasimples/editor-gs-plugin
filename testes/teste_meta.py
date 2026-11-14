"""Cliente da Meta (servico/meta.py) e rotas (servico/meta_api.py) com transporte falso: sem rede, sem .env real, estado em pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -B testes/teste_meta.py"""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(RAIZ))
tmp = Path(tempfile.mkdtemp(prefix="meta-"))
os.environ["EDITOR_GS_ESTADO"] = str(tmp / "estado"); os.environ["EDITOR_GS_HOME"] = str(tmp / "home")
for k in ("META_IG_TOKEN", "META_IG_USER_ID", "META_FB_TOKEN", "META_FB_IG_USER_ID", "META_APP_ID", "META_APP_SECRET", "META_GRAPH_VERSION"):
    os.environ.pop(k, None)
import httpx
from servico import meta
from servico import caminhos as cam
assert str(cam.ENV).startswith(str(tmp)), "o teste não pode ler o .env real"
FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

TOKEN_IG = "IGAA" + "x" * 40; TOKEN_FB = "EAA" + "y" * 40
ENV_IG = {"META_IG_TOKEN": TOKEN_IG, "META_IG_USER_ID": "1784"}
ENV_FB = {"META_FB_TOKEN": TOKEN_FB, "META_FB_IG_USER_ID": "1790"}
ENV_2 = {**ENV_IG, **ENV_FB}
CHAMADAS = []


def falso(rotas):
    """Transporte falso: rotas = {(método, caminho) ou caminho: dict | callable(req) -> dict | (status, dict)}."""
    def h(req: httpx.Request):
        CHAMADAS.append(req)
        chave = (req.method, req.url.path)
        alvo = rotas.get(chave, rotas.get(req.url.path))
        if alvo is None:
            return httpx.Response(404, json={"error": {"message": f"rota falsa inexistente {req.method} {req.url.path}", "code": 803}})
        r = alvo(req) if callable(alvo) else alvo
        status, corpo = r if isinstance(r, tuple) else (200, r)
        return httpx.Response(status, json=corpo)
    return httpx.MockTransport(h)


# 1. situação sem credenciais (sem rede)
s = meta.situacao(env={})
check(s == {"configurada": False, "pendente": "META_PENDENTE", "como": "docs/META-APP.md", "versao": "v26.0", "credenciais": {"ig": False, "fb": False}, "business_discovery": False, "renovacao_automatica": False}, f"situacao sem credenciais: {s}")
try:
    meta.conta(env={}); check(False, "conta sem credenciais deveria falhar")
except meta.ErroMeta as e:
    check(e.code == "META_PENDENTE" and "META-APP" in str(e), "conta sem credenciais → ErroMeta META_PENDENTE")

# 2. situação com as duas credenciais: host certo, token só no cabeçalho, nada de token na saída
rotas = {("GET", "/v26.0/me"): {"user_id": "1784", "username": "thiago.obsstudio"}, ("GET", "/v26.0/1790"): {"id": "1790", "username": "thiago.obsstudio"}}
CHAMADAS.clear()
s = meta.situacao(transport=falso(rotas), env=ENV_2)
check(s["configurada"] and s["credenciais"] == {"ig": True, "fb": True} and s["business_discovery"] and s["tokens"]["ig"]["valido"] and s["tokens"]["fb"]["valido"], f"situacao com as duas credenciais: {json.dumps(s)[:200]}")
hosts = {c.url.host for c in CHAMADAS}
check(hosts == {"graph.instagram.com", "graph.facebook.com"}, f"hosts por credencial: {hosts}")
check(all(c.headers.get("Authorization", "").startswith("Bearer ") and "access_token" not in str(c.url) for c in CHAMADAS), "token só no cabeçalho, nunca na URL")
check(TOKEN_IG not in json.dumps(s) and TOKEN_FB not in json.dumps(s), "situacao não expõe token")
s = meta.situacao(transport=falso({}), env=ENV_IG)
check(s["configurada"] and s["tokens"]["ig"]["valido"] is False and any("business_discovery" in a for a in s["avisos"]), f"token que não responde: valido=False e aviso; sem fb avisa concorrentes: {s['avisos']}")

# 3. conta + mídias (parse e cache)
midias_api = {"data": [
    {"id": "m1", "media_type": "VIDEO", "media_product_type": "REELS", "permalink": "https://www.instagram.com/reel/AAA/", "caption": "Como gravar " + "x" * 200, "timestamp": "2026-11-09T12:00:00+0000", "thumbnail_url": "https://cdn/t1.jpg", "like_count": 10, "comments_count": 2},
    {"id": "m2", "media_type": "IMAGE", "media_product_type": "FEED", "permalink": "https://www.instagram.com/p/BBB/", "caption": "Carrossel", "timestamp": "2026-11-08T12:00:00+0000", "media_url": "https://cdn/i2.jpg", "like_count": 5, "comments_count": 0}],
    "paging": {"next": "https://graph.instagram.com/next"}}
n_midias = {"n": 0}
def rota_midias(req):
    n_midias["n"] += 1
    assert req.url.params["limit"] == "25" and "permalink" in req.url.params["fields"]
    return midias_api
rotas = {("GET", "/v26.0/1784"): {"user_id": "1784", "username": "thiago.obsstudio", "followers_count": 1000, "media_count": 2, "account_type": "Media_Creator"}, ("GET", "/v26.0/1784/media"): rota_midias}
cli = meta.Cliente("ig", transport=falso(rotas), env=ENV_IG)
c = cli.conta()
check(c["usuario"] == "thiago.obsstudio" and c["seguidores"] == 1000 and c["id"] == "1784" and c["credencial"] == "ig", f"conta: {c}")
m = cli.midias()
check(m["n"] == 2 and m["proxima"] and m["itens"][0]["tipo"] == "REELS" and m["itens"][0]["thumbnail"] == "https://cdn/t1.jpg" and m["itens"][0]["legenda"].endswith("…") and len(m["itens"][0]["legenda"]) == 118, f"midias: parse do reel {m['itens'][0]}")
check(m["itens"][1]["tipo"] == "IMAGE" and m["itens"][1]["thumbnail"] == "https://cdn/i2.jpg" and m["itens"][1]["likes"] == 5, "midias: imagem usa media_url como thumbnail")
cli.midias(); check(n_midias["n"] == 1, "cache de 60 s: segunda chamada não vai à rede")
meta._cache.clear()

# 4. insights da mídia: tudo de uma vez e, na recusa de uma métrica, uma a uma com erro tolerado
def rota_insights(req):
    met = req.url.params["metric"]
    if "," in met:
        return (400, {"error": {"message": "(#100) The following metrics (ig_reels_avg_watch_time) are not supported for this media", "code": 100, "type": "OAuthException"}})
    if met == "ig_reels_avg_watch_time":
        return (400, {"error": {"message": "(#100) metric not supported", "code": 100}})
    return {"data": [{"name": met, "period": "lifetime", "values": [{"value": {"views": 500, "reach": 400, "saved": 7, "shares": 3, "likes": 10, "comments": 2, "total_interactions": 22, "ig_reels_video_view_total_time": 9000}[met]}]}]}
rotas = {("GET", "/v26.0/m1"): {"id": "m1", "media_product_type": "REELS", "media_type": "VIDEO"}, ("GET", "/v26.0/m1/insights"): rota_insights}
ins = meta.Cliente("ig", transport=falso(rotas), env=ENV_IG).insights_midia("m1")
check(ins["tipo_produto"] == "REELS" and ins["metricas"]["views"] == 500 and ins["metricas"]["reach"] == 400 and ins["metricas"]["total_interactions"] == 22, f"insights_midia: métricas atuais {ins['metricas']}")
check(list(ins["erros"]) == ["ig_reels_avg_watch_time"] and "metric" in ins["erros"]["ig_reels_avg_watch_time"].lower(), f"insights_midia: erro por métrica tolerado {ins['erros']}")
rotas = {("GET", "/v26.0/1784/insights"): lambda req: {"data": [{"name": n, "period": "day", "total_value": {"value": 100}} for n in req.url.params["metric"].split(",")]} if req.url.params["metric_type"] == "total_value" else (400, {"error": {"message": "x"}})}
ic = meta.Cliente("ig", transport=falso(rotas), env=ENV_IG).insights_conta(dias=7)
check(ic["metricas"].get("reach") == 100 and ic["metricas"].get("follower_count") == 100 and not ic["erros"] and ic["dias"] == 7, f"insights_conta: total_value por métrica {ic['metricas']}")

# 5. comentários pseudonimizados + comentários do dono
coms = {"data": [{"id": "c1", "text": "Qual webcam?", "timestamp": "2026-11-09T13:00:00+0000", "username": "fulano_123", "like_count": 1,
                  "replies": {"data": [{"id": "c1r", "text": "Logitech C920", "timestamp": "2026-11-09T14:00:00+0000", "username": "thiago.obsstudio"}]}},
                 {"id": "c2", "text": "Top", "timestamp": "2026-11-09T13:30:00+0000", "username": "beltrano", "like_count": 0}]}
rotas = {("GET", "/v26.0/1784"): {"user_id": "1784", "username": "thiago.obsstudio"}, ("GET", "/v26.0/m1/comments"): coms}
cm = meta.Cliente("ig", transport=falso(rotas), env=ENV_IG).comentarios("m1")
check(cm["n"] == 2 and cm["sem_resposta"] == 1 and cm["itens"][0]["respondido"] and cm["itens"][0]["respostas"][0]["proprio"], f"comentarios: respondido/sem_resposta {cm['sem_resposta']}")
check("fulano_123" not in json.dumps(cm) and "usuario" not in cm["itens"][0] and len(cm["itens"][0]["autor"]) == 8 and cm["itens"][0]["respostas"][0]["autor"] == "thiago.obsstudio", "comentarios: autor pseudonimizado, dono nomeado")
meta._cache.clear()

# 6. limite de publicação
rotas = {("GET", "/v26.0/1784/content_publishing_limit"): {"data": [{"quota_usage": 2, "config": {"quota_total": 100, "quota_duration": 86400}}]}}
lim = meta.Cliente("ig", transport=falso(rotas), env=ENV_IG).limite_publicacao()
check(lim == {"usado": 2, "total": 100, "restante": 98, "janela_s": 86400}, f"limite_publicacao: {lim}")

# 7. business_discovery: só com fb; parse do perfil e das mídias; erro claro só com ig
bd = {"business_discovery": {"username": "agapemultimidia", "name": "Ágape", "followers_count": 50000, "media_count": 900, "follows_count": 10,
      "media": {"data": [{"id": "b1", "caption": "ref", "media_type": "VIDEO", "media_product_type": "REELS", "permalink": "https://www.instagram.com/reel/CCC/", "timestamp": "2026-11-01T00:00:00+0000", "like_count": 300, "comments_count": 12, "view_count": 9000}]}, "id": "1790"}}
def rota_bd(req):
    f = req.url.params["fields"]
    assert f.startswith("business_discovery.username(agapemultimidia){") and "media.limit(10){" in f and "view_count" in f, f
    assert req.headers["Authorization"] == f"Bearer {TOKEN_FB}"
    return bd
r = meta.business_discovery("@agapemultimidia", n=10, transport=falso({("GET", "/v26.0/1790"): rota_bd}), env=ENV_2)
check(r["perfil"]["usuario"] == "agapemultimidia" and r["perfil"]["seguidores"] == 50000 and r["n"] == 1 and r["itens"][0]["views"] == 9000 and r["itens"][0]["likes"] == 300 and r["itens"][0]["tipo"] == "REELS", f"business_discovery: {r['perfil']}")
check(CHAMADAS[-1].url.host == "graph.facebook.com", "business_discovery usa graph.facebook.com mesmo com ig presente")
try:
    meta.business_discovery("agapemultimidia", transport=falso({}), env=ENV_IG); check(False, "business_discovery só com ig deveria falhar")
except meta.ErroMeta as e:
    check(e.code == "SEM_FB" and "META_FB_TOKEN" in str(e), f"business_discovery só com ig: erro claro ({e})")
try:
    meta.Cliente("fb", transport=falso({}), env=ENV_FB).business_discovery("joão sem.conta!"); check(False, "username inválido")
except meta.ErroMeta as e:
    check("inválido" in str(e), "business_discovery recusa username inválido antes da rede")
try:
    meta.Cliente("fb", transport=falso({("GET", "/v26.0/1790"): {"id": "1790"}}), env=ENV_FB).business_discovery("privado"); check(False, "sem dados")
except meta.ErroMeta as e:
    check("privada" in str(e), "business_discovery sem dados: mensagem explica")

# 8. erro da Graph API: code/subcode, sem vazar token (mesmo quando a Meta ecoa o token na mensagem)
rotas = {("GET", "/v26.0/1784"): (400, {"error": {"message": f"Error validating access token {TOKEN_IG} access_token={TOKEN_IG}: Session has expired", "type": "OAuthException", "code": 190, "error_subcode": 463, "fbtrace_id": "x"}})}
try:
    meta.Cliente("ig", transport=falso(rotas), env=ENV_IG).conta(); check(False, "erro 190 deveria levantar")
except meta.ErroMeta as e:
    check(e.code == 190 and e.subcode == 463 and e.tipo == "OAuthException" and e.http == 400, f"ErroMeta carrega code/subcode/tipo/http: {e.dict()}")
    check(TOKEN_IG not in str(e) and "<removido>" in str(e) and "expired" in str(e), f"mensagem sem token: {e}")
    check(TOKEN_IG not in json.dumps(e.dict()), "e.dict() sem token")
try:
    meta.Cliente("ig", transport=httpx.MockTransport(lambda req: httpx.Response(500, text="<html>oops</html>")), env=ENV_IG).conta(); check(False, "HTML 500")
except meta.ErroMeta as e:
    check(e.http == 500 and "não é JSON" in str(e), f"resposta não JSON vira ErroMeta: {e}")

# 9. publicar_reel: container IN_PROGRESS → FINISHED → media_publish → permalink; trial e cover; ERROR levanta
estado = {"n": 0}; dormidas = []
def rota_media(req):
    corpo = dict(httpx.QueryParams(req.content.decode()))
    assert corpo["media_type"] == "REELS" and corpo["video_url"] == "https://pub/final.mp4" and corpo["caption"] == "legenda" and corpo["share_to_feed"] == "true", corpo
    assert corpo["cover_url"] == "https://pub/capa.jpg" and json.loads(corpo["trial_params"]) == {"graduation_strategy": "MANUAL"}, corpo
    return {"id": "cont1"}
def rota_cont(req):
    estado["n"] += 1
    return {"id": "cont1", "status_code": "IN_PROGRESS" if estado["n"] < 3 else "FINISHED", "status": "ok"}
def rota_publish(req):
    assert dict(httpx.QueryParams(req.content.decode()))["creation_id"] == "cont1"
    return {"id": "pub9"}
rotas = {("POST", "/v26.0/1784/media"): rota_media, ("GET", "/v26.0/cont1"): rota_cont, ("POST", "/v26.0/1784/media_publish"): rota_publish, ("GET", "/v26.0/pub9"): {"id": "pub9", "permalink": "https://www.instagram.com/reel/ZZZ/"}}
p = meta.publicar_reel("https://pub/final.mp4", "legenda", cover_url="https://pub/capa.jpg", trial=True, transport=falso(rotas), env=ENV_IG, intervalo_s=1, dormir=dormidas.append)
check(p == {"id": "pub9", "permalink": "https://www.instagram.com/reel/ZZZ/", "container_id": "cont1", "status": "PUBLISHED"}, f"publicar_reel: {p}")
check(estado["n"] == 3 and dormidas == [1, 1], f"esperou o container duas vezes antes de publicar: {dormidas}")
rotas2 = {**rotas, ("GET", "/v26.0/cont1"): {"id": "cont1", "status_code": "ERROR", "status": "Error: The video file is too small"}}
try:
    meta.publicar_reel("https://pub/final.mp4", "legenda", cover_url="https://pub/capa.jpg", trial=True, transport=falso(rotas2), env=ENV_IG, dormir=lambda s: None); check(False, "ERROR deveria levantar")
except meta.ErroMeta as e:
    check(e.code == "ERROR" and "too small" in str(e), f"container ERROR: {e}")
try:
    meta.publicar_reel("/local/final.mp4", "x", transport=falso({}), env=ENV_IG); check(False, "URL local")
except meta.ErroMeta as e:
    check("pública" in str(e), "publicar_reel recusa caminho local antes da rede")
# tempo máximo: nunca sai de IN_PROGRESS
rotas3 = {**rotas, ("GET", "/v26.0/cont1"): {"id": "cont1", "status_code": "IN_PROGRESS"}}
try:
    meta.publicar_reel("https://pub/final.mp4", "legenda", cover_url="https://pub/capa.jpg", trial=True, transport=falso(rotas3), env=ENV_IG, intervalo_s=10, maximo_s=30, dormir=lambda s: None); check(False, "timeout")
except meta.ErroMeta as e:
    check("IN_PROGRESS" in str(e), "container que nunca termina: erro depois do tempo máximo")

# 10. renovar_token: só ig; guarda em estado/meta_token.json com permissão restrita; .env não é tocado; credenciais() passa a usar o novo
NOVO = "IGAA" + "n" * 40
def rota_refresh(req):
    assert req.url.params["grant_type"] == "ig_refresh_token" and req.url.params["access_token"] == TOKEN_IG
    return {"access_token": NOVO, "token_type": "bearer", "expires_in": 5184000}
rn = meta.Cliente("ig", transport=falso({("GET", "/v26.0/refresh_access_token"): rota_refresh, ("GET", "/refresh_access_token"): rota_refresh}), env=ENV_IG).renovar_token()
check(rn["renovado"] and rn["dias"] == 60 and "token" not in json.dumps(rn) and NOVO not in json.dumps(rn), f"renovar_token: {rn}")
arq = cam.estado("meta_token.json")
check(arq.exists() and json.loads(arq.read_text())["ig"]["token"] == NOVO and (os.name == "nt" or oct(arq.stat().st_mode)[-3:] == "600"), "token novo em estado/meta_token.json com chmod 600")
os.environ.update(ENV_IG)
check(meta.credenciais()["ig"]["token"] == NOVO and meta.credenciais()["ig"]["expira_em"], "credenciais() prefere o token guardado ao do ambiente")
for k in ENV_IG: os.environ.pop(k)
try:
    meta.renovar_token(transport=falso({}), env=ENV_FB); check(False, "renovar só com fb")
except meta.ErroMeta as e:
    check(e.code == "SEM_IG", "renovar_token só com fb: erro claro")

# 11. rotas: 409 sem credencial (situacao 200), 502 em erro da Graph
from fastapi import FastAPI
from fastapi.testclient import TestClient
from servico import meta_api
app = FastAPI(); app.include_router(meta_api.router); tc = TestClient(app)
r = tc.get("/api/gs/meta/situacao")
check(r.status_code == 200 and r.json()["configurada"] is False and r.json()["pendente"] == "META_PENDENTE" and r.json()["como"] == "docs/META-APP.md", f"GET situacao sem credencial: 200 {r.json()}")
for rota in ("/api/gs/meta/conta", "/api/gs/meta/midias", "/api/gs/meta/midias/m1/insights", "/api/gs/meta/midias/m1/comentarios", "/api/gs/meta/limite", "/api/gs/meta/concorrente/agape", "/api/gs/meta/insights"):
    r = tc.get(rota); check(r.status_code == 409 and "META-APP" in r.json()["detail"], f"GET {rota} sem credencial: 409")
r = tc.post("/api/gs/meta/renovar"); check(r.status_code == 409, "POST renovar sem credencial: 409")
check(not any(getattr(rt, "path", "").endswith("publicar") for rt in meta_api.router.routes), "nenhuma rota de publicar no router")
os.environ.update(ENV_IG)
# com credencial: o gateway cria o Cliente sem transporte; aqui o transporte falso entra por monkeypatch (nunca rede)
original = meta.Cliente.__init__
def init_falso(self, qual=None, transport=None, env=None, timeout=40):
    original(self, qual, transport=falso({("GET", "/v26.0/1784"): (400, {"error": {"message": f"boom {TOKEN_IG}", "code": 190}}), ("GET", "/v26.0/me"): (400, {"error": {"message": "token velho", "code": 190}})}), env=env, timeout=timeout)
meta.Cliente.__init__ = init_falso
try:
    r = tc.get("/api/gs/meta/concorrente/agape"); check(r.status_code == 409 and "META_FB_TOKEN" in r.json()["detail"], f"concorrente só com ig: 409 explicando ({r.status_code})")
    r = tc.get("/api/gs/meta/situacao"); check(r.status_code == 200 and r.json()["configurada"] and r.json()["tokens"]["ig"]["valido"] is False and TOKEN_IG not in r.text and NOVO not in r.text, "situacao com credencial e token recusado: 200, valido=False, nada vaza")
    r = tc.get("/api/gs/meta/conta"); check(r.status_code == 502 and "boom" in r.json()["detail"] and TOKEN_IG not in r.text, f"erro da Graph vira 502 sem token: {r.status_code} {r.json()}")
finally:
    meta.Cliente.__init__ = original
    for k in ENV_IG: os.environ.pop(k, None)

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
