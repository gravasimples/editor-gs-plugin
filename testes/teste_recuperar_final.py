"""Testes isolados da recuperação da mensagem final: pedido entregue sem comentário `## Resumo` ganha o texto final achado no log da
rodada (arquivo em pasta temporária), uma vez só; pedidos com entrega, com rodada ativa ou recentes ficam; autor das mensagens do app."""
import asyncio, json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def ndjson(eventos):
    return "\n".join(json.dumps({"ts": "x", "stream": "stdout", "chunk": json.dumps(e)}) for e in eventos) + "\n"

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"; api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"; api.RUN_LOGS = tmp / "run-logs"
    api.ENTRADA.mkdir(); api.SAIDA.mkdir(); (api.RUN_LOGS / "c" / "a").mkdir(parents=True)
    api.CFG["agent_id"] = "ag-opus"; api.CFG["ocultar_issues"] = []
    agora = datetime.now(timezone.utc); recente = agora.isoformat(); antigo = (agora - timedelta(minutes=10)).isoformat(); velho = (agora - timedelta(days=3)).isoformat()
    entrega = "## Resumo\nVídeo de 34 s.\n\n## Arquivos\n- final_9x16.mp4"
    (api.RUN_LOGS / "c/a/r1.ndjson").write_text(ndjson([{"type": "assistant", "message": {"content": [{"type": "text", "text": "Vou conferir."}]}},
                                                          {"type": "result", "subtype": "success", "is_error": False, "result": entrega}]), encoding="utf-8")
    (api.RUN_LOGS / "c/a/r3.ndjson").write_text(ndjson([{"type": "result", "subtype": "success", "result": "Só um texto sem seções."}]), encoding="utf-8")
    issues = [{"id": "i1", "identifier": "GRA-1", "status": "done", "assigneeAgentId": "ag-opus", "updatedAt": antigo},        # sem ## Resumo → recupera
              {"id": "i2", "identifier": "GRA-2", "status": "done", "assigneeAgentId": "ag-opus", "updatedAt": antigo},        # já tem entrega
              {"id": "i3", "identifier": "GRA-3", "status": "in_review", "assigneeAgentId": "ag-opus", "updatedAt": antigo},   # log sem seções
              {"id": "i4", "identifier": "GRA-4", "status": "done", "assigneeAgentId": "ag-opus", "updatedAt": antigo},        # rodada ativa
              {"id": "i5", "identifier": "GRA-5", "status": "done", "assigneeAgentId": "ag-opus", "updatedAt": velho},         # velho demais
              {"id": "i6", "identifier": "GRA-6", "status": "in_progress", "assigneeAgentId": "ag-opus", "updatedAt": antigo}]  # em andamento
    comentarios = {"i2": [{"id": "c2", "authorAgentId": "ag-opus", "body": "## Resumo\ntudo certo", "createdAt": "x"}],
                   "i1": [{"id": "c1", "authorAgentId": "ag-opus", "body": "Plano: 6 cenas.", "createdAt": "2026-10-31T03:31:00Z"}, {"id": "c0", "body": "Reserva automática: o X não conseguiu (y). Passando para Z.", "createdAt": "2026-10-31T03:32:00Z"}]}
    runs = {"i1": [{"runId": "r1", "status": "succeeded", "finishedAt": antigo}, {"runId": "r0", "status": "succeeded", "finishedAt": velho}],
            "i3": [{"runId": "r3", "status": "succeeded", "finishedAt": antigo}], "i4": [{"runId": "r4", "status": "running"}], "i5": [{"runId": "r5", "status": "succeeded", "finishedAt": velho}]}
    posts = []
    async def pc_falso(metodo, url, **kw):
        if url.endswith("/issues") and metodo == "GET": return issues
        if metodo == "GET" and url.startswith("/api/issues/") and url.count("/") == 3: return next(i for i in issues if i["id"] == url.split("/")[-1])
        if url.endswith("/runs"): return runs.get(url.split("/")[-2], [])
        if url.endswith("/comments") and metodo == "GET": return comentarios.get(url.split("/")[-2], [])
        if url.endswith("/comments") and metodo == "POST":
            iid = url.split("/")[-2]; posts.append((iid, kw["json"]["body"])); comentarios.setdefault(iid, []).append({"id": f"n{len(posts)}", "body": kw["json"]["body"], "createdAt": "2026-10-31T03:40:00Z"}); return {"id": "n"}
        if url.endswith("/log"):
            rid = url.split("/")[-2]; return {"runId": rid, "store": "local_file", "logRef": f"c/a/{rid}.ndjson", "content": ""}
        if url.endswith("/agents"): return [{"id": "ag-opus", "name": "Editor GS", "status": "idle"}]
        if url.endswith("/interactions"): return []
        return []
    api._pc = pc_falso
    api.INDICE.write_text(json.dumps({k: {"slug": f"s-{k}"} for k in ("i1", "i2", "i3", "i4", "i5", "i6")}))

    check(api._texto_final_do_log((api.RUN_LOGS / "c/a/r1.ndjson").read_text()) == entrega and api._texto_final_do_log((api.RUN_LOGS / "c/a/r3.ndjson").read_text()) is None and api._texto_final_do_log("lixo\n{\"a\":1}\n") is None, "texto final só quando o result tem seções ##")
    check(api._texto_final_do_log(ndjson([{"type": "result", "status": "success", "response": "## Resumo\nponte do Gemini"}])) == "## Resumo\nponte do Gemini", "formato da ponte do Gemini (response) também vale")

    feitas = asyncio.run(api.recuperar_mensagens_finais())
    check([f["codigo"] for f in feitas] == ["GRA-1"] and feitas[0]["run"] == "r1", f"só o pedido entregue sem ## Resumo e com rodada concluída recupera ({[f['codigo'] for f in feitas]})")
    check(len(posts) == 1 and posts[0][0] == "i1" and posts[0][1].startswith(entrega) and api.MARCA_RECUPERADA in posts[0][1], "comentário postado com o texto do log e a marca de recuperação")
    idx = json.loads(api.INDICE.read_text())
    check(idx["i1"]["recuperados"] == ["r1"] and idx["i3"]["recuperados"] == ["r3"] and "recuperados" not in idx["i2"] and "recuperados" not in idx["i4"], f"rodadas lidas ficam marcadas no índice ({idx['i1'].get('recuperados')}, {idx['i3'].get('recuperados')})")
    n = len(posts); asyncio.run(api.recuperar_mensagens_finais())
    check(len(posts) == n, "segunda passada não reposta nem relê")
    # rodada recém-terminada espera
    issues.append({"id": "i7", "identifier": "GRA-7", "status": "done", "assigneeAgentId": "ag-opus", "updatedAt": recente}); runs["i7"] = [{"runId": "r1", "status": "succeeded", "finishedAt": recente}]
    idx["i7"] = {"slug": "s7"}; api.INDICE.write_text(json.dumps(idx)); asyncio.run(api.recuperar_mensagens_finais())
    check(len(posts) == n, "rodada terminada há menos de 2 min ainda não é recuperada (o agente pode estar postando)")

    # conversa: autor das mensagens
    c = TestClient(api.app)
    r = c.get("/api/gs/conversas/i1"); j = r.json(); autores = {m["id"]: m["autor"] for m in j["mensagens"]}
    check(r.status_code == 200 and autores["c1"] == "editor" and autores["c0"] == "app" and autores["n1"] == "editor", f"recuperada aparece como do Editor, reserva como aviso do app ({autores})")
    check(any(s["titulo"].lower().startswith("resumo") for s in j["textos"]), "a mensagem recuperada vira seções de texto no app")
    r = c.post("/api/gs/reserva"); check(r.status_code == 200 and "recuperadas" in r.json(), "rota manual devolve as recuperações")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
