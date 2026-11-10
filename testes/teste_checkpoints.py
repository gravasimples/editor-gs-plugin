"""Checkpoints e "Desfazer" (10/11/2026): foto da pasta de entrega antes de cada rodada do executor, restauração (arquivos alterados,
apagados e criados), limite de 5 por conversa, mensagem de sistema na conversa e 409 com rodada em andamento. Isolado: pasta temporária,
executor local com claude falso, gateway pelo transporte falso do FastAPI.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_checkpoints.py"""
import asyncio, json, os, stat, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "testes")); import _falso  # noqa: E402
from fastapi.testclient import TestClient
from servico import checkpoints as ckp, executor_local as exl

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="checkpoints-teste-"))
saida = tmp / "workspace" / "saida"; saida.mkdir(parents=True)

# ---- módulo: tirar, listar, restaurar
p = saida / "2026-11-10-reel"; p.mkdir()
(p / "final_9x16.mp4").write_bytes(b"V" * (6 * 1024 * 1024))  # grande: hardlink
(p / "final_9x16.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\noi\n", encoding="utf-8")
(p / "capa.png").write_bytes(b"P" * 10)
(p / "_trabalho").mkdir(); (p / "_trabalho" / "tmp.bin").write_bytes(b"x" * 100)
check(ckp.tirar(saida / "nao-existe") is None and ckp.listar(saida / "nao-existe") == [], "pasta inexistente: sem checkpoint e lista vazia")
c1 = ckp.tirar(p, rodada=1)
check(c1 and c1["n"] == 1 and c1["rodada"] == 1 and c1["arquivos"] == 3 and c1["resumo"].startswith("3 arquivos, 6") and (p / c1["pasta"] / "manifesto.json").is_file(), f"checkpoint 1: {c1 and c1['resumo']} ({c1 and c1['pasta']})")
m1 = json.loads((p / c1["pasta"] / "manifesto.json").read_text(encoding="utf-8"))
modos = {a["caminho"]: a["modo"] for a in m1["arquivos"]}
check(set(modos) == {"final_9x16.mp4", "final_9x16.srt", "capa.png"} and modos["final_9x16.srt"] == "copia" and modos["capa.png"] == "copia" and modos["final_9x16.mp4"] in ("hardlink", "copia"), f"manifesto: 3 arquivos, _trabalho fora, pequenos por cópia, vídeo por {modos['final_9x16.mp4']}")
check(all("tamanho" in a and "mtime" in a for a in m1["arquivos"]) and m1["bytes"] == 6 * 1024 * 1024 + (p / "final_9x16.srt").stat().st_size + 10, "manifesto com tamanho e mtime")
lst = ckp.listar(p); check(len(lst) == 1 and lst[0]["n"] == 1 and lst[0]["rodada"] == 1 and lst[0]["resumo"] == c1["resumo"], "listar devolve o checkpoint")

# a "rodada" muda a entrega: altera o SRT, apaga a capa, cria um arquivo novo, troca o vídeo (escreve temporário e renomeia, como o ffmpeg)
time.sleep(1.1)
(p / "final_9x16.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nmudou\n", encoding="utf-8")
(p / "capa.png").unlink(); (p / "novo.md").write_text("# novo", encoding="utf-8")
(p / "final_9x16.tmp.mp4").write_bytes(b"N" * (6 * 1024 * 1024)); (p / "final_9x16.tmp.mp4").replace(p / "final_9x16.mp4")
r = ckp.restaurar(p)  # sem n: o último
check(r["n"] == 1 and sorted(r["restaurados"]) == ["capa.png", "final_9x16.mp4", "final_9x16.srt"] and r["apagados"] == ["novo.md"] and r["faltando"] == [], f"restaurar: {r['restaurados']} de volta, {r['apagados']} apagado")
check((p / "final_9x16.srt").read_text(encoding="utf-8").endswith("oi\n") and (p / "capa.png").read_bytes() == b"P" * 10 and not (p / "novo.md").exists() and (p / "final_9x16.mp4").read_bytes()[:1] == b"V" and (p / "_trabalho" / "tmp.bin").is_file(), "pasta voltou ao estado do checkpoint 1; _trabalho intacta")
check(r["checkpoint_novo"] and r["checkpoint_novo"]["n"] == 2 and r["checkpoint_novo"]["motivo"].startswith("antes de desfazer") and len(ckp.listar(p)) == 2, "o estado anterior ao desfazer virou o checkpoint 2")
r2 = ckp.restaurar(p, 2)
check(r2["n"] == 2 and (p / "novo.md").is_file() and (p / "final_9x16.mp4").read_bytes()[:1] == b"N" and not (p / "capa.png").exists() and (p / "final_9x16.srt").read_text(encoding="utf-8").endswith("mudou\n") and len(ckp.listar(p)) == 3, "desfazer o desfazer: volta ao estado 2 (vídeo novo, sem capa, com novo.md)")
try:
    ckp.restaurar(p, 99); check(False, "n inexistente deveria falhar")
except KeyError as e:
    check("99" in str(e), "n inexistente: KeyError")
try:
    ckp.restaurar(saida / "vazia-sem-ckp"); check(False, "sem checkpoint deveria falhar")
except ValueError:
    check(True, "sem checkpoint: ValueError")

# ---- limite de 5 (o mais velho sai; `preservar` segura o alvo de um desfazer)
for i in range(4):
    ckp.tirar(p, rodada=10 + i)
lst = ckp.listar(p); check(len(lst) == 5 and [c["n"] for c in lst] == [7, 6, 5, 4, 3] and not any(d.name.startswith("1-") or d.name.startswith("2-") for d in (p / ckp.PASTA).iterdir()), f"limite de 5: ficam {[c['n'] for c in lst]}, pastas 1 e 2 apagadas")
r3 = ckp.restaurar(p, 3)  # o mais velho: o checkpoint novo (8) poda o mais velho que não seja o alvo
lst = ckp.listar(p); check(r3["n"] == 3 and len(lst) == 5 and 3 in [c["n"] for c in lst] and 4 not in [c["n"] for c in lst] and 8 in [c["n"] for c in lst], f"voltar ao mais velho: ele é preservado e o seguinte sai ({[c['n'] for c in lst]})")
vazia = saida / "vazia"; vazia.mkdir(); cv = ckp.tirar(vazia, rodada=1)
(vazia / "x.srt").write_text("x", encoding="utf-8"); rv = ckp.restaurar(vazia)
check(cv["arquivos"] == 0 and rv["apagados"] == ["x.srt"] and not (vazia / "x.srt").exists(), "pasta vazia: checkpoint vazio vale e desfazer apaga o que foi criado")

# ---- executor local + gateway (claude falso): checkpoint antes de cada rodada, rotas, 409
FALSO = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
prompt = sys.stdin.read()
pasta = Path(os.environ["FALSO_SAIDA"]); pasta.mkdir(parents=True, exist_ok=True)
modo = os.environ.get("FALSO_MODO", "ok")
if modo == "lento":
    time.sleep(20)
(pasta / "final_9x16.srt").write_text("rodada " + os.environ.get("FALSO_RODADA", "?"), encoding="utf-8")
(pasta / ("extra-" + os.environ.get("FALSO_RODADA", "x") + ".md")).write_text("extra", encoding="utf-8")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "## Resumo\nFeito.\n\n## Arquivos\n- saida/x/final_9x16.srt", "total_cost_usd": 0.1, "usage": {}, "session_id": "s", "num_turns": 1, "duration_ms": 5}))
'''
ws = tmp / "workspace"; (ws / "AGENTS.md").write_text("# Editor\n", encoding="utf-8"); (ws / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
falso = tmp / "claude_falso.py"; falso.write_text(FALSO, encoding="utf-8"); falso.chmod(falso.stat().st_mode | stat.S_IEXEC); falso = _falso.executavel(falso)
A1 = "agente-teste"
ex = exl.Executor(tmp, {"pasta": str(tmp / "executor"), "prefixo": "GRA", "tentativas": 1, "timeout_s": 2, "intervalo_s": 0.1, "agentes": [{"id": A1, "nome": "Editor GS", "motor": "claude", "comando": str(falso)}]}, porta=3298, workspace=ws)
LOOP = asyncio.new_event_loop(); asyncio.set_event_loop(LOOP)
def run(coro):
    return LOOP.run_until_complete(coro)

from servico import api
api.SAIDA = saida; api.INDICE = tmp / "conversas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.GSI_DB = tmp / "gs.db"; api.LICENCA_EXIGIDA = False
api.EXECUTOR = ex; api.CFG["agent_id"] = A1; ex.antes_da_rodada = api._checkpoint_antes_da_rodada
async def sync(forcar=False): return None
api._sincronizar_instrucoes = sync
slug = "2026-11-10-pedido"
issue = run(ex.chamar("POST", "/api/companies/local/issues", json={"title": "Pedido", "description": f"Corta.\n\n<!-- gs-slug: {slug} -->", "status": "todo", "assigneeAgentId": A1}))
cid = issue["id"]; api.INDICE.write_text(json.dumps({cid: {"slug": slug}}), encoding="utf-8")
os.environ["FALSO_SAIDA"] = str(saida / slug); os.environ["FALSO_RODADA"] = "1"; os.environ["FALSO_MODO"] = "ok"
cli = TestClient(api.app)
check(cli.get(f"/api/gs/conversas/{cid}/checkpoints").json() == {"slug": slug, "itens": []}, "sem entrega: lista vazia")
check(cli.post(f"/api/gs/conversas/{cid}/desfazer", json={}).status_code == 404, "sem entrega: desfazer dá 404")
run(ex.rodar_uma_vez(esperar=True))
check(not (saida / slug / ckp.PASTA).exists() and (saida / slug / "final_9x16.srt").read_text(encoding="utf-8") == "rodada 1", "1ª rodada: a pasta ainda não existia, sem checkpoint; entrega criada")
run(ex.chamar("POST", f"/api/issues/{cid}/comments", json={"body": "ajusta"})); run(ex.chamar("PATCH", f"/api/issues/{cid}", json={"status": "todo"}))
os.environ["FALSO_RODADA"] = "2"; run(ex.rodar_uma_vez(esperar=True))
lst = cli.get(f"/api/gs/conversas/{cid}/checkpoints").json()["itens"]
check(len(lst) == 1 and lst[0]["rodada"] == 2 and lst[0]["arquivos"] == 2 and lst[0]["resumo"].startswith("2 arquivos") and (saida / slug / "final_9x16.srt").read_text(encoding="utf-8") == "rodada 2" and (saida / slug / "extra-2.md").is_file(), f"2ª rodada: checkpoint tirado antes dela (rodada {lst and lst[0]['rodada']}, {lst and lst[0]['resumo']})")
run(ex.chamar("POST", f"/api/issues/{cid}/comments", json={"body": "de novo"})); run(ex.chamar("PATCH", f"/api/issues/{cid}", json={"status": "todo"}))
os.environ["FALSO_RODADA"] = "3"; run(ex.rodar_uma_vez(esperar=True))
lst = cli.get(f"/api/gs/conversas/{cid}/checkpoints").json()["itens"]
check([c["rodada"] for c in lst] == [3, 2] and lst[0]["arquivos"] == 3, "3ª rodada: dois checkpoints, mais novo primeiro")

r = cli.post(f"/api/gs/conversas/{cid}/desfazer", json={"n": lst[1]["n"]})
j = r.json()
check(r.status_code == 200 and j["rodada"] == 2 and (saida / slug / "final_9x16.srt").read_text(encoding="utf-8") == "rodada 1" and not (saida / slug / "extra-2.md").exists() and not (saida / slug / "extra-3.md").exists() and (saida / slug / "extra-1.md").is_file(), f"desfazer pelo gateway volta ao estado antes da rodada 2 ({r.status_code}: {j.get('mensagem') or j})")
check(j["mensagem"].startswith("↶ Desfeito: voltou ao estado antes da rodada 2 (") and j["checkpoint_novo"]["n"] == 3, "mensagem de sucesso e checkpoint novo do estado anterior")
cm = run(ex.chamar("GET", f"/api/issues/{cid}/comments"))
check(cm[-1]["body"] == j["mensagem"] and cm[-1]["authorUserId"] == "app", "mensagem de sistema registrada na conversa (aviso do app)")
conv = cli.get(f"/api/gs/conversas/{cid}").json()
check(conv["mensagens"][-1]["autor"] == "app" and "Desfeito" in conv["mensagens"][-1]["texto"] and not any(e["caminho"].startswith(f"{slug}/{ckp.PASTA}") for e in conv["entregas"]), "a conversa mostra o aviso e _checkpoints não aparece nas entregas")
r = cli.post(f"/api/gs/conversas/{cid}/desfazer", json={})  # sem n: o último (o checkpoint 3, estado de antes do desfazer)
check(r.status_code == 200 and r.json()["n"] == 3 and (saida / slug / "final_9x16.srt").read_text(encoding="utf-8") == "rodada 3", "desfazer sem n volta ao último checkpoint (desfaz o desfazer)")
check(cli.post(f"/api/gs/conversas/{cid}/desfazer", json={"n": 99}).status_code == 404, "n inexistente: 404")
check(cli.post(f"/api/gs/conversas/{cid}/desfazer", content=b"{nao", headers={"content-type": "application/json"}).status_code == 400, "JSON inválido: 400")

# 409 com rodada em andamento
os.environ["FALSO_MODO"] = "lento"
run(ex.chamar("POST", f"/api/issues/{cid}/comments", json={"body": "mais uma"})); run(ex.chamar("PATCH", f"/api/issues/{cid}", json={"status": "todo"}))
async def durante():
    rr = await ex.rodar_uma_vez()
    await asyncio.sleep(0.5)
    resp = cli.post(f"/api/gs/conversas/{cid}/desfazer", json={})
    check(resp.status_code == 409 and "Parar" in resp.text, f"rodada em andamento: desfazer dá 409 ({resp.status_code})")
    await ex.chamar("POST", f"/api/heartbeat-runs/{rr['id']}/cancel", json={})
    await ex.chamar("PATCH", f"/api/issues/{cid}", json={"status": "blocked"})
    while ex.tarefas:
        await asyncio.gather(*list(ex.tarefas), return_exceptions=True)
run(durante())
check(cli.post(f"/api/gs/conversas/{cid}/desfazer", json={}).status_code == 200, "depois de parar, desfazer volta a funcionar")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
