#!/usr/bin/env python3
"""Conecta a conta ChatGPT (Codex) ao Paperclip e libera o agente "Editor GS (Codex)".

Uso (no Ubuntu):  python3 ~/projetos/editor-gs/servico/conectar_codex.py
O script imprime um link; abra no navegador, entre com a conta ChatGPT e volte. Ele termina sozinho:
cria a conexão no Paperclip, tenta de novo a verificação do agente e grava o id em servico/config.json.
Não lê nem copia credenciais do ~/.codex: o Paperclip faz um login próprio, isolado, na pasta dele."""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CFG_PATH = RAIZ / "servico" / "config.json"
CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
BASE = CFG["paperclip_url"]; C = CFG["company_id"]
NOME_AGENTE = "Editor GS (Codex)"
INTENT = {"provider": "openai", "method": "subscription", "name": "ChatGPT do Raphael (Codex)", "ownership": "personal", "agentIds": [], "allAgents": False}

def req(metodo, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + url, data=data, method=metodo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t else {})
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        try: return e.code, json.loads(t)
        except Exception: return e.code, {"error": t}

def agente_codex():
    st, ags = req("GET", f"/api/companies/{C}/agents")
    return next((a for a in ags if a.get("adapterType") == "codex_local" and a.get("name") == NOME_AGENTE), None)

def main():
    st, h = req("GET", "/api/health")
    if st != 200:
        print(f"Paperclip fora do ar em {BASE} (HTTP {st}). Suba o Paperclip e rode de novo."); return 2
    st, lista = req("GET", f"/api/companies/{C}/ai-connections")
    ja = [c for c in (lista.get("connections") or []) if c.get("provider") == "openai" and c.get("status") == "connected"]
    if ja:
        print(f"Conexão OpenAI já existe no Paperclip: {ja[0].get('name')} ({ja[0]['id'][:8]}). Pulando o login.")
    else:
        st, at = req("POST", f"/api/companies/{C}/ai-connections/local/attempts", {**INTENT, "restart": True})
        if st != 201:
            print("Não consegui iniciar o login:", at); return 2
        sid = at["sessionId"]
        url = None
        for _ in range(60):
            st, ck = req("POST", f"/api/companies/{C}/ai-connections/local/check", {**INTENT, "localSessionId": sid})
            if ck.get("status") == "ready": break
            if ck.get("authorizationUrl") and ck["authorizationUrl"] != url:
                url = ck["authorizationUrl"]
                print("\n1) Abra este link no navegador e entre com a conta ChatGPT (a mesma do `codex login`):\n")
                print("   " + url + "\n")
                if ck.get("code"): print("   Código, se a página pedir:", ck["code"], "\n")
                print("2) Depois de aparecer 'login bem-sucedido' no navegador, só espere aqui.\n")
            if ck.get("error"):
                print("Aviso do Paperclip:", ck["error"])
            time.sleep(5)
        else:
            print("Deu o tempo de espera sem login. Rode de novo quando puder."); return 1
        # pode demorar alguns segundos até o Paperclip gravar a credencial
        for _ in range(60):
            st, ck = req("POST", f"/api/companies/{C}/ai-connections/local/check", {**INTENT, "localSessionId": sid})
            if ck.get("status") == "ready": break
            if ck.get("status") == "expired": print("A tentativa expirou. Rode de novo."); return 1
            time.sleep(5)
        st, fim = req("POST", f"/api/companies/{C}/ai-connections/local", {**INTENT, "localSessionId": sid})
        if st != 201:
            print("Login feito, mas não consegui salvar a conexão:", fim); return 2
        print("Conexão ChatGPT salva no Paperclip:", fim.get("connectionId", "")[:8])
    ag = agente_codex()
    if not ag:
        print(f"Agente '{NOME_AGENTE}' não encontrado no Paperclip. Me avise no chat."); return 2
    req("POST", f"/api/agents/{ag['id']}/lifecycle/retry", {})
    for _ in range(36):
        time.sleep(5)
        st, a = req("GET", f"/api/agents/{ag['id']}")
        if a.get("lifecycleState") == "ready" and a.get("status") != "paused": break
        if a.get("lifecycleState") == "ready" and a.get("status") == "paused":
            req("POST", f"/api/agents/{ag['id']}/resume", {}); continue
        if a.get("lifecycleError"):
            req("POST", f"/api/agents/{ag['id']}/lifecycle/retry", {})
    st, a = req("GET", f"/api/agents/{ag['id']}")
    print(f"Agente: status={a.get('status')} ciclo={a.get('lifecycleState')} erro={a.get('lifecycleError')}")
    if CFG.get("agent_codex_id") != ag["id"]:
        CFG["agent_codex_id"] = ag["id"]
        CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("servico/config.json: agent_codex_id gravado. Reinicie o gateway (servico/rodar.sh) ou me avise.")
    if a.get("status") in ("idle", "running") and a.get("lifecycleState") == "ready":
        print("\nPronto: o Codex está ligado ao Editor GS. Teste com um pedido 'Traduzir legenda' no app."); return 0
    print("\nO agente ainda não ficou pronto. Me mande esta saída no chat."); return 1

if __name__ == "__main__":
    sys.exit(main())
