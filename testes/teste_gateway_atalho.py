"""Testes isolados do atalho do celular (link secreto) e das anotações. Pastas temporárias, sem rede.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_atalho.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import os
from fastapi.testclient import TestClient
from servico import api

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.WORKSPACE = tmp / "ws"; api.ENTRADA = api.WORKSPACE / "entrada"; api.RECEBIDOS = api.ENTRADA / "_recebidos"; api.SAIDA = api.WORKSPACE / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.ENTRADA.mkdir(parents=True); api.SAIDA.mkdir()
    os.environ["EDITOR_GS_URL_PUBLICA"] = "https://gs.exemplo.ts.net/"
    c = TestClient(api.app)

    # token
    r = c.get("/api/gs/atalho"); a = r.json()
    check(r.status_code == 200 and len(a["token"]) >= 20 and a["url"] == f"https://gs.exemplo.ts.net/api/webhooks/compartilhar/{a['token']}", "link secreto gerado com a URL pública")
    check(c.get("/api/gs/atalho").json()["token"] == a["token"] and (api.WORKSPACE / "atalho.json").exists(), "token estável entre chamadas (gravado em workspace/atalho.json)")
    check(c.post("/api/webhooks/compartilhar/token-errado", data={"acao": "anotacao", "texto": "x"}).status_code == 403, "token errado dá 403")

    # anotação pelo webhook, com link e arquivo
    r = c.post(f"/api/webhooks/compartilhar/{a['token']}", data={"acao": "anotacao", "texto": "Reels sobre presets https://www.instagram.com/p/abc/ ver depois"}, files=[("arquivos", ("print.png", b"\x89PNG\x00", "image/png"))])
    n = r.json(); check(r.status_code == 200 and n["acao"] == "anotacao" and n["links"] == ["https://www.instagram.com/p/abc/"] and n["arquivos"] == ["print.png"] and n["origem"] == "celular", f"anotação do celular com link e arquivo ({r.text[:120]})")
    check((api.WORKSPACE / "anotacoes" / n["id"] / "print.png").exists() and not list((api.WORKSPACE / "anotacoes").glob("_tmp-*")), "arquivo da anotação na pasta dela, sem pasta temporária sobrando")
    lst = c.get("/api/gs/anotacoes").json(); check(len(lst) == 1 and lst[0]["titulo"].startswith("Reels sobre presets"), "lista de anotações")

    # anotação pelo app, vazia recusada
    check(c.post("/api/gs/anotacoes", data={"texto": "   "}).status_code == 400, "anotação vazia dá 400")
    r = c.post("/api/gs/anotacoes", data={"texto": "Ideia: webcam no automático"}); check(r.status_code == 200 and r.json()["origem"] == "app" and len(c.get("/api/gs/anotacoes").json()) == 2, "anotação pelo app")

    # pedido pelo webhook → material recebido
    r = c.post(f"/api/webhooks/compartilhar/{a['token']}", data={"acao": "pedido", "text": "Edite este vídeo"}, files=[("arquivos", ("take.mp4", b"\x00" * 100, "video/mp4"))])
    j = r.json(); check(r.status_code == 200 and j["acao"] == "pedido" and j["url"].startswith("/novo?recebido=") and (api.RECEBIDOS / j["token"] / "take.mp4").exists(), f"pedido pelo webhook guarda o material e devolve a URL do Novo pedido ({r.text[:100]})")
    check(c.get(f"/api/gs/recebidos/{j['token']}").json()["texto"] == "Edite este vídeo", "material recebido legível pelo app")
    check(c.post(f"/api/webhooks/compartilhar/{a['token']}", data={"acao": "pedido"}).status_code == 400, "pedido sem nada dá 400")

    # anotação vira pedido (vai para recebidos e sai da lista)
    r = c.post(f"/api/gs/anotacoes/{n['id']}/pedido"); j = r.json()
    check(r.status_code == 200 and j["url"].startswith("/novo?recebido=") and (api.RECEBIDOS / j["token"] / "print.png").exists(), "anotação vira material recebido com o arquivo")
    rec = json.loads((api.RECEBIDOS / j["token"] / "recebido.json").read_text()); check(rec["texto"].startswith("Reels sobre presets") and rec["anotacao"] == n["id"], "texto da anotação vira o pedido")
    lst = c.get("/api/gs/anotacoes").json(); nn = next(x for x in lst if x["id"] == n["id"])
    check(len(lst) == 2 and nn["status"] == "em_producao" and nn["pedido"] == j["url"] and (api.WORKSPACE / "anotacoes" / n["id"]).exists(), "anotação vai para Em produção com o link do pedido (não some)")
    check(c.post(f"/api/gs/anotacoes/{n['id']}/pedido").status_code == 409, "anotação já em produção dá 409")
    check(c.post(f"/api/gs/anotacoes/{n['id']}/status", data={"status": "feita"}).json()["status"] == "feita" and c.post(f"/api/gs/anotacoes/{n['id']}/status", data={"status": "a_fazer"}).json()["status"] == "a_fazer", "muda de coluna: feita e de volta para a fazer")
    check(c.post(f"/api/gs/anotacoes/{n['id']}/status", data={"status": "x"}).status_code == 400 and c.post("/api/gs/anotacoes/nao-existe-1/status", data={"status": "feita"}).status_code == 404, "status inválido 400; anotação inexistente 404")
    check(c.post(f"/api/gs/anotacoes/{n['id']}/pedido").status_code == 200, "de volta em A fazer, pode virar pedido de novo")
    check(c.get("/api/gs/anotacoes").json()[0]["status"] == "a_fazer", "anotação nova nasce em A fazer")

    # apagar
    outra = c.get("/api/gs/anotacoes").json()[0]["id"]
    check(c.delete(f"/api/gs/anotacoes/{outra}").status_code == 200 and len(c.get("/api/gs/anotacoes").json()) == 1, "apagar anotação (a que virou pedido continua, em produção)")
    check(c.delete("/api/gs/anotacoes/..%2Fx").status_code in (400, 404, 405) and c.delete("/api/gs/anotacoes/nao-existe-1").status_code == 404, "id inválido e inexistente")

    # novo token invalida o antigo
    r = c.post("/api/gs/atalho/novo"); b = r.json()
    check(r.status_code == 200 and b["token"] != a["token"] and c.post(f"/api/webhooks/compartilhar/{a['token']}", data={"acao": "anotacao", "texto": "x"}).status_code == 403 and c.post(f"/api/webhooks/compartilhar/{b['token']}", data={"acao": "anotacao", "texto": "x"}).status_code == 200, "gerar novo link invalida o anterior")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
