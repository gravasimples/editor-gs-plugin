#!/usr/bin/env python3
"""Ponte entre o adaptador `gemini_local` do Paperclip e o Antigravity CLI (`agy`).

O Paperclip só sabe falar com o Gemini CLI antigo (flags --approval-mode, --sandbox=none, --resume, --prompt e eventos
stream-json com "type"). O `agy` usa outras flags e eventos com "event". Este script traduz os dois lados e nada mais:
não desliga permissões (as ferramentas liberadas ficam em ~/.gemini/antigravity-cli/settings.json → permissions.allow).

Uso pelo Paperclip (adapterConfig.command = caminho deste arquivo, engine = cli).
"""
import json, os, shutil, subprocess, sys

AGY = os.environ.get("AGY_BIN") or shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")


def traduzir_args(argv):
    out, prompt = [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a in ("--output-format", "--model", "--resume", "--prompt", "-p", "--approval-mode") and nxt is None:
            i += 1; continue
        if a == "--output-format":
            out += ["--output-format", "stream-json" if nxt in ("stream-json", "json") else nxt]; i += 2
        elif a == "--model":
            out += ["--model", nxt]; i += 2
        elif a == "--resume":
            out += ["--conversation", nxt]; i += 2
        elif a in ("--prompt", "-p"):
            prompt = nxt; i += 2
        elif a == "--approval-mode":
            i += 2  # agy não tem; permissões vêm do settings.json
        elif a.startswith("--approval-mode=") or a.startswith("--sandbox=") or a in ("--yolo",):
            i += 1
        elif a == "--sandbox":
            out.append("--sandbox"); i += 1
        else:
            out.append(a); i += 1
    if prompt is None and not sys.stdin.isatty():
        prompt = sys.stdin.read()
    if prompt is not None:
        out += ["-p", prompt]
    return out


def emitir(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n"); sys.stdout.flush()


def _alvo(su: dict) -> str:
    """Alvo legível de uma chamada de ferramenta do agy (caminho, comando ou ferramenta MCP), para o log e para a mensagem de ações negadas."""
    p = ((su.get("tool_info") or {}).get("parameters") or {})
    for k in ("Path", "path", "AbsolutePath", "CommandLine", "command", "Url", "url", "Query", "query", "name"):
        if p.get(k):
            return str(p[k])[:160]
    return ""


def main():
    if "--version" in sys.argv[1:]:
        return subprocess.call([AGY, "--version"])
    args = traduzir_args(sys.argv[1:])
    if "--output-format" not in args:
        return subprocess.call([AGY] + args)
    env = dict(os.environ)
    proc = subprocess.Popen([AGY] + args, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, encoding="utf-8", errors="replace", env=env)
    cid = None; textos = {}; passos_emitidos = set(); ferramentas = []; chamadas = []
    for linha in proc.stdout:
        linha = linha.rstrip("\n")
        if not linha.strip():
            continue
        try:
            ev = json.loads(linha)
        except Exception:
            sys.stderr.write(linha + "\n"); continue
        tipo = ev.get("event")
        if tipo == "init":
            cid = (ev.get("init") or {}).get("conversation_id") or ev.get("conversation_id")
            emitir({"type": "system", "subtype": "init", "session_id": cid, "model": (ev.get("init") or {}).get("model"), "cwd": (ev.get("init") or {}).get("cwd")})
        elif tipo == "step_update":
            su = ev.get("step_update") or {}
            cid = cid or su.get("conversation_id")
            idx = su.get("step_index"); st = su.get("step_type"); estado = su.get("state")
            if st == "agent_response":
                textos[idx] = textos.get(idx, "") + (su.get("text_delta") or "")
                if estado == "DONE" and idx not in passos_emitidos:
                    passos_emitidos.add(idx)
                    txt = textos.get(idx, "").strip()
                    if txt:
                        emitir({"type": "message", "role": "assistant", "content": txt, "session_id": cid})
                    if su.get("usage"):
                        emitir({"type": "step_finish", "usage": su["usage"], "session_id": cid})
            elif st and st != "user_input":
                nome = su.get("tool_name") or su.get("name") or st
                alvo = _alvo(su)
                if estado == "DONE" and (idx, nome) not in ferramentas:
                    ferramentas.append((idx, nome))
                    chamadas.append(f"{nome}({alvo})" if alvo else nome)
                    emitir({"type": "tool_result", "name": nome, "step": idx, "target": alvo, "session_id": cid})
                if su.get("usage") and estado == "DONE":
                    emitir({"type": "step_finish", "usage": su["usage"], "session_id": cid})
        elif tipo == "result":
            r = ev.get("result") or {}
            cid = cid or r.get("conversation_id")
            status = (r.get("status") or "").upper()
            resposta = (r.get("response") or "").strip()
            negadas = r.get("denied_actions") or []
            if negadas:
                resposta = (resposta + "\n\n" if resposta else "") + "Ações negadas pelo modo sem terminal (não liberadas em settings.json → permissions.allow): " + ", ".join(sorted({(d.get('display_name') or d.get('action') or '?') for d in negadas}))
                if chamadas:  # o agy não diz qual chamada foi negada; listar os alvos de todas ajuda a achar a regra que falta
                    resposta += "\nFerramentas chamadas nesta rodada: " + "; ".join(chamadas[-12:])
            saida = {"type": "result", "session_id": cid, "status": "success" if status == "SUCCESS" else "error", "response": resposta,
                     "num_turns": r.get("num_turns"), "duration_seconds": r.get("duration_seconds")}
            if r.get("usage"):
                saida["usage"] = r["usage"]
            if status != "SUCCESS":
                saida["is_error"] = True; saida["error"] = r.get("error") or r.get("message") or f"agy terminou com status {status or 'desconhecido'}"
            emitir(saida)
        elif tipo == "error":
            emitir({"type": "error", "error": ev.get("error") or ev.get("message") or linha, "session_id": cid})
        else:
            emitir({"type": "agy_" + str(tipo), "raw": ev})
    rc = proc.wait()
    return rc


if __name__ == "__main__":
    sys.exit(main())
