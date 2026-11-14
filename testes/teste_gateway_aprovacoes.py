"""Testes isolados do revisor de marca, da central de aprovação (Paperclip falso) e do bloqueio de escrita no Notion."""
import json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, aprovacoes as aprv, marca_revisor as mrev

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

# revisor
r = mrev.revisar({"descricao": "Mais de 20 mil alunos já aprenderam — e por R$ 297 você também. Últimas vagas! #a #b #c #d #e #f #g #h #i #j #k", "titulo": "COMO GRAVAR AULA NO OBS SEM ERRO", "gancho": "Ó, olha só", "roteiro": "Ajusta o bitrate aí."})
ids = {a["regra"] for a in r["avisos"]}
check({"alunos", "preco", "escassez", "travessao", "hashtags", "caixa_alta", "jargao"} <= ids and not r["ok"] and r["resumo"]["alta"] >= 3, f"revisor pega alunos, preço, escassez, travessão, hashtags, caixa alta e jargão ({sorted(ids)})")
check(r["avisos"][0]["gravidade"] == "alta" and r["avisos"][-1]["gravidade"] == "baixa" and all("trecho" in a and "campo" in a for a in r["avisos"]), "avisos ordenados por gravidade, com campo e trecho")
limpo = mrev.revisar({"descricao": "Olha só: três cenas no OBS e você já grava a aula. Salva pra usar antes de gravar. #obsstudio #gravasimples", "titulo": "Três cenas no OBS pra sua aula", "gancho": "Você só precisa de três cenas"})
check(limpo["ok"] and limpo["avisos"] == [], "texto na voz da marca passa limpo")
check(mrev.revisar({})["ok"] and mrev.revisar({"descricao": None})["ok"], "sem texto: ok")

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.GSI_DB = tmp / "gs.db"; api.SAIDA.mkdir()
    api.NOTION_ESCRITA = False
    for slug in ("s1", "s2", "s3"):
        d = api.SAIDA / slug; d.mkdir(); (d / "final_9x16.mp4").write_bytes(b"0"); (d / "capa.png").write_bytes(b"1")
    (api.SAIDA / "s1" / "final_9x16.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nsão 20 mil alunos\n", encoding="utf-8")
    api.INDICE.write_text(json.dumps({"i1": {"slug": "s1", "notion_page": "abc"}, "i2": {"slug": "s2"}, "i3": {"slug": "s3"}, "i5": {"slug": "s1"}}), encoding="utf-8")
    api.TEXTOS_CACHE.write_text(json.dumps({"i1": {"id": "i1", "slug": "s1", "secoes": [{"chave": "descricao", "titulo": "Legenda do post", "conteudo": "Legenda limpa #a"}, {"chave": "gancho", "titulo": "Gancho", "conteudo": "Gancho bom"}]},
                                            "i2": {"id": "i2", "slug": "s2", "secoes": [{"chave": "descricao", "titulo": "Legenda", "conteudo": "Por R$ 97 — corre que são as últimas vagas"}]}}), encoding="utf-8")
    agora = datetime.now(timezone.utc); iso = lambda d: d.isoformat().replace("+00:00", "Z")
    issues = [{"id": "i1", "identifier": "GRA-901", "title": "Entrega em revisão", "status": "in_review", "updatedAt": iso(agora - timedelta(hours=3))},
              {"id": "i2", "identifier": "GRA-902", "title": "Entrega done sem aprovação", "status": "done", "updatedAt": iso(agora - timedelta(hours=1))},
              {"id": "i3", "identifier": "GRA-903", "title": "Já aprovada", "status": "done", "updatedAt": iso(agora - timedelta(hours=5))},
              {"id": "i5", "identifier": "GRA-905", "title": "Done antiga", "status": "done", "updatedAt": iso(agora - timedelta(days=10))},
              {"id": "i4", "identifier": "GRA-904", "title": "Esperando decisão", "status": "in_progress", "updatedAt": "2026-10-31T12:00:00Z"}]
    aprv.registrar(api.SAIDA / "s3", comentario="ok")
    coments, patches = [], []
    async def pc(metodo, url, **kw):
        if url.endswith("/issues") and metodo == "GET": return issues
        if url.endswith("/issues/i4/interactions"): return [{"id": "x1", "kind": "request_confirmation", "title": "Plano de cenas", "summary": "6 cenas", "status": "pending", "payload": {"prompt": "Posso montar?"}}]
        if url.endswith("/interactions"): return []
        if "/issues/" in url and url.endswith("/comments") and metodo == "POST": coments.append((url, kw["json"]["body"])); return {"id": "c"}
        if url.endswith("/comments"): return []
        if metodo == "PATCH": patches.append((url, kw["json"])); return {}
        if metodo == "GET" and "/issues/" in url: return next(i for i in issues if url.endswith(i["id"]))
        return {}
    api._pc = pc
    async def sync(forcar=False): return None
    api._sincronizar_instrucoes = sync
    c = TestClient(api.app)
    r = c.get("/api/gs/aprovacoes").json()
    ids_e = [e["id"] for e in r["entregas"]]
    check(ids_e == ["i2", "i1"] and r["n"] == 3 and r["decisoes"][0]["interacao"]["titulo"] == "Plano de cenas" and r["antigas_sem_aprovacao"] == 1, f"fila: in_review e done recente sem aprovação (aprovada e antiga ficam fora, antiga contada), mais a decisão ({ids_e}, antigas {r.get('antigas_sem_aprovacao')})")
    e1 = next(e for e in r["entregas"] if e["id"] == "i1"); e2 = next(e for e in r["entregas"] if e["id"] == "i2")
    check(e1["video"]["nome"] == "final_9x16.mp4" and e1["capa"]["nome"] == "capa.png" and e1["textos"]["gancho"] == "Gancho bom" and e1["etiquetas"]["formato"] == "reel", "cartão traz vídeo, capa, textos e etiquetas")
    check(any(a["regra"] == "alunos" and a["campo"] == "srt" for a in e1["revisao"]["avisos"]) and not e1["revisao"]["ok"], "revisor lê também o SRT da entrega (20 mil alunos na legenda do vídeo)")
    check({a["regra"] for a in e2["revisao"]["avisos"]} >= {"preco", "escassez", "travessao"} and e2["revisao"]["resumo"]["alta"] == 2, "revisor aponta preço, escassez e travessão na legenda da outra entrega")
    # pedido de ajuste com segundo
    check(aprv.pedido_ajuste("tirar o zoom", 83.6, "final_9x16.mp4") == "Ajuste no vídeo final_9x16.mp4, aos 1:23 (83 s): tirar o zoom" and aprv.pedido_ajuste("texto", None) == "texto", "pedido de ajuste com o instante")
    r = c.post("/api/gs/conversas/i1/ajuste", data={"texto": "tira o zoom", "segundo": "12.4", "arquivo": "final_9x16.mp4"})
    check(r.status_code == 200 and coments and "aos 0:12 (12 s): tira o zoom" in coments[-1][1], "rota de ajuste manda a mensagem com o instante")
    # aprovar: registra localmente e NÃO escreve no Notion
    r = c.post("/api/gs/conversas/i1/aprovar", data={"comentario": "Top"}).json()
    check(r["ok"] and "desligado" in (r["notion"] or "") and (api.SAIDA / "s1" / "aprovacao.json").exists() and json.loads((api.SAIDA / "s1" / "aprovacao.json").read_text())["comentario"] == "Top", "aprovar grava aprovacao.json e não toca o Notion")
    check([e["id"] for e in c.get("/api/gs/aprovacoes").json()["entregas"]] == ["i2"], "depois de aprovar, sai da fila")
    r = c.post("/api/gs/aprovacoes/lote", data={"ids": "i2,i9"}).json()
    check(r["aprovadas"] == ["i2"] and (api.SAIDA / "s2" / "aprovacao.json").exists() and len(r["erros"]) == 1, "lote aprova o que existe e reporta o erro do resto")
    check(c.post("/api/gs/conversas/i1/textos/notion", data={"chave": "descricao"}).status_code == 409, "enviar texto ao Notion está bloqueado (409)")
    (api.SAIDA / "s2" / "aprovacao.json").unlink(); r = c.post("/api/gs/aprovacoes/vistas", data={"ids": "i2,i9"}).json()
    check(r["vistas"] == ["i2"] and json.loads((api.SAIDA / "s2" / "aprovacao.json").read_text())["tipo"] == "vista" and c.get("/api/gs/aprovacoes").json()["entregas"] == [], "marcar como vista tira da fila sem comentar na issue")
    # revisão por rota
    api.TEXTOS_CACHE.write_text("{}")
    async def pc2(metodo, url, **kw):
        if url.endswith("/comments") and metodo == "GET": return [{"id": "m1", "body": "## Legenda do post\n\nVale R$ 97 hoje", "createdAt": "2026-10-31T10:00:00Z", "authorAgentId": "ag"}]
        return await pc(metodo, url, **kw)
    api._pc = pc2
    r = c.get("/api/gs/conversas/i1/revisao-marca").json()
    check(r["conversa"] == "i1" and any(a["regra"] == "preco" for a in r["avisos"]), "rota de revisão lê a última entrega em texto da conversa")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
