"""Automações 3, 5, 6 e 7 (03/11/2026): variação do vencedor, pós-mortem automático, alertas e melhor horário. Banco SQLite sintético em pasta
temporária (nada do gs.db real). Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_automacoes_dados.py"""
import sqlite3, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import automacoes_dados as ad

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

td = Path(tempfile.mkdtemp()); db = td / "gs.db"; agora = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
con = sqlite3.connect(db)
con.executescript("""
create table sources(source_id integer primary key, platform text, handle text, kind text);
create table performance_snapshots(platform text, item_id text, owner text, horizon text, computed_at text, age_days real, views int, ratio_vs_format_median real, format text);
create table yt_videos(video_id text, source_id int, title text, published_at text);
create table ig_posts(shortcode text, owner_handle text, caption text, posted_at text, url text, is_paid int);
create table ig_comments(comment_id text, shortcode text, posted_at text, is_owner int);
create table yt_comments(comment_id text, video_id text, posted_at text, is_owner int);
create table comment_classifications(platform text, comment_id text, classification text, is_current int);
insert into sources values (1,'youtube','gs','own'),(2,'instagram','thiago','own'),(3,'instagram','outro','competitor');
""")
def snap(plat, iid, owner, idade, razao, views=1000, quando="2026-11-03T10:00:00Z"):
    con.execute("insert into performance_snapshots values (?,?,?,?,?,?,?,?,?)", (plat, iid, owner, "current", quando, idade, views, razao, "reel"))
snap("instagram", "SUBIU", "thiago", 3, 4.0); snap("instagram", "CAIU", "thiago", 5, 0.2); snap("instagram", "NOVO", "thiago", 0.5, 0.1)
snap("instagram", "VELHO", "thiago", 40, 9.0); snap("instagram", "CONC", "outro", 3, 9.0); snap("instagram", "MEDIO", "thiago", 4, 1.0)
snap("instagram", "SUBIU", "thiago", 2, 0.5, quando="2026-11-01T10:00:00Z")  # snapshot antigo não conta
for sc, cap in (("SUBIU", "Pare de gravar assim\nresto"), ("CAIU", "Outro post"), ("RISCO", "Post com problema")):
    con.execute("insert into ig_posts values (?,?,?,?,?,0)", (sc, "thiago", cap, "2026-10-30T22:00:00Z", None))
for i in range(4):
    con.execute("insert into ig_comments values (?,?,?,0)", (f"c{i}", "RISCO", "2026-11-01T12:00:00Z"))
    con.execute("insert into comment_classifications values ('instagram',?,?,1)", (f"c{i}", "OBJECTION" if i < 3 else "QUESTION"))
con.commit()

cfg = ad.PADRAO["alertas"]
al = ad.alertas(db, {}, cfg, agora); tipos = {(a["tipo"], a["item"]) for a in al}
check(("tracao", "SUBIU") in tipos and ("queda", "CAIU") in tipos, f"tração e queda pelos snapshots mais recentes ({sorted(tipos)})")
check(("queda", "NOVO") not in tipos and all(i != "VELHO" for _, i in tipos) and all(i != "CONC" for _, i in tipos) and all(i != "MEDIO" for _, i in tipos),
      "não alerta post novo demais, velho, de concorrente nem na média")
check(("risco", "RISCO") in tipos, "3 comentários de objeção no mesmo post viram alerta de risco (pergunta não conta)")
check(next(a for a in al if a["item"] == "SUBIU")["titulo"] == "Pare de gravar assim", "título do Instagram = primeira linha da legenda")
est = {"alertas_enviados": [a["chave"] for a in al]}
check(ad.alertas(db, est, cfg, agora) == [], "cada alerta sai uma vez")
t, corpo = ad.texto_alerta(next(a for a in al if a["tipo"] == "tracao")); check("4.0×" in t and "views" in corpo, "texto do push de tração")

# melhor horário: 3 posts segunda à noite (BRT) com razão alta, 3 terça de manhã baixa, 1 sábado (pouca amostra)
for i, (data, r) in enumerate([("2026-10-05T23:30:00Z", 3.0), ("2026-10-12T22:10:00Z", 2.0), ("2026-10-19T23:00:00Z", 4.0),
                               ("2026-10-06T11:00:00Z", 0.5), ("2026-10-13T12:00:00Z", 0.6), ("2026-10-20T10:30:00Z", 0.4), ("2026-10-24T15:00:00Z", 9.0)]):
    con.execute("insert into yt_videos values (?,1,?,?)", (f"v{i}", f"vídeo {i}", data)); snap("youtube", f"v{i}", "gs", 10, r)
con.commit()
m = ad.melhor_horario(db, {"dias": 365, "min_n": 3, "cada_dias": 7}, agora)
yt = m["redes"]["youtube"]
check(yt["melhores"][0]["dia"] == "segunda" and yt["melhores"][0]["faixa"] == "noite" and yt["melhores"][0]["mediana"] == 3.0, f"segunda à noite (horário de Brasília) é a melhor ({yt['melhores'][:1]})")
check(yt["piores"][0]["dia"] == "terça" and yt["piores"][0]["faixa"] == "manhã", "terça de manhã é a pior")
sab = next(x for x in yt["todas"] if x["dia"] == "sábado")
check(sab["pouca_amostra"] and sab not in yt["melhores"], "faixa com 1 post (mesmo com 9×) fica marcada como pouca amostra e fora do pódio")
check(ad.melhor_horario_devido(agora, {"melhor_horario": m}, {"cada_dias": 7}) is False and ad.melhor_horario_devido(agora + timedelta(days=8), {"melhor_horario": m}, {"cada_dias": 7}), "recalcula só depois de 7 dias")

# pós-mortem: uma vez por dia, depois das 8h
brt = agora.astimezone(ad.BRT)
check(ad.posmortem_devido(brt, {}, {"hora": 8}) and not ad.posmortem_devido(brt, {"posmortem": {"ultimo_dia": brt.date().isoformat()}}, {"hora": 8}), "pós-mortem roda uma vez por dia")
check(not ad.posmortem_devido(brt.replace(hour=7), {}, {"hora": 8}), "e não antes das 8h")

# variação do vencedor
feitos = [{"slug": "a", "razao": 2.0, "codigo": "GRA-1", "titulo": "A", "views": 900, "etiquetas": {"gancho": "g"}, "hipotese": "h"}, {"slug": "b", "razao": 3.0}, {"slug": "c", "razao": 1.1}, {"slug": "d", "razao": None}]
c = ad.variacao_candidatos(feitos, {}, {"min_razao": 1.5, "max_por_semana": 2}, agora)
check([x["slug"] for x in c] == ["b", "a"], "só acima de 1,5×, maior razão primeiro")
check([x["slug"] for x in ad.variacao_candidatos(feitos, {"variacoes": {"b": {"quando": "2026-10-01T10:00:00-03:00"}}}, {"min_razao": 1.5, "max_por_semana": 2}, agora)] == ["a"], "peça já variada não volta")
cheio = {"variacoes": {"x": {"quando": (agora - timedelta(days=1)).isoformat()}, "y": {"quando": (agora - timedelta(days=2)).isoformat()}}}
check(ad.variacao_candidatos(feitos, cheio, {"min_razao": 1.5, "max_por_semana": 2}, agora) == [], "teto de 2 por semana")
saida, entrada = td / "saida", td / "entrada"; (entrada / "a").mkdir(parents=True); (saida / "a").mkdir(parents=True)
(saida / "a" / "final_9x16.mp4").write_bytes(b"0")
check(ad.material_da_peca(saida, entrada, "a") == "saida/a/final_9x16.mp4", "sem bruto, usa o final entregue")
(entrada / "a" / "bruto.mov").write_bytes(b"0" * 10)
check(ad.material_da_peca(saida, entrada, "a") == "entrada/a/bruto.mov" and ad.material_da_peca(saida, entrada, "zzz") is None, "prefere o bruto; sem nada, None")
txt = ad.variacao_pedido(feitos[0], "entrada/a/bruto.mov")
check("DUAS variações" in txt and "final_variacao_angulo_9x16.mp4" in txt and "final_variacao_formato_9x16.mp4" in txt and "Não publique" in txt, "pedido pede duas variações, uma mudança por vez, sem publicar")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
