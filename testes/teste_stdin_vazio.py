"""stdin vazio por padrão (11/11/2026, GRA-66): filho chamado pelas ferramentas não herda o stdin do processo (no MCP, o canal com o Claude).
Reproduz a trava: um processo pai com stdin aberto e nunca fechado chama, pelo util.rodar, um filho que lê o stdin até o fim.
Sem a correção o filho espera para sempre; com ela recebe EOF na hora. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_stdin_vazio.py"""
import subprocess, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

PAI = f"""
import sys; sys.path.insert(0, {str(RAIZ / 'mcp' / 'editor-de-video')!r})
from editor_video.util import rodar
r = rodar([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"], timeout=15)
print("FILHO", r.stdout.strip())
r2 = rodar.__globals__["subprocess"].run([sys.executable, "-c", "import sys; print(sys.stdin.read())"], input="abc", capture_output=True, text=True, timeout=15)
print("INPUT", r2.stdout.strip())
"""
t0 = time.time()
p = subprocess.Popen([sys.executable, "-I", "-c", PAI], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
# o stdin do pai fica aberto (como o canal do MCP): só lemos a saída
try:
    out = p.stdout.read(); err = p.stderr.read(); p.wait(40)
except Exception as e:  # noqa: BLE001
    p.kill(); out, err = "", str(e)
dt = time.time() - t0
check("FILHO 0" in out, f"filho que lê o stdin recebe EOF na hora ({dt:.1f} s){'' if 'FILHO 0' in out else ' · ' + err[-300:]}")
check("INPUT abc" in out, "subprocess.run(input=...) continua mandando o texto ao filho")
check(dt < 30, "sem esperar o tempo-limite")
p.stdin.close()

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
