"""workspace/fluxos e workspace/estilos ligados às pastas do código (11/11/2026, GRA-66). Isolado em pasta temporária.
Confere: cria o link, segunda chamada não refaz, alvo novo (plugin atualizado) troca o link sem apagar o alvo antigo, pasta de verdade fica
intacta, alvo ausente não cria nada. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_caminhos_ligadas.py"""
import os, shutil, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import caminhos as C

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-ligadas-"))
v1 = tmp / "plugin-1.2" / "fluxos"; v1.mkdir(parents=True); (v1 / "reels-padrao.md").write_text("v1", encoding="utf-8")
v2 = tmp / "plugin-1.3" / "fluxos"; v2.mkdir(parents=True); (v2 / "reels-padrao.md").write_text("v2", encoding="utf-8")
ws = tmp / "workspace"; ws.mkdir()

check(C._ligar(ws / "fluxos", v1) == "criado" and (ws / "fluxos" / "reels-padrao.md").read_text(encoding="utf-8") == "v1", "cria o link e o fluxo é lido pelo workspace")
check(C._ligar(ws / "fluxos", v1) == "ok", "segunda chamada não refaz")
check(C._ligar(ws / "fluxos", v2) == "criado" and (ws / "fluxos" / "reels-padrao.md").read_text(encoding="utf-8") == "v2", "plugin em pasta nova: o link passa a apontar para ela")
check((v1 / "reels-padrao.md").exists(), "trocar o link não apaga o alvo antigo")
propria = ws / "estilos"; propria.mkdir(); (propria / "meu.json").write_text("{}", encoding="utf-8")
check(C._ligar(propria, v1) == "pasta própria" and (propria / "meu.json").exists(), "pasta de verdade no lugar do link fica intacta")
check(C._ligar(ws / "outra", tmp / "nao-existe") == "sem alvo" and not (ws / "outra").exists(), "alvo ausente não cria nada")

for p in (ws / "fluxos",):
    os.rmdir(p) if p.is_junction() else p.unlink()
shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
