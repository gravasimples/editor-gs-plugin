"""Laboratório (13/11/2026): registro + avaliações em workspace temporário."""
import os, sys, tempfile
from pathlib import Path
TMP = Path(tempfile.mkdtemp(prefix="lab-")); os.environ["EDITOR_GS_WORKSPACE"] = str(TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from servico import novidades as nov
falhas = 0
def check(c, m):
    global falhas; print(("PASS " if c else "FAIL ") + m); falhas += 0 if c else 1
reg = nov.registro()
check(len(reg) > 0 and all({"id", "titulo", "como_testar", "onde", "data"} <= set(i) for i in reg), "registro tem os campos")
check(len({i["id"] for i in reg}) == len(reg), "ids únicos")
r = nov.listar(); check(r["para_testar"] == len(reg), "tudo começa para testar")
a = reg[0]["id"]; b = reg[1]["id"]
nov.avaliar(a, "funcionou")
try:
    nov.avaliar(b, "com_problema", ""); check(False, "problema sem nota barrado")
except ValueError:
    check(True, "problema sem nota barrado")
nov.avaliar(b, "com_problema", "travou em 40%")
r = nov.listar(); check(r["para_testar"] == len(reg) - 2 and r["com_problema"] == 1, "contagens")
check(r["itens"][-1]["id"] == a or r["itens"][-1]["estado"] in ("funcionou", "ignorado"), "funcionou vai para o fim")
check(nov.retornos()[0]["nota"] in ("travou em 40%", ""), "retornos")
check((TMP / "laboratorio" / "avaliacoes.json").is_file(), "grava no workspace")
com = next((i for i in reg if i.get("midia")), None)
if com:
    check(next(i for i in nov.listar()["itens"] if i["id"] == com["id"])["midia"] == [], "mídia ausente some da lista")
    nov.pasta_midia(com["id"]).mkdir(parents=True); (nov.pasta_midia(com["id"]) / com["midia"][0]).write_bytes(b"x")
    check(next(i for i in nov.listar()["itens"] if i["id"] == com["id"])["midia"] == [com["midia"][0]], "mídia presente aparece")
    check(nov.arquivo_midia(com["id"], "../avaliacoes.json") is None and nov.arquivo_midia("nao-existe", com["midia"][0]) is None, "mídia só do próprio item")
print(f"\n{falhas} falha(s)"); sys.exit(1 if falhas else 0)
