#!/usr/bin/env python3
"""Liga a conta Claude de outra pessoa (padrão: o Thiago) a um agente próprio do Editor GS, sem tocar no login do Raphael.

Uso (no Ubuntu, num terminal comum, porque o login é interativo):
    python3 ~/projetos/editor-gs/servico/conectar_claude.py            # pessoa "thiago"
    python3 ~/projetos/editor-gs/servico/conectar_claude.py --so-agente  # pula o login (já feito) e só cria/confere o agente

O que faz:
 1. usa a pasta ~/.claude-<pessoa> como CLAUDE_CONFIG_DIR (login separado do ~/.claude do Raphael);
 2. se não estiver logado, roda `claude auth login` nessa pasta: o terminal mostra um link; a pessoa abre o link no
    navegador dela, entra com a conta Claude dela (precisa de assinatura Pro ou Max), copia o código que a página mostra
    e manda; o código é colado aqui. A credencial fica só em ~/.claude-<pessoa>/.credentials.json (0600), fora do git;
 3. cria no Paperclip o agente "Editor GS (<Pessoa>)" igual ao Editor GS (Opus 5.5), com CLAUDE_CONFIG_DIR dessa pasta;
 4. grava `agent_<pessoa>_id` e `agentes_por_pessoa` em servico/config.json: pedido de quem entrou pela chave dessa
    pessoa (EDITOR_GS_CHAVES) vai para o agente dela e gasta a janela da assinatura dela.
Não copia credenciais entre pastas e não imprime token."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import plataforma  # noqa: E402
CFG_PATH = RAIZ / "servico" / "config.json"
CLAUDE = plataforma.claude_bin()


def req(base, metodo, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + url, data=data, method=metodo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        try:
            return e.code, json.loads(t)
        except Exception:  # noqa: BLE001
            return e.code, {"error": t}


def logado(pasta: Path) -> bool:
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(pasta)}
    try:
        r = subprocess.run([CLAUDE, "auth", "status"], env=env, capture_output=True, text=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        print("não consegui rodar o claude:", e); return False
    txt = (r.stdout + r.stderr).lower()
    return r.returncode == 0 and ("logged in" in txt or "autenticado" in txt or '"loggedin": true' in txt or "subscription" in txt)


def login(pasta: Path, pessoa: str):
    pasta.mkdir(mode=0o700, exist_ok=True)
    # settings sem segredo (modelo, tema): a pasta nova nasce vazia
    orig = Path.home() / ".claude" / "settings.json"
    if orig.is_file() and not (pasta / "settings.json").exists():
        try:
            d = json.loads(orig.read_text(encoding="utf-8"))
            (pasta / "settings.json").write_text(json.dumps({k: v for k, v in d.items() if k in ("model", "theme", "autoUpdatesChannel")}, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    print(f"\nLogin da conta Claude de {pessoa.title()} (pasta {pasta}).")
    print("Vai aparecer um link. Mande o link para a pessoa; ela abre no navegador DELA, entra com a conta Claude dela,")
    print("copia o código que a página mostra e te manda. Cole o código aqui quando pedir.\n")
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(pasta)}
    r = subprocess.run([CLAUDE, "auth", "login", "--claudeai"], env=env)
    if r.returncode != 0 or not logado(pasta):
        print("\nO login não terminou. Rode de novo quando tiver o código."); sys.exit(1)
    print("\nLogin feito.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pessoa", default="thiago")
    ap.add_argument("--so-agente", action="store_true", help="não faz login; só cria/confere o agente")
    ap.add_argument("--modelo", default=None, help="modelo do agente (padrão: o mesmo do Editor GS)")
    a = ap.parse_args()
    pessoa = a.pessoa.strip().lower()
    pasta = Path.home() / f".claude-{pessoa}"
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    base, C = cfg["paperclip_url"], cfg["company_id"]

    if not a.so_agente and not logado(pasta):
        login(pasta, pessoa)
    elif not logado(pasta):
        print(f"Sem login em {pasta}. Rode sem --so-agente."); return 2
    else:
        print(f"Conta já logada em {pasta}.")

    st, h = req(base, "GET", "/api/health")
    if st != 200:
        print(f"Paperclip fora do ar em {base} (HTTP {st}). Suba o Paperclip e rode de novo."); return 2
    st, ags = req(base, "GET", f"/api/companies/{C}/agents")
    nome = f"Editor GS ({pessoa.title()})"
    chave_cfg = f"agent_{pessoa}_id"
    ag = next((x for x in ags if x.get("id") == cfg.get(chave_cfg)), None) or next((x for x in ags if x.get("name") == nome), None)
    if not ag:
        opus = next((x for x in ags if x.get("id") == cfg["agent_id"]), None)
        if not opus:
            print("Agente Editor GS (Opus) não encontrado no Paperclip."); return 2
        st, opus_full = req(base, "GET", f"/api/agents/{opus['id']}")
        ac = dict(opus_full.get("adapterConfig") or {})
        for k in ("instructionsFilePath", "instructionsRootPath", "instructionsEntryFile", "instructionsBundleMode", "env"):
            ac.pop(k, None)
        if a.modelo:
            ac["model"] = a.modelo
        # valores conhecidos do agente Opus (os do Paperclip voltam mascarados na API)
        ac["env"] = {"CLAUDE_CONFIG_DIR": {"type": "plain", "value": str(pasta)},
                     "MCP_TIMEOUT": {"type": "plain", "value": "120000"}, "MCP_TOOL_TIMEOUT": {"type": "plain", "value": "1800000"},
                     "BASH_MAX_TIMEOUT_MS": {"type": "plain", "value": "1800000"}, "BASH_DEFAULT_TIMEOUT_MS": {"type": "plain", "value": "600000"}}
        corpo = {"name": nome, "role": opus_full.get("role") or "general", "title": f"Editor de vídeo (conta Claude de {pessoa.title()})",
                 "capabilities": opus_full.get("capabilities"), "adapterType": "claude_local", "adapterConfig": ac,
                 "runtimeConfig": opus_full.get("runtimeConfig"), "permissions": {"canCreateAgents": False, "canCreateSkills": False}}
        st, ag = req(base, "POST", f"/api/companies/{C}/agents", corpo)
        if st not in (200, 201):
            print("Não consegui criar o agente:", st, ag); return 2
        print(f"Agente criado: {nome} ({ag['id'][:8]}).")
        # instruções: mesmo AGENTS.md do workspace (o gateway sincroniza depois; aqui só garante o primeiro)
        st, ag_full = req(base, "GET", f"/api/agents/{ag['id']}")
        if not (ag_full.get("adapterConfig") or {}).get("instructionsFilePath"):
            alvo = Path.home() / ".paperclip" / "instances" / "default" / "companies" / C / "agents" / ag["id"] / "instructions" / "AGENTS.md"
            alvo.parent.mkdir(parents=True, exist_ok=True)
            fonte = RAIZ / "workspace" / "AGENTS.md"
            if fonte.is_file():
                alvo.write_bytes(fonte.read_bytes())
            ac2 = dict(ag_full.get("adapterConfig") or {}); ac2.pop("env", None)
            ac2.update({"instructionsFilePath": str(alvo), "instructionsRootPath": str(alvo.parent), "instructionsEntryFile": "AGENTS.md", "instructionsBundleMode": "file"})
            ac2["env"] = ac["env"]
            st, _ = req(base, "PATCH", f"/api/agents/{ag['id']}", {"adapterConfig": ac2})
            print("instruções:", "ok" if st in (200, 201) else f"HTTP {st}")
    else:
        print(f"Agente já existe: {ag.get('name')} ({ag['id'][:8]}).")

    cfg[chave_cfg] = ag["id"]
    cfg.setdefault("agentes_por_pessoa", {})[pessoa] = chave_cfg
    CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"config.json: {chave_cfg} e agentes_por_pessoa gravados.")

    req(base, "POST", f"/api/agents/{ag['id']}/lifecycle/retry", {})
    for _ in range(36):
        time.sleep(5)
        st, x = req(base, "GET", f"/api/agents/{ag['id']}")
        if x.get("lifecycleState") == "ready" and x.get("status") != "paused":
            print("Agente pronto (verificação do Paperclip passou)."); break
        if x.get("lifecycleError"):
            print("Paperclip:", str(x.get("lifecycleError"))[:300])
    else:
        print("O agente ainda não ficou pronto; confira no painel do Paperclip (porta 3100).")
    print("\nReinicie o gateway do Editor GS para o chip e o roteamento aparecerem (matar o uvicorn da 3200 e rodar servico/rodar.sh).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
