"""Porta de entrada por chave (acesso de fora da máquina): cookie, página /entrar, caminhos livres, localhost sem chave,
agente por pessoa. Sem Paperclip. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_acesso.py"""
import os
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ["EDITOR_GS_CHAVES"] = "thiago:chaveDoThiago123456, raphael:chaveDoRaphael654321, curta:abc"
from fastapi.testclient import TestClient
from servico import api, acesso as acs

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

FORA = "http://editor-exemplo.tailnet-exemplo.ts.net"
c = TestClient(api.app, base_url=FORA, follow_redirects=False)
r = c.get("/api/gs/quem"); check(r.status_code == 401, f"de fora sem cookie: API responde 401 ({r.status_code})")
r = c.get("/", headers={"accept": "text/html,*/*"}); check(r.status_code == 302 and r.headers.get("location") == "/entrar", f"de fora sem cookie: página vai para /entrar ({r.status_code} {r.headers.get('location')})")
r = c.get("/entrar"); check(r.status_code == 200 and "chave" in r.text and "Set-Cookie" not in r.headers, "GET /entrar mostra o campo da chave sem gravar cookie")
r = c.get("/entrar?chave=errada-errada-errada"); check(r.status_code == 403 and "Set-Cookie" not in r.headers, "chave errada: 403 e sem cookie")
r = c.get("/entrar?chave=abc"); check(r.status_code == 403, "chave curta demais no .env não vale")
r = c.get("/entrar?chave=chaveDoThiago123456"); ck = r.headers.get("set-cookie", "")
check(r.status_code == 302 and r.headers.get("location") == "/" and acs.COOKIE in ck and "HttpOnly" in ck and "Max-Age=" in ck and "Secure" not in ck, f"chave certa por http: cookie HttpOnly sem Secure e volta para / ({ck[:80]})")
r = c.get("/api/gs/quem"); check(r.status_code == 200 and r.json() == {"quem": "thiago", "acesso_por_chave": True}, f"com cookie: API passa e sabe quem é ({r.text})")
r = c.get("/", headers={"accept": "text/html"}); check(r.status_code == 200, f"com cookie: o app abre ({r.status_code})")
r = c.get("/entrar/sair"); check(r.status_code == 302 and acs.COOKIE in r.headers.get("set-cookie", "") and "Max-Age=0" in r.headers.get("set-cookie", ""), "sair apaga o cookie")
r = c.get("/api/gs/quem"); check(r.status_code == 401, "depois de sair, volta a exigir a chave")
cs = TestClient(api.app, base_url="https://editor-exemplo.tailnet-exemplo.ts.net", follow_redirects=False)
r = cs.get("/entrar?chave=chaveDoRaphael654321", headers={"x-forwarded-proto": "https"}); check("Secure" in r.headers.get("set-cookie", ""), "pelo Funnel (https): cookie Secure")
r = cs.get("/api/gs/quem"); check(r.status_code == 200 and r.json()["quem"] == "raphael", f"a chave do Raphael identifica o Raphael ({r.text})")

novo = TestClient(api.app, base_url=FORA, follow_redirects=False)
r = novo.get("/manifest.webmanifest"); check(r.status_code != 401, f"manifesto do PWA passa sem cookie ({r.status_code})")
r = novo.get("/sw.js"); check(r.status_code == 200, f"service worker passa sem cookie (o PWA antigo precisa se atualizar) ({r.status_code})")
r = novo.get("/arquivos/x/y.mp4"); check(r.status_code == 401, f"arquivo de entrega sem cookie: 401 ({r.status_code})")
r = novo.get("/entrar", headers={"accept": "text/html"}); check(r.status_code == 200, "navegar para /entrar sem cookie não redireciona em laço")
r = novo.get("/api/webhooks/compartilhar/token-qualquer"); check(r.status_code != 401, f"webhook de compartilhar usa o token dele, não a chave ({r.status_code})")
r = novo.post("/api/gs/pedidos", data={"texto": "x"}); check(r.status_code == 401, "POST de fora sem cookie: 401")

local = TestClient(api.app, base_url="http://localhost:3200")
r = local.get("/api/gs/quem"); check(r.status_code == 200 and r.json()["quem"] == "", f"localhost passa sem chave ({r.text})")
local2 = TestClient(api.app, base_url="http://127.0.0.1:3200")
r = local2.get("/api/gs/quem"); check(r.status_code == 200, "127.0.0.1 passa sem chave")
check(acs.local("[::1]:3200") and acs.local("LOCALHOST") and not acs.local("localhost.evil.com") and not acs.local("editor-exemplo.tailnet-exemplo.ts.net"), "só hosts locais de verdade contam como locais")

# agente por pessoa
cfg_antes = {k: api.CFG.get(k) for k in ("agent_thiago_id", "agentes_por_pessoa")}
api.CFG["agent_thiago_id"] = "ag-thiago"; api.CFG["agentes_por_pessoa"] = {"thiago": "agent_thiago_id"}
modelos_antes = dict(api.MODELOS); api.MODELOS.clear(); api.MODELOS.update(api._modelos_de({}))  # mapa base: o config real pode pôr o Fable como padrão (10/11)
t = acs.QUEM.set("thiago")
check(api._agente_do_modelo("padrao") == "ag-thiago" and api._agente_do_modelo("") == "ag-thiago", "pedido do Thiago (padrão) vai para o agente da conta dele")
check(api._agente_do_modelo("fable") == api.CFG.get("agent_fable_id"), "o Thiago pedindo o Fable usa o Fable")
acs.QUEM.reset(t)
check(api._agente_do_modelo("padrao") == api.CFG["agent_id"], "sem pessoa (localhost) o padrão continua o Editor GS")
t = acs.QUEM.set("raphael"); check(api._agente_do_modelo("padrao") == api.CFG["agent_id"], "o Raphael sem agente próprio usa o Editor GS"); acs.QUEM.reset(t)
api.CFG["agent_thiago_id"] = None
t = acs.QUEM.set("thiago"); check(api._agente_do_modelo("padrao") == api.CFG["agent_id"], "Thiago sem agente configurado ainda cai no Editor GS"); acs.QUEM.reset(t)
api.MODELOS.clear(); api.MODELOS.update(modelos_antes)
for k, v in cfg_antes.items():
    if v is None: api.CFG.pop(k, None)
    else: api.CFG[k] = v
check("thiago" in api.MODELOS and api.MODELOS["thiago"]["chave"] == "agent_thiago_id", "modelo 'thiago' existe na lista de chips")

# sem chaves no .env: nada muda (comportamento antigo)
os.environ["EDITOR_GS_CHAVES"] = ""
r = novo.get("/api/gs/quem"); check(r.status_code == 200 and r.json() == {"quem": "", "acesso_por_chave": False}, "sem EDITOR_GS_CHAVES o app não pede chave")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
