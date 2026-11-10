"""Menu ⋯ da conversa (concluir, excluir → Lixeira, restaurar) e anexos do Google Drive (listar, pedido em backlog até o download, mensagem depois
do download, erro do Drive). Paperclip falso, rclone falso, índice e entrada/ em pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_menu_drive.py"""
import asyncio, json, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, drive_anexos as dra

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-menu-"))
api.INDICE = tmp / "conversas.json"; api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"; api.ENTRADA.mkdir(); api.SAIDA.mkdir()
async def _nada(): return None
api._sincronizar_instrucoes = _nada
api.CFG["reserva_automatica"] = False; api.CFG["automacoes_laco"] = False
async def _parado(): return None
api._laco_push = _parado

# --- funções puras do módulo ---
check(dra.alvo("gsp2:", "10. Mídias/a.mp4") == "gsp2:10. Mídias/a.mp4" and dra.alvo("gs:Central", "x/y") == "gs:Central/x/y" and dra.alvo("gs:Central", "") == "gs:Central", "alvo junta remote e caminho")
for ruim in ("../segredo", "a/../../b", "a\\b"):
    try:
        dra.caminho_seguro(ruim); check(False, f"caminho {ruim!r} recusado")
    except dra.ErroDrive:
        check(True, f"caminho {ruim!r} recusado")
check(dra.raizes("x", env="Central=gsp2:;Pessoal=gsp:Fotos") == [{"id": "0", "rotulo": "Central", "remoto": "gsp2:"}, {"id": "1", "rotulo": "Pessoal", "remoto": "gsp:Fotos"}], "DRIVE_ANEXOS com duas raízes")
(tmp / "p").mkdir(); (tmp / "p" / "take.mp4").write_text("x")
check(dra.nomes_destino([{"raiz": "0", "caminho": "a/take.mp4"}, {"raiz": "0", "caminho": "b/take.mp4"}, {"raiz": "0", "caminho": "c/foto final.png"}], tmp / "p") == ["take-2.mp4", "take-3.mp4", "foto_final.png"], "nomes não sobrescrevem nem repetem")
try:
    dra.selecao(json.dumps([{"raiz": "0", "caminho": f"a{i}.mp4"} for i in range(11)])); check(False, "limite de 10 itens")
except dra.ErroDrive:
    check(True, "limite de 10 itens")

# --- rclone falso ---
baixados = []; falhar = {"on": False}
dra.raizes = lambda rclone, env=None: [{"id": "0", "rotulo": "Central", "remoto": "gsp2:"}]
class P:  # subprocess.CompletedProcess falso
    def __init__(s, rc=0, out="", err=""): s.returncode, s.stdout, s.stderr = rc, out, err
def run_falso(cmd, **kw):
    if cmd[1] == "lsjson":
        return P(out=json.dumps([{"Name": "Takes", "IsDir": True}, {"Name": "aula.mp4", "IsDir": False, "Size": 5_000_000, "ModTime": "2026-11-01T10:00:00Z", "MimeType": "video/mp4"},
                                 {"Name": "Roteiro", "IsDir": False, "Size": -1, "ModTime": "2026-11-02T10:00:00Z", "MimeType": "application/vnd.google-apps.document"}]))
    if cmd[1] == "copyto":
        if falhar["on"]:
            return P(rc=1, err="couldn't fetch token: invalid_grant")
        time.sleep(0.05); Path(cmd[3]).write_text("video"); baixados.append((cmd[2], cmd[3])); return P()
    return P(rc=1, err="?")
dra.subprocess.run = run_falso

# --- Paperclip falso ---
estado = {}; chamadas = []
async def pc_falso(metodo, url, **kw):
    chamadas.append((metodo, url, kw.get("json")))
    if metodo == "POST" and url.endswith("/issues"):
        i = {"id": f"n{len(estado)}", "identifier": f"GRA-{90 + len(estado)}", "title": kw["json"]["title"], "status": kw["json"]["status"], "description": kw["json"]["description"], "activeRun": None}
        estado[i["id"]] = i; return i
    if metodo == "GET" and url.endswith("/issues"):
        return list(estado.values())
    if metodo == "GET" and url.startswith("/api/issues/"):
        return estado[url.rsplit("/", 1)[-1]]
    if metodo == "POST" and url.endswith("/cancel"):
        return {"status": "cancelled"}
    if metodo == "PATCH":
        estado[url.rsplit("/", 1)[-1]]["status"] = kw["json"]["status"]; return {"ok": True}
    return {}
api._pc = pc_falso

with TestClient(api.app) as c:
    r = c.get("/api/gs/drive/listar", params={"raiz": "0", "caminho": "10. Mídias"}); j = r.json()
    check(r.status_code == 200 and j["pastas"] == [{"nome": "Takes", "caminho": "10. Mídias/Takes"}] and j["arquivos"][1]["nome"] == "aula.mp4" and j["arquivos"][1]["tipo"] == "video" and j["arquivos"][0]["baixavel"] is False, f"listar: pastas, arquivos e Google Docs não baixável ({j})")
    check(c.get("/api/gs/drive/listar", params={"caminho": "../x"}).status_code == 400, "listar recusa caminho com ..")

    # pedido novo só com arquivo do Drive: nasce em backlog, vira todo depois do download
    r = c.post("/api/gs/conversas", data={"pedido": "Edite este take", "drive": json.dumps([{"raiz": "0", "caminho": "10. Mídias/aula.mp4"}])}); j = r.json()
    cid = j["id"]
    check(r.status_code == 200, "pedido criado")
    criado = next(b for m, u, b in chamadas if m == "POST" and u.endswith("/issues"))
    check(criado["status"] == "backlog" and "entrada/" in criado["description"] and "aula.mp4" in criado["description"], "pedido do Drive nasce em backlog e já cita o arquivo")
    for _ in range(100):
        if estado[cid]["status"] == "todo": break
        time.sleep(0.05)
    meta = json.loads(api.INDICE.read_text())[cid]
    check(estado[cid]["status"] == "todo" and meta["drive"]["estado"] == "pronto" and baixados and baixados[-1][0] == "gsp2:10. Mídias/aula.mp4" and Path(baixados[-1][1]).exists(), "download termina e libera o pedido para a fila")

    # mensagem com Drive numa conversa entregue: comentário só depois do download, e reabre
    estado[cid]["status"] = "in_review"; chamadas.clear()
    r = c.post(f"/api/gs/conversas/{cid}/mensagens", data={"texto": "use este também", "drive": json.dumps([{"raiz": "0", "caminho": "10. Mídias/aula.mp4"}])})
    check(r.status_code == 200 and r.json().get("drive") == 1, "mensagem com Drive responde na hora")
    for _ in range(100):
        if any(m == "POST" and u.endswith("/comments") for m, u, _ in chamadas): break
        time.sleep(0.05)
    com = next((b for m, u, b in chamadas if m == "POST" and u.endswith("/comments")), None)
    check(com and "use este também" in com["body"] and "aula-2.mp4" in com["body"] and "Google Drive" in com["body"], "comentário leva o texto e o arquivo baixado (sem sobrescrever)")
    time.sleep(0.1)
    check(estado[cid]["status"] == "todo", "mensagem reabre a conversa entregue")

    # erro do Drive: avisa na conversa e marca o erro
    falhar["on"] = True; chamadas.clear()
    r = c.post("/api/gs/conversas", data={"pedido": "outro", "drive": json.dumps([{"raiz": "0", "caminho": "x.mp4"}])}); cid2 = r.json()["id"]
    for _ in range(100):
        if (json.loads(api.INDICE.read_text())[cid2].get("drive") or {}).get("estado") == "erro": break
        time.sleep(0.05)
    meta = json.loads(api.INDICE.read_text())[cid2]
    check(meta["drive"]["estado"] == "erro" and "expirou" in meta["drive"]["erro"] and estado[cid2]["status"] == "backlog" and any("Não consegui baixar" in (b or {}).get("body", "") for m, u, b in chamadas), "erro do Drive: fica fora da fila, avisa na conversa com a dica do token")
    falhar["on"] = False

    # menu ⋯: concluir, excluir, lixeira, restaurar
    estado[cid]["status"] = "in_progress"; estado[cid]["activeRun"] = {"id": "run-1"}; chamadas.clear()
    r = c.post(f"/api/gs/conversas/{cid}/concluir"); j = r.json()
    check(r.status_code == 200 and estado[cid]["status"] == "done" and j["run_cancelada"] and any(u == "/api/heartbeat-runs/run-1/cancel" for _, u, _ in chamadas), "concluir para o agente e marca done")
    check(not (api.SAIDA / "x").exists() and not any("APROVADO" in ((b or {}).get("body") or "") for _, _, b in chamadas), "concluir não registra aprovação")
    estado[cid]["activeRun"] = None
    r = c.post(f"/api/gs/conversas/{cid}/excluir")
    check(r.status_code == 200 and estado[cid]["status"] == "cancelled", "excluir cancela a issue")
    lista = c.get("/api/gs/conversas").json(); lix = c.get("/api/gs/lixeira").json()
    check(all(x["id"] != cid for x in lista) and any(x["id"] == cid and x["excluida"] for x in lix), "excluída some da lista e aparece na Lixeira")
    check(c.post(f"/api/gs/conversas/{cid}/concluir").status_code == 409, "concluir na Lixeira é recusado")
    r = c.post(f"/api/gs/conversas/{cid}/restaurar")
    check(r.status_code == 200 and estado[cid]["status"] == "done" and not json.loads(api.INDICE.read_text())[cid].get("excluida"), "restaurar volta ao status de antes (done)")
    estado[cid]["status"] = "todo"; c.post(f"/api/gs/conversas/{cid}/excluir"); r = c.post(f"/api/gs/conversas/{cid}/restaurar")
    check(r.json()["status"] == "blocked", "excluída enquanto na fila volta pausada (não recomeça sozinha)")
    check(c.post("/api/gs/conversas/a$b/excluir").status_code in (400, 404), "id inválido recusado")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
