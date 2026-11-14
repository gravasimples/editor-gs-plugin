"""Testes isolados do compartilhamento pelo celular (gateway). Nunca tocam workspace/: tudo em pasta temporária,
Paperclip substituído por um dublê. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_compartilhar.py"""
import json, re, sys, tempfile
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
        m = re.fullmatch(r".*/api/issues/issue-(\d+)", url)
        if metodo == "GET" and m:
            return {"id": f"issue-{m.group(1)}", "identifier": f"GRA-{m.group(1)}", "createdAt": "2026-11-11T10:00:00Z", **criadas[int(m.group(1)) - 1]}
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

    # 4b. Conversa mostra só o que o usuário digitou; o prompt montado pelo app fica em "detalhes"; título curto sem GRA-NN (11/11/2026)
    longo = "Corte o tempo morto do GRA-7 e deixe dinâmico, com legenda grande e zoom nas partes mais importantes da fala"
    tok = c.post("/api/gs/recebidos", data={"texto": "x"}, files=[("arquivos", ("t.mp4", b"\x00", "video/mp4"))]).json()["token"]
    r = c.post("/api/gs/conversas", data={"pedido": longo + "\n\nSiga a ficha de marca: `marca/manual.md`.", "pedido_usuario": longo, "fluxo": "reels-padrao", "recebido": tok})
    cid = r.json()["id"]; t = criadas[-1]["title"]
    check(len(t) <= 61 and "GRA-" not in t and t.startswith("Corte o tempo morto do e deixe") and t.endswith("…"), f"título curto sem GRA-NN ({t})")
    d = c.get(f"/api/gs/conversas/{cid}").json(); ped = d["mensagens"][0]
    check(ped["texto"] == longo and "Siga a ficha" in (ped["detalhes"] or "") and "saida/" in ped["detalhes"], "fala do usuário = texto digitado; prompt completo em detalhes")
    check(ped["anexos"] == ["t.mp4"] and ped["fluxo"] == "reels-padrao", "anexos e fluxo como chips")
    criadas.append({"title": "Teste tecnico do sistema 3", "description": "Teste tecnico do sistema 3\n\nEntregue os arquivos em `saida/x/`\n\n<!-- gs-slug: 2026-11-10-teste-x -->"})
    d = c.get(f"/api/gs/conversas/issue-{len(criadas)}").json()
    check(d["teste"] is True and d["mensagens"][0]["texto"] == "Teste tecnico do sistema 3", "pedido antigo: separa pelo bloco do app e marca teste")

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
