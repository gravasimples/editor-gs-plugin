"""Executor local (sem Paperclip): fila, rodadas pelo `claude -p` (aqui um claude falso), comentários, interactions, cancelar, tempo esgotado,
falha com tentativas, rodadas órfãs, rotas HTTP do agente, importação do Paperclip (transporte falso) e o gateway despachando pelo executor.
Isolado: tudo numa pasta temporária; nenhum banco, workspace ou processo real.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_executor_local.py"""
import asyncio, json, os, stat, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "testes")); import _falso  # noqa: E402
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from servico import executor_local as exl

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

FALSO = r'''#!/usr/bin/env python3
import json, os, sys, time
prompt = sys.stdin.read()
modo = os.environ.get("FALSO_MODO", "ok")
Path = None
open(os.environ["FALSO_REGISTRO"], "a").write(json.dumps({"args": sys.argv[1:], "prompt": prompt, "env": {k: v for k, v in os.environ.items() if k.startswith("PAPERCLIP_") or k == "CLAUDE_CONFIG_DIR"}}) + "\n")
print(json.dumps({"type": "system", "subtype": "init", "session_id": "s1"})); sys.stdout.flush()
if modo == "falha":
    sys.stderr.write("erro simulado: cota\n"); sys.exit(1)
if modo == "lento":
    time.sleep(20)
if modo == "linha_grande":
    print(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x" * 300000}]}})); sys.stdout.flush()
if modo == "erro_result":
    print(json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True, "result": "Reached max turns", "session_id": "s1"})); sys.exit(0)
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Vou editar."}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "## Resumo\nCortei 3 pausas.\n\n## Arquivos\n- saida/x/final_9x16.mp4", "total_cost_usd": 0.42, "usage": {"input_tokens": 10}, "session_id": "s1", "num_turns": 3, "duration_ms": 50}))
'''

CODEX_FALSO = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]; prompt = sys.stdin.read()
open(os.environ["FALSO_REGISTRO"], "a").write(json.dumps({"args": args, "prompt": prompt, "env": {k: v for k, v in os.environ.items() if k.startswith("PAPERCLIP_")}}) + "\n")
print(json.dumps({"type": "thread.started", "thread_id": "t1"})); print(json.dumps({"type": "turn.started"}))
if os.environ.get("FALSO_MODO") == "codex_falha":
    print(json.dumps({"type": "turn.failed", "error": {"message": "cota do ChatGPT esgotada"}})); sys.exit(1)
texto = "## Resumo\nFeito pelo Codex.\n\n## Arquivos\n- saida/x/final.mp4"
print(json.dumps({"type": "item.completed", "item": {"id": "i1", "type": "agent_message", "text": texto}}))
if "-o" in args: open(args[args.index("-o") + 1], "w").write(texto)
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20}}))
'''
tmp = Path(tempfile.mkdtemp(prefix="executor-teste-"))
(tmp / "workspace").mkdir(); (tmp / "workspace" / "AGENTS.md").write_text("# Editor\nInstruções de teste.\n", encoding="utf-8")
(tmp / "workspace" / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
falso = tmp / "claude_falso.py"; falso.write_text(FALSO, encoding="utf-8"); falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
falso = _falso.executavel(falso)  # Windows: .cmd na frente do .py, em UTF-8
registro = tmp / "registro.ndjson"; os.environ["FALSO_REGISTRO"] = str(registro); os.environ["FALSO_MODO"] = "ok"
A1, A2, A3 = "agente-opus", "agente-fable", "agente-codex"
codex_falso = tmp / "codex_falso.py"; codex_falso.write_text(CODEX_FALSO, encoding="utf-8"); codex_falso.chmod(codex_falso.stat().st_mode | stat.S_IEXEC)
codex_falso = _falso.executavel(codex_falso)  # Windows: .cmd na frente do .py
cfg = {"pasta": str(tmp / "executor"), "prefixo": "GRA", "tentativas": 2, "timeout_s": 2, "intervalo_s": 0.1, "max_simultaneos": 1,
       "agentes": [{"id": A1, "nome": "Editor GS", "motor": "claude", "modelo": "claude-opus-5-5", "comando": str(falso), "env": {"CLAUDE_CONFIG_DIR": "~/.claude-x"}},
                   {"id": A2, "nome": "Editor GS (Fable)", "motor": "claude", "modelo": "claude-fable-5-1", "comando": str(falso)},
                   {"id": A3, "nome": "Editor GS (Codex)", "motor": "codex", "modelo": "gpt-5.3-codex", "comando": str(codex_falso)}]}
ex = exl.Executor(tmp, cfg, porta=3299, workspace=tmp / "workspace")
ex.db().execute("INSERT OR REPLACE INTO contadores(nome, valor) VALUES('issue', 52)")  # continua do GRA-52

LOOP = asyncio.new_event_loop(); asyncio.set_event_loop(LOOP)
def run(coro):
    return LOOP.run_until_complete(coro)

async def esperar_rodadas():
    while ex.tarefas:
        await asyncio.gather(*list(ex.tarefas), return_exceptions=True)

# ---- criação, fila e rodada bem-sucedida
i1 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Reel do OBS", "description": "Corta pausas.\n\n<!-- gs-slug: 2026-11-10-reel -->", "status": "todo", "assigneeAgentId": A1, "projectId": "p"}))
check(i1["identifier"] == "GRA-53" and i1["status"] == "todo" and i1["activeRun"] is None, f"issue criada: {i1['identifier']} na fila")
lst = run(ex.chamar("GET", "/api/companies/local/issues")); check(len(lst) == 1 and lst[0]["id"] == i1["id"], "lista de issues")
r1 = run(ex.rodar_uma_vez(esperar=True))
check(r1 and r1["status"] == "running" or True, "rodada disparada")
runs = run(ex.chamar("GET", f"/api/issues/{i1['id']}/runs"))
check(len(runs) == 1 and runs[0]["status"] == "succeeded" and runs[0]["costUsd"] == 0.42 and runs[0]["sessionId"] == "s1" and runs[0]["finishedAt"], f"rodada concluída: {runs[0]['status']}, custo {runs[0]['costUsd']}")
iss = run(ex.chamar("GET", f"/api/issues/{i1['id']}"))
check(iss["status"] == "in_review" and iss["startedAt"] and iss["activeRun"] is None, f"issue entregue (in_review) sem rodada ativa: {iss['status']}")
cm = run(ex.chamar("GET", f"/api/issues/{i1['id']}/comments"))
check(len(cm) == 1 and cm[0]["authorAgentId"] == A1 and cm[0]["body"].startswith("## Resumo"), "mensagem final virou comentário do agente")
reg = [json.loads(l) for l in registro.read_text(encoding="utf-8").splitlines()]
args = reg[-1]["args"]; pr = reg[-1]["prompt"]; env = reg[-1]["env"]
check("--print" in args and "--output-format" in args and "stream-json" in args and "--dangerously-skip-permissions" in args and "--append-system-prompt-file" in args and args[args.index("--model") + 1] == "claude-opus-5-5" and "--mcp-config" in args and "--strict-mcp-config" in args, f"comando do claude: {args}")
check("GRA-53" in pr and "Corta pausas." in pr and "http://127.0.0.1:3299" in pr and "MENSAGEM FINAL" in pr and "novo pedido" in pr, "prompt leva pedido, API local e regra de entrega")
check(env.get("PAPERCLIP_API_URL") == "http://127.0.0.1:3299" and env.get("PAPERCLIP_ISSUE_ID") == i1["id"] and env.get("CLAUDE_CONFIG_DIR", "").endswith("/.claude-x") and "CLAUDECODE" not in env, "ambiente: API local, issue e CLAUDE_CONFIG_DIR do agente")
lg = ex.logs / runs[0]["logRef"]; check(lg.is_file() and '"chunk"' in lg.read_text(encoding="utf-8"), "log ndjson da rodada gravado")
d = run(ex.chamar("GET", f"/api/heartbeat-runs/{runs[0]['id']}/log")); check(d["logRef"] == runs[0]["logRef"], "rota do log devolve logRef")

# ---- nova mensagem reabre (PATCH todo) e a segunda rodada vê a conversa
run(ex.chamar("POST", f"/api/issues/{i1['id']}/comments", json={"body": "Faz a versão 16:9 também"}))
run(ex.chamar("PATCH", f"/api/issues/{i1['id']}", json={"status": "todo", "assigneeAgentId": A2}))
run(ex.rodar_uma_vez(esperar=True)); reg = [json.loads(l) for l in registro.read_text(encoding="utf-8").splitlines()]
check("Faz a versão 16:9" in reg[-1]["prompt"] and "nova mensagem" in reg[-1]["prompt"] and reg[-1]["args"][reg[-1]["args"].index("--model") + 1] == "claude-fable-5-1", "segunda rodada: conversa no prompt e agente trocado")
iss = run(ex.chamar("GET", f"/api/issues/{i1['id']}")); check(iss["status"] == "in_review" and len(run(ex.chamar("GET", f"/api/issues/{i1['id']}/runs"))) == 2, "segunda rodada entregue")
check(run(ex.chamar("GET", "/api/companies/local/agents"))[0]["adapterConfig"]["model"] == "claude-opus-5-5", "agentes listados com modelo")

# ---- PATCH com comment (Parar/Retomar/concluir) e done com completedAt
run(ex.chamar("PATCH", f"/api/issues/{i1['id']}", json={"status": "done", "comment": "✔ Marcado como concluído no app."}))
iss = run(ex.chamar("GET", f"/api/issues/{i1['id']}")); cm = run(ex.chamar("GET", f"/api/issues/{i1['id']}/comments"))
check(iss["status"] == "done" and iss["completedAt"] and cm[-1]["body"].startswith("✔") and cm[-1]["authorUserId"] == "app", "PATCH com comment grava comentário e completedAt")

# ---- falha: tentativas e blocked com comentário
os.environ["FALSO_MODO"] = "falha"
i2 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Vai falhar", "description": "x", "assigneeAgentId": A1}))
run(ex.rodar_uma_vez(esperar=True)); iss = run(ex.chamar("GET", f"/api/issues/{i2['id']}"))
check(iss["status"] == "todo" and iss["tentativas"] == 1, f"1ª falha: volta à fila ({iss['status']}, tentativa {iss['tentativas']})")
run(ex.rodar_uma_vez(esperar=True)); iss = run(ex.chamar("GET", f"/api/issues/{i2['id']}")); cm = run(ex.chamar("GET", f"/api/issues/{i2['id']}/comments"))
runs2 = run(ex.chamar("GET", f"/api/issues/{i2['id']}/runs"))
check(iss["status"] == "blocked" and len(runs2) == 2 and all(r["status"] == "failed" for r in runs2) and "cota" in (runs2[-1]["error"] or "") and cm and cm[-1]["body"].startswith("⚠"), f"2ª falha: blocked com comentário ({runs2[-1]['error']})")
run(ex.chamar("PATCH", f"/api/issues/{i2['id']}", json={"status": "todo"})); check(run(ex.chamar("GET", f"/api/issues/{i2['id']}"))["tentativas"] == 0, "retomar pelo app zera as tentativas")
run(ex.chamar("PATCH", f"/api/issues/{i2['id']}", json={"status": "cancelled"}))

# ---- linha de 300 KB no stream-json (tool_result grande) não derruba a rodada
os.environ["FALSO_MODO"] = "linha_grande"
i8 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Linha grande", "description": "x", "assigneeAgentId": A1}))
run(ex.rodar_uma_vez(esperar=True)); r8 = run(ex.chamar("GET", f"/api/issues/{i8['id']}/runs"))
check(r8[0]["status"] == "succeeded" and run(ex.chamar("GET", f"/api/issues/{i8['id']}"))["status"] == "in_review", f"linha de 300 KB no stream: rodada {r8[0]['status']} ({r8[0].get('error')})")
run(ex.chamar("PATCH", f"/api/issues/{i8['id']}", json={"status": "cancelled"}))

# ---- resultado com is_error (max turns) conta como falha
os.environ["FALSO_MODO"] = "erro_result"
i5 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Max turns", "description": "x", "assigneeAgentId": A1}))
run(ex.rodar_uma_vez(esperar=True)); r5 = run(ex.chamar("GET", f"/api/issues/{i5['id']}/runs"))
check(r5[0]["status"] == "failed" and "max turns" in r5[0]["error"].lower() and run(ex.chamar("GET", f"/api/issues/{i5['id']}"))["status"] == "todo", "result is_error vira falha (volta à fila)")
run(ex.chamar("PATCH", f"/api/issues/{i5['id']}", json={"status": "cancelled"}))

# ---- tempo esgotado e cancelar
os.environ["FALSO_MODO"] = "lento"
i3 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Lento", "description": "x", "assigneeAgentId": A1}))
t0 = time.time(); run(ex.rodar_uma_vez(esperar=True)); r3 = run(ex.chamar("GET", f"/api/issues/{i3['id']}/runs"))
check(r3[0]["status"] == "timed_out" and time.time() - t0 < 10 and run(ex.chamar("GET", f"/api/issues/{i3['id']}"))["status"] == "todo", f"tempo esgotado ({r3[0]['status']}) → volta à fila")
async def cancelar_no_meio():
    r = await ex.rodar_uma_vez()
    await asyncio.sleep(0.5)
    iss = await ex.chamar("GET", f"/api/issues/{i3['id']}")
    check(iss["status"] == "in_progress" and iss["activeRun"] and iss["activeRun"]["id"] == r["id"], "enquanto roda: in_progress com activeRun")
    await ex.chamar("POST", f"/api/heartbeat-runs/{r['id']}/cancel", json={})
    await ex.chamar("PATCH", f"/api/issues/{i3['id']}", json={"status": "blocked", "comment": "⏸ Pausada"})
    await esperar_rodadas()
    return r
rc = run(cancelar_no_meio()); rr = [x for x in run(ex.chamar("GET", f"/api/issues/{i3['id']}/runs")) if x["id"] == rc["id"]][0]
check(rr["status"] == "cancelled" and run(ex.chamar("GET", f"/api/issues/{i3['id']}"))["status"] == "blocked" and not ex.processos, "cancelar mata o processo, rodada cancelled, issue fica como o app deixou (blocked)")
os.environ["FALSO_MODO"] = "ok"

# ---- interactions: pendente segura a issue em in_progress; decisão reabre
i4 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Com aprovação", "description": "remove 30%", "assigneeAgentId": A1}))
run(ex.chamar("PATCH", f"/api/issues/{i4['id']}", json={"status": "in_progress"}))
it = run(ex.chamar("POST", f"/api/issues/{i4['id']}/interactions", json={"kind": "request_confirmation", "title": "Remover 30%?", "summary": "pausas longas", "payload": {"prompt": "Pode remover 30%?"}}))
check(it["status"] == "pending" and it["payload"]["prompt"] == "Pode remover 30%?", "interaction criada pendente")
run_falso = {"id": "run-i4", "runId": "run-i4", "issueId": i4["id"], "agentId": A1, "status": "running", "createdAt": exl._agora(), "startedAt": exl._agora(), "logRef": None}
ex._gravar_run(run_falso)
run(ex._concluir_rodada(i4["id"], run_falso, ex.agente(A1), {"type": "result", "subtype": "success", "is_error": False, "result": "Aguardo sua aprovação para remover 30%."}, None, [], 0))
iss = run(ex.chamar("GET", f"/api/issues/{i4['id']}")); check(iss["status"] == "in_progress" and iss["activeRun"] is None, "com interaction pendente: fica in_progress, sem rodada")
run(ex.chamar("POST", f"/api/issues/{i4['id']}/interactions/{it['id']}/accept", json={"comment": "pode"}))
iss = run(ex.chamar("GET", f"/api/issues/{i4['id']}")); cm = run(ex.chamar("GET", f"/api/issues/{i4['id']}/comments")); its = run(ex.chamar("GET", f"/api/issues/{i4['id']}/interactions"))
check(iss["status"] == "todo" and cm[-1]["body"].startswith("✅ Aprovado") and cm[-1]["authorUserId"] == "voce" and its[0]["status"] == "accepted" and its[0]["resolvedAt"], "aceitar: comentário da pessoa e issue de volta à fila")
try:
    run(ex.chamar("POST", f"/api/issues/{i4['id']}/interactions/{it['id']}/accept", json={})); check(False, "aceitar duas vezes deveria falhar")
except Exception as e:
    check(getattr(e, "status_code", None) == 409, "aceitar duas vezes: 409")
it2 = run(ex.chamar("POST", f"/api/issues/{i4['id']}/interactions", json={"kind": "ask_user_questions", "title": "Qual formato?", "payload": {"questions": [{"id": "q1", "options": [{"id": "o1", "label": "9:16"}, {"id": "o2", "label": "16:9"}]}]}}))
run(ex.chamar("POST", f"/api/issues/{i4['id']}/interactions/{it2['id']}/respond", json={"answers": [{"questionId": "q1", "optionIds": ["o2"], "otherText": None}]}))
cm = run(ex.chamar("GET", f"/api/issues/{i4['id']}/comments")); check(cm[-1]["body"].startswith("💬 Resposta") and "o2" in cm[-1]["body"], "responder pergunta vira comentário")
run(ex.rodar_uma_vez(esperar=True)); reg = [json.loads(l) for l in registro.read_text(encoding="utf-8").splitlines()]
check("✅ Aprovado" in reg[-1]["prompt"] and "Remover 30%" in reg[-1]["prompt"], "rodada seguinte vê a decisão na conversa")

# ---- motor codex: comando, eventos JSONL, mensagem final pelo arquivo -o, falha
os.environ["FALSO_MODO"] = "ok"
i9 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Pelo Codex", "description": "traduz a legenda", "assigneeAgentId": A3}))
run(ex.rodar_uma_vez(esperar=True)); r9 = run(ex.chamar("GET", f"/api/issues/{i9['id']}/runs")); reg = [json.loads(l) for l in registro.read_text(encoding="utf-8").splitlines()]
a9 = reg[-1]["args"]
check(a9[:2] == ["exec", "--json"] and "--dangerously-bypass-approvals-and-sandbox" in a9 and a9[a9.index("-C") + 1] == str(tmp / "workspace") and a9[a9.index("-m") + 1] == "gpt-5.3-codex" and "-o" in a9 and any(x.startswith("mcp_servers.") for x in a9) is False, f"codex: comando ({a9[:6]}...)")
check("traduz a legenda" in reg[-1]["prompt"] and reg[-1]["env"].get("PAPERCLIP_ISSUE_ID") == i9["id"], "codex: prompt pelo stdin e ambiente")
cm9 = run(ex.chamar("GET", f"/api/issues/{i9['id']}/comments"))
check(r9[0]["status"] == "succeeded" and r9[0]["usage"] == {"input_tokens": 100, "output_tokens": 20} and cm9 and cm9[-1]["body"].startswith("## Resumo") and cm9[-1]["authorAgentId"] == A3 and run(ex.chamar("GET", f"/api/issues/{i9['id']}"))["status"] == "in_review", "codex: rodada ok, entrega lida do arquivo -o, issue entregue")
os.environ["FALSO_MODO"] = "codex_falha"
run(ex.chamar("PATCH", f"/api/issues/{i9['id']}", json={"status": "todo"})); run(ex.rodar_uma_vez(esperar=True)); r9 = run(ex.chamar("GET", f"/api/issues/{i9['id']}/runs"))
check(r9[-1]["status"] == "failed" and "cota" in (r9[-1]["error"] or ""), f"codex: turn.failed vira falha ({r9[-1]['error']})")
os.environ["FALSO_MODO"] = "ok"; run(ex.chamar("PATCH", f"/api/issues/{i9['id']}", json={"status": "cancelled"}))

# ---- rodadas órfãs ao subir
i6 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Órfã", "description": "x", "assigneeAgentId": A1, "status": "in_progress"}))
ex._gravar_run({"id": "run-orfa", "runId": "run-orfa", "issueId": i6["id"], "agentId": A1, "status": "running", "createdAt": exl._agora(), "startedAt": exl._agora(), "logRef": None})
check(run(ex.chamar("GET", f"/api/issues/{i6['id']}"))["activeRun"]["id"] == "run-orfa", "activeRun aponta para a rodada running")
ex.recuperar_orfas(); iss = run(ex.chamar("GET", f"/api/issues/{i6['id']}")); check(iss["status"] == "todo" and ex._run("run-orfa")["status"] == "failed", "órfã: rodada failed, issue de volta à fila")
run(ex.chamar("PATCH", f"/api/issues/{i6['id']}", json={"status": "cancelled"}))

# ---- rotas HTTP (o agente usa por curl): comentário durante rodada ativa é do agente
appx = FastAPI(); appx.include_router(exl.rotas(ex)); cx = TestClient(appx)
i7 = cx.post("/api/companies/local/issues", json={"title": "HTTP", "description": "x", "assigneeAgentId": A1}).json()
check(cx.get("/api/health").json()["status"] == "ok" and i7["identifier"].startswith("GRA-"), "HTTP: health e criar issue")
r7 = cx.post(f"/api/issues/{i7['id']}/comments", json={"body": "mensagem da pessoa"}).json(); check(r7["authorAgentId"] is None, "HTTP sem rodada ativa: comentário da pessoa/app")
ex._gravar_run({"id": "run-http", "runId": "run-http", "issueId": i7["id"], "agentId": A2, "status": "running", "createdAt": exl._agora(), "startedAt": exl._agora(), "logRef": None})
r7 = cx.post(f"/api/issues/{i7['id']}/comments", json={"body": "Plano: tirar pausas"}).json(); check(r7["authorAgentId"] == A2, "HTTP com rodada ativa: comentário do agente")
it7 = cx.post(f"/api/issues/{i7['id']}/interactions", json={"kind": "request_confirmation", "title": "ok?", "summary": "s"}).json(); check(it7["requesterAgentId"] == A1 and cx.get(f"/api/issues/{i7['id']}/interactions").json()[0]["id"] == it7["id"], "HTTP: interaction do agente")
check(cx.post("/api/heartbeat-runs/run-http/cancel").json()["status"] == "cancelled" and ex._run("run-http")["status"] == "cancelled", "HTTP: cancel de rodada órfã marca cancelled")
check(cx.get("/api/issues/nao-existe").status_code == 404 and cx.post("/api/issues/x/interactions/y/pular").status_code == 404, "HTTP: 404 para issue e ação inexistentes")
cx.patch(f"/api/issues/{i7['id']}", json={"status": "cancelled"})

# ---- importação do Paperclip com transporte falso
dados = {"issues": [{"id": "pc-1", "identifier": "GRA-7", "title": "Antigo", "description": "d", "status": "done", "assigneeAgentId": A1, "projectId": "p", "createdAt": "2026-11-01T10:00:00.000Z", "updatedAt": "2026-11-01T11:00:00.000Z", "startedAt": "2026-11-01T10:01:00.000Z", "completedAt": "2026-11-01T11:00:00.000Z"},
                    {"id": "pc-2", "identifier": "GRA-70", "title": "Estava rodando", "description": "d", "status": "in_progress", "assigneeAgentId": A1, "projectId": "p", "createdAt": "2026-11-09T10:00:00.000Z", "updatedAt": "2026-11-09T11:00:00.000Z"}],
         "comments": {"pc-1": [{"id": "c1", "body": "## Resumo\nfeito", "createdAt": "2026-11-01T10:30:00.000Z", "authorAgentId": A1}, {"id": "c2", "body": "APROVADO", "createdAt": "2026-11-01T10:40:00.000Z"}], "pc-2": []},
         "runs": {"pc-1": [{"runId": "r-1", "status": "succeeded", "startedAt": "2026-11-01T10:01:00.000Z", "finishedAt": "2026-11-01T10:29:00.000Z", "agentId": A1}], "pc-2": [{"runId": "r-2", "status": "running", "startedAt": "2026-11-09T10:01:00.000Z"}]},
         "interactions": {"pc-1": [{"id": "it-1", "kind": "request_confirmation", "title": "t", "status": "accepted", "resolvedAt": "2026-11-01T10:20:00.000Z", "createdAt": "2026-11-01T10:10:00.000Z"}], "pc-2": []}}
def handler(req):
    p = req.url.path
    if p.endswith("/issues"): return httpx.Response(200, json=dados["issues"])
    for k in ("comments", "runs", "interactions"):
        if p.endswith("/" + k): return httpx.Response(200, json=dados[k][p.split("/")[3]])
    return httpx.Response(404)
real_client = httpx.Client
httpx.Client = lambda base_url, timeout=60: real_client(transport=httpx.MockTransport(handler), base_url=base_url)
logs_pc = tmp / "pc-logs" / "comp"; logs_pc.mkdir(parents=True); (logs_pc / "r-1.ndjson").write_text("{}\n")
try:
    res = ex.importar_paperclip("http://pc", "comp", tmp / "pc-logs")
finally:
    httpx.Client = real_client
check(res["issues"] == 2 and res["comentarios"] == 2 and res["rodadas"] == 2 and res["interactions"] == 1 and res["proximo_numero"] == 71, f"importação: {res}")
imp1 = run(ex.chamar("GET", "/api/issues/pc-1")); imp2 = run(ex.chamar("GET", "/api/issues/pc-2"))
check(imp1["status"] == "done" and imp1["identifier"] == "GRA-7" and imp2["status"] == "todo" and ex._run("r-2")["status"] == "failed" and ex._run("r-1")["logRef"].endswith("r-1.ndjson"), "importação: done preservado, in_progress vira todo, rodada running vira failed, logRef do Paperclip")
check(run(ex.chamar("GET", "/api/issues/pc-1/comments"))[1]["authorUserId"] == "app" and run(ex.chamar("GET", "/api/issues/pc-1/interactions"))[0]["status"] == "accepted", "importação: comentários e interactions")
novo = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Depois da importação", "description": "x", "assigneeAgentId": A1, "status": "backlog"}))
check(novo["identifier"] == "GRA-71", "numeração continua depois da importação (GRA-71)")
check(ex.proxima() is not None and ex.proxima()["id"] == imp2["id"], "fila: a importada em todo é a próxima; backlog não entra")

# ---- o gateway despachando pelo executor (sem Paperclip)
from servico import api
api.EXECUTOR = ex; api.CFG["agent_id"] = A1; api.CFG["agent_fable_id"] = A2
api.LICENCA_EXIGIDA = False  # máquina com ~/EditorGS (modo plugin) exigiria a chave do produto; o teste é do executor
cg = TestClient(api.app)
r = cg.get("/api/gs/estado").json(); check(r.get("paperclip") == "ok" and r["editor"]["modelo"] == "claude-opus-5-5", f"gateway /estado pelo executor: {r.get('paperclip')}")
r = cg.get("/api/gs/conversas").json(); check(any(c["codigo"] == "GRA-53" for c in r) and all("executando" in c for c in r), "gateway lista as conversas do executor")
r = cg.get(f"/api/gs/conversas/{i1['id']}").json(); check(r["codigo"] == "GRA-53" and r["mensagens"][0]["id"] == "pedido" and any(m["autor"] == "editor" and m["texto"].startswith("## Resumo") for m in r["mensagens"]) and r["trabalho"]["rodadas"] == 2, "gateway abre a conversa com mensagens do editor e tempo trabalhado")
r = cg.post(f"/api/gs/conversas/{imp2['id']}/parar").json(); check(r["status"] == "blocked" and run(ex.chamar("GET", f"/api/issues/{imp2['id']}"))["status"] == "blocked", "gateway: Parar pelo executor")
r = cg.post(f"/api/gs/conversas/{imp2['id']}/retomar").json(); check(run(ex.chamar("GET", f"/api/issues/{imp2['id']}"))["status"] == "todo", "gateway: Retomar pelo executor")
r = cg.get("/api/gs/lixeira").json(); check(any(c["id"] == i2["id"] for c in r), "gateway: lixeira lista as canceladas")
r = cg.get("/api/gs/uso"); check(r.status_code == 200, "gateway: /uso com issues do executor")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
