"""Pasta vigiada do Drive e kit de derivação (03/11/2026). Sem Drive real: listagens sintéticas. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_pasta_vigiada.py"""
import sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import pasta_vigiada as pv, clipes as clp

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

agora = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
def it(path, size=100, min_atras=10, id_=None):
    return {"Path": path, "Name": path.rsplit("/", 1)[-1], "Size": size, "ModTime": (agora - timedelta(minutes=min_atras)).isoformat().replace("+00:00", "Z"), "ID": id_ or path}

check(pv.regra_da_pasta("Kit/aula 3.mp4")["modo"] == "kit", "subpasta Kit vira kit de derivação")
check(pv.regra_da_pasta("Cortes de live/live.mp4")["modo"] == "clipador", "subpasta Cortes vira Clipador")
check(pv.regra_da_pasta("Reels Profissional/take.mov") == {"modo": "reel", "estilo": "profissional", "pasta": "Reels Profissional"}, "subpasta Profissional vira Reel nível 3")
check(pv.regra_da_pasta("Opinião/x.mp4")["estilo"] == "opiniao" and pv.regra_da_pasta("take.mp4") == {"modo": "reel", "estilo": "padrao", "pasta": ""}, "acento ignorado; raiz = Reel padrão")

est = {}
lista = [it("velho.mp4", min_atras=60 * 48), it("novo.mp4"), it("Kit/aula.mp4"), it("Kit/aula.txt"), it("foto.jpg"), it("subindo.mp4", min_atras=1)]
p1, est = pv.prontos(lista, est, agora)
check(p1 == [] and est["vistos"]["velho.mp4"]["estado"] == "ja_estavam", "primeira leitura: nada vira pedido ainda (falta a 2ª leitura) e o vídeo de 2 dias atrás fica como 'já estava'")
lista2 = [it("velho.mp4", min_atras=60 * 48), it("novo.mp4"), it("Kit/aula.mp4"), it("Kit/aula.txt"), it("foto.jpg"), it("subindo.mp4", size=300, min_atras=0)]
p2, est = pv.prontos(lista2, est, agora + timedelta(minutes=10))
nomes = sorted(x["Path"] for x in p2)
check(nomes == ["Kit/aula.mp4", "novo.mp4"], f"2ª leitura com mesmo tamanho: viram pedido só os vídeos estáveis ({nomes})")
check(next(x for x in p2 if x["Path"] == "Kit/aula.mp4")["instrucao_arquivo"] == "Kit/aula.txt", ".txt com o mesmo nome vira a instrução")
for x in p2:
    est["vistos"][x["chave"]] = {"caminho": x["Path"], "estado": "pedido", "quando": (agora + timedelta(minutes=10)).astimezone(timezone(timedelta(hours=-3))).isoformat()}
p3, est = pv.prontos(lista2, est, agora + timedelta(minutes=20))
check([x["Path"] for x in p3] == ["subindo.mp4"], "o que já virou pedido não volta; o que terminou de subir entra na leitura seguinte")
cheio = {"primeira_leitura": "x", "tamanhos": {"a.mp4": 100}, "vistos": {f"k{i}": {"estado": "pedido", "quando": "2026-11-03T10:00-03:00"} for i in range(6)}}
check(pv.prontos([it("a.mp4")], cheio, agora)[0] == [], "teto de 6 pedidos por dia")

t, r = pv.texto_pedido({"Path": "take.mp4", "regra": pv.regra_da_pasta("take.mp4")}, "", 15 * 60)
check(r["modo"] == "clipador", "vídeo de 15 min solto na pasta vai para o Clipador")
t, r = pv.texto_pedido({"Path": "Tutorial/t.mp4", "regra": pv.regra_da_pasta("Tutorial/t.mp4")}, "foca no áudio", 40)
check(r["estilo"] == "tutorial" and "foca no áudio" in t and "estilo tutorial" in t, "Reel no estilo da subpasta com a instrução do .txt")

k = clp.pedido_kit("entrada/x/aula.mp4", "aula", "erros de áudio", 9, ["reels", "stories"])
check("5 Reels" in k and "Não faça: carrossel, youtube" in k and "kit-derivacao" in k and "Não publique" in k, "pedido do kit: teto de 5 Reels, tira as peças desmarcadas, não publica")
fluxo = (RAIZ / "fluxos" / "kit-derivacao.md").read_text()
check('"kit": true' in fluxo and "final_c01_9x16.mp4" in fluxo and "newsletter" in fluxo, "fluxo do kit: marca trechos usados, nomes por corte, sem e-mail/newsletter")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
