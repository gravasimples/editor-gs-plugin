"""Botão Parar/Retomar da conversa: cancela o run ativo no Paperclip e pausa o pedido (blocked); retomar devolve à fila (todo). Paperclip falso.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_parar.py"""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

chamadas = []; estado = {"i1": {"id": "i1", "status": "in_progress", "activeRun": {"id": "run-9"}}, "i2": {"id": "i2", "status": "todo", "activeRun": None}, "i3": {"id": "i3", "status": "done", "activeRun": None}}
async def pc_falso(metodo, url, **kw):
    chamadas.append((metodo, url, kw.get("json")))
    if metodo == "GET" and url.startswith("/api/issues/"):
        return estado[url.rsplit("/", 1)[-1]]
    if metodo == "POST" and url.endswith("/cancel"):
        if "run-falha" in url:
            raise api.HTTPException(500, "sem run")
        return {"status": "cancelled"}
    if metodo == "PATCH":
        estado[url.rsplit("/", 1)[-1]]["status"] = kw["json"]["status"]; return {"ok": True}
    return {}
api._pc = pc_falso
c = TestClient(api.app)
r = c.post("/api/gs/conversas/i1/parar"); j = r.json()
check(r.status_code == 200 and j["run_cancelada"] and j["status"] == "blocked" and estado["i1"]["status"] == "blocked", f"parar: cancela o run ativo e pausa o pedido ({j})")
check(any(m == "POST" and u == "/api/heartbeat-runs/run-9/cancel" for m, u, _ in chamadas) and any(m == "PATCH" and (b or {}).get("status") == "blocked" and "Parar" in (b or {}).get("comment", "") for m, u, b in chamadas), "chama o cancel do heartbeat run e o PATCH com comentário")
chamadas.clear(); r = c.post("/api/gs/conversas/i2/parar"); j = r.json()
check(j["run_cancelada"] is False and estado["i2"]["status"] == "blocked" and not any(u.endswith("/cancel") for _, u, _ in chamadas), "sem run ativo: só pausa, sem cancel")
chamadas.clear(); r = c.post("/api/gs/conversas/i3/parar"); j = r.json()
check(j["status"] == "done" and estado["i3"]["status"] == "done" and not any(m == "PATCH" for m, _, _ in chamadas), "pedido concluído: não muda nada")
estado["i4"] = {"id": "i4", "status": "in_progress", "activeRun": {"id": "run-falha"}}
r = c.post("/api/gs/conversas/i4/parar"); check(r.status_code == 200 and r.json()["run_cancelada"] is False and estado["i4"]["status"] == "blocked", "cancel que falha não impede a pausa")
r = c.post("/api/gs/conversas/i1/retomar"); check(r.status_code == 200 and estado["i1"]["status"] == "todo", "retomar devolve o pedido à fila")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
