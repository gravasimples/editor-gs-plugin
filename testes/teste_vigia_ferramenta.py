"""Vigia de ferramenta travada no executor local (11/11/2026, GRA-66 ficou 3 h numa chamada do MCP): leitura do stream, limite por ferramenta,
1º passo encerra o processo de trabalho preso (a ferramenta responde com erro e a rodada segue), 2º passo encerra a rodada e o pedido volta à fila.
Isolado: claude falso, servidor MCP falso e trabalho falso numa pasta temporária; limites em segundos. Nenhum banco ou processo real.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_vigia_ferramenta.py"""
import asyncio, json, os, stat, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "testes")); import _falso  # noqa: E402
from servico import executor_local as exl, plataforma

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

# ---- funções puras
uso = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__editor-de-video__montar_remotion", "input": {}},
                                                   {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "ls"}}]}}
res = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}
check(exl.eventos_ferramenta(uso) == [("inicio", "t1", "montar_remotion")], "só ferramenta do MCP entra (Bash tem timeout próprio)")
check(exl.eventos_ferramenta(res) == [("fim", "t1", None)] and exl.eventos_ferramenta({"type": "result"}) == [], "tool_result fecha a chamada")
agora = 10_000.0
pend = {"a": ("montar_remotion", agora - 30 * 60), "b": ("info", agora - 25 * 60)}
check(exl.ferramenta_travada(pend, agora) == ("b", "info", 25.0), "render com 30 min está no limite dele (90); info com 25 min passou do padrão (20)")
check(exl.ferramenta_travada({"a": ("montar_remotion", agora - 95 * 60)}, agora)[1] == "montar_remotion", "render acima de 90 min é travado")
check(exl.ferramenta_travada(pend, agora, {"padrao_min": 30}) is None, "limite configurável")
arvore = [{"pid": 2, "ppid": 1, "cmd": "python.exe -I servidor.py"}, {"pid": 3, "ppid": 2, "cmd": "python.exe -I servidor.py"},
          {"pid": 4, "ppid": 3, "cmd": "conhost.exe 0x4"}, {"pid": 5, "ppid": 3, "cmd": "cmd.exe /c npx remotion render"},
          {"pid": 6, "ppid": 5, "cmd": "node remotion-cli.js"}, {"pid": 7, "ppid": 1, "cmd": "conhost.exe"}]
check([p["pid"] for p in exl.trabalhadores_do_mcp(arvore)] == [5], "trabalhador = filho do servidor MCP (lançador do venv e conhost ficam de fora)")

# ---- integração: claude falso → servidor.py falso → trabalho preso
SERVIDOR = r'''import os, subprocess, sys, time
if os.environ.get("VIGIA_MODO") == "sem_trabalho":
    time.sleep(60); sys.exit(0)
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
p.wait(); sys.exit(0)
'''
CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
sys.stdin.read()
def out(o): print(json.dumps(o)); sys.stdout.flush()
out({"type": "system", "subtype": "init", "session_id": "s1"})
out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__editor-de-video__montar_remotion", "input": {}}]}})
subprocess.run([sys.executable, os.environ["VIGIA_SERVIDOR"]])
out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "erro: render interrompido", "is_error": True}]}})
out({"type": "result", "subtype": "success", "is_error": False, "result": "## Resumo\nRefiz o render.", "total_cost_usd": 0.1, "session_id": "s1"})
'''
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-vigia-"))
(tmp / "workspace").mkdir(); (tmp / "workspace" / "AGENTS.md").write_text("# teste\n", encoding="utf-8")
(tmp / "workspace" / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
srv = tmp / "mcp" / "servidor.py"; srv.parent.mkdir(); srv.write_text(SERVIDOR, encoding="utf-8")
cl = tmp / "claude_falso.py"; cl.write_text(CLAUDE, encoding="utf-8"); cl.chmod(cl.stat().st_mode | stat.S_IEXEC); cl = _falso.executavel(cl)
os.environ["VIGIA_SERVIDOR"] = str(srv)
cfg = {"pasta": str(tmp / "executor"), "tentativas": 2, "timeout_s": 120, "intervalo_s": 0.1,
       "vigia_ferramenta": {"intervalo_s": 0.5, "graca_min": 0.05, "por_ferramenta": {"montar_remotion": 0.03}},
       "agentes": [{"id": "a1", "nome": "Editor GS", "motor": "claude", "comando": str(cl)}]}
ex = exl.Executor(tmp, cfg, porta=3298, workspace=tmp / "workspace")
LOOP = asyncio.new_event_loop(); asyncio.set_event_loop(LOOP)
run = LOOP.run_until_complete

# 1º passo basta: o trabalho preso morre, a ferramenta responde com erro e a rodada termina normal
os.environ["VIGIA_MODO"] = "trabalho"
i1 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Render preso", "description": "x", "status": "todo", "assigneeAgentId": "a1"}))
t0 = time.monotonic(); run(ex.rodar_uma_vez(esperar=True)); dur = time.monotonic() - t0
r1 = run(ex.chamar("GET", f"/api/issues/{i1['id']}/runs"))[0]
log1 = (ex.logs / r1["logRef"]).read_text(encoding="utf-8")
check(r1["status"] == "succeeded" and dur < 40, f"trabalho preso encerrado e a rodada seguiu ({r1['status']}, {dur:.0f} s)")
check('"vigia"' in log1 and "montar_remotion sem resposta" in log1, "aviso do vigia gravado no registro da rodada")
check(run(ex.chamar("GET", f"/api/issues/{i1['id']}"))["status"] == "in_review", "pedido entregue")

# 2º passo: sem processo de trabalho (o servidor é que pendura) → rodada encerrada, aviso na conversa, volta à fila
os.environ["VIGIA_MODO"] = "sem_trabalho"
i2 = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Servidor preso", "description": "x", "status": "todo", "assigneeAgentId": "a1"}))
t0 = time.monotonic(); run(ex.rodar_uma_vez(esperar=True)); dur = time.monotonic() - t0
r2 = run(ex.chamar("GET", f"/api/issues/{i2['id']}/runs"))[0]
iss2 = run(ex.chamar("GET", f"/api/issues/{i2['id']}")); cm2 = run(ex.chamar("GET", f"/api/issues/{i2['id']}/comments"))
check(r2["status"] == "failed" and "travou" in (r2.get("error") or "") and dur < 40, f"rodada encerrada pelo vigia ({r2['status']}: {r2.get('error')}, {dur:.0f} s)")
check(iss2["status"] == "todo" and iss2.get("tentativas") == 1, f"pedido volta à fila para a 2ª tentativa ({iss2['status']}, {iss2.get('tentativas')})")
check(any(c["body"].startswith("🔧") and "montar_remotion" in c["body"] for c in cm2), "aviso na conversa")
run(ex.chamar("PATCH", f"/api/issues/{i2['id']}", json={"status": "cancelled"}))

# desligado por config: nada de vigia
check(exl.Executor(tmp, {**cfg, "vigia_ferramenta": False}, porta=3297, workspace=tmp / "workspace").vigia_ferramenta is None, "vigia_ferramenta=false desliga")
import subprocess  # todos os processos da máquina (no Windows um órfão perde o pai e some da árvore do teste)
if plataforma.WINDOWS:
    _ps = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"], capture_output=True, text=True, errors="replace").stdout
    _todos = [{"pid": d["ProcessId"], "cmd": d.get("CommandLine") or ""} for d in json.loads(_ps or "[]")]
else:
    _todos = [{"pid": int(l.split(None, 1)[0]), "cmd": l.split(None, 1)[1]} for l in subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout.splitlines() if len(l.split(None, 1)) == 2]
vivos = [p for p in _todos if "time.sleep(60)" in p["cmd"] and "Get-CimInstance" not in p["cmd"]]
check(not vivos, f"nenhum processo de teste ficou vivo ({len(vivos)})")
for p in vivos:
    plataforma.matar_arvore(p["pid"], True)

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
