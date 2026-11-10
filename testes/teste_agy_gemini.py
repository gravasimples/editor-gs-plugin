"""Testes isolados da ponte servico/agy_gemini.py (Paperclip gemini_local ↔ Antigravity CLI): tradução de flags e de eventos,
com um `agy` falso em pasta temporária. Não toca a rede nem workspace/."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "servico"))
import agy_gemini as ponte

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

a = ponte.traduzir_args(["--output-format", "stream-json", "--resume", "abc", "--model", "gemini-3.8-flash-high", "--approval-mode", "yolo", "--sandbox=none", "--prompt", "oi"])
check(a == ["--output-format", "stream-json", "--conversation", "abc", "--model", "gemini-3.8-flash-high", "-p", "oi"], f"flags do Gemini CLI viram flags do agy ({a})")
check(ponte.traduzir_args(["--sandbox", "--prompt", "x"]) == ["--sandbox", "-p", "x"], "--sandbox sozinho é mantido")
check(ponte.traduzir_args(["--output-format", "json", "-p", "x", "--extra"]) == ["--output-format", "stream-json", "--extra", "-p", "x"], "json vira stream-json; args extras passam")

with tempfile.TemporaryDirectory(prefix="editor-gs-agy-") as tmp:
    falso = Path(tmp) / "agy"
    eventos = [
        {"event": "init", "conversation_id": "c1", "init": {"model": "m", "cwd": "/x"}},
        {"event": "step_update", "step_update": {"conversation_id": "c1", "step_index": 0, "state": "DONE", "step_type": "user_input"}},
        {"event": "step_update", "step_update": {"conversation_id": "c1", "step_index": 1, "state": "ACTIVE", "step_type": "agent_response", "text_delta": "Olá "}},
        {"event": "step_update", "step_update": {"conversation_id": "c1", "step_index": 1, "state": "DONE", "step_type": "agent_response", "text_delta": "mundo", "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}},
        {"event": "step_update", "step_update": {"conversation_id": "c1", "step_index": 2, "state": "DONE", "step_type": "tool_call", "tool_name": "listar_trilhas"}},
        {"event": "result", "result": {"conversation_id": "c1", "status": "SUCCESS", "response": "Olá mundo", "num_turns": 1, "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}, "denied_actions": [{"action": "command", "display_name": "RunCommand"}]}},
    ]
    falso.write_text("#!/usr/bin/env python3\nimport json,sys\nsys.stderr.write('ARGS ' + json.dumps(sys.argv[1:]) + '\\n')\nfor e in " + json.dumps(eventos) + ":\n    print(json.dumps(e))\nprint('linha solta nao json')\n", encoding="utf-8")
    falso.chmod(0o755)
    agy_bin = falso
    if sys.platform == "win32":  # CreateProcess não executa script por shebang: um .cmd chama o Python com o mesmo arquivo
        agy_bin = falso.with_suffix(".cmd"); agy_bin.write_text(f'@"{sys.executable}" -X utf8 "{falso}" %*\r\n', encoding="utf-8")
    env = {**os.environ, "AGY_BIN": str(agy_bin), "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, str(RAIZ / "servico" / "agy_gemini.py"), "--output-format", "stream-json", "--approval-mode", "yolo", "--sandbox=none", "--resume", "c1", "--prompt", "oi"], capture_output=True, text=True, env=env, timeout=60)
    linhas = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    tipos = [l["type"] for l in linhas]
    check(p.returncode == 0 and "ARGS" in p.stderr and '"--conversation", "c1"' in p.stderr and '"-p", "oi"' in p.stderr, f"agy falso recebeu as flags traduzidas (rc={p.returncode}, stderr={p.stderr[:120]!r})")
    check(tipos[:1] == ["system"] and "message" in tipos and "step_finish" in tipos and "tool_result" in tipos and tipos[-1] == "result", f"eventos traduzidos na ordem esperada ({tipos})")
    msg = next(l for l in linhas if l["type"] == "message")
    check(msg["role"] == "assistant" and msg["content"] == "Olá mundo" and msg["session_id"] == "c1", "texto acumulado por passo vira uma mensagem do assistente")
    res = linhas[-1]
    check(res["status"] == "success" and res["usage"]["total_tokens"] == 12 and "RunCommand" in res["response"] and "Ações negadas" in res["response"], "result traz uso e lista as ações negadas na resposta")
    check("linha solta nao json" in p.stderr, "linha que não é JSON vai para stderr, não quebra o stdout")
    # falha do agy
    falso.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'event':'result','result':{'conversation_id':'c2','status':'ERROR','error':'cota'}}))\nraise SystemExit(3)\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(RAIZ / "servico" / "agy_gemini.py"), "--output-format", "stream-json", "-p", "x"], capture_output=True, text=True, env=env, timeout=60)
    res = json.loads(p.stdout.strip().splitlines()[-1])
    check(p.returncode == 3 and res["type"] == "result" and res["status"] == "error" and res.get("is_error") and "cota" in res["error"], f"erro do agy vira result de erro e preserva o código de saída ({p.returncode}, {res})")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
