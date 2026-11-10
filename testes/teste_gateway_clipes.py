"""Testes isolados do Clipador (gateway): pastas temporárias, Paperclip por dublê. Sem transcrição nem LLM.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_clipes.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, clipes as clp, referencias as refs

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.ENTRADA = tmp / "entrada"; api.RECEBIDOS = api.ENTRADA / "_recebidos"; api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.REFERENCIAS = tmp / "referencias"; api.CLIPES = tmp / "clipes"; api.ENTRADA.mkdir(); api.SAIDA.mkdir(); api.REFERENCIAS.mkdir()
    criadas = []
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            criadas.append(kw["json"]); return {"id": f"issue-{len(criadas)}", "identifier": f"GRA-{len(criadas)}", **kw["json"]}
        if metodo == "GET" and "/issues/" in url and url.endswith(tuple(f"issue-{i}" for i in range(1, 20))):
            return {"id": url.rsplit("/", 1)[-1], "status": "done", "description": ""}
        return []
    api._pc = pc_falso
    refs.YTDLP = tmp / "nao-existe"
    c = TestClient(api.app)

    # 1. Arquivo longo anexado → issue PROPOR com fluxo cortes-longos e origem em entrada/
    r = c.post("/api/gs/clipes", data={"nota": "live de terça sobre áudio", "tipo_origem": "live", "n": 8}, files=[("arquivos", ("live terca.mp4", b"\x00" * 500, "video/mp4"))])
    check(r.status_code == 200 and r.json()["codigo"] == "GRA-1", f"clipador cria issue ({r.status_code} {r.text[:100]})")
    cid = r.json()["id"]; slug = r.json()["slug"]
    d = criadas[-1]["description"]
    check("cortes-longos" in d and f"entrada/{slug}/live_terca.mp4" in d and "fase PROPOR" in d and "origem: live" in d, "issue cita fluxo, origem e tipo")
    check((api.ENTRADA / slug / "live_terca.mp4").exists(), "vídeo salvo em entrada/<slug>/")
    check(json.loads(api.INDICE.read_text())[cid]["clipador"]["origem"].endswith("live_terca.mp4"), "índice guarda a origem")

    # 2. Sem cortes.json ainda
    r = c.get(f"/api/gs/conversas/{cid}/cortes"); check(r.status_code == 404 or (r.status_code == 200 and not r.json()["pronto"]), "sem saída ainda: não pronto")

    # 3. Editor grava cortes.json → lista com ids e duração calculada
    (api.SAIDA / slug).mkdir()
    (api.SAIDA / slug / "cortes.json").write_text(json.dumps({"origem": f"entrada/{slug}/live_terca.mp4", "duracao_s": 3600, "tipo_origem": "live", "cortes": [
        {"id": "c01", "inicio": 120.5, "fim": 165.0, "titulo": "Microfone de lapela no OBS", "gancho": "Seu microfone está no lugar errado", "destaque": "errado", "motivo": "dúvida recorrente", "tema": "áudio", "tipo": "tutorial", "nota": 5, "pessoas": ""},
        {"inicio": 900, "fim": 950, "titulo": "Resposta do aluno", "gancho": "x", "destaque": "x", "motivo": "prova", "tema": "áudio", "tipo": "resposta", "nota": 3, "pessoas": "aluno João"}]}, ensure_ascii=False))
    (api.SAIDA / slug / "palavras.json").write_text("{}")
    r = c.get(f"/api/gs/conversas/{cid}/cortes"); j = r.json()
    check(r.status_code == 200 and j["pronto"] and len(j["cortes"]) == 2 and j["cortes"][1]["id"] == "c02" and j["cortes"][0]["duracao"] == 44.5, "cortes listados com id e duração")

    # 4. Editar os escolhidos → uma issue por corte, com extrair_trecho, gancho e regras de call quando há pessoas
    r = c.post(f"/api/gs/conversas/{cid}/cortes/editar", data={"ids": "c01,c02"}); j = r.json()
    check(r.status_code == 200 and len(j["criados"]) == 2 and set(j["editados"]) == {"c01", "c02"}, f"dois pedidos de edição criados ({r.status_code} {r.text[:80]})")
    d1 = criadas[-2]["description"]; d2 = criadas[-1]["description"]
    check("extrair_trecho" in d1 and "de 120.5 s a 165.0 s" in d1 and "Seu microfone está no lugar errado" in d1 and f"saida/{slug}/palavras.json" in d1 and "reels-padrao" in d1, "pedido do corte cita trecho, gancho, palavras e fluxo")
    check("aluno João" in d2 and "regras de call" in d2, "corte com pessoas recebe regras de call")
    check(criadas[-2]["title"].startswith("Corte c01:"), "título do pedido do corte")
    check(c.get(f"/api/gs/conversas/{cid}/cortes").json()["cortes"][0]["editado"]["codigo"] == "GRA-2", "estado editado gravado por corte")
    r = c.post(f"/api/gs/conversas/{cid}/cortes/editar", data={"ids": "c01"}); check(r.status_code == 200 and r.json()["criados"] == [], "corte já editado não cria de novo")

    # 5. Link: cria referência (download em segundo plano) e aponta a origem para ela
    r = c.post("/api/gs/clipes", data={"nota": "aula no YouTube https://www.youtube.com/watch?v=abc", "tipo_origem": "youtube"})
    check(r.status_code == 200 and "referencias/" in criadas[-1]["description"] and "pode estar baixando" in criadas[-1]["description"], f"link vira referência e issue ({r.status_code})")
    # 6. Referência existente sem vídeo → 400; nada → 400; tipo inválido vira outro
    (api.REFERENCIAS / "ref-x").mkdir(); (api.REFERENCIAS / "ref-x" / "referencia.json").write_text(json.dumps({"id": "ref-x", "criado": "2026", "video": None, "titulo": "t", "pedidos": []}))
    check(c.post("/api/gs/clipes", data={"referencia": "ref-x"}).status_code == 400, "referência sem vídeo dá 400")
    check(c.post("/api/gs/clipes", data={"nota": "nada"}).status_code == 400, "sem vídeo nem link dá 400")
    r = c.post("/api/gs/clipes", data={"tipo_origem": "zzz"}, files=[("arquivos", ("call.mp4", b"\x00" * 10, "video/mp4"))])
    check(r.status_code == 200 and "origem: outro" in criadas[-1]["description"], "tipo inválido vira outro")
    # 7. Texto do pedido de call avisa das regras
    t = clp.pedido_editar("entrada/x.mp4", None, {"id": "c01", "inicio": 1, "fim": 2, "titulo": "t", "gancho": "g", "destaque": "g"}, "call")
    check("regras de call" in t, "pedido de call cita as regras")
    # 8. cortes.json do fluxo de Reels (silêncios removidos, sem lista "cortes") não é proposta do Clipador
    pr = Path(tempfile.mkdtemp()); (pr / "cortes.json").write_text(json.dumps({"trechos": [[0, 1]], "duracao": 3}))
    check(clp.ler_cortes(pr) is None, "cortes.json de Reels é ignorado (sem KeyError)")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
