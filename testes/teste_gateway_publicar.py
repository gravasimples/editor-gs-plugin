"""Testes isolados de publicar/guardar (Publora + Drive). Sem rede: Publora por MockTransport, rclone por script falso,
pastas temporárias. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_publicar.py"""
import json, os, stat, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _falso  # noqa: E402
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import httpx
from fastapi.testclient import TestClient
from servico import api, publicar as pub

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

CHAMADAS = []
def publora_falsa(req: httpx.Request):
    CHAMADAS.append((req.method, req.url.path, req.headers.get("x-publora-key"), len(req.content) if req.url.host == "s3.falso" else req.content))
    p = req.url.path
    if req.url.host == "s3.falso":
        return httpx.Response(200)
    if req.headers.get("x-publora-key") != "sk_teste":
        return httpx.Response(401, json={"error": "unauthorized"})
    if p.endswith("/platform-connections"):
        return httpx.Response(200, json={"success": True, "connections": [
            {"platformId": "instagram-111", "username": "thiago.obsstudio", "displayName": "Thiago", "connectionStatus": "active", "tokenStatus": "ok"},
            {"platformId": "youtube-UC22", "username": "gravasimples", "displayName": "Grava Simples", "connectionStatus": "active", "tokenStatus": "ok"}]})
    if p.endswith("/create-post"):
        return httpx.Response(200, json={"success": True, "postGroupId": "pg1", "scheduledTime": None})
    if p.endswith("/get-upload-url"):
        return httpx.Response(200, json={"success": True, "uploadUrl": "https://s3.falso/up?x=1", "fileUrl": "https://media/x.mp4", "mediaId": "m1"})
    if "/complete-media/" in p:
        return httpx.Response(404)
    if p.endswith("/upload-instagram-cover"):
        ct = req.headers.get("content-type", "")
        return httpx.Response(200, json={"success": True, "cover": {"mediaId": "cv1", "url": "https://media/capa.jpg"}}) if ct.startswith("multipart/form-data") and b"pg1" in req.content and b"capa.png" in req.content else httpx.Response(400, json={"error": "multipart esperado"})
    if "/update-post/" in p:
        corpo = json.loads(req.content)
        return httpx.Response(200, json={"success": True, "scheduledTime": corpo.get("scheduledTime")})
    if "/get-post/" in p:
        agendado = any(c[1].endswith("/update-post/pg1") for c in CHAMADAS)
        return httpx.Response(200, json={"success": True, "postGroupId": "pg1", "status": "scheduled" if agendado else "draft", "scheduledTime": None,
                                         "posts": [{"platform": "instagram", "platformId": "instagram-111", "status": "scheduled" if agendado else "draft", "postedId": None, "permalink": None}]})
    return httpx.Response(404, json={"error": p})

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    # pastas isoladas
    api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"; api.ENTRADA = tmp / "entrada"
    slug = "2026-10-29-teste"; (api.SAIDA / slug).mkdir(parents=True)
    (api.SAIDA / slug / "final_9x16.mp4").write_bytes(b"\x00" * 5000); (api.SAIDA / slug / "post.md").write_text("## Descrição do post\noi\n")
    api.INDICE.write_text(json.dumps({"c1": {"slug": slug}}))
    transporte = httpx.MockTransport(publora_falsa)
    _orig_init = pub.Publora.__init__
    def init_falso(self, chave=None, transport=None): _orig_init(self, chave, transporte)
    pub.Publora.__init__ = init_falso
    c = TestClient(api.app)

    # 1. Sem chave: estado mostra pendências, nada quebra
    os.environ.pop("PUBLORA_API_KEY", None); os.environ.pop("DRIVE_DESTINO", None)
    pub.RCLONE = str(tmp / "nao-existe")
    r = c.get("/api/gs/publicar/estado")
    check(r.status_code == 200 and not r.json()["publora"]["configurado"] and "PUBLORA_API_KEY" in r.json()["publora"]["pendencias"][0], "sem chave: Publora pendente")
    check(not r.json()["drive"]["configurado"] and any("rclone" in x for x in r.json()["drive"]["pendencias"]), "sem rclone: Drive pendente")
    r = c.post("/api/gs/conversas/c1/publicar", data={"legenda": "x", "plataformas": "instagram-111"})
    check(r.status_code == 400 and "PUBLORA_API_KEY" in r.text, "publicar sem chave dá 400 explicando")

    # 2. Com chave: contas listadas
    os.environ["PUBLORA_API_KEY"] = "sk_teste"
    r = c.get("/api/gs/publicar/estado")
    check(r.json()["publora"]["configurado"] and [x["plataforma"] for x in r.json()["publora"]["contas"]] == ["instagram", "youtube"], "contas da Publora listadas com plataforma")

    # 3. Rascunho (sem quando): create-post + upload, sem update-post
    CHAMADAS.clear()
    r = c.post("/api/gs/conversas/c1/publicar", data={"legenda": "Legenda #gs", "plataformas": "instagram-111"})
    check(r.status_code == 200 and r.json()["postGroupId"] == "pg1" and r.json()["status"] == "draft", f"rascunho criado ({r.status_code} {r.text[:100]})")
    rotas = [x[1] for x in CHAMADAS]
    check(rotas[:3] == ["/api/v1/create-post", "/api/v1/get-upload-url", "/up"], f"ordem: create-post, get-upload-url, PUT S3 ({rotas})")
    check(not any("/update-post" in x for x in rotas), "rascunho não chama update-post")
    corpo = json.loads(CHAMADAS[0][3]); check(corpo["platformSettings"]["instagram"]["videoType"] == "REELS" and corpo["content"] == "Legenda #gs", "create-post com REELS e legenda")
    check(CHAMADAS[2][3] == 5000, "PUT no S3 manda o arquivo inteiro")
    reg = json.loads((api.SAIDA / slug / "publicacoes.json").read_text())
    check(len(reg) == 1 and reg[0]["tipo"] == "publora" and reg[0]["postGroupId"] == "pg1", "registro em publicacoes.json")

    # 3b. Capa do Reels: multipart em upload-instagram-cover e update-post com coverUrl, antes de agendar
    (api.SAIDA / slug / "capa.png").write_bytes(b"\x89PNG" + b"\x00" * 300)
    CHAMADAS.clear()
    r = c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "instagram-111", "capa": "capa.png"})
    check(r.status_code == 200 and r.json().get("capa") == "https://media/capa.jpg", f"capa enviada e URL devolvida ({r.text[:120]})")
    rotas = [x[1] for x in CHAMADAS]
    check("/api/v1/upload-instagram-cover" in rotas and rotas.index("/api/v1/upload-instagram-cover") > rotas.index("/up"), "capa sobe depois do vídeo")
    up = [x for x in CHAMADAS if "/update-post/pg1" in x[1]]
    check(len(up) == 1 and json.loads(up[0][3])["platformSettings"]["instagram"]["coverUrl"] == "https://media/capa.jpg", "update-post prende a capa (coverUrl)")
    reg = json.loads((api.SAIDA / slug / "publicacoes.json").read_text()); check(reg[-1].get("capa_arquivo") == "capa.png" and reg[-1].get("capa"), "registro guarda a capa")
    CHAMADAS.clear()
    r = c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "youtube-UC22", "capa": "capa.png"})
    check(r.status_code == 200 and not any("cover" in x[1] for x in CHAMADAS), "capa ignorada quando não há Instagram")
    check(c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "instagram-111", "capa": "../capa.png"}).status_code == 400, "capa com caminho é recusada")
    check(c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "instagram-111", "capa": "nao.png"}).status_code == 400, "capa inexistente dá 400")

    # 4. Agendado: update-post com scheduledTime, youtube recebe título
    CHAMADAS.clear()
    r = c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "instagram-111,youtube-UC22", "quando": "2026-11-01T14:00:00.000Z", "titulo": "Tire sua webcam do automático"})
    check(r.status_code == 200 and r.json()["status"] == "scheduled" and r.json()["scheduledTime"] == "2026-11-01T14:00:00.000Z", "agendado com scheduledTime")
    up = [x for x in CHAMADAS if "/update-post/pg1" in x[1]]
    check(len(up) == 1 and json.loads(up[0][3])["status"] == "scheduled", "update-post status=scheduled")
    corpo = json.loads(CHAMADAS[0][3]); check(corpo["platformSettings"]["youtube"]["title"] == "Tire sua webcam do automático" and corpo["platforms"] == ["instagram-111", "youtube-UC22"], "youtube com título e duas contas")

    # 5. Erros de entrada
    check(c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": ""}).status_code == 400, "sem conta dá 400")
    check(c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "instagram-111", "arquivo": "../x.mp4"}).status_code == 400, "arquivo com caminho é recusado")
    check(c.post("/api/gs/conversas/c1/publicar", data={"legenda": "L", "plataformas": "instagram-111", "arquivo": "nao.mp4"}).status_code == 400, "arquivo inexistente dá 400")
    check(c.post("/api/gs/conversas/zzz/publicar", data={"legenda": "L", "plataformas": "instagram-111"}).status_code == 404, "conversa sem entrega dá 404")

    # 6. Histórico com atualização de status
    r = c.get("/api/gs/conversas/c1/publicacoes?atualizar=1")
    check(r.status_code == 200 and len(r.json()) == 4 and r.json()[0]["status"] == "scheduled", "publicacoes atualiza status pela Publora")

    # 7. Drive com rclone falso
    falso = tmp / "rclone"; falso.write_text("#!/bin/sh\necho \"$@\" >> \"$RCLONE_LOG\"\nif [ \"$1\" = listremotes ]; then echo 'gs:'; fi\nif [ \"$1\" = lsjson ]; then echo '[{\"Name\": \"2026-10-29-teste\", \"ID\": \"abc\", \"IsDir\": true}]'; fi\n")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC); falso = _falso.executavel(falso); os.environ["RCLONE_LOG"] = str(tmp / "rclone.log")
    pub.RCLONE = str(falso); os.environ["DRIVE_DESTINO"] = "gs:10. Mídias/Editor GS"
    check(c.get("/api/gs/publicar/estado").json()["drive"]["configurado"], "Drive configurado com rclone + remote + destino")
    r = c.post("/api/gs/conversas/c1/drive", data={"arquivos": "final_9x16.mp4,post.md"})
    check(r.status_code == 200 and r.json()["arquivos"] == ["final_9x16.mp4", "post.md"] and r.json()["link"] == "https://drive.google.com/drive/folders/abc", f"drive copia e devolve link privado pelo ID da pasta ({r.text[:120]})")
    check("link " not in (tmp / "rclone.log").read_text(), "nunca chama rclone link (não torna a pasta pública)")
    log = (tmp / "rclone.log").read_text()
    check(f"copyto {api.SAIDA / slug / 'final_9x16.mp4'} gs:10. Mídias/Editor GS/{slug}/final_9x16.mp4" in log, "rclone copyto para DRIVE_DESTINO/<slug>/")
    check(c.post("/api/gs/conversas/c1/drive", data={"arquivos": "nao.mp4"}).status_code == 400, "arquivo inexistente no Drive dá 400")
    os.environ["DRIVE_DESTINO"] = "outro:pasta"
    check("remote 'outro'" in c.get("/api/gs/publicar/estado").json()["drive"]["pendencias"][0], "remote não configurado aparece na pendência")
    check(len(c.get("/api/gs/conversas/c1/publicacoes").json()) == 5, "registro do Drive no histórico")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
