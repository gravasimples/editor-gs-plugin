"""Atualização automática do plugin (13/11/2026). Isolado: cache falso em pasta temporária, versão remota, comandos do claude e subida
falsos. Confere: fora do modo plugin não liga; sem versão nova não mexe; com pedido rodando espera; com fila livre pausa, atualiza, sobe a
pasta nova; erro tira a PAUSA; gateway novo tira a PAUSA da atualização e registra o histórico; PAUSA manual não é tocada.
Rodar: ~/.venvs/editor-gs/Scripts/python -I testes/teste_atualizador.py"""
import json, shutil, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import atualizador as A, caminhos as C

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-atz-"))
base = tmp / ".claude" / "plugins" / "cache" / "editor-gs" / "editor-gs"
for v in ("1.2.4", "1.2.5"):
    (base / v / ".claude-plugin").mkdir(parents=True); (base / v / "scripts").mkdir()
    (base / v / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": v}), encoding="utf-8")
C.RAIZ = base / "1.2.4"; C.ESTADO = tmp / "estado"


class Exec:
    def __init__(s): s.pasta = tmp / "executor"; s.pasta.mkdir(exist_ok=True); s.runs = []
    def rodando(s): return s.runs
    def pausada(s): return (s.pasta / "PAUSA").exists()
    def pausar(s, motivo="", por=""): (s.pasta / "PAUSA").write_text(json.dumps({"motivo": motivo}), encoding="utf-8")
    def retomar(s): (s.pasta / "PAUSA").unlink(missing_ok=True)


ex = Exec(); cmds, subiu = [], []
check(A.modo_plugin() and A.ligado({}) and not A.ligado({"atualizar_sozinho": False}), "modo plugin detectado pela pasta do cache; chave desliga")
check(not A.modo_plugin(RAIZ), "pasta do projeto não é modo plugin")
check(A.mais_nova("1.2.10", "1.2.9") and not A.mais_nova("1.2.4", "1.2.4") and not A.mais_nova("", "1.2.4"), "comparação de versão numérica")

e = A.checar(ex, _remota=lambda: "1.2.4", _rodar_=cmds.append, _subir_=subiu.append)
check(not e["disponivel"] and not cmds and not ex.pausada(), "sem versão nova não mexe")
e = A.checar(ex, _remota=lambda: (_ for _ in ()).throw(OSError("sem rede")))
check("sem rede" in e["erro"], "sem internet registra e segue")

ex.runs = [{"id": "r1"}]
e = A.checar(ex, _remota=lambda: "1.2.5", _rodar_=cmds.append, _subir_=subiu.append)
check(e["disponivel"] and "andamento" in e["aguardando"] and not cmds and not ex.pausada(), "pedido rodando: espera a fila esvaziar")
ex.runs = []
ex.pausar("manual", "Raphael")
e = A.checar(ex, _remota=lambda: "1.2.5", _rodar_=cmds.append, _subir_=subiu.append)
check("pausada" in e["aguardando"] and not cmds, "PAUSA manual: não atualiza")
ex.retomar()

e = A.checar(ex, _remota=lambda: "1.2.5", _rodar_=cmds.append, _subir_=subiu.append)
check(cmds == [["plugin", "marketplace", "update", "editor-gs"], ["plugin", "update", "editor-gs@editor-gs"]], f"roda os dois comandos ({cmds})")
check(subiu == [base / "1.2.5"] and ex.pausada() and e["aplicando"]["para"] == "1.2.5", "sobe a pasta da versão nova com a fila pausada")

C.RAIZ = base / "1.2.5"
e = A.ao_iniciar(ex)
check(not ex.pausada() and e["historico"][-1]["ok"] and not e.get("aplicando") and e["local"] == "1.2.5", "gateway novo tira a PAUSA e registra o histórico")

def falha(args): raise RuntimeError("sem permissão")
C.RAIZ = base / "1.2.4"
e = A.checar(ex, _remota=lambda: "1.2.5", _rodar_=falha, _subir_=subiu.append)
check("sem permissão" in e["erro"] and not ex.pausada(), "erro no comando tira a PAUSA e registra")
ex.pausar("manual", "Raphael"); A.ao_iniciar(ex)
check(ex.pausada(), "ao iniciar, PAUSA manual continua")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
