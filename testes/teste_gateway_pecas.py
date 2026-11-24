"""Testes isolados da ficha única da peça: inferência de etiquetas, gravação humana, listagem com filtros, ficha com métricas de um gs.db falso. Pastas temporárias."""
import json, sqlite3, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, pecas

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.GSI_DB = tmp / "gs.db"; pecas.ETIQUETAS_CFG = tmp / "etiquetas.json"
    api.SAIDA.mkdir()
    # gs.db falso
    con = sqlite3.connect(api.GSI_DB)
    con.execute("create table performance_snapshots (platform, item_id, horizon, computed_at, views, likes, comments, engagement_rate, format, theme, ratio_vs_format_median, median_views_format, age_days)")
    con.execute("insert into performance_snapshots values ('youtube','abc123','current','2026-10-30T08:00:00Z',1500,80,12,0.06,'long','audio',1.8,830,5.0)")
    con.execute("insert into performance_snapshots values ('youtube','abc123','current','2026-10-29T08:00:00Z',900,50,8,0.06,'long','audio',1.1,830,4.0)")
    con.execute("insert into performance_snapshots values ('instagram','CxyZ12','current','2026-10-30T08:00:00Z',22000,900,40,0.04,'reel','obs',2.4,9000,3.0)")
    con.commit(); con.close()
    # entregas
    a = api.SAIDA / "2026-10-30-reel-webcam"; a.mkdir(); (a / "final_9x16.mp4").write_bytes(b"0" * 10); (a / "capa.png").write_bytes(b"1")
    (a / "final_9x16_palavras.json").write_text(json.dumps({"origem": "tts-clonada", "palavras": []}), encoding="utf-8")
    (a / "publicacoes.json").write_text(json.dumps([{"tipo": "publora", "quando": "2026-10-30T10:00:00", "posts": [{"permalink": "https://www.instagram.com/reel/CxyZ12/"}]}]), encoding="utf-8")
    b = api.SAIDA / "2026-10-29-aula-youtube"; b.mkdir(); (b / "final_16x9.mp4").write_bytes(b"0"); (b / "final_16x9.srt").write_text("1")
    (b / "final_16x9_palavras.json").write_text(json.dumps({"origem": "transcricao", "palavras": [{"palavra": "oi"}]}), encoding="utf-8")
    (b / "publicacoes.json").write_text(json.dumps([{"tipo": "youtube", "quando": "2026-10-29T12:00:00", "id": "abc123"}]), encoding="utf-8")
    c = api.SAIDA / "2026-10-28-carrossel-luz"; c.mkdir(); (c / "carrossel.pdf").write_bytes(b"0"); (c / "slide-01.png").write_bytes(b"0")
    (api.SAIDA / "_lixo").mkdir()
    api.TEXTOS_CACHE.write_text(json.dumps({"i1": {"id": "i1", "codigo": "GRA-40", "titulo": "Reel webcam", "slug": "2026-10-30-reel-webcam", "pasta": "Pulso do GSI", "secoes": [{"chave": "gancho", "titulo": "Gancho", "conteudo": "1. **Sua webcam parece de 2010?**\n2. Outra"}, {"chave": "descricao", "titulo": "Legenda do post", "conteudo": "Legenda x"}]},
                                            "i2": {"id": "i2", "codigo": "GRA-41", "titulo": "Aula YouTube", "slug": "2026-10-29-aula-youtube", "pasta": None, "secoes": []}}), encoding="utf-8")
    api.INDICE.write_text(json.dumps({"i1": {"slug": "2026-10-30-reel-webcam", "pasta": "Pulso do GSI"}, "i2": {"slug": "2026-10-29-aula-youtube", "notion_page": "abc"}}), encoding="utf-8")
    cli = TestClient(api.app)

    # inferência
    r = cli.get("/api/gs/pecas").json(); por = {i["slug"]: i for i in r["itens"]}
    check(set(por) == {"2026-10-30-reel-webcam", "2026-10-29-aula-youtube", "2026-10-28-carrossel-luz"} and r["resumo"]["total"] == 3, "lista as três entregas (ignora _pastas)")
    e1 = por["2026-10-30-reel-webcam"]["etiquetas"]
    check(e1["formato"] == "reel" and e1["voz"] == "clonada" and e1["gancho"] == "Sua webcam parece de 2010?" and e1["origem"] == "pulso", f"reel: formato, voz clonada, gancho do texto e origem pulso inferidos ({e1})")
    e2 = por["2026-10-29-aula-youtube"]["etiquetas"]
    check(e2["formato"] == "youtube" and e2["voz"] == "thiago" and "origem" not in e2, "youtube: formato e voz do Thiago; origem notion só na ficha (índice)")
    e3 = por["2026-10-28-carrossel-luz"]["etiquetas"]
    check(e3["formato"] == "carrossel" and e3["voz"] == "sem", "carrossel: formato e sem voz")
    check(por["2026-10-30-reel-webcam"]["estado"] == "postado ou agendado" and por["2026-10-30-reel-webcam"]["views"] == 22000 and por["2026-10-30-reel-webcam"]["vs_mediana"] == 2.4, "reel casa com o Instagram pelo permalink: views e razão do último snapshot")
    check(por["2026-10-29-aula-youtube"]["views"] == 1500 and por["2026-10-29-aula-youtube"]["medido_em"].startswith("2026-10-30"), "youtube casa pelo id e pega o snapshot mais novo")
    check(por["2026-10-28-carrossel-luz"]["views"] is None and por["2026-10-28-carrossel-luz"]["estado"] == "ainda não usado", "sem publicação: sem métrica")
    check(r["resumo"]["sem_etiqueta"] == 3 and r["resumo"]["com_metrica"] == 2 and r["resumo"]["formatos"]["reel"] == 1 and r["opcoes"]["campanhas"][0] == "Orgânico", "resumo e opções padrão")

    # etiquetas humanas
    r = cli.post("/api/gs/pecas/2026-10-30-reel-webcam/etiquetas", data={"campanha": "Black", "pilar": "Áudio e vídeo", "cta": "salvar", "redes": "instagram,tiktok,xx"})
    j = r.json()
    check(r.status_code == 200 and j["etiquetas"]["campanha"] == "Black" and j["etiquetas"]["redes"] == ["instagram", "tiktok"] and j["etiquetas"]["formato"] == "reel" and j["humanas"].get("formato") is None, "humanas por cima das inferidas; redes validadas")
    check(json.loads((a / "peca.json").read_text())["etiquetas"]["campanha"] == "Black" and j["por"] == "Raphael" and j["atualizado"], "peca.json gravado")
    r = cli.post("/api/gs/pecas/2026-10-30-reel-webcam/etiquetas", data={"formato": "story", "gancho": "Gancho editado"}).json()
    check(r["etiquetas"]["formato"] == "story" and r["etiquetas"]["gancho"] == "Gancho editado" and r["auto"]["formato"] == "reel", "humano sobrescreve formato e gancho; auto continua visível")
    r = cli.post("/api/gs/pecas/2026-10-30-reel-webcam/etiquetas", data={"limpar": "formato"}).json()
    check(r["etiquetas"]["formato"] == "reel" and r["etiquetas"]["campanha"] == "Black", "vazio apaga a escolha humana e volta ao inferido, sem mexer nas outras")
    check(cli.post("/api/gs/pecas/2026-10-30-reel-webcam/etiquetas", data={"voz": "robo"}).status_code == 400, "voz inválida dá 400")
    check(cli.post("/api/gs/pecas/nao-existe/etiquetas", data={"campanha": "x"}).status_code == 404 and cli.get("/api/gs/pecas/../x").status_code in (404, 422), "peça inexistente dá 404")
    # filtros
    r = cli.get("/api/gs/pecas?campanha=Black").json()
    check([i["slug"] for i in r["itens"]] == ["2026-10-30-reel-webcam"] and r["resumo"]["total"] == 3, "filtro por campanha; resumo continua do total")
    check(len(cli.get("/api/gs/pecas?formato=carrossel").json()["itens"]) == 1 and len(cli.get("/api/gs/pecas?q=webcam").json()["itens"]) == 1 and len(cli.get("/api/gs/pecas?estado=ainda%20n%C3%A3o%20usado").json()["itens"]) == 1, "filtros por formato, texto e estado")
    # opções
    r = cli.post("/api/gs/pecas/opcoes", data={"campo": "campanhas", "valor": "Níver"}).json()
    check("Níver" in r["campanhas"] and "Níver" in cli.get("/api/gs/pecas").json()["opcoes"]["campanhas"] and cli.post("/api/gs/pecas/opcoes", data={"campo": "x", "valor": "y"}).status_code == 400, "campanha nova nas opções")
    # ficha
    f = cli.get("/api/gs/pecas/2026-10-30-reel-webcam").json()
    check(f["conversa"]["id"] == "i1" and f["conversa"]["codigo"] == "GRA-40" and f["textos"]["descricao"] == "Legenda x" and f["textos"]["gancho"].startswith("1.") and f["etiquetas"]["campanha"] == "Black", "ficha junta conversa, textos e etiquetas")
    check(f["ids_publicados"] == [{"plataforma": "instagram", "id": "CxyZ12"}] and f["metricas"][0]["views"] == 22000 and f["estado"] == "postado ou agendado" and len(f["arquivos"]) >= 2, "ficha com ids publicados, métricas e arquivos")
    f2 = cli.get("/api/gs/pecas/2026-10-29-aula-youtube").json()
    check(f2["etiquetas"]["origem"] == "notion" and f2["metricas"][0]["ratio_vs_format_median"] == 1.8, "ficha do YouTube: origem notion pelo índice e razão do snapshot")
    # sem banco
    api.GSI_DB = tmp / "nao-existe.db"
    check(cli.get("/api/gs/pecas").json()["resumo"]["com_metrica"] == 0 and cli.get("/api/gs/pecas/2026-10-30-reel-webcam").json()["metricas"] == [], "sem gs.db: lista e ficha funcionam sem métricas")

    # licença por ativo (10/11/2026): banco/<fonte>/<id>.licenca.json e tabela de trilhas/README.md; só o que a entrega cita
    check(f["ativos"] == [] and f["alertas"] == [] and json.loads((a / "peca.json").read_text(encoding="utf-8")).get("ativos") == [], "sem material citado: ativos vazio na ficha e no peca.json")
    banco = tmp / "banco"; (banco / "pexels").mkdir(parents=True); (banco / "pixabay").mkdir(); (banco / "freesound").mkdir()
    (banco / "pexels" / "111.licenca.json").write_text(json.dumps({"origem": "pexels", "tipo": "video", "id": "111", "url": "https://www.pexels.com/video/111/", "autor": "Ana", "licenca": "Pexels License (uso comercial, sem atribuição obrigatória)", "atribuicao": "Vídeo de Ana no Pexels"}), encoding="utf-8")
    (banco / "pixabay" / "222.licenca.json").write_text(json.dumps({"origem": "pixabay", "tipo": "imagem", "id": "222", "url": "https://pixabay.com/photos/222/", "licenca": "Pixabay Content License (uso comercial; mostrar a origem)", "atribuicao": "Foto de Bo no Pixabay"}), encoding="utf-8")
    (banco / "freesound" / "333.licenca.json").write_text(json.dumps({"origem": "freesound", "tipo": "audio", "id": "333", "url": "https://freesound.org/s/333/", "licenca": "CC BY 4.0", "atribuicao": None}), encoding="utf-8")
    trilhas = tmp / "trilhas"; trilhas.mkdir()
    (trilhas / "README.md").write_text("# Trilhas\n\n| Arquivo | Origem | Licença | Observação |\n|---|---|---|---|\n| calma-piano.mp3 | Pixabay Music | Pixabay Content License | |\n| energia-lofi.mp3 | Incompetech | CC-BY 4.0 | |\n| bbc-chuva.wav | BBC Sound Effects | não comercial (RemArc) | |\n| proprio-jingle.mp3 | Grava Simples (comprada) | própria | |\n", encoding="utf-8")
    pecas.ETIQUETAS_CFG = tmp / "etiquetas.json"; _banco, _trilhas = pecas._cam.WORKSPACE, pecas._cam.TRILHAS
    pecas._cam.WORKSPACE = tmp; pecas._cam.TRILHAS = trilhas  # ativos() lê WORKSPACE/banco e TRILHAS/README.md
    (a / "plano.json").write_text(json.dumps({"cenas": [{"visual": "banco/pexels/111.mp4"}, {"visual": "banco/pixabay/222.jpg"}, {"sfx": "banco/freesound/333.wav"}, {"fundo": "banco/pexels/999.mp4"}], "trilha": "trilhas/energia-lofi.mp3"}), encoding="utf-8")
    api.TEXTOS_CACHE.write_text(json.dumps({"i1": {"id": "i1", "codigo": "GRA-40", "titulo": "Reel webcam", "slug": "2026-10-30-reel-webcam", "pasta": "Pulso do GSI", "secoes": [{"chave": "resumo", "titulo": "Resumo", "conteudo": "Trilha: bbc-chuva.wav no fundo e calma-piano.mp3 na abertura."}]}}), encoding="utf-8")
    try:
        f = cli.get("/api/gs/pecas/2026-10-30-reel-webcam").json()
        por_arq = {x["arquivo"]: x for x in f["ativos"]}
        check(set(por_arq) == {"banco/pexels/111.mp4", "banco/pixabay/222.jpg", "banco/freesound/333.wav", "banco/pexels/999.mp4", "trilhas/energia-lofi.mp3", "trilhas/bbc-chuva.wav", "trilhas/calma-piano.mp3"}, f"ativos citados no plano.json e no Resumo ({sorted(por_arq)})")
        check(por_arq["banco/pexels/111.mp4"]["licenca"] == "pexels" and por_arq["banco/pexels/111.mp4"]["atribuicao"] == "Vídeo de Ana no Pexels" and por_arq["banco/pexels/111.mp4"]["url"].startswith("https://www.pexels.com") and por_arq["banco/pexels/111.mp4"]["origem"] == "pexels", "pexels: licença, atribuição e url do .licenca.json")
        check(por_arq["banco/pixabay/222.jpg"]["licenca"] == "pixabay" and por_arq["banco/freesound/333.wav"]["licenca"] == "cc-by" and por_arq["banco/pexels/999.mp4"]["licenca"] == "desconhecida", "pixabay, cc-by e banco sem .licenca.json (desconhecida)")
        check(por_arq["trilhas/energia-lofi.mp3"]["licenca"] == "cc-by" and por_arq["trilhas/bbc-chuva.wav"]["licenca"] == "nc" and por_arq["trilhas/calma-piano.mp3"]["licenca"] == "pixabay" and por_arq["trilhas/energia-lofi.mp3"]["origem"] == "Incompetech", "trilhas pela tabela do README: cc-by, nc e pixabay; citada só pelo nome também conta")
        msgs = {x["msg"] for x in f["alertas"]}
        check("Trilha energia-lofi.mp3 é CC-BY sem crédito na legenda" in msgs and "Trilha bbc-chuva.wav é só para uso não comercial" in msgs and "Trilha 333.wav é CC-BY sem crédito na legenda" in msgs and "Vídeo 999.mp4 sem licença registrada" in msgs and not any("111.mp4" in m or "222.jpg" in m or "calma-piano" in m for m in msgs), f"alertas: cc-by sem crédito, nc e desconhecida; pexels/pixabay sem alerta ({sorted(msgs)})")
        pj = json.loads((a / "peca.json").read_text(encoding="utf-8"))
        check(len(pj["ativos"]) == 7 and len(pj["alertas"]) == 4 and pj["etiquetas"]["campanha"] == "Black", "ativos e alertas gravados no peca.json sem perder as etiquetas")
        lin = next(i for i in cli.get("/api/gs/pecas").json()["itens"] if i["slug"] == "2026-10-30-reel-webcam")
        check(lin["alertas"] == 4, "lista traz o número de alertas gravado")
        (trilhas / "README.md").write_text("# Trilhas\n\n| Arquivo | Origem | Licença | Observação |\n|---|---|---|---|\n| energia-lofi.mp3 | Incompetech | CC-BY 4.0 | crédito: Kevin MacLeod (incompetech.com) |\n", encoding="utf-8")
        f = cli.get("/api/gs/pecas/2026-10-30-reel-webcam").json(); por_arq = {x["arquivo"]: x for x in f["ativos"]}
        check(por_arq["trilhas/energia-lofi.mp3"]["atribuicao"].startswith("crédito") and not any("energia-lofi" in x["msg"] for x in f["alertas"]) and "trilhas/bbc-chuva.wav" not in por_arq, "cc-by com crédito anotado não alerta; trilha citada só pelo nome e fora da tabela some da lista (peca.json não se cita)")
        (a / "ativos.json").write_text(json.dumps([{"arquivo": "materiais/take-obs.mp4", "origem": "Drive da empresa", "licenca": "proprio"}]), encoding="utf-8")
        f = cli.get("/api/gs/pecas/2026-10-30-reel-webcam").json()
        check(any(x["arquivo"] == "materiais/take-obs.mp4" and x["licenca"] == "proprio" for x in f["ativos"]) and not any("take-obs" in x["msg"] for x in f["alertas"]), "ativos.json deixado na pasta entra como próprio, sem alerta")
        check(pecas.licenca_normalizar("CC0 1.0") == "cc0" and pecas.licenca_normalizar("material da empresa") == "proprio" and pecas.licenca_normalizar("Creative Commons Attribution-NonCommercial") == "nc" and pecas.licenca_normalizar("") == "desconhecida", "normalização de licença")
    finally:
        pecas._cam.WORKSPACE = _banco; pecas._cam.TRILHAS = _trilhas

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
