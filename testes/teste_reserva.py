"""Testes isolados da reserva automática: pedido travado (blocked) passa para o próximo modelo da lista do fluxo e depois para o padrão;
limite de trocas; comentário com o motivo; linha de estilo por tema no pedido. Paperclip por dublê; índice em pasta temporária."""
import asyncio, json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"; api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"
    api.ENTRADA.mkdir(); api.SAIDA.mkdir()
    api.CFG["agent_id"] = "ag-opus"; api.CFG["agent_fable_id"] = "ag-fable"; api.CFG["agent_codex_id"] = "ag-codex"; api.CFG["agent_gemini_id"] = "ag-gemini"
    api.CFG["modelos"] = {}; api.MODELOS.clear(); api.MODELOS.update(api._modelos_de(api.CFG))  # mapa base (o config real pode pôr o Fable como padrão)
    api.CFG["fluxo_modelo"] = {"traduzir-legenda": ["codex", "gemini"]}; api.CFG["reserva_max"] = 2; api.CFG["reserva_automatica"] = True; api.CFG["ocultar_issues"] = []
    issues = [{"id": "i1", "identifier": "GRA-1", "title": "Traduzir", "status": "blocked", "assigneeAgentId": "ag-gemini", "updatedAt": "2026-10-31T01:00:00Z"},
              {"id": "i2", "identifier": "GRA-2", "title": "Reels", "status": "blocked", "assigneeAgentId": "ag-opus", "updatedAt": "2026-10-31T01:00:00Z"},
              {"id": "i3", "identifier": "GRA-3", "title": "Em andamento", "status": "in_progress", "assigneeAgentId": "ag-codex", "updatedAt": "2026-10-31T01:00:00Z"},
              {"id": "i4", "identifier": "GRA-4", "title": "Sem índice", "status": "blocked", "assigneeAgentId": "ag-codex", "updatedAt": "2026-10-31T01:00:00Z"},
              {"id": "i5", "identifier": "GRA-5", "title": "Rodando", "status": "blocked", "assigneeAgentId": "ag-codex", "updatedAt": "2026-10-31T01:00:00Z"},
              {"id": "i6", "identifier": "GRA-6", "title": "Entregue", "status": "blocked", "assigneeAgentId": "ag-codex", "updatedAt": "2026-10-31T01:00:00Z"},
              {"id": "i7", "identifier": "GRA-7", "title": "Recente", "status": "blocked", "assigneeAgentId": "ag-codex", "updatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}]
    comentarios = {"i1": [{"authorAgentId": "ag-gemini", "body": "## Resumo\nNão consegui concluir.\nAções negadas pelo modo sem terminal: ReadFile\nFerramentas chamadas: read_file(x)", "createdAt": "2026-10-31T01:00:01Z"},
                          {"authorAgentId": "ag-gemini", "body": "Paperclip exhausted the bounded original-owner disposition repair", "createdAt": "2026-10-31T01:00:02Z"}]}
    runs = {"i1": [{"status": "succeeded", "createdAt": "2026-10-31T01:00:00Z", "finishedAt": "2026-10-31T01:00:30Z", "error": None, "retryExhaustedReason": "unchanged_source_state_exhausted"}],
            "i5": [{"status": "running", "createdAt": "2026-10-31T01:00:00Z"}], "i6": [{"status": "succeeded", "finishedAt": "2026-10-31T01:00:30Z"}]}
    comentarios["i6"] = [{"authorAgentId": "ag-codex", "body": "## Resumo\nEntreguei tudo.\n## Arquivos\nfinal.mp4", "createdAt": "2026-10-31T01:00:40Z"}]
    posts, patches = [], []
    async def pc_falso(metodo, url, **kw):
        if url.endswith("/issues") and metodo == "GET":
            return issues
        if metodo == "GET" and url.startswith("/api/issues/") and url.count("/") == 3:
            return next(i for i in issues if i["id"] == url.split("/")[-1])
        if url.endswith("/runs"):
            return runs.get(url.split("/")[-2], [])
        if url.endswith("/comments") and metodo == "GET":
            return comentarios.get(url.split("/")[-2], [])
        if url.endswith("/comments") and metodo == "POST":
            posts.append((url.split("/")[-2], kw["json"]["body"])); return {"id": "c"}
        if metodo == "PATCH":
            patches.append((url.split("/")[-1], kw["json"]))
            for i in issues:
                if i["id"] == url.split("/")[-1]:
                    i.update(kw["json"])
            return {}
        if metodo == "POST" and url.endswith("/issues"):
            return {"id": "novo", "identifier": "GRA-9", **kw["json"]}
        return []
    api._pc = pc_falso
    api.INDICE.write_text(json.dumps({"i1": {"slug": "s1", "fluxo": "traduzir-legenda"}, "i2": {"slug": "s2", "fluxo": "reels-padrao"}, "i3": {"slug": "s3", "fluxo": "traduzir-legenda"},
                                      "i5": {"slug": "s5", "fluxo": "traduzir-legenda"}, "i6": {"slug": "s6", "fluxo": "traduzir-legenda"}, "i7": {"slug": "s7", "fluxo": "traduzir-legenda"}}))

    # próximo modelo
    check(api._proximo_modelo("gemini", "traduzir-legenda", ["gemini"]) == "codex" and api._proximo_modelo("codex", "traduzir-legenda", ["codex"]) == "gemini", "próximo modelo segue a lista do fluxo pulando o atual")
    check(api._proximo_modelo("codex", "traduzir-legenda", ["gemini", "codex"]) == "padrao" and api._proximo_modelo("padrao", "reels-padrao", ["padrao"]) is None, "depois da lista vem o padrão; o padrão não tem reserva")
    api.CFG["agent_gemini_id"] = None
    check(api._proximo_modelo("codex", "traduzir-legenda", ["codex"]) == "padrao", "modelo sem agente é pulado")
    api.CFG["agent_gemini_id"] = "ag-gemini"

    # rodada 1: i1 (gemini, blocked) → codex; i2 (opus) fica; i3 em andamento fica; i4 sem índice fica
    trocas = asyncio.run(api.reservar_travados())
    check([t["codigo"] for t in trocas] == ["GRA-1"] and trocas[0]["de"] == "gemini" and trocas[0]["para"] == "codex", f"só o pedido travado com índice e reserva disponível troca; execução ativa, entrega recente ou trava nova ficam ({[t['codigo'] for t in trocas]})")
    check(patches == [("i1", {"status": "todo", "assigneeAgentId": "ag-codex"})], f"issue reaberta para o agente de reserva ({patches})")
    check(len(posts) == 1 and posts[0][0] == "i1" and "Gemini (Antigravity)" in posts[0][1] and "Codex (ChatGPT)" in posts[0][1] and "unchanged_source_state_exhausted" in posts[0][1] and "Não consegui concluir" in posts[0][1] and "## Resumo" not in posts[0][1] and "Paperclip exhausted" not in posts[0][1], f"comentário diz de quem para quem e o motivo ({posts[0][1][:160]})")
    idx = json.loads(api.INDICE.read_text())
    check(idx["i1"]["reservas"][0]["de"] == "gemini" and idx["i1"]["reservas"][0]["para"] == "codex" and "motivo" in idx["i1"]["reservas"][0], "troca registrada no índice")
    # rodada 2: codex também trava → padrão
    issues[0]["status"] = "blocked"; trocas = asyncio.run(api.reservar_travados())
    check(trocas and trocas[0]["para"] == "padrao" and patches[-1] == ("i1", {"status": "todo", "assigneeAgentId": "ag-opus"}), f"segunda troca cai no padrão ({trocas})")
    # rodada 3: limite de 2 trocas
    issues[0]["status"] = "blocked"; n = len(patches); trocas = asyncio.run(api.reservar_travados())
    check(trocas == [] and len(patches) == n, "depois de reserva_max trocas o pedido fica travado para o Raphael decidir")
    # desligada
    api.CFG["reserva_automatica"] = False; issues[0]["status"] = "blocked"; idx = json.loads(api.INDICE.read_text()); idx["i1"]["reservas"] = []; api.INDICE.write_text(json.dumps(idx))
    check(asyncio.run(api.reservar_travados()) == [], "reserva_automatica=false não troca nada"); api.CFG["reserva_automatica"] = True
    # conversa expõe reservas; mensagem reabre pedido travado
    c = TestClient(api.app)
    issues[0]["status"] = "blocked"; idx["i1"]["reservas"] = [{"de": "gemini", "para": "codex", "quando": "x", "motivo": "m"}]; api.INDICE.write_text(json.dumps(idx))
    por = {x["codigo"]: x for x in c.get("/api/gs/conversas").json()}
    check(por["GRA-1"]["reservas"][0]["para"] == "codex" and por["GRA-2"]["reservas"] == [], "lista de conversas traz as reservas de cada pedido")
    r = c.post("/api/gs/conversas/i1/mensagens", data={"texto": "tenta de novo"})
    check(r.status_code == 200 and patches[-1][0] == "i1" and patches[-1][1]["status"] == "todo", "mensagem numa conversa travada reabre o pedido")
    r = c.post("/api/gs/reserva"); check(r.status_code == 200 and "trocas" in r.json(), "rota manual da reserva responde")

    # divisão de agentes (11/11/2026): config real → padrão Opus, Sonnet para modelo pronto, Codex para pesquisa
    real = json.loads((RAIZ / "servico" / "config.json").read_text(encoding="utf-8"))
    mr = api._modelos_de(real); fm = real["fluxo_modelo"]
    check(mr["padrao"]["chave"] == "agent_id" and mr["sonnet"]["chave"] == "agent_sonnet_id" and real.get("agent_sonnet_id") and mr["fable"]["chave"] == "agent_fable_alto_id", "config: padrão é o Opus (agent_id), Sonnet e Fable configurados")
    sonnet = next(a for a in real["executor"]["agentes"] if a["id"] == real["agent_sonnet_id"])
    check(sonnet["motor"] == "claude" and sonnet["modelo"].startswith("claude-sonnet") and sonnet.get("effort") == "medium", f"config: agente Sonnet no executor ({sonnet})")
    check(all(fm[f] == ["codex", "padrao"] for f in ("pesquisa-skills", "reproduzir-skill")) and all(fm[f] == ["sonnet", "padrao"] for f in ("stories-serie", "reel-reciclado")) and fm["traduzir-legenda"] == ["codex", "gemini"], f"config: fluxo_modelo novo ({fm})")
    salvo = (dict(api.CFG), dict(api.MODELOS))
    api.CFG.update({"agent_id": "ag-opus", "agent_sonnet_id": "ag-sonnet", "agent_codex_id": "ag-codex", "agent_gemini_id": None, "agent_fable_alto_id": "ag-fable-alto", "agent_fable_id": "ag-fable", "modelos": real["modelos"], "fluxo_modelo": fm, "reserva_max": 2})
    api.MODELOS.clear(); api.MODELOS.update(api._modelos_de(api.CFG))
    check(api._modelo_padrao_do_fluxo("stories-serie") == "sonnet" and api._modelo_padrao_do_fluxo("pesquisa-skills") == "codex" and api._modelo_padrao_do_fluxo("reels-padrao") == "padrao" and api._modelo_padrao_do_fluxo("traduzir-legenda") == "codex", "roteamento: stories → Sonnet, pesquisa → Codex, reels → padrão (Opus)")
    check(api._agente_do_modelo("padrao") == "ag-opus" and api._modelo_pedido_no_texto("usa o Sonnet nesse") == "sonnet", "padrão é o agente do Opus; 'usa o Sonnet' troca")
    check(api._proximo_modelo("padrao", "reels-padrao", ["padrao"]) is None and api._proximo_modelo("fable", "pesquisa-skills", ["fable"]) == "codex", "'opus' e 'padrao' são o mesmo agente: não vira reserva de si mesmo")
    # troca imediata por limite de uso (gancho do executor): codex → padrão → bloqueia
    api.INDICE.write_text(json.dumps({"L1": {"slug": "l1", "fluxo": "pesquisa-skills"}, "L2": {"slug": "l2", "fluxo": "stories-serie"}}))
    t1 = api._trocar_por_limite({"id": "L1", "identifier": "GRA-L1"}, {"id": "ag-codex"}, "You've hit your usage limit")
    idx = json.loads(api.INDICE.read_text())
    check(t1 == "ag-opus" and idx["L1"]["reservas"][0]["de"] == "codex" and idx["L1"]["reservas"][0]["para"] == "padrao" and idx["L1"]["reservas"][0]["imediata"] and "usage limit" in idx["L1"]["reservas"][0]["motivo"], f"limite no Codex: troca já para o Opus e registra ({idx['L1']})")
    check(api._trocar_por_limite({"id": "L1"}, {"id": "ag-opus"}, "session limit") is None, "limite também no Opus: sem próximo (todos tentados), sem laço")
    check(api._trocar_por_limite({"id": "L2"}, {"id": "ag-sonnet"}, "session limit") == "ag-opus" and api._trocar_por_limite({"id": "L2"}, {"id": "ag-opus"}, "session limit") is None, "stories: Sonnet → Opus e para")
    check(api._trocar_por_limite({"id": "sem-indice"}, {"id": "ag-opus"}, "x") is None, "pedido sem índice não troca")
    api.CFG.clear(); api.CFG.update(salvo[0]); api.MODELOS.clear(); api.MODELOS.update(salvo[1])

    # linha de estilo por tema no pedido
    check(api._linha_estilo("padrao").startswith("Estilo: `padrao`") and "Desligado neste estilo" in api._linha_estilo("padrao") and "zoom" in api._linha_estilo("padrao"), "13/11: linha do padrao diz o que ele desliga")
    lt = api._linha_estilo("tutorial")
    check("tutorial" in lt and "terco_inferior" in lt and "jcut_s" in lt and "estilos/tutorial.json" in lt and "zoom" in lt.split("Desligado neste estilo")[1].split("Ligado:")[0], f"estilo por tema explica o que ligar e desligar ({lt[:120]}…)")
    check(api._linha_estilo("inexistente") == "Estilo de legenda: `inexistente`.", "estilo sem arquivo não quebra")
    c.post("/api/gs/conversas", data={"pedido": "Vídeo do zero", "fluxo": "video-locucao", "estilo": "tutorial"})
    idx = json.loads(api.INDICE.read_text())
    check(idx["novo"]["fluxo"] == "video-locucao" and idx["novo"]["estilo"] == "tutorial" and idx["novo"]["modelo"] == "padrao", f"índice guarda fluxo, estilo e modelo do pedido ({idx['novo']})")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
