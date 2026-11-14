"""AGENTS.md e .mcp.json do agente numa instalação limpa (13/11/2026, GRA-1 do Thiago: "Append system prompt file not found"). Isolado em
pasta temporária: código falso em <tmp>/plugin-x, dados em <tmp>/EditorGS/workspace. Confere: cria os dois, segunda chamada não mexe,
AGENTS.md do plugin novo substitui a cópia, .mcp.json com caminho do WSL é refeito sem perder outro servidor, modo desenvolvimento não mexe.
Rodar: ~/.venvs/editor-gs/Scripts/python -I testes/teste_caminhos_agente.py"""
import json, os, shutil, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import caminhos as C

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-agente-"))
codigo = tmp / "plugin-1.2.4"; (codigo / "workspace").mkdir(parents=True); (codigo / "workspace" / "AGENTS.md").write_text("instruções v1", encoding="utf-8")
ws = tmp / "EditorGS" / "workspace"; ws.mkdir(parents=True)
C.RAIZ, C.WORKSPACE = codigo, ws

check(C._instrucoes() == "criado" and (ws / "AGENTS.md").read_text(encoding="utf-8") == "instruções v1", "instalação limpa: AGENTS.md copiado do código")
check(C._instrucoes() == "ok", "segunda chamada não reescreve")
(codigo / "workspace" / "AGENTS.md").write_text("instruções v2", encoding="utf-8")
check(C._instrucoes() == "atualizado" and (ws / "AGENTS.md").read_text(encoding="utf-8") == "instruções v2", "plugin atualizado: a cópia acompanha")

check(C._mcp() == "criado", "instalação limpa: .mcp.json criado")
m = json.loads((ws / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["editor-de-video"]
check(m["args"][-1] == str(codigo / "mcp" / "editor-de-video" / "servidor.py") and m["command"].lower().endswith(("python.exe", "python")), f"aponta para o Python do venv e o servidor do código atual ({m})")
check(C._mcp() == "ok", "segunda chamada não reescreve")
(ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"editor-de-video": {"command": "/home/rapha/projetos/editor-gs/mcp/editor-de-video/servidor.sh", "args": []},
                                                         "outro": {"command": "x"}}}), encoding="utf-8")
check(C._mcp() == "atualizado", "caminho velho (WSL) é refeito")
d = json.loads((ws / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
check("outro" in d and d["editor-de-video"]["args"][-1].endswith("servidor.py"), "outro servidor que a pessoa pôs continua")

(codigo / "marca-padrao").mkdir(); (codigo / "marca-padrao" / "manual.md").write_text("<!-- marca-padrao -->\nmanual v1", encoding="utf-8")
check(C._marca() == {"manual.md": "criado"} and "manual v1" in (ws / "marca" / "manual.md").read_text(encoding="utf-8"), "sem GSI: manual padrão entra em marca/")
(codigo / "marca-padrao" / "manual.md").write_text("<!-- marca-padrao -->\nmanual v2", encoding="utf-8")
check(C._marca() == {"manual.md": "atualizado"}, "cópia antiga do padrão acompanha o plugin")
(ws / "marca" / "manual.md").write_text("<!-- Cópia só leitura gerada pelo gateway. A fonte é o GSI -->\nmanual do GSI", encoding="utf-8")
check(C._marca() == {"manual.md": "do GSI"} and "manual do GSI" in (ws / "marca" / "manual.md").read_text(encoding="utf-8"), "manual gerado pelo GSI nunca é sobrescrito")

C.WORKSPACE = codigo / "workspace"
check(C._mcp() == "modo desenvolvimento" and not (codigo / "workspace" / ".mcp.json").exists(), "modo desenvolvimento não mexe no .mcp.json do repositório")
check(C._instrucoes() == "ok", "modo desenvolvimento: AGENTS.md é o próprio arquivo do código")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
