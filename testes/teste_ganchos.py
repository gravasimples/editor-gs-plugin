"""Testes isolados da biblioteca de ganchos: peças do app (etiqueta gancho + métrica), experimentos, conteúdos próprios do GSI; filtros,
ordenação, texto do pedido e endpoint. Sem rede, banco temporário.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_ganchos.py"""
import json, sqlite3, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, ganchos as g

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); db = tmp / "gs.db"; saida = tmp / "saida"; saida.mkdir()
    con = sqlite3.connect(db)
    con.executescript("""
    create table sources(source_id int, platform text, handle text, kind text);
    create table performance_snapshots(snapshot_id int, platform text, item_id text, owner text, horizon text, computed_at text, views int, likes int, comments int, engagement_rate real, format text, theme text, median_views_format real, ratio_vs_format_median real, age_days int);
    create table ig_posts(shortcode text, caption text, posted_at text, url text, is_paid int);
    create table yt_videos(video_id text, title text, published_at text);""")
    con.executemany("insert into sources values (?,?,?,?)", [(1, "youtube", "gravasimples", "own"), (2, "instagram", "thiago.obsstudio", "own")])
    snaps = [("youtube", "Y1", "gravasimples", 9000, 4.5, "short"), ("youtube", "Y2", "gravasimples", 300, 0.4, "long"), ("instagram", "I1", "thiago.obsstudio", 60000, 12.0, "reel"), ("instagram", "I2", "thiago.obsstudio", 100, 0.1, "reel"), ("instagram", "I3", "thiago.obsstudio", 5000, 1.0, "reel"), ("youtube", "X1", "outro", 1, 99.0, "short")]
    con.executemany("insert into performance_snapshots values (?,?,?,?,'current','2026-10-28T08:00:00Z',?,0,0,0.1,?,'',5000,?,10)", [(i, a, b, c, d, f, e) for i, (a, b, c, d, e, f) in enumerate(snaps)])
    con.executemany("insert into yt_videos values (?,?,?)", [("Y1", "3 funções do OBS para quem grava aula", "2024-09-12T12:00:00Z"), ("Y2", "Tutorial longo", "2024-10-01T00:00:00Z"), ("X1", "Concorrente", "2024-01-01")])
    con.executemany("insert into ig_posts values (?,?,?,?,?)", [("I1", "**Galera**, gravar com qualidade é simples.\nSegunda linha.", "2025-03-28T11:00:00Z", "https://www.instagram.com/p/I1/", 0), ("I2", "#tag só\nOi", "2026-01-01", None, 0), ("I3", "Reel pago com legenda boa", "2026-02-01", None, 1)])
    con.commit(); con.close()
    # peça do app com gancho e métrica; peça sem gancho; experimento
    pa = saida / "2026-08-01-peca"; pa.mkdir(); (pa / "final_9x16.mp4").write_bytes(b"\x00")
    (pa / "publicacoes.json").write_text(json.dumps([{"tipo": "publora", "quando": "2026-08-01T10:00:00", "posts": [{"permalink": "https://www.instagram.com/reel/I1/"}]}]))
    (pa / "peca.json").write_text(json.dumps({"etiquetas": {"gancho": "Seu áudio tá sujo?", "pilar": "Áudio e vídeo"}}))
    pb = saida / "2026-08-02-sem-gancho"; pb.mkdir(); (pb / "final_9x16.mp4").write_bytes(b"\x00")
    pc = saida / "2026-11-01-reciclado"; pc.mkdir()
    (pc / "experimento.json").write_text(json.dumps({"codigo": "GRA-38", "quando": "2026-11-01T19:00:00", "status": "aberto", "original": {"plataforma": "instagram", "id": "I1", "url": "https://www.instagram.com/p/I1/", "titulo": "Galera, gravar…", "publicado": "2025-03-28", "views": 60000, "razao": 12.0}, "gancho_original": "Agora eu vou te mostrar", "gancho_novo": "Ainda configura o OBS do **zero**?"}))
    cache = {"c1": {"slug": "2026-08-02-sem-gancho", "titulo": "Peça só com seção", "codigo": "GRA-2", "secoes": [{"chave": "gancho", "conteudo": "- **Webcam** travada? Olha isso."}]}}
    itens = g.listar(saida, db, cache)
    r = g.resumo(itens)
    check(r["por_origem"] == {"app": 2, "experimento": 2, "youtube": 2, "instagram": 1} and r["total"] == 7, f"junta peças (etiqueta e seção), experimentos e GSI próprio (sem concorrente, sem pago, sem legenda vazia) ({r['por_origem']})")
    ig = next(i for i in itens if i["origem"] == "instagram")
    check(itens[0]["razao"] == 12.0 and itens[-1]["razao"] is None and ig["gancho"] == "Galera, gravar com qualidade é simples.", f"ordem por razão (sem métrica no fim); primeira linha sem Markdown ({ig['gancho']})")
    app_ = {i["gancho"]: i for i in itens if i["origem"] == "app"}
    check(app_["Seu áudio tá sujo?"]["razao"] == 12.0 and app_["Seu áudio tá sujo?"]["slug"] == "2026-08-01-peca" and app_["Webcam travada? Olha isso"]["razao"] is None, "peça do app traz a razão pela publicação casada; seção ## Gancho vira gancho sem métrica")
    exp = [i for i in itens if i["origem"] == "experimento"]
    check({e["papel"] for e in exp} == {"gancho original", "gancho novo"} and next(e for e in exp if e["papel"] == "gancho novo")["gancho"] == "Ainda configura o OBS do zero?" and next(e for e in exp if e["papel"] == "gancho original")["razao"] == 12.0, "experimento: gancho original com a razão da peça original; novo sem Markdown")
    check(all(i["razao"] is not None for i in g.listar(saida, db, cache, so_medidos=True)) and len(g.listar(saida, db, cache, so_medidos=True)) == 5, "só com métrica")
    check([i["origem"] for i in g.listar(saida, db, cache, origem="youtube")] == ["youtube", "youtube"] and g.listar(saida, db, cache, minimo=2.0, origem="youtube")[0]["gancho"].startswith("3 funções") and len(g.listar(saida, db, cache, minimo=2.0, origem="youtube")) == 1, "filtros de origem e razão mínima")
    check(len(g.listar(saida, db, cache, q="webcam")) == 1 and g.listar(saida, db, cache, q="zzz") == [], "filtro por palavra")
    t = g.texto_pedido(ig)
    check(t.startswith("Use este gancho como frase de impacto (adapte, não copie): \"Galera, gravar com qualidade é simples.\" (rendeu 12.0× a mediana") and "não claim" in t and "fonte" in t.lower(), "texto do pedido traz o gancho, a prova e a fonte")
    check("rendeu" not in g.texto_pedido(app_["Webcam travada? Olha isso"]), "sem métrica, o texto não inventa prova")
    api.SAIDA = saida; api.GSI_DB = db; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_CACHE.write_text(json.dumps(cache))
    c = TestClient(api.app)
    j = c.get("/api/gs/ganchos?medidos=sim&origem=tudo").json()
    check(len(j["itens"]) == 5 and j["resumo"]["acima"] == 4 and all("pedido" in i for i in j["itens"]), f"GET /api/gs/ganchos com filtros e texto do pedido ({len(j['itens'])}, {j['resumo']})")
    check(c.get("/api/gs/ganchos?minimo=abc").status_code == 200 and len(c.get("/api/gs/ganchos?q=funcoes").json()["itens"]) == 0 and len(c.get("/api/gs/ganchos?q=funções").json()["itens"]) == 1, "mínimo inválido vira 0; filtro por palavra literal")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
