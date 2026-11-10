"""Testes isolados: entregas em texto na mensagem final (servico/textos.py + rotas). Paperclip por dublê; cache, referências e saída em pasta temporária.
Nunca toca servico/textos.json, workspace/referencias nem workspace/saida."""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, textos as txt

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

MSG = """Pronto. Dois formatos em `saida/x/`.

## Resumo
Cortei 358 s para 112 s: 14 pausas e 3 refações.

## Legenda do post
Webcam travada no OBS? Olha só o que resolve.

Segue pra mais.

## Hashtags
#obs #gravasimples #webcam

## Título (YouTube)
Webcam travada no OBS: o ajuste que resolve

## Gancho
Sua webcam trava no OBS?

## Pendências
- [CONFERIR] o nome do driver.

## Arquivos
final_9x16.mp4, final_16x9.mp4, capa.png
"""

# ---- módulo ----
s = txt.secoes_de(MSG)
check([x["chave"] for x in s] == ["mensagem", "resumo", "descricao", "hashtags", "titulo", "gancho", "pendencias", "arquivos"], f"seções separadas e normalizadas ({[x['chave'] for x in s]})")
check(s[2]["conteudo"] == "Webcam travada no OBS? Olha só o que resolve.\n\nSegue pra mais.", "conteúdo da seção preserva parágrafos")
check(txt.post_de(s) == {"descricao": s[2]["conteudo"], "hashtags": "#obs #gravasimples #webcam", "titulo": "Webcam travada no OBS: o ajuste que resolve", "gancho": "Sua webcam trava no OBS?"}, "post_de monta o que o Publicar precisa")
check(txt.secoes_de("sem títulos\n### sub\n") == [] and txt.secoes_de("") == [], "texto sem ## não tem seções")
d = txt.secoes_de("## Roteiro\na\n## Roteiro\nb\n## Descrição do post\nc")
check([x["chave"] for x in d] == ["roteiro", "roteiro-2", "descricao"], "títulos repetidos ganham sufixo; 'Descrição do post' vira descricao")
check(txt.chave_de("Perguntas que viram conteúdo") == "perguntas-que-viram-conteudo" and txt.chave_de("Para gravar") == "gravar" and txt.chave_de("Análise") == "analise", "chaves derivadas do título")
msgs = [{"id": "1", "autor": "voce", "texto": "## Faz\nx"}, {"id": "2", "autor": "editor", "texto": "Plano: vou cortar."}, {"id": "3", "autor": "editor", "texto": MSG, "quando": "2026-10-30T03:00:00Z"}, {"id": "4", "autor": "editor", "texto": "Feito o ajuste."}]
e = txt.entrega_de_mensagens(msgs)
check(e and e["id"] == "3" and len(e["secoes"]) == 8, "a entrega é a última mensagem do Editor com seções (mensagens do usuário não contam)")
check(txt.entrega_de_mensagens([{"autor": "editor", "texto": "oi"}]) is None, "sem seções não há entrega em texto")

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"
    api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "ref" / "_textos"; api.DIST = tmp / "dist"
    api.ENTRADA.mkdir(); api.SAIDA.mkdir(); (api.SAIDA / "s1").mkdir(); (api.SAIDA / "s2").mkdir()
    (api.SAIDA / "s2" / "post.md").write_text("## Descrição do post\nantiga\n## Hashtags\n#a\n", encoding="utf-8")
    issues = [{"id": "i1", "identifier": "GRA-31", "title": "Webcam", "description": "<!-- gs-slug: s1 -->", "status": "in_review", "updatedAt": "2026-10-30T03:00:00Z"},
              {"id": "i2", "identifier": "GRA-32", "title": "Antiga", "description": "<!-- gs-slug: s2 -->", "status": "done", "updatedAt": "2026-10-29T10:00:00Z"},
              {"id": "i3", "identifier": "GRA-33", "title": "Sem texto", "description": "x", "status": "todo", "updatedAt": "2026-10-29T11:00:00Z"},
              {"id": "i4", "identifier": "GRA-2", "title": "Oculta", "description": "x", "status": "done", "updatedAt": "2026-10-29T11:00:00Z"}]
    comentarios = {"i1": [{"id": "c0", "authorAgentId": "ag", "body": "Primeira versão.\n\n## Roteiro\nVersão antiga do roteiro, só um take.\n\n## Hashtags\n#obs", "createdAt": "2026-10-30T02:00:00Z"},
                          {"id": "c1", "authorAgentId": "ag", "body": MSG, "createdAt": "2026-10-30T03:00:00Z"}], "i2": [{"id": "c2", "authorAgentId": "ag", "body": "Entregue em saida/s2.", "createdAt": "2026-10-29T10:00:00Z"}], "i3": [], "i4": []}
    chamadas = {"comments": 0}
    async def pc_falso(metodo, url, **kw):
        if url.endswith("/issues"): return issues
        if url.endswith("/comments"): chamadas["comments"] += 1; return comentarios[url.split("/")[-2]]
        if url.endswith("/interactions"): return []
        if url.endswith("/agents"): return [{"id": api.CFG["agent_id"], "status": "idle"}]
        for it in issues:
            if url.endswith("/issues/" + it["id"]): return it
        return []
    api._pc = pc_falso
    api.INDICE.write_text(json.dumps({"i1": {"slug": "s1", "pasta": "Semana 44"}, "i2": {"slug": "s2"}}))
    c = TestClient(api.app)

    # conversa: textos e post vindos da mensagem; post.md antigo continua valendo
    r = c.get("/api/gs/conversas/i1"); j = r.json()
    check(r.status_code == 200 and [s["chave"] for s in j["textos"]] == ["mensagem", "resumo", "descricao", "hashtags", "titulo", "gancho", "pendencias", "arquivos"], "conversa traz as seções da mensagem final")
    check(j["post"]["descricao"].startswith("Webcam travada") and j["post_origem"] == "mensagem" and j["relatorio"] is None, "post do Publicar vem da mensagem (sem post.md nem relatorio.md)")
    check(json.loads(api.TEXTOS_CACHE.read_text())["i1"]["secoes"][1]["chave"] == "resumo", "abrir a conversa alimenta o cache de textos")
    j2 = c.get("/api/gs/conversas/i2").json()
    check(j2["post"] == {"descricao": "antiga", "hashtags": "#a"} and j2["post_origem"] == "arquivo" and j2["textos"] == [], "entrega antiga com post.md: post vem do arquivo")

    # lista de textos: só conversas com seções de texto; oculta GRA-2; cache evita refazer chamadas
    r = c.get("/api/gs/textos"); j = r.json(); n0 = chamadas["comments"]
    check(r.status_code == 200 and [x["codigo"] for x in j["itens"]] == ["GRA-31"] and [t["chave"] for t in j["tipos"]][:2] == ["roteiro", "descricao"], "página Textos lista só quem tem texto entregue")
    item = j["itens"][0]
    check([s["chave"] for s in item["secoes"]] == ["resumo", "descricao"] and item["pasta"] == "Semana 44" and item["guardadas"] == [], "só seções de leitura (resumo, legenda) aparecem; pasta vem do índice")
    c.get("/api/gs/textos"); check(chamadas["comments"] == n0, "segunda listagem não busca comentários de novo (cache por updatedAt)")
    issues[2]["updatedAt"] = "2026-10-30T04:00:00Z"; comentarios["i3"] = [{"id": "c3", "authorAgentId": "ag", "body": "## Roteiro\nGancho: olha só.\n\n## Para gravar\n- tela do OBS", "createdAt": "2026-10-30T04:00:00Z"}]
    j = c.get("/api/gs/textos").json(); check([x["codigo"] for x in j["itens"]] == ["GRA-33", "GRA-31"] and chamadas["comments"] == n0 + 1, "issue atualizada é relida e entra ordenada pela data")
    check([x["codigo"] for x in c.get("/api/gs/textos?tipo=roteiro").json()["itens"]] == ["GRA-33"], "filtro por tipo")
    check([x["codigo"] for x in c.get("/api/gs/textos?q=refa%C3%A7%C3%B5es").json()["itens"]] == ["GRA-31"], "busca no conteúdo (sem acento também)")
    check([x["codigo"] for x in c.get("/api/gs/textos?pasta=Semana%2044").json()["itens"]] == ["GRA-31"], "filtro por pasta")
    check("GRA-2" not in json.dumps(json.loads(api.TEXTOS_CACHE.read_text())), "issue oculta não entra no cache")

    # busca geral usa o cache
    r = c.get("/api/gs/busca?q=refa%C3%A7%C3%B5es").json()
    check(len(r) == 1 and r[0]["codigo"] == "GRA-31" and r[0]["onde"] == "resumo", "busca nas conversas encontra a seção da mensagem")

    # guardar como referência (.md só aqui), listar, apagar
    r = c.post("/api/gs/conversas/i1/textos/guardar", data={"chave": "descricao"}); j = r.json()
    check(r.status_code == 200 and j["nome"] == "2026-10-30-gra-31-descricao.md" and (api.TEXTOS_DIR / j["nome"]).exists(), "guardar grava .md em referencias/_textos/")
    md = (api.TEXTOS_DIR / j["nome"]).read_text(encoding="utf-8")
    check(md.startswith("# Webcam — Legenda do post") and "Origem: Editor GS GRA-31" in md and "Tipo: descricao" in md and "Segue pra mais." in md, "arquivo guardado tem título, origem, tipo e o texto")
    check("2026-10-30-gra-31-descricao.md" in (api.TEXTOS_DIR / "INDICE.md").read_text(encoding="utf-8"), "INDICE.md para o Editor é refeito")
    check(c.get("/api/gs/textos").json()["itens"][1]["guardadas"] == ["descricao"], "lista marca a seção como guardada")
    g = c.get("/api/gs/textos/guardados").json()
    check(len(g) == 1 and g[0]["codigo"] == "GRA-31" and g[0]["chave"] == "descricao" and g[0]["titulo"].startswith("Webcam"), "listagem dos guardados")
    check(c.post("/api/gs/conversas/i1/textos/guardar", data={"chave": "nao-existe"}).status_code == 400, "seção inexistente dá 400")
    check(c.post("/api/gs/conversas/i2/textos/guardar", data={"chave": "descricao"}).status_code == 404, "conversa sem entrega em texto dá 404")
    # mensagem antiga (versão anterior da entrega): guardar pelo id do comentário + título da seção
    r = c.post("/api/gs/conversas/i1/textos/guardar", data={"mensagem": "c0", "secao": "Roteiro"}); j = r.json()
    check(r.status_code == 200 and j["chave"] == "roteiro" and j["nome"] == "2026-10-30-gra-31-roteiro.md" and "Versão antiga do roteiro" in (api.TEXTOS_DIR / j["nome"]).read_text(encoding="utf-8"), f"guardar seção de mensagem antiga pelo título ({j})")
    check(c.post("/api/gs/conversas/i1/textos/guardar", data={"mensagem": "c0", "secao": "Legenda do post"}).status_code == 404, "mensagem antiga sem a seção pedida dá 404")
    check(c.post("/api/gs/conversas/i1/textos/guardar", data={"mensagem": "nao", "secao": "Roteiro"}).status_code == 404 and c.post("/api/gs/conversas/i1/textos/guardar", data={}).status_code == 400, "mensagem inexistente dá 404; sem chave nem mensagem dá 400")
    # enviar seção para um cartão existente do Notion (Notion por dublê: GET/PATCH da página e busca de cartões)
    notion = {"paginas": {"abc123": {"id": "abc123", "url": "https://notion.so/abc123", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Webcam travada"}]}, "Roteiro do pulso": {"type": "rich_text", "rich_text": [{"plain_text": "[Pulso] versão antiga"}]}}},
                          "beef01": {"id": "beef01", "url": None, "properties": {"Name": {"type": "title", "title": [{"plain_text": "Outra base"}]}}}}, "patches": []}
    api._notion_get = lambda pid: notion["paginas"].get(pid) or (_ for _ in ()).throw(api.HTTPException(502, "Notion 404"))
    api._notion_patch = lambda pid, props: notion["patches"].append((pid, props)) or {"id": pid}
    api._notion_cartoes = lambda q, limite=20: [{"id": "abc123", "titulo": "Webcam travada", "status": "Ideias", "formato": ["Reels"], "url": "https://notion.so/abc123"}] if "web" in q.lower() else []
    api.NOTION_ESCRITA = True  # 31/10: desligado por decisão; o teste cobre a capacidade
    r = c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Legenda do post", "pagina": "abc123"}); jn = r.json()
    check(r.status_code == 200 and jn["ok"] and jn["titulo"] == "Webcam travada" and jn["secoes"] == ["descricao"] and jn["modo"] == "acrescentar", f"envio da seção ao cartão ({jn})")
    pid, props = notion["patches"][-1]; txt_env = "".join(x["text"]["content"] for x in props["Roteiro do pulso"]["rich_text"])
    check(pid == "abc123" and list(props) == ["Roteiro do pulso"] and txt_env.startswith("[Pulso] versão antiga\n\n[Editor GS GRA-31 · Legenda do post · ") and "Olha só o que resolve" in txt_env, f"acrescenta ao campo sem mexer em Status ({txt_env[:80]!r})")
    rn = c.post("/api/gs/conversas/i1/textos/notion", data={"mensagem": "c0", "secao": "Roteiro", "pagina": "abc-123", "modo": "substituir"}).json()
    txt2 = "".join(x["text"]["content"] for x in notion["patches"][-1][1]["Roteiro do pulso"]["rich_text"])
    check(rn["ok"] and txt2.startswith("[Editor GS GRA-31 · Roteiro") and "versão antiga do roteiro" in txt2.lower() and "[Pulso]" not in txt2, "mensagem antiga + substituir troca o campo inteiro")
    check(c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Resumo"}).status_code == 400, "sem cartão de destino (pedido não veio do Notion) dá 400")
    check(c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Resumo", "pagina": "beef01"}).status_code == 400, "cartão sem o campo Roteiro do pulso dá 400")
    check(c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Resumo", "pagina": "abc123", "modo": "apagar"}).status_code == 400, "modo inválido dá 400")
    check(c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Roteiro", "pagina": "abc123"}).status_code == 400 and c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Resumo", "pagina": "nada"}).status_code == 502, "seção inexistente na entrega dá 400; cartão inexistente devolve o erro do Notion")
    check(len(notion["patches"]) == 2, "nenhuma escrita extra no Notion fora das duas aprovadas")
    g = c.get("/api/gs/notion/cartoes?q=web").json(); check(len(g) == 1 and g[0]["id"] == "abc123" and c.get("/api/gs/notion/cartoes?q=zzz").json() == [], "busca de cartões por título")
    longo = "x" * 4000; api._notion_get = lambda pid: {"id": pid, "url": None, "properties": {"Name": {"type": "title", "title": []}, "Roteiro do pulso": {"type": "rich_text", "rich_text": [{"plain_text": longo}]}}}
    c.post("/api/gs/conversas/i1/textos/notion", data={"secao": "Resumo", "pagina": "abc123"})
    rt = notion["patches"][-1][1]["Roteiro do pulso"]["rich_text"]
    check(len(rt) >= 3 and all(len(x["text"]["content"]) <= 1900 for x in rt), f"texto longo vai em itens de até 1900 caracteres ({len(rt)} itens)")
    r = c.post("/api/gs/conversas/i1/textos/guardar", data={"chave": "tudo"}).json()
    check(r["nome"].endswith("-tudo.md") and "## Resumo" in (api.TEXTOS_DIR / r["nome"]).read_text(encoding="utf-8"), "chave 'tudo' guarda as seções de texto num arquivo só")
    check(c.delete("/api/gs/textos/guardados/INDICE.md").status_code == 400 and c.delete("/api/gs/textos/guardados/2026-01-01-nada-x.md").status_code == 404, "apagar recusa nome fora do padrão e inexistente")
    try:
        txt.apagar(api.TEXTOS_DIR, "../x.md"); check(False, "apagar recusa caminho relativo")
    except ValueError:
        check(True, "apagar recusa caminho relativo")
    check(c.delete(f"/api/gs/textos/guardados/{j['nome']}").status_code == 200 and not (api.TEXTOS_DIR / j["nome"]).exists() and len(c.get("/api/gs/textos/guardados").json()) == 2, "apagar remove o arquivo e refaz o índice (fica o roteiro da versão antiga e o tudo)")

    # Drive: post.md ausente vira post.txt gerado da mensagem (sem rclone configurado, a rota reclama do Drive, mas o arquivo já foi escrito)
    r = c.post("/api/gs/conversas/i1/drive", data={"arquivos": "post.md"})
    check(r.status_code == 400 and (api.SAIDA / "s1" / "post.txt").read_text(encoding="utf-8").startswith("Legenda do post\nWebcam"), "Salvar no Drive gera post.txt a partir da mensagem")
    check(all(e["nome"] != "post.txt" for e in api._entregas("s1")), "post.txt não aparece no cartão")

    # link do atalho aberto no navegador vai para a Ajuda; token errado dá 403
    api._atalho_arq = lambda: tmp / "atalho.json"
    tok = c.get("/api/gs/atalho").json()["token"]
    r = c.get(f"/api/webhooks/compartilhar/{tok}", follow_redirects=False)
    check(r.status_code == 302 and r.headers["location"] == "/ajuda?de=atalho", "GET no link secreto redireciona para a Ajuda")
    check(c.get("/api/webhooks/compartilhar/errado", follow_redirects=False).status_code == 403, "token errado dá 403")
    check(c.get("/api/gs/atalho").json()["app"].startswith("https://"), "atalho devolve o endereço do app")

    # QR, versão e cabeçalhos de cache
    r = c.get("/api/gs/qr?texto=https://x.ts.net"); check(r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and b"<svg" in r.content, "QR em SVG")
    api.DIST.mkdir(); (api.DIST / "versao.json").write_text('{"build": "20261030"}'); (api.DIST / "index.html").write_text("<html></html>")
    r = c.get("/api/gs/versao"); check(r.json()["build"] == "20261030" and r.json()["gateway_desde"], "versão do build lida de dist/versao.json")
    r = c.get("/api/gs/estado"); check("Cache-Control" not in r.headers or r.headers.get("Cache-Control") != "no-cache", "rotas de API não ganham no-cache")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
