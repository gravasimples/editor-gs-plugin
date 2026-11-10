"""Testes isolados: pastas (projetos) de pedidos e fichas de marca. Paperclip por dublê, índice/pastas/entrada em pasta temporária,
GSI falso (contexto/ e gs.db mínimos). Nunca toca servico/conversas.json, servico/pastas.json nem workspace/."""
import json, sqlite3, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, marca

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"; api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"; api.MARCA_DIR = tmp / "marca"
    api.ENTRADA.mkdir(); api.SAIDA.mkdir()
    issues = [{"id": "i1", "identifier": "GRA-21", "title": "Webcam", "description": "<!-- gs-slug: s1 -->", "status": "done", "updatedAt": "2026-10-29T10:00:00Z"},
              {"id": "i2", "identifier": "GRA-22", "title": "Áudio", "description": "x", "status": "todo", "updatedAt": "2026-10-29T11:00:00Z"},
              {"id": "i3", "identifier": "GRA-23", "title": "Onboarding", "description": "sem índice", "status": "in_review", "updatedAt": "2026-10-29T12:00:00Z"}]
    criadas = []
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            criadas.append(kw["json"]); return {"id": f"novo-{len(criadas)}", "identifier": f"GRA-{10 + len(criadas)}", **kw["json"]}
        if url.endswith("/issues"):
            return issues
        return []
    api._pc = pc_falso
    class _Resp:
        def __init__(self, j): self._j = j
        def json(self): return self._j
    class _PCFalso:  # /api/health do Paperclip (rota /api/gs/estado e /api/gs/operacao): dublê, nunca a instância real
        async def get(self, url, **kw): return _Resp({"status": "ok", "version": "teste"})
    api.PC = _PCFalso()
    api.INDICE.write_text(json.dumps({"i1": {"slug": "s1", "pasta": "Black 2026"}, "i2": {"slug": "s2"}}))
    c = TestClient(api.app)

    # listagem
    r = c.get("/api/gs/pastas"); j = r.json()
    check(r.status_code == 200 and j["pastas"] == [{"nome": "Black 2026", "criada": None, "n": 1}] and j["sem_pasta"] == 1, "pastas vindas só do índice aparecem com contagem")
    r = c.get("/api/gs/conversas"); por = {x["codigo"]: x for x in r.json()}
    check(por["GRA-21"]["pasta"] == "Black 2026" and por["GRA-22"]["pasta"] is None and por["GRA-23"]["pasta"] is None, "conversas trazem o campo pasta (None sem pasta ou sem índice)")

    # modelo por pedido: chip (modelo=fable), texto ("usa o Fable") ou padrão
    api.CFG["agent_id"] = "ag-opus"; api.CFG["agent_fable_id"] = "ag-fable"
    api.CFG["modelos"] = {}; api.MODELOS.clear(); api.MODELOS.update(api._modelos_de(api.CFG))  # mapa base (o config real pode pôr o Fable como padrão)
    c.post("/api/gs/conversas", data={"pedido": "Edite este vídeo", "modelo": "fable"}); c.post("/api/gs/conversas", data={"pedido": "Edite este vídeo e usa o Fable nessa edição"}); c.post("/api/gs/conversas", data={"pedido": "Edite este vídeo"})
    check([x["assigneeAgentId"] for x in criadas[-3:]] == ["ag-fable", "ag-fable", "ag-opus"], f"pedido vai para o agente do modelo escolhido ({[x['assigneeAgentId'] for x in criadas[-3:]]})")
    por = {x["codigo"]: x for x in c.get("/api/gs/conversas").json()}
    check(api._modelo_pedido_no_texto("volta para o opus") == "padrao" and api._modelo_pedido_no_texto("faz o corte") is None and api._modelo_pedido_no_texto("usa o Codex aqui") == "codex", "troca de modelo lida do texto")
    # roteamento por fluxo: fluxo mecânico vai para o Codex só se o agente existir; chip "padrao" explícito respeita o padrão; chip fable vence o fluxo
    api.CFG["agent_codex_id"] = None; api.CFG["fluxo_modelo"] = {"traduzir-legenda": "codex"}
    c.post("/api/gs/conversas", data={"pedido": "Traduza", "fluxo": "traduzir-legenda"}); sem = criadas[-1]["assigneeAgentId"]
    api.CFG["agent_codex_id"] = "ag-codex"
    c.post("/api/gs/conversas", data={"pedido": "Traduza", "fluxo": "traduzir-legenda"}); com = criadas[-1]["assigneeAgentId"]
    c.post("/api/gs/conversas", data={"pedido": "Traduza", "fluxo": "traduzir-legenda", "modelo": "padrao"}); forcado = criadas[-1]["assigneeAgentId"]
    c.post("/api/gs/conversas", data={"pedido": "Traduza", "fluxo": "traduzir-legenda", "modelo": "fable"}); fab = criadas[-1]["assigneeAgentId"]
    check((sem, com, forcado, fab) == ("ag-opus", "ag-codex", "ag-opus", "ag-fable"), f"roteamento por fluxo com e sem agente Codex, chip vence ({sem}, {com}, {forcado}, {fab})")
    api.CFG["agent_codex_id"] = None; api.CFG["agent_gemini_id"] = "ag-gemini"; api.CFG["fluxo_modelo"] = {"apostila": ["codex", "gemini"], "dublagem": ["codex"]}
    check(api._modelo_padrao_do_fluxo("apostila") == "gemini" and api._modelo_padrao_do_fluxo("dublagem") == "padrao" and api._modelo_pedido_no_texto("usa o Gemini nisso") == "gemini", "lista de preferência por fluxo: cai no Gemini quando o Codex não existe; 'usa o Gemini' no texto")
    api.CFG["agent_gemini_id"] = None
    api.CFG["fluxo_modelo"] = {}; api.CFG["agent_codex_id"] = None
    est = c.get("/api/gs/estado").json(); disp = {m["id"]: m["disponivel"] for m in est.get("modelos", [])}
    check(list(disp) == ["padrao", "fable", "codex", "gemini", "thiago"] and disp["padrao"] and disp["fable"] and not disp["codex"], f"estado lista os modelos e diz qual está configurado ({est.get('modelos')})")
    api.CFG["agent_fable_id"] = None
    check(c.post("/api/gs/conversas", data={"pedido": "x", "modelo": "fable"}).status_code == 503, "sem agente Fable configurado, pedir Fable dá 503")
    api.CFG["agent_fable_id"] = "ag-fable"
    # mensagem na conversa troca o agente (PATCH) quando pede outro modelo
    patches = []; coments = []
    issue_f = {"id": "i9", "identifier": "GRA-99", "title": "x", "description": "<!-- gs-slug: s9 -->", "status": "done", "assigneeAgentId": "ag-opus"}
    async def pc2(metodo, url, **kw):
        if metodo == "PATCH": patches.append(kw["json"]); return {}
        if url.endswith("/comments") and metodo == "POST": coments.append(kw["json"]["body"]); return {}
        if url.endswith("/issues/i9"): return issue_f
        return await pc_falso(metodo, url, **kw)
    api._pc = pc2
    r = c.post("/api/gs/conversas/i9/mensagens", data={"texto": "Refaz com o Fable, mais robusto"}).json()
    check(r["trocou"] and r["modelo"]["id"] == "fable" and patches[-1] == {"status": "todo", "assigneeAgentId": "ag-fable"} and "Fable 5.1" in coments[-1], "mensagem 'refaz com o Fable' reatribui a issue ao agente Fable")
    r = c.post("/api/gs/conversas/i9/mensagens", data={"texto": "Ficou bom."}).json()
    check(not r["trocou"] and patches[-1] == {"status": "todo", "assigneeAgentId": "ag-opus"}, "mensagem comum reabre para o mesmo agente")
    r = c.post("/api/gs/conversas/i9/mensagens", data={"texto": "continua", "modelo": "padrao"}).json()
    check(not r["trocou"], "pedir o modelo que já está em uso não conta como troca")
    # anexos numa conversa existente (take do "Gravo eu mesmo", arquivo para uma cena)
    r = c.post("/api/gs/conversas/i9/mensagens", data={"texto": "Aqui está o take, edite."}, files=[("arquivos", ("take 1.mp4", b"0" * 2048, "video/mp4")), ("arquivos", ("print.png", b"\x89PNG", "image/png"))])
    slug_i9 = json.loads(api.INDICE.read_text()).get("i9", {}).get("slug")
    check(r.status_code == 200 and slug_i9 and (api.ENTRADA / slug_i9 / "take_1.mp4").exists() and (api.ENTRADA / slug_i9 / "print.png").exists(), f"anexos gravados em entrada/<slug>/ e slug no índice ({slug_i9})")
    check("Aqui está o take" in coments[-1] and f"`entrada/{slug_i9}/take_1.mp4`" in coments[-1] and "print.png" in coments[-1], "mensagem lista os anexos para o agente")
    r = c.post("/api/gs/conversas/i9/mensagens", data={"texto": ""}, files=[("arquivos", ("so-arquivo.mp4", b"1" * 100, "video/mp4"))])
    check(r.status_code == 200 and coments[-1].startswith("Arquivos anexados agora:"), "só anexo, sem texto, também vale")
    check(c.post("/api/gs/conversas/i9/mensagens", data={"texto": "  "}).status_code == 400, "sem texto e sem anexo dá 400")
    api._pc = pc_falso
    class _Resp:
        def __init__(self, j): self._j = j
        def json(self): return self._j
    class _PCFalso:  # /api/health do Paperclip (rota /api/gs/estado e /api/gs/operacao): dublê, nunca a instância real
        async def get(self, url, **kw): return _Resp({"status": "ok", "version": "teste"})
    api.PC = _PCFalso()

    # criar / repetida / vazia
    r = c.post("/api/gs/pastas", data={"nome": "  Semana   44 "}); check(r.status_code == 200 and r.json()["nome"] == "Semana 44", "criar pasta normaliza espaços")
    check(c.post("/api/gs/pastas", data={"nome": "semana 44"}).status_code == 409, "pasta repetida (sem diferenciar maiúsculas) dá 409")
    check(c.post("/api/gs/pastas", data={"nome": "   "}).status_code == 400, "nome vazio dá 400")
    check(json.loads(api.PASTAS.read_text())[0]["nome"] == "Semana 44", "pasta gravada em pastas.json")
    j = c.get("/api/gs/pastas").json(); check([p["nome"] for p in j["pastas"]] == ["Black 2026", "Semana 44"] and j["pastas"][1]["n"] == 0, "listagem ordena por uso e inclui pasta vazia")

    # mover pedido (inclusive um que não estava no índice) e tirar da pasta
    r = c.post("/api/gs/conversas/i3/pasta", data={"pasta": "semana 44"}); check(r.status_code == 200 and r.json()["pasta"] == "Semana 44", "mover pedido sem índice usa o nome canônico da pasta")
    check(json.loads(api.INDICE.read_text())["i3"] == {"pasta": "Semana 44"}, "índice ganhou a entrada só com a pasta (slug continua vindo da descrição)")
    r = c.post("/api/gs/conversas/i2/pasta", data={"pasta": "Clientes"}); check(r.json()["pasta"] == "Clientes" and any(p["nome"] == "Clientes" for p in json.loads(api.PASTAS.read_text())), "mover para pasta nova cria a pasta")
    r = c.post("/api/gs/conversas/i2/pasta", data={"pasta": ""}); check(r.json()["pasta"] is None and "pasta" not in json.loads(api.INDICE.read_text())["i2"], "pasta vazia tira o pedido da pasta")
    check(c.post("/api/gs/conversas/abc%20def/pasta", data={"pasta": "a"}).status_code == 400, "id inválido é recusado")

    # renomear e apagar
    r = c.post("/api/gs/pastas/Semana 44/renomear", data={"novo": "Semana 45"}); check(r.status_code == 200 and r.json()["movidas"] == 1 and json.loads(api.INDICE.read_text())["i3"]["pasta"] == "Semana 45", "renomear muda a pasta e os pedidos dela")
    check(c.post("/api/gs/pastas/Semana 45/renomear", data={"novo": "clientes"}).status_code == 409, "renomear para nome existente dá 409")
    check(c.post("/api/gs/pastas/Nada/renomear", data={"novo": "x"}).status_code == 404, "renomear pasta inexistente dá 404")
    r = c.delete("/api/gs/pastas/Semana 45"); check(r.status_code == 200 and r.json()["liberadas"] == 1 and "pasta" not in json.loads(api.INDICE.read_text())["i3"], "apagar pasta libera os pedidos (nada mais é apagado)")
    check(c.delete("/api/gs/pastas/Semana 45").status_code == 404, "apagar de novo dá 404")

    # novo pedido: pasta escolhida e pasta por origem (pulso → Pulso do GSI)
    r = c.post("/api/gs/conversas", data={"pedido": "Carrossel da Black", "pasta": "black 2026"}); check(r.status_code == 200 and r.json()["pasta"] == "Black 2026", "novo pedido entra na pasta escolhida (nome canônico)")
    r = c.post("/api/gs/conversas", data={"pedido": "Vindo do pulso", "origem": "pulso"}); check(r.json()["pasta"] == "Pulso do GSI", "pedido do pulso vai para a pasta Pulso do GSI")
    r = c.post("/api/gs/conversas", data={"pedido": "Sem pasta"}); check(r.json()["pasta"] is None, "pedido do app sem pasta fica sem pasta")
    check(any(p["nome"] == "Pulso do GSI" for p in c.get("/api/gs/pastas").json()["pastas"]), "pasta por origem foi criada")

    # ---- marca: GSI falso ----
    gsi = tmp / "gsi"; (gsi / "contexto").mkdir(parents=True); (gsi / "dados").mkdir()
    (gsi / "contexto" / "manual-marca-grava-simples.md").write_text("# Manual\n\nIntro do manual.\n\n## Voz e roteiro\n\nFrases curtas.\n\n## Identidade visual\n\n- Marinho #000921\n- Laranja #F79615\n", encoding="utf-8")
    (gsi / "contexto" / "tom-de-voz.md").write_text("# Tom\n\n## Voz\n\n| Objetivo | Tom |\n|---|---|\n| Educar | prático |\n", encoding="utf-8")
    db = gsi / "dados" / "gs.db"; con = sqlite3.connect(db)
    con.executescript("""CREATE TABLE products (product_slug TEXT PRIMARY KEY, name TEXT, aliases_json TEXT, category TEXT, components_json TEXT, audience TEXT, problem TEXT, promise TEXT, deliverables_json TEXT, hotmart_ucode TEXT, status TEXT, confidence REAL, source TEXT, source_ref TEXT, pending_fields_json TEXT, captured_at TEXT, updated_at TEXT, notes TEXT);
    CREATE TABLE offers (offer_id TEXT PRIMARY KEY, product_slug TEXT, name TEXT, price REAL, currency TEXT, installments INTEGER, installment_value REAL, access_period TEXT, sales_url TEXT, checkout_domain TEXT, observed_on TEXT, valid_from TEXT, valid_to TEXT, hotmart_offer_code TEXT, status TEXT, confidence REAL, source TEXT, source_ref TEXT, notes TEXT);
    INSERT INTO products VALUES ('descomplica-obs','Descomplica OBS','["OBS para infoprodutores"]','course',NULL,'Infoprodutores','OBS difícil','Presets prontos','["presets"]',NULL,'observed',0.9,'site',NULL,'["número de alunos"]','2026-09-30','2026-09-30',NULL);
    INSERT INTO products VALUES ('executa','Executa',NULL,'program',NULL,NULL,NULL,NULL,NULL,NULL,'pending_validation',0.5,'notion',NULL,NULL,'2026-09-30','2026-09-30',NULL);
    INSERT INTO offers VALUES ('obs-197','descomplica-obs','Página',197.0,'BRL',12,19.66,'12 meses','https://x','x','2026-09-30',NULL,NULL,NULL,'observed',0.95,'site',NULL,NULL);"""); con.commit(); con.close()
    api.GSI_RAIZ = gsi; api.GSI_DB = db

    r = c.get("/api/gs/marca"); j = r.json()
    check(r.status_code == 200 and j["manual"]["existe"] and [s["titulo"] for s in j["manual"]["secoes"]] == ["Introdução", "Voz e roteiro", "Identidade visual"], "manual dividido em seções (intro + ##)")
    check(j["voz"]["secoes"][0]["conteudo"].startswith("| Objetivo"), "tom de voz lido com a tabela")
    check(j["produtos_md"]["existe"] is False, "arquivo ausente vira existe=false sem erro")
    p = {x["slug"]: x for x in j["produtos"]["itens"]}
    check(p["descomplica-obs"]["ofertas"][0]["preco"] == 197.0 and p["descomplica-obs"]["ofertas"][0]["visto_em"] == "2026-09-30" and p["descomplica-obs"]["pendencias"] == ["número de alunos"], "produto traz ofertas com data e pendências")
    check(p["executa"]["status"] == "pending_validation" and "NÃO são claims" in j["produtos"]["aviso"], "estado pendente e aviso de claims presentes")
    check(not api.MARCA_DIR.exists(), "GET sem gravar não escreve a cópia")
    r = c.get("/api/gs/marca?gravar=1"); j = r.json()
    check(r.status_code == 200 and sorted(j["arquivos"]) == ["manual.md", "produtos.md", "voz.md"], "gravar=1 escreve manual.md, voz.md e produtos.md")
    prod = (api.MARCA_DIR / "produtos.md").read_text(encoding="utf-8")
    check("PENDENTE DE VALIDAÇÃO" in prod and "R$ 197,00 ou 12× R$ 19,66" in prod and "visto em 2026-09-30" in prod and "Pendências (não afirmar): número de alunos" in prod, "produtos.md marca estado, preço com data e pendências")
    check((api.MARCA_DIR / "manual.md").read_text(encoding="utf-8").startswith("<!-- Cópia só leitura"), "cópia do manual avisa que é só leitura")
    api.GSI_DB = gsi / "nao-existe.db"
    j = c.get("/api/gs/marca").json(); check("erro" in j["produtos"] and j["produtos"]["itens"] == [] and j["manual"]["existe"], "sem gs.db: produtos com erro, manual continua")
    check(marca._secoes("só um parágrafo\n") == [{"titulo": "Introdução", "conteudo": "só um parágrafo"}], "_secoes sem ## devolve só a introdução")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
