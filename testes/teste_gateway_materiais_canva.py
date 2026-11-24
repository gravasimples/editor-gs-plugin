"""Testes isolados: materiais do Drive (rclone falso) e Canva Connect (MockTransport). Pastas temporárias."""
import base64, json, os, stat, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _falso  # noqa: E402
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import httpx
from fastapi.testclient import TestClient
from servico import api, materiais as mat, publicar as pub, canva_connect as cv

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.MATERIAIS = tmp / "materiais"; api.ESTILOS_DIR = tmp / "estilos"; api.ESTILOS_DIR.mkdir(); api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    cv.ARQ_TOKEN = tmp / "canva_token.json"
    c = TestClient(api.app)

    # --- materiais ---
    os.environ.pop("DRIVE_DESTINO", None); os.environ.pop("DRIVE_MATERIAIS", None); pub.RCLONE = str(tmp / "nao")
    r = c.get("/api/gs/materiais"); check(r.status_code == 200 and not r.json()["configurado"] and any("DRIVE_MATERIAIS" in x for x in r.json()["pendencias"]), "materiais: pendências sem config")
    check(c.post("/api/gs/materiais/sincronizar").status_code == 400, "sincronizar sem config dá 400")
    # rclone falso: 'sync' copia uma pasta de origem simulada; 'listremotes' responde gs:; 'backend copyid' cria arquivo
    origem = tmp / "drive"; (origem / "logo").mkdir(parents=True); (origem / "fotos").mkdir()
    from PIL import Image
    Image.new("RGB", (200, 80), (255, 255, 255)).save(origem / "logo" / "logo-grava-simples.png"); Image.new("RGB", (100, 100), (10, 10, 10)).save(origem / "fotos" / "thiago.jpg")
    falso = tmp / "rclone"; falso.write_text(f'#!/bin/sh\ncase "$1" in\n listremotes) echo "gs:";;\n sync) rm -rf "$3"; mkdir -p "$3"; cp -r "{origem}"/. "$3"/;;\n backend) mkdir -p "$5"; printf "x" > "$5/arquivo-do-link.mp4";;\n link) echo "https://drive.google.com/drive/folders/abc";;\nesac\n')
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC); falso = _falso.executavel(falso); pub.RCLONE = str(falso)
    os.environ["DRIVE_DESTINO"] = "gs:10. Mídias/Editor GS"; os.environ["DRIVE_MATERIAIS"] = "gs:10. Mídias/Materiais"
    r = c.post("/api/gs/materiais/sincronizar"); j = r.json()
    check(r.status_code == 200 and j["n"] == 2 and (api.MATERIAIS / "INDICE.md").exists(), f"sincronizar espelha e indexa ({r.status_code} {r.text[:80]})")
    check((api.ESTILOS_DIR / "logo.png").exists() and j.get("logo_copiado"), "logo oficial copiado para estilos/logo.png")
    idx = (api.MATERIAIS / "INDICE.md").read_text(encoding="utf-8"); check("fotos/thiago.jpg" in idx and "## logo" in idx, "índice lista arquivos por pasta")
    r = c.get("/api/gs/materiais"); check(r.json()["configurado"] and r.json()["n_arquivos"] == 2 and r.json()["itens"][0]["tipo"] in ("imagem", "video", "arquivo"), "estado após sincronizar")
    r = c.post("/api/gs/materiais/buscar", data={"link": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view"})
    check(r.status_code == 200 and r.json()["id"] == "1AbCdEfGhIjKlMnOp" and r.json()["arquivos"] == ["arquivo-do-link.mp4"], "buscar por link usa copyid")
    check(c.post("/api/gs/materiais/buscar", data={"link": "sem id"}).status_code == 400, "link sem id dá 400")

    # --- canva ---
    os.environ.pop("CANVA_CLIENT_ID", None); os.environ.pop("CANVA_CLIENT_SECRET", None)
    r = c.get("/api/gs/canva/estado"); check(r.status_code == 200 and not r.json()["configurado"] and r.json()["redirect_uri"].endswith("/api/gs/canva/callback"), "canva: estado sem credenciais")
    os.environ["CANVA_CLIENT_ID"] = "cid123"; os.environ["CANVA_CLIENT_SECRET"] = "seg"
    r = c.get("/api/gs/canva/conectar", follow_redirects=False)
    check(r.status_code == 302 and r.headers["location"].startswith("https://www.canva.com/api/oauth/authorize?") and "code_challenge_method=S256" in r.headers["location"] and "client_id=cid123" in r.headers["location"], "conectar redireciona para o Canva com PKCE")
    state = httpx.URL(r.headers["location"]).params["state"]
    chamadas = []
    def canva_falso(req: httpx.Request):
        chamadas.append((req.method, req.url.path, dict(req.headers)))
        if req.url.path.endswith("/oauth/token"):
            body = dict(x.split("=", 1) for x in req.content.decode().split("&"))
            if body["grant_type"] == "authorization_code" and body.get("code") == "abc" and body.get("code_verifier"):
                return httpx.Response(200, json={"access_token": "AT1", "refresh_token": "RT1", "expires_in": 14400, "token_type": "Bearer"})
            if body["grant_type"] == "refresh_token" and body.get("refresh_token") == "RT1":
                return httpx.Response(200, json={"access_token": "AT2", "refresh_token": "RT2", "expires_in": 14400})
            return httpx.Response(400, json={"error": "bad"})
        if req.url.path.endswith("/imports") and req.method == "POST":
            meta = json.loads(req.headers["import-metadata"])
            if meta.get("mime_type", "").endswith("presentation") and req.headers["authorization"] == "Bearer AT2" and len(req.content) == 10:
                return httpx.Response(200, json={"job": {"id": "job1", "status": "in_progress"}})
            return httpx.Response(400, json={"error": "meta"})
        if req.url.path.endswith("/imports/job1"):
            return httpx.Response(200, json={"job": {"id": "job1", "status": "success", "result": {"designs": [{"id": "DXYZ", "urls": {"edit_url": "https://www.canva.com/design/DXYZ/edit", "view_url": "https://www.canva.com/design/DXYZ/view"}}]}}})
        return httpx.Response(404)
    transporte = httpx.MockTransport(canva_falso)
    _tc, _tv, _imp = cv.trocar_codigo, cv.token_valido, cv.importar
    cv.trocar_codigo = lambda code, state, ru, transport=None: _tc(code, state, ru, transport=transporte)
    cv.token_valido = lambda transport=None: _tv(transport=transporte)
    cv.importar = lambda arquivo, titulo, transport=None, esperar_s=90: _imp(arquivo, titulo, transport=transporte, esperar_s=esperar_s)
    check(c.get("/api/gs/canva/callback?code=abc&state=errado").status_code == 400, "callback com state errado é recusado")
    r = c.get(f"/api/gs/canva/callback?code=abc&state={state}", follow_redirects=False)
    check(r.status_code == 302 and json.loads(cv.ARQ_TOKEN.read_text())["refresh_token"] == "RT1", "callback troca o código e guarda o token")
    check(c.get("/api/gs/canva/estado").json()["conectado"], "estado conectado")
    # força refresh: token 'vencido'
    t = json.loads(cv.ARQ_TOKEN.read_text()); t["obtido_em"] = 0; cv.ARQ_TOKEN.write_text(json.dumps(t))
    slug = "2026-10-29-carrossel"; (api.SAIDA / slug).mkdir(parents=True); (api.SAIDA / slug / "carrossel.pptx").write_bytes(b"0123456789"); api.INDICE.write_text(json.dumps({"c1": {"slug": slug}}))
    r = c.post("/api/gs/conversas/c1/canva", data={"arquivo": "carrossel.pptx", "titulo": "Tire sua webcam do automático"})
    check(r.status_code == 200 and r.json()["design_id"] == "DXYZ" and r.json()["edit_url"].endswith("/edit"), f"importa o PPTX e devolve o link de edição ({r.status_code} {r.text[:100]})")
    check(json.loads(cv.ARQ_TOKEN.read_text())["refresh_token"] == "RT2", "refresh token renovado e guardado")
    check(c.get("/api/gs/conversas/c1/canva").json()[0]["design_id"] == "DXYZ", "canva.json registra o design")
    check(c.post("/api/gs/conversas/c1/canva", data={"arquivo": "../x.pptx"}).status_code == 400 and c.post("/api/gs/conversas/c1/canva", data={"arquivo": "nao.pptx"}).status_code == 400, "arquivo inválido ou ausente dá 400")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
