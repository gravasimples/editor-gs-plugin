"""Testes isolados do compartilhamento pelo celular (gateway). Nunca tocam workspace/: tudo em pasta temporária,
Paperclip substituído por um dublê. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_compartilhar.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.ENTRADA = tmp / "entrada"; api.RECEBIDOS = api.ENTRADA / "_recebidos"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.ENTRADA.mkdir()
    criadas = []
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            criadas.append(kw["json"]); return {"id": f"issue-{len(criadas)}", "identifier": f"GRA-{len(criadas)}", **kw["json"]}
        return []
    api._pc = pc_falso
    c = TestClient(api.app, follow_redirects=False)

    # 1. share_target do PWA: POST multipart → redireciona para o Novo pedido com o token
    r = c.post("/compartilhar", data={"title": "obvio04", "text": "Edite com reels-padrao"}, files=[("arquivos", ("obvio04.mp4", b"\x00" * 1000, "video/mp4"))])
    check(r.status_code == 303, "compartilhar redireciona (303)")
    loc = r.headers.get("location", "")
    check(loc.startswith("/novo?recebido="), f"redireciona para /novo?recebido= ({loc})")
    token = loc.split("=", 1)[1]
    check((api.RECEBIDOS / token / "obvio04.mp4").stat().st_size == 1000, "arquivo guardado em entrada/_recebidos/<token>/")
    r = c.get(f"/api/gs/recebidos/{token}")
    check(r.status_code == 200 and r.json()["texto"] == "obvio04\nEdite com reels-padrao", "GET recebidos devolve texto (título + texto)")
    check(r.json()["arquivos"][0]["nome"] == "obvio04.mp4" and r.json()["arquivos"][0]["tipo"] == "video", "GET recebidos lista o arquivo com tipo")

    # 2. Atalho do iPhone: JSON com token e url
    r = c.post("/api/gs/recebidos", data={"texto": "Só legendar"}, files=[("arquivos", ("a b.m4a", b"\x01" * 10, "audio/m4a"))])
    check(r.status_code == 200 and r.json()["url"] == f"/novo?recebido={r.json()['token']}", "POST recebidos devolve token e url")
    check(r.json()["arquivos"][0]["nome"] == "a_b.m4a", "nome de arquivo saneado")
    token2 = r.json()["token"]

    # 3. Token inválido / inexistente
    check(c.get("/api/gs/recebidos/../../etc").status_code in (404, 400), "token com caminho é recusado")
    check(c.get("/api/gs/recebidos/nao-existe-123").status_code == 404, "token inexistente dá 404")
    check(c.post("/api/gs/recebidos", data={"texto": "  "}).status_code == 400, "sem texto e sem arquivo dá 400")

    # 4. Novo pedido com o material recebido: arquivos vão para entrada/<slug>/ e a pasta temporária some
    r = c.post("/api/gs/conversas", data={"pedido": "Edite este vídeo", "fluxo": "reels-padrao", "estilo": "padrao", "recebido": token})
    check(r.status_code == 200, f"nova conversa com recebido ({r.status_code} {r.text[:120]})")
    slug = r.json().get("slug") or ""
    check((api.ENTRADA / slug / "obvio04.mp4").exists(), "arquivo movido para entrada/<slug>/")
    check(not (api.RECEBIDOS / token).exists(), "pasta _recebidos/<token> apagada")
    check(f"entrada/{slug}/obvio04.mp4" in criadas[-1]["description"], "descrição da issue cita o arquivo")
    check(c.get(f"/api/gs/recebidos/{token}").status_code == 404, "token já usado dá 404")

    # 5. Sem pedido escrito: título vem do arquivo recebido
    r = c.post("/api/gs/conversas", data={"pedido": "", "recebido": token2})
    check(r.status_code == 200 and criadas[-1]["title"] == "Editar a_b.m4a", "sem pedido, título usa o arquivo recebido")
    check(c.post("/api/gs/conversas", data={"pedido": "", "recebido": "x"}).status_code == 400, "sem pedido, sem arquivo e token ruim dá 400")

    # 6. Fallback do app: rota do PWA aberta direto devolve o index.html; API e arquivos continuam 404
    if api.DIST.exists():
        r = c.get(f"/novo?recebido={token2}")
        check(r.status_code == 200 and "text/html" in r.headers.get("content-type", ""), "GET /novo?recebido= devolve o index.html")
        check(c.get("/c/abc-123").status_code == 200, "GET /c/<id> devolve o index.html")
        check(c.get("/nao-existe.png").status_code == 404, "arquivo inexistente continua 404")
        check(c.get("/api/gs/nada").status_code == 404, "rota de API inexistente continua 404")
    else:
        print("SKIP fallback do app (app/dist não existe)")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
