"""Campanhas e lançamentos e perfil vivo (03/11/2026). Arquivo de campanhas e banco SQLite sintéticos em pasta temporária. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_campanhas.py"""
import sqlite3, sys, tempfile
from datetime import date, datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import campanhas as cmp, perfil as prf

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

td = Path(tempfile.mkdtemp()); arq = td / "campanhas.json"
c = cmp.salvar({"nome": "Black 2026", "inicio": "2026-11-20", "fim": "2026-11-30", "objetivo": "aquecer", "mensagem": "gravar sem medo", "meta_pecas": "4", "redes": "instagram,youtube"}, arq)
check(c["id"] == "black-2026" and c["meta_pecas"] == 4 and c["redes"] == ["instagram", "youtube"], "cria com id do nome, meta e redes")
for ruim, msg in (({"nome": ""}, "nome vazio"), ({"nome": "X", "inicio": "2026-11-30", "fim": "2026-11-01"}, "fim antes do início"), ({"nome": "Y", "inicio": "30/11"}, "data fora do formato")):
    try:
        cmp.salvar(ruim, arq); check(False, f"recusa {msg}")
    except ValueError:
        check(True, f"recusa {msg}")
c2 = cmp.salvar({"id": "black-2026", "nome": "Black 2026", "inicio": "2026-11-20", "fim": "2026-11-30", "objetivo": "novo objetivo"}, arq)
check(len(cmp.listar_bruto(arq)) == 1 and c2["objetivo"] == "novo objetivo" and c2["criada"] == c["criada"], "editar mantém a mesma campanha")
check(cmp.situacao(c2, date(2026, 11, 10)) == "planejada" and cmp.situacao(c2, date(2026, 11, 25)) == "no ar" and cmp.situacao(c2, date(2026, 12, 2)) == "encerrada", "situação pelo período")

def linha(slug, camp=None, estado="ainda não usado", views=None, razao=None, pub=None, formato="reel"):
    return {"slug": slug, "titulo": slug.upper(), "codigo": None, "conversa": None, "etiquetas": {"campanha": camp, "formato": formato}, "estado": estado, "publicado_em": pub, "views": views, "vs_mediana": razao}
linhas = [linha("a", "Black 2026", "postado ou agendado", 1000, 1.5, "2026-11-21T10:00"), linha("b", "black 2026", "postado ou agendado", 300, 0.5, "2026-11-22"), linha("c", "black 2026", formato="carrossel"),
          linha("d", None, "postado ou agendado", 50, 0.2, "2026-11-25"), linha("e", "Orgânico", "postado ou agendado", 10, 0.1, "2026-11-26"), linha("f", None, "postado ou agendado", 9, 1, "2026-10-01")]
r = cmp.resumo(c2, linhas, date(2026, 11, 25))
check(r["n_pecas"] == 3 and r["n_publicadas"] == 2 and r["views"] == 1300 and r["razao_mediana"] == 1.0, f"soma views e mediana da razão das peças da campanha (sem diferenciar maiúsculas) ({r['views']}, {r['razao_mediana']})")
check(r["melhor"]["slug"] == "a" and r["formatos"] == {"reel": 2, "carrossel": 1}, "melhor peça e contagem por formato")
check(sorted(s["slug"] for s in r["sugestoes"]) == ["d", "e"], "sugere ligar as publicadas no período sem campanha ou como Orgânico (fora do período não)")
check(r["progresso"] is None, "sem meta, sem barra")
t = cmp.texto_pedido(c2)
check("Black 2026" in t and "novo objetivo" in t and "sem preço" in t, "texto do pedido leva a campanha e a regra do orgânico")
check("| A | reel |" in cmp.pedido_analise(r) and "sem inventar número" in cmp.pedido_analise(r), "pedido de análise com a tabela das peças")
cmp.apagar("black-2026", arq); check(cmp.listar_bruto(arq) == [], "apagar remove só o registro")

# perfil vivo
db = td / "gs.db"; con = sqlite3.connect(db)
con.executescript("""create table sources(source_id int, platform text, handle text, kind text);
create table performance_snapshots(platform text, item_id text, owner text, horizon text, computed_at text, views int, ratio_vs_format_median real, format text);
create table ig_posts(shortcode text, video_duration_s real); create table yt_videos(video_id text, duration_s real);
create table ig_post_metrics(shortcode text, captured_at text); create table yt_video_metrics(video_id text, captured_at text);
insert into sources values (1,'instagram','thiago','own'),(2,'instagram','outro','competitor');
insert into ig_post_metrics values ('x','2026-10-01T10:00:00Z'); insert into yt_video_metrics values ('y','2026-11-03T10:00:00Z');""")
for i in range(6):
    con.execute("insert into ig_posts values (?,?)", (f"curto{i}", 12)); con.execute("insert into ig_posts values (?,?)", (f"medio{i}", 45))
    con.execute("insert into performance_snapshots values ('instagram',?,'thiago','current','2026-11-03',1000,?, 'reel')", (f"curto{i}", 2.0))
    con.execute("insert into performance_snapshots values ('instagram',?,'thiago','current','2026-11-03',500,?, 'reel')", (f"medio{i}", 0.6))
    con.execute("insert into performance_snapshots values ('instagram',?,'thiago','current','2026-10-01',500,?, 'reel')", (f"curto{i}", 0.1))  # snapshot antigo não conta
con.execute("insert into performance_snapshots values ('instagram','conc','outro','current','2026-11-03',9,9,'reel')"); con.execute("insert into ig_posts values ('conc', 12)")
con.commit()
rr = prf.rende(db, [{"tipo": "erro", "rotulo": "Erro / alerta", "razao_mediana": 1.3, "medidos": 4, "pouca_amostra": True}, {"tipo": "pergunta", "rotulo": "Pergunta", "razao_mediana": 0.8, "medidos": 9, "pouca_amostra": False}], None, datetime(2026, 11, 3, 12))
faixas = {x["faixa"]: x for x in rr["duracao"]["reels"]}
check(rr["n_pecas"] == 12 and faixas["até 15 s"]["mediana"] == 2.0 and faixas["31–60 s"]["mediana"] == 0.6, "último snapshot de cada peça própria, mediana por faixa de duração (concorrente fora)")
check(any("até 15 s rendem mais" in p for p in rr["pistas"]) and any("erro / alerta" in p and "pouca amostra" in p for p in rr["pistas"]), "pistas de duração e de gancho, com aviso de pouca amostra")
check(any("Instagram paradas há 33 dias" in a for a in rr["avisos"]) and not any("YouTube" in a for a in rr["avisos"]), "avisa quando a coleta de uma rede está parada")
check("## O que rende" in prf.rende_markdown(rr) and "Pistas para calibrar" in prf.rende_markdown(rr), "seção 'O que rende' no perfil.md do Editor")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
