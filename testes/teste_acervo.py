"""Testes isolados da busca no acervo por fala: fontes do GSI e do app em pastas temporárias, busca sem acento, pontuação, janela de corte,
link no instante, endpoints do gateway com Paperclip falso e download do trecho falso. Sem rede.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_acervo.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, acervo as acv

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); gsi = tmp / "gsi"; tr = gsi / "dados" / "transcricoes"; (tr / "youtube").mkdir(parents=True); (tr / "instagram").mkdir()
    idx = {"youtube:v1": {"plataforma": "youtube", "id": "v1", "url": "https://www.youtube.com/watch?v=v1", "titulo": "Áudio com qualidade no OBS", "data": "2026-05-10", "formato": "long", "duracao_s": 600, "status": "transcrito", "arquivo": "dados/transcricoes/youtube/v1.json"},
           "youtube:v2": {"plataforma": "youtube", "id": "v2", "url": "https://www.youtube.com/watch?v=v2", "titulo": "Live de terça", "data": "2026-09-01", "formato": "live", "duracao_s": 3000, "status": "transcrito", "arquivo": "dados/transcricoes/youtube/v2.json"},
           "instagram:r1": {"plataforma": "instagram", "id": "r1", "url": "https://www.instagram.com/reel/r1/", "titulo": "Reel do mic", "data": "2026-03-01", "formato": "reel", "duracao_s": 40, "status": "transcrito", "arquivo": "dados/transcricoes/instagram/r1.json"},
           "youtube:v9": {"plataforma": "youtube", "id": "v9", "status": "indisponivel"},
           "youtube:v8": {"plataforma": "youtube", "id": "v8", "status": "transcrito", "arquivo": "dados/transcricoes/youtube/nao-existe.json"}}
    (tr / "indice.json").write_text(json.dumps(idx), encoding="utf-8")
    (tr / "youtube" / "v1.json").write_text(json.dumps({"segmentos": [{"s": 0, "e": 4, "t": "Fala galera, hoje é sobre áudio."}, {"s": 4, "e": 9, "t": "Primeiro a gente liga a supressão de ruído no filtro."}, {"s": 9, "e": 20, "t": "Depois o ganho, e pronto."}, {"s": 20, "e": 60, "t": "Agora o compressor. Ele segura o pico da voz e deixa tudo mais parelho."}, {"s": 60, "e": 70, "t": "Fim da parte de áudio."}]}), encoding="utf-8")
    (tr / "youtube" / "v2.json").write_text(json.dumps({"segmentos": [{"s": 100, "e": 104, "t": "Alguém perguntou de ruído."}, {"s": 104, "e": 110, "t": "A supressão resolve na maioria dos casos."}, {"s": 200, "e": 205, "t": "Supressão de ruído de novo: cuidado com o excesso."}]}), encoding="utf-8")
    (tr / "instagram" / "r1.json").write_text(json.dumps({"segmentos": [{"s": 0.0, "e": 3.6, "t": "Microfone barato com supressão de ruído? Dá sim."}]}), encoding="utf-8")
    saida = tmp / "saida"; ent = tmp / "entrada" / "2026-10-28-obvio"; ent.mkdir(parents=True); (ent / "obvio.mp4").write_bytes(b"\x00" * 10)
    pa = saida / "2026-10-28-obvio"; pa.mkdir(parents=True)
    (pa / "palavras.json").write_text(json.dumps({"arquivo": str(ent / "obvio.mp4"), "duracao_s": 120, "segmentos": [{"inicio": 34.65, "fim": 41.19, "texto": "Dá pra ter qualidade boa com a sua webcam."}, {"inicio": 41.2, "fim": 50.0, "texto": "Sem supressão de ruído o áudio fica sujo."}]}), encoding="utf-8")
    (pa / "palavras_cortado.json").write_text(json.dumps({"arquivo": str(ent / "obvio.mp4"), "segmentos": [{"inicio": 0, "fim": 5, "texto": "Sem supressão de ruído o áudio fica sujo."}]}), encoding="utf-8")
    cache = {"issue-x": {"slug": "2026-10-28-obvio", "titulo": "O óbvio 3", "codigo": "GRA-9", "id": "issue-x", "secoes": []}}
    fs = acv.fontes(gsi, saida, cache)
    r = acv.resumo(fs)
    check(r["total"] == 4 and r["gsi"] == 3 and r["app"] == 1 and r["com_video_local"] == 1, f"fontes: 3 do GSI (sem indisponível e sem arquivo ausente) + 1 do app, sem a versão cortada ({r})")
    app_f = next(f for f in fs if f["origem"] == "app")
    check(app_f["titulo"] == "O óbvio 3" and app_f["conversa"] == "issue-x" and app_f["video_local"].endswith("obvio.mp4"), "fonte do app traz título da conversa e vídeo local")
    res = acv.buscar("supressao de ruido", fs)
    check(len(res) == 5 and all(x["pontos"] == 3 for x in res[:4]), f"busca sem acento acha a frase em 4 fontes + 1 trecho fraco ({len(res)}: {[x['pontos'] for x in res]})")
    check(res[0]["fonte"]["id"] == "app:2026-10-28-obvio:palavras" and res[1]["fonte"]["id"] == "gsi:youtube:v2" and res[1]["inicio"] == 200 and res[3]["fonte"]["id"] == "gsi:instagram:r1", f"mais pontos primeiro, depois mais recente (entrega de hoje, v2, v1, r1) ({[x['fonte']['id'] for x in res[:4]]})")
    fraco = res[-1]
    check(fraco["pontos"] == 1 and fraco["fonte"]["id"] == "gsi:youtube:v2" and fraco["inicio"] == 100, "palavras espalhadas em dois segmentos seguidos valem 1 ponto")
    v1 = next(x for x in res if x["fonte"]["id"] == "gsi:youtube:v1")
    check(v1["inicio"] == 4 and v1["antes"].startswith("Fala galera") and v1["depois"].startswith("Depois o ganho") and v1["link"] == f"https://www.youtube.com/watch?v=v1&t={int(v1['instante'])}s" and v1["instante"] >= 4, "trecho vem com contexto antes/depois e link no instante do termo (fase 2)")
    check(v1["corte_sugerido"] == {"inicio": 3.7, "fim": 60.0}, f"janela de corte: do segmento até fechar frase depois de 40 s ({v1['corte_sugerido']})")
    check(acv.buscar("supressão", fs, origem="instagram")[0]["fonte"]["plataforma"] == "instagram" and len(acv.buscar("supressão", fs, origem="instagram")) == 1 and all(x["fonte"]["origem"] == "app" for x in acv.buscar("supressão", fs, origem="app")), "filtro por origem/plataforma")
    check(acv.buscar("", fs) == [] and acv.buscar("a", fs) == [] and acv.buscar("xyzw", fs) == [], "consulta vazia, curta ou sem resultado: lista vazia")
    check(len(acv.buscar("ruído", fs, max_por_fonte=1)) == 4, "até N trechos por fonte")
    segs = acv.segmentos(next(f for f in fs if f["id"] == "gsi:youtube:v1"))
    check(acv.janela_corte(segs, 4) == (59.7, 70.0) and acv.janela_corte(segs, 0)[1] >= 15, "janela no fim do vídeo e mínimo de 15 s")
    check(acv.link_instante({"url": "https://www.instagram.com/reel/r1/", "plataforma": "instagram"}, 10) == "https://www.instagram.com/reel/r1/" and acv.link_instante({"url": None}, 1) is None, "link do Instagram sem instante; sem url, None")

    # gateway
    api.GSI_RAIZ = gsi; api.SAIDA = saida; api.ENTRADA = tmp / "entrada"; api.WORKSPACE = tmp; api.CLIPES_DIR = tmp / "clipes"; api.INDICE = tmp / "conversas.json"; api.TEXTOS_CACHE = tmp / "textos.json"
    api.TEXTOS_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    criadas = []
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            criadas.append(kw["json"]); return {"id": f"issue-{len(criadas)}", "identifier": f"GRA-{len(criadas)}", **kw["json"]}
        return []
    api._pc = pc_falso
    c = TestClient(api.app)
    j = c.get("/api/gs/acervo?q=supress%C3%A3o%20de%20ru%C3%ADdo").json()
    check(len(j["resultados"]) == 5 and j["fontes"]["total"] == 4 and j["resultados"][0]["corte_sugerido"]["inicio"] >= 0, "GET /api/gs/acervo devolve trechos e resumo das fontes")
    check(c.get("/api/gs/acervo?q=").json()["resultados"] == [], "sem consulta: só o resumo")
    # corte de entrega do app: vídeo local, sem download
    r = c.post("/api/gs/acervo/corte", data={"fonte_id": "app:2026-10-28-obvio:palavras", "inicio": "41.2", "fim": "60", "titulo": "Áudio sujo sem supressão", "gancho": "Seu áudio tá sujo?", "q": "supressão de ruído"})
    check(r.status_code == 200 and r.json()["arquivo"] == "entrada/2026-10-28-obvio/obvio.mp4" and criadas[-1]["title"] == "Corte do acervo: Áudio sujo sem supressão", f"corte de entrega usa o vídeo local ({r.status_code} {r.text[:120]})")
    d = criadas[-1]["description"]
    check("extraia o corte a01 de `entrada/2026-10-28-obvio/obvio.mp4` (de 41.2 s a 60.0 s" in d and "saida/2026-10-28-obvio/palavras.json" in d and "Seu áudio tá sujo?" in d and "fluxos/reels-padrao.md" in d and "busca por fala" in d, "pedido do Clipador com trecho, palavras, gancho e fluxo")
    idx_c = json.loads(api.INDICE.read_text())["issue-1"]
    check(idx_c["origem"] == "acervo" and idx_c["acervo"]["fonte"] == "app:2026-10-28-obvio:palavras" and idx_c["slug"].startswith(idx_c["slug"][:10]) and "acervo-" in idx_c["slug"], "índice guarda a origem acervo e a fonte")
    # corte de fonte do GSI: baixa só a janela (falso) e rebaseia os tempos
    chamadas = []
    def baixar_falso(url, inicio, fim, pasta, margem=5.0):
        chamadas.append((url, inicio, fim, str(pasta))); pasta = Path(pasta); pasta.mkdir(parents=True, exist_ok=True); (pasta / "origem.mp4").write_bytes(b"\x00" * 10); return pasta / "origem.mp4", min(inicio, margem)
    acv.baixar_trecho = baixar_falso
    r = c.post("/api/gs/acervo/corte", data={"fonte_id": "gsi:youtube:v2", "inicio": "200", "fim": "230", "titulo": "Excesso de supressão", "q": "supressão"})
    j2 = r.json()
    check(r.status_code == 200 and j2["arquivo"] == "clipes/acervo-youtube-v2-200s/origem.mp4" and j2["corte"]["inicio"] == 5.0 and j2["corte"]["fim"] == 35.0 and chamadas[-1][:3] == ("https://www.youtube.com/watch?v=v2", 200.0, 230.0), f"fonte do GSI: baixa a janela e rebaseia início/fim no arquivo ({r.status_code} {str(j2)[:120]})")
    d2 = criadas[-1]["description"]
    check("Origem é call" not in d2 and "só a janela do original" in d2 and "t=200s" in d2 and "clipes/acervo-youtube-v2-200s/origem.mp4" in d2, "pedido avisa que o arquivo é só a janela e dá o link no instante")
    check(c.post("/api/gs/acervo/corte", data={"fonte_id": "gsi:youtube:v2", "inicio": "10", "fim": "5"}).status_code == 400 and c.post("/api/gs/acervo/corte", data={"fonte_id": "nada", "inicio": "1", "fim": "5"}).status_code == 404, "validação: fim antes do início; fonte inexistente")
    def baixar_falha(url, inicio, fim, pasta, margem=5.0): raise acv.ErroAcervo("sem rede")
    acv.baixar_trecho = baixar_falha
    r = c.post("/api/gs/acervo/corte", data={"fonte_id": "gsi:youtube:v1", "inicio": "4", "fim": "20"})
    check(r.status_code == 502 and "sem rede" in r.text and len(criadas) == 2, "download que falha: 502 e nenhum pedido")

# 03/11/2026: entrega com "palavras": <contagem> (não lista) quebrava a busca inteira com 500
_tmp = Path(tempfile.mkdtemp()) / "x.palavras.json"; _tmp.write_text(json.dumps({"palavras": 42, "segmentos": [{"s": 0, "e": 1, "t": "oi microfone"}, 7]}), encoding="utf-8")
check(acv.segmentos({"arquivo": str(_tmp)}) == [(0.0, 1.0, "oi microfone")], "arquivo com 'palavras' numérico ou segmento inválido não derruba a busca")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
