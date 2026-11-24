"""Testes isolados de Arquivos: armazenamento, limpeza de trabalho antigo, uso do Editor e uploads avulsos. Pastas temporárias, Paperclip por dublê.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_arquivos.py"""
import os, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, arquivos

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.WORKSPACE = tmp / "ws"; api.SAIDA = api.WORKSPACE / "saida"; api.ENTRADA = api.WORKSPACE / "entrada"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    for n in ("saida/velha/_trabalho", "saida/velha/_anteriores", "saida/velha/trabalho", "saida/nova/_trabalho", "entrada/x", "referencias"):
        (api.WORKSPACE / n).mkdir(parents=True)
    (api.SAIDA / "velha" / "final_9x16.mp4").write_bytes(b"\x00" * 3000)
    (api.SAIDA / "velha" / "_trabalho" / "camada.png").write_bytes(b"\x00" * 200000)
    (api.SAIDA / "velha" / "trabalho" / "tmp.bin").write_bytes(b"\x00" * 100000)
    (api.SAIDA / "velha" / "_anteriores" / "v1.png").write_bytes(b"\x00" * 50000)
    (api.SAIDA / "nova" / "_trabalho" / "camada.png").write_bytes(b"\x00" * 70000)
    (api.ENTRADA / "x" / "bruto.mp4").write_bytes(b"\x00" * 1000)
    antigo = time.time() - 40 * 86400
    for p in (api.SAIDA / "velha").rglob("*"):
        os.utime(p, (antigo, antigo))
    os.utime(api.SAIDA / "velha", (antigo, antigo))
    issues = [{"status": "done", "createdAt": "2026-10-29T10:00:00Z", "startedAt": "2026-10-29T10:05:00Z", "completedAt": "2026-10-29T10:25:00Z"},
              {"status": "in_review", "createdAt": "2026-10-28T10:00:00Z", "startedAt": "2026-10-28T10:05:00Z", "completedAt": None},
              {"status": "todo", "createdAt": "2026-10-20T10:00:00Z"}, {"status": "cancelled", "createdAt": "2026-10-29T10:00:00Z"}]
    async def pc_falso(metodo, url, **kw):
        return issues if url.endswith("/issues") else []
    api._pc = pc_falso
    c = TestClient(api.app)

    r = c.get("/api/gs/armazenamento"); j = r.json()
    check(r.status_code == 200 and j["pastas_mb"]["saida"] == 0.4 and j["trabalho_mb"] == 0.4 and j["anteriores_mb"] == 0.1 and j["disco"]["livre_gb"] > 0, f"tamanhos por pasta, trabalho e anteriores: {j['pastas_mb']} {j['trabalho_mb']} {j['anteriores_mb']}")
    cand = j["limpeza"]["candidatos"]
    check(sorted((x["slug"], x["pasta"]) for x in cand) == [("velha", "_trabalho"), ("velha", "trabalho")] and j["limpeza"]["mb"] == 0.3, f"só as pastas de trabalho da entrega parada há 40 dias são candidatas (padrão 30 dias): {cand}")
    check(c.post("/api/gs/armazenamento/limpar", data={"dias": 3}).status_code == 400, "limpar com menos de 7 dias é recusado")
    r = c.post("/api/gs/armazenamento/limpar", data={}); j2 = r.json()
    check(r.status_code == 200 and j2["mb"] == 0.3 and not (api.SAIDA / "velha" / "_trabalho").exists() and not (api.SAIDA / "velha" / "trabalho").exists(), "limpeza apaga as duas pastas de trabalho antigas")
    check((api.SAIDA / "velha" / "_anteriores" / "v1.png").exists() and (api.SAIDA / "velha" / "final_9x16.mp4").exists() and (api.SAIDA / "nova" / "_trabalho" / "camada.png").exists() and (api.ENTRADA / "x" / "bruto.mp4").exists(), "versões anteriores, entrega, trabalho recente e entrada ficam")
    check(c.get("/api/gs/armazenamento").json()["limpeza"]["candidatos"] == [], "depois da limpeza não há candidatos")

    from datetime import datetime, timezone
    u = arquivos.uso(issues, agora=datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc))
    check(u["periodos"]["hoje"] == {"criados": 1, "concluidos": 1} and u["periodos"]["7_dias"]["criados"] == 2 and u["periodos"]["30_dias"]["criados"] == 3, f"uso conta pedidos por período sem os cancelados: {u['periodos']}")
    check(u["aguardando_voce"] == 1 and u["na_fila"] == 1 and u["duracao_media_min"] == 20.0 and u["n_medidos"] == 1, "uso: aguardando, fila e duração média")
    r = c.get("/api/gs/uso"); check(r.status_code == 200 and "periodos" in r.json(), "rota /api/gs/uso responde")

    # tempo economizado: estimativa por fluxo + duração do vídeo final / slides / páginas (ffmpeg gera um vídeo de 30 s)
    import subprocess, json as _json
    (api.SAIDA / "reel").mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:size=64x64:rate=5:d=30", "-c:v", "libx264", "-preset", "ultrafast", str(api.SAIDA / "reel" / "final_9x16.mp4")], check=True)
    (api.SAIDA / "carro").mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (api.SAIDA / "carro" / f"slide-0{i + 1}.png").write_bytes(b"\x89PNG")
    (api.SAIDA / "carro" / "capa.png").write_bytes(b"\x89PNG")
    iss = [{"id": "i1", "status": "done", "description": "x\n\nFluxo: `fluxos/reels-padrao.md` (siga).", "completedAt": "2026-10-29T10:25:00Z"},
           {"id": "i2", "status": "done", "description": "Fluxo: `fluxos/carrossel.md`", "completedAt": "2026-10-20T10:00:00Z"},
           {"id": "i3", "status": "todo", "description": "Fluxo: `fluxos/reels-padrao.md`"}, {"id": "i4", "status": "done", "description": "sem pasta"}]
    idx = {"i1": {"slug": "reel"}, "i2": {"slug": "carro"}, "i3": {"slug": "reel"}, "i4": {"slug": "nao-existe"}}
    e1 = arquivos.economia_pedido(api.SAIDA, "reel", iss[0]); e2 = arquivos.economia_pedido(api.SAIDA, "carro", iss[1])
    check(e1 and e1["minutos"] == 24 and e1["fluxo"] == "reels-padrao" and abs(e1["video_s"] - 30) < 0.5, f"reel de 30 s: 20 fixos + 8 × 0,5 min = 24 ({e1})")
    check(e2 and e2["minutos"] == 90 and e2["itens"] == 5, f"carrossel de 5 slides (capa.png não conta): 30 + 12 × 5 = 90 ({e2})")
    check(arquivos.economia_pedido(api.SAIDA, "reel", iss[2]) is None and arquivos.economia_pedido(api.SAIDA, "nao-existe", iss[3]) is None, "pedido não concluído ou sem pasta não conta")
    tot = arquivos.economia(api.SAIDA, iss, idx, agora=datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc))
    check(tot["total_min"] == 114 and tot["n_entregas"] == 2 and tot["periodos_min"]["hoje"] == 24 and tot["periodos_min"]["30_dias"] == 114 and tot["por_fluxo"] == {"reels-padrao": 24, "carrossel": 90}, f"soma por período e por fluxo: {tot['periodos_min']} {tot['por_fluxo']}")
    check(arquivos._fluxo_de({"description": "Edite os clipes do Clipador"}) == "clipes" and arquivos._fluxo_de({"description": ""}) == "", "fluxo lido da descrição (Clipador sem linha de fluxo)")

    r = c.post("/api/gs/biblioteca/upload", files=[("arquivos", ("take 1.mp4", b"\x00" * 500, "video/mp4")), ("arquivos", ("logo.png", b"\x89PNG", "image/png"))])
    check(r.status_code == 200 and r.json()["salvos"] == ["entrada/_biblioteca/take_1.mp4", "entrada/_biblioteca/logo.png"] and (api.ENTRADA / "_biblioteca" / "take_1.mp4").stat().st_size == 500, f"upload avulso salva em entrada/_biblioteca com nome saneado: {r.text[:120]}")
    lst = c.get("/api/gs/biblioteca/avulsos").json()
    check(len(lst) == 2 and {x["tipo"] for x in lst} == {"video", "imagem"} and all(x["caminho"].startswith("entrada/_biblioteca/") for x in lst), "lista de avulsos com tipo e caminho")
    check(c.delete("/api/gs/biblioteca/avulsos/logo.png").status_code == 200 and len(c.get("/api/gs/biblioteca/avulsos").json()) == 1, "apagar avulso")
    check(c.delete("/api/gs/biblioteca/avulsos/..%2Fx%2Fbruto.mp4").status_code in (400, 404, 405) and (api.ENTRADA / "x" / "bruto.mp4").exists(), "nome com caminho é recusado")
    check(c.delete("/api/gs/biblioteca/avulsos/nao.png").status_code == 404, "avulso inexistente 404")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
