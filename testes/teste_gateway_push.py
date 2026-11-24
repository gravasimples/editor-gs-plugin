"""Testes isolados das notificações push: chaves VAPID em pasta temporária, inscrições, envio por dublê (sem rede), vigia de status e rotas."""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, push

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    push.VAPID = tmp / "vapid.json"; push.INSCRICOES = tmp / "insc.json"
    c = push.chaves()
    check(len(c["publica"]) > 60 and "PRIVATE KEY" in c["privada"] and push.chaves()["publica"] == c["publica"], "chaves VAPID geradas uma vez e reaproveitadas")
    sub = {"endpoint": "https://push.exemplo/abc", "keys": {"p256dh": "BPx", "auth": "a1"}}
    check(push.inscrever(sub, "Android Chrome")["n"] == 1 and push.inscrever(sub)["n"] == 1 and push.inscrever({**sub, "endpoint": "https://push.exemplo/def"})["n"] == 2, "inscrever: mesmo endpoint substitui, outro soma")
    try:
        push.inscrever({"endpoint": "x"}); check(False, "inscrição sem chaves recusada")
    except ValueError:
        check(True, "inscrição sem chaves recusada")
    enviados = []
    class Resp: status_code = 410
    class Morta(Exception):
        response = Resp()
    def raw(s, payload, v):
        if s["endpoint"].endswith("def"): raise Morta("gone")
        enviados.append((s["endpoint"], json.loads(payload)))
    r = push.enviar("Entrega pronta", "GRA-30", "/c/i1", "pronto-i1", _raw=raw)
    check(r == {"enviadas": 1, "removidas": 1, "erros": []} and enviados[0][1]["url"] == "/c/i1" and len(push.listar()) == 1, "enviar: manda aos vivos, remove inscrição morta (410)")
    check(push.remover("https://push.exemplo/abc")["n"] == 0 and push.enviar("x", _raw=raw)["enviadas"] == 0, "remover e enviar sem inscritos")

    # vigia
    v = push.Vigia()
    i1 = {"id": "i1", "identifier": "GRA-1", "title": "Webcam travada", "status": "in_progress"}
    i2 = {"id": "i2", "identifier": "GRA-2", "title": "Carrossel luz", "status": "done"}
    check(v.avaliar([i1, i2]) == [] and v.visto == {"i1": "in_progress", "i2": "done"}, "primeira leitura só memoriza (nada de avisar entregas antigas)")
    av = v.avaliar([{**i1, "status": "in_review"}, i2])
    check(len(av) == 1 and av[0][0].startswith("Entrega pronta") and "GRA-1" in av[0][0] and av[0][2] == "/c/i1", "in_progress → in_review avisa entrega pronta")
    check(v.avaliar([{**i1, "status": "done"}, i2]) == [], "in_review → done não avisa de novo")
    av = v.avaliar([{**i1, "status": "blocked"}, i2])
    check(len(av) == 1 and "travado" in av[0][0], "blocked avisa pedido travado")
    av = v.avaliar([{**i1, "status": "in_progress"}, i2], {"i1": [{"id": "x1", "title": "Plano de cenas"}]})
    check(len(av) == 1 and "decisão" in av[0][0] and av[0][1] == "Plano de cenas" and av[0][3] == "decisao-i1", "interaction pendente nova avisa decisão")
    check(v.avaliar([i1, i2], {"i1": [{"id": "x1", "title": "Plano de cenas"}]}) == [], "a mesma interaction não avisa duas vezes")
    av = v.avaliar([i1, i2, {"id": "i3", "identifier": "GRA-3", "title": "Novo", "status": "done"}])
    check(av == [], "issue que já nasce done (nunca vista) não avisa")

    # rotas
    cli = TestClient(api.app)
    r = cli.get("/api/gs/push/chave"); check(r.status_code == 200 and r.json()["chave"] == c["publica"] and r.json()["inscritos"] == 0, "rota da chave pública")
    r = cli.post("/api/gs/push/inscrever", json={"inscricao": sub, "aparelho": "teste"}); check(r.status_code == 200 and r.json()["n"] == 1, "rota inscrever")
    check(cli.post("/api/gs/push/inscrever", json={"endpoint": "x"}).status_code == 400, "rota inscrever recusa inválida")
    push._enviar_raw = raw
    r = cli.post("/api/gs/push/teste"); check(r.status_code == 200 and r.json()["enviadas"] == 1, "rota de teste manda aos inscritos")
    r = cli.post("/api/gs/push/sair", json={"endpoint": sub["endpoint"]}); check(r.json()["n"] == 0, "rota sair")
    src = (RAIZ / "app" / "public" / "push-sw.js").read_text(encoding="utf-8"); vite = (RAIZ / "app" / "vite.config.ts").read_text(encoding="utf-8")
    check("addEventListener('push'" in src and "notificationclick" in src and "importScripts: ['push-sw.js']" in vite, "service worker de push importado pelo Workbox")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
