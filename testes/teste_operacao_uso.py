"""Testes isolados: painel Operação (resumo sem rede), uso por agente (arquivos.uso) e estado de uso das entregas na Biblioteca (pasta temporária)."""
import json, sys, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, arquivos as arq, operacao as opr

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    r = opr.resumo(tmp, {"status": "ok"}, {"em_andamento": [], "na_fila": 0, "aguardando_voce": 0, "hoje": {"criados": 0, "concluidos": 0}})
    check(set(["quando", "gateway", "gpu", "disco", "processos", "claude", "paperclip", "pedidos", "avisos"]) <= set(r) and r["disco"]["total_gb"] > 0 and isinstance(r["processos"].get("paperclip"), int), "resumo da operação com todas as chaves")
    check(r["gateway"]["no_ar_min"] >= 0 and (r["gpu"] is None or r["gpu"]["vram_total_mb"] > 0), "gateway e gpu coerentes")
    # uso por agente
    agora = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc); iso = lambda d: d.isoformat().replace("+00:00", "Z")
    issues = [{"id": "a", "status": "done", "assigneeAgentId": "ag-opus", "createdAt": iso(agora - timedelta(hours=3)), "startedAt": iso(agora - timedelta(hours=2)), "completedAt": iso(agora - timedelta(hours=1))},
              {"id": "b", "status": "in_progress", "assigneeAgentId": "ag-fable", "createdAt": iso(agora - timedelta(hours=1)), "startedAt": iso(agora - timedelta(minutes=10))},
              {"id": "c", "status": "done", "assigneeAgentId": "ag-opus", "createdAt": iso(agora - timedelta(days=2)), "startedAt": iso(agora - timedelta(days=2)), "completedAt": iso(agora - timedelta(days=2) + timedelta(minutes=30))},
              {"id": "d", "status": "cancelled", "assigneeAgentId": "ag-opus", "createdAt": iso(agora)}]
    u = arq.uso(issues, agora=agora)
    check("por_agente" not in u, "sem mapa de agentes, nada de por_agente (compatível)")
    u = arq.uso(issues, agora=agora, agentes={"ag-opus": "Editor GS", "ag-fable": "Editor GS (Fable)"})
    pa = u["por_agente"]
    check(pa["Editor GS"] == {"pedidos_30d": 2, "concluidos_30d": 2, "em_andamento": 0, "duracao_media_min": 45.0} and pa["Editor GS (Fable)"]["em_andamento"] == 1 and pa["Editor GS (Fable)"]["duracao_media_min"] is None, f"por_agente conta pedidos, concluídos, em andamento e média ({pa})")
    check("cancelled" not in json.dumps(pa) and sum(x["pedidos_30d"] for x in pa.values()) == 3, "cancelados ficam fora")
    # biblioteca: estado de uso
    api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.SAIDA.mkdir()
    for slug, regs in (("post-a", [{"tipo": "publora", "quando": "2026-10-30T10:00:00"}]), ("yt-b", [{"tipo": "drive", "quando": "2026-10-29T10:00:00"}, {"tipo": "youtube", "quando": "2026-10-30T11:00:00"}]), ("drive-c", [{"tipo": "drive", "quando": "2026-10-28T09:00:00"}]), ("novo-d", None)):
        d = api.SAIDA / slug; d.mkdir(); (d / "final_9x16.mp4").write_bytes(b"0" * 10)
        if regs: (d / "publicacoes.json").write_text(json.dumps(regs), encoding="utf-8")
    api.INDICE.write_text(json.dumps({"i1": {"slug": "post-a", "pasta": "Black 2026"}}), encoding="utf-8")
    c = TestClient(api.app)
    j = {p["slug"]: p for p in c.get("/api/gs/biblioteca").json()}
    check(j["post-a"]["uso"]["rotulo"] == "postado ou agendado" and j["post-a"]["uso"]["publora"] == 1 and j["post-a"]["conversa"] == "i1" and j["post-a"]["pasta"] == "Black 2026", "entrega publicada na Publora: postado, com conversa e pasta do índice")
    check(j["yt-b"]["uso"]["rotulo"] == "postado ou agendado" and j["yt-b"]["uso"]["drive"] == 1 and j["yt-b"]["uso"]["ultimo"] == "2026-10-30T11:00:00", "YouTube conta como postado; último registro")
    check(j["drive-c"]["uso"]["rotulo"] == "no Drive" and j["novo-d"]["uso"]["rotulo"] == "ainda não usado" and j["novo-d"]["uso"]["ultimo"] is None and j["novo-d"]["conversa"] is None, "só Drive e ainda não usado")
    r = c.get("/api/gs/operacao")
    check(r.status_code == 200 and "avisos" in r.json() and r.json()["paperclip"] is not None, "rota /api/gs/operacao responde mesmo com o Paperclip fora (status offline)")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
