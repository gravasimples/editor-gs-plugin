"""Porta única do Editor GS nos três sistemas (10/11/2026). Uso:
    python scripts/editor_gs.py instalar | subir | parar | status | abrir | caminhos | checar
No Windows, `scripts\\editor-gs.cmd <comando>` chama este arquivo com o Python certo (e instala uv + Python 3.14 na primeira vez).
No Linux/macOS os `.sh` continuam valendo (editor-gs.sh delega `instalar` ao instalar.sh); aqui `subir`/`parar` funcionam nos três.
Dados em ~/EditorGS quando a pasta existe ou EDITOR_GS_HOME está definida (modo plugin); senão dentro do projeto (desenvolvimento)."""
import json, os, shutil, subprocess, sys, time, urllib.request, zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import plataforma as plat  # noqa: E402

HOME_GS = Path(os.environ["EDITOR_GS_HOME"]).expanduser() if os.environ.get("EDITOR_GS_HOME") else ((Path.home() / "EditorGS") if (Path.home() / "EditorGS").is_dir() else None)
if os.environ.get("CLAUDE_PLUGIN_ROOT") and not HOME_GS:
    HOME_GS = Path.home() / "EditorGS"
if HOME_GS:
    os.environ["EDITOR_GS_HOME"] = str(HOME_GS)


def carregar_env():
    """Lê .env do projeto e o de ~/EditorGS (chaves já definidas no ambiente vencem)."""
    for f in [RAIZ / ".env"] + ([HOME_GS / ".env"] if HOME_GS else []):
        if f.is_file():
            for linha in f.read_text(encoding="utf-8", errors="replace").splitlines():
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                k, v = linha.split("=", 1); k = k.strip().replace("export ", ""); v = v.strip().strip('"').strip("'")
                os.environ.setdefault(k, os.path.expanduser(v))


carregar_env()
VENV = plat.venv_editor_gs()
PY = plat.python_venv(VENV)
PORTA = int(os.environ.get("EDITOR_GS_PORTA") or 3200)
HOST = os.environ.get("EDITOR_GS_HOST") or "127.0.0.1"
URL = f"http://localhost:{PORTA}"
LOGS = Path(os.environ.get("EDITOR_GS_LOGS") or (HOME_GS / "logs" if HOME_GS else RAIZ / "docs" / "logs"))
PIDFILE = LOGS / "gateway.pid"
DADOS = HOME_GS or RAIZ


def saude(timeout=2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/api/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def instalado() -> bool:
    return PY.exists() and (RAIZ / "app" / "dist").is_dir()


def ambiente_gateway() -> dict:
    env = plat.ambiente_cuda(python=PY)
    env["PYTHONUTF8"] = "1"  # Windows: console e pipes em UTF-8 (o Claude escreve stream-json em UTF-8)
    env.setdefault("EDITOR_GS_VENV", str(VENV))
    return env


def pid_gateway():
    try:
        pid = int(PIDFILE.read_text().strip())
        if plat.WINDOWS:
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, timeout=15, **plat.TEXTO_CONSOLE)
            if str(pid) in r.stdout:
                return pid
        else:
            os.kill(pid, 0); return pid
    except Exception:  # noqa: BLE001
        pass
    return plat.pid_na_porta(PORTA)


# ------------------------------------------------------------------ comandos
def parar(silencioso=False):
    pid = pid_gateway()
    if not pid:
        if not silencioso:
            print("Editor GS já estava parado.")
        return False
    try:
        plat.matar_arvore(pid)
        for _ in range(20):
            time.sleep(0.25)
            if not saude(0.5):
                break
        else:
            plat.matar_arvore(pid, forcar=True)
    except Exception as e:  # noqa: BLE001
        print(f"não consegui parar o processo {pid}: {e}")
    PIDFILE.unlink(missing_ok=True)
    if not silencioso:
        print("Editor GS parado.")
    return True


def subir():
    if not instalado():
        print(f"não instalado (venv {VENV} ou app/dist ausentes). Rode: instalar"); return 1
    parar(silencioso=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"gateway-{time.strftime('%Y-%m-%d')}.log"
    cmd = [str(PY), "-m", "uvicorn", "servico.api:app", "--host", HOST, "--port", str(PORTA), "--log-level", "info"]
    with log.open("ab") as lg:
        proc = subprocess.Popen(cmd, cwd=str(RAIZ), env=ambiente_gateway(), stdin=subprocess.DEVNULL, stdout=lg, stderr=subprocess.STDOUT, **plat.flags_segundo_plano())
    PIDFILE.write_text(str(proc.pid))
    for _ in range(60):
        time.sleep(0.5)
        if saude(1):
            print(f"Editor GS: 200  → abra {URL}"); return 0
        if proc.poll() is not None:
            break
    print(f"Editor GS não respondeu em {URL}. Veja o log: {log}"); return 1


def garantir():
    """Vigia: se o app já responde, não faz nada; senão sobe. Para a tarefa agendada que roda a cada 5 min (o processo morre sem aviso às vezes)."""
    if saude(2):
        return 0
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "vigia.log").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} gateway fora do ar (pid gravado: {pid_gateway()}); subindo de novo\n")
    return subir()


def status():
    if not instalado():
        print(f"não instalado (venv {VENV} ausente). Rode: instalar"); return 1
    if saude():
        print(f"no ar em {URL}")
        try:
            r = subprocess.run([str(PY), "-m", "servico.executor_local", "status"], cwd=str(RAIZ), capture_output=True, text=True, timeout=30, env=ambiente_gateway())
            print("\n".join(r.stdout.splitlines()[:30]))
        except Exception:  # noqa: BLE001
            pass
        return 0
    print("instalado, fora do ar. Rode: subir"); return 1


def checar():
    """Hook de início de sessão do plugin: uma linha; nunca instala nem sobe nada."""
    if not instalado():
        print("Editor GS: ainda não instalado nesta máquina. Para instalar, peça /editor-gs:instalar (uma vez; baixa Python, Node, ffmpeg e o motor de edição).")
    elif saude():
        print(f"Editor GS: instalado e no ar em {URL} (dados em {DADOS}). Ferramentas MCP editor-gs disponíveis (novo_pedido, listar_pedidos, ver_pedido, fila).")
    else:
        print(f"Editor GS: instalado, mas o app não está no ar. Para subir, peça /editor-gs:subir (abre em {URL}).")
    return 0


def abrir():
    plat.abrir_navegador(URL); print(URL); return 0


def caminhos():
    r = subprocess.run([str(PY if PY.exists() else sys.executable), str(RAIZ / "servico" / "caminhos.py")], env=ambiente_gateway())
    return r.returncode


# ------------------------------------------------------------------ instalação
def _baixar(url: str, destino: Path, rotulo: str):
    print(f"   baixando {rotulo}…", flush=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r, destino.open("wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    return destino


def _extrair_zip(zip_: Path, pasta_final: Path):
    """Extrai um zip cujo conteúdo é uma única pasta raiz e a renomeia para `pasta_final`."""
    tmp = pasta_final.with_name(pasta_final.name + "_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zip_) as z:
        z.extractall(tmp)
    sub = [p for p in tmp.iterdir() if p.is_dir()]
    shutil.rmtree(pasta_final, ignore_errors=True)
    (sub[0] if len(sub) == 1 and not any(p.is_file() for p in tmp.iterdir()) else tmp).rename(pasta_final)
    shutil.rmtree(tmp, ignore_errors=True)


def _json(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _rodar(cmd, **k):
    print("   $", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], **k)
    if r.returncode != 0:
        raise SystemExit(f"falhou (código {r.returncode}): {cmd[0]}")
    return r


def smart_app_control() -> str:
    """Estado do Smart App Control do Windows 11: 'ligado', 'avaliacao', 'desligado' ou 'desconhecido'."""
    if not plat.WINDOWS:
        return "desconhecido"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            v, _ = winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")
        return {0: "desligado", 1: "ligado", 2: "avaliacao"}.get(int(v), "desconhecido")
    except Exception:  # noqa: BLE001
        return "desconhecido"


class _Tee:
    """Espelha o que a instalação imprime num log em ~/EditorGS/logs (o comando /editor-gs:instalar acompanha por ele)."""

    def __init__(self, caminho: Path):
        self.ter = sys.stdout; self.arq = caminho.open("a", encoding="utf-8", errors="replace")

    def write(self, s):
        self.ter.write(s); self.arq.write(s); self.arq.flush()

    def flush(self):
        self.ter.flush(); self.arq.flush()


def instalar_windows():
    """Windows nativo, tudo no perfil do usuário, sem admin: ferramentas portáteis em ~/EditorGS/bin, uv + Python 3.14, venv, Node/Remotion/app.
    Observação (10/11/2026): o Smart App Control do Windows 11 bloqueia DLLs sem reputação (CTranslate2/Whisper, PyTorch) e o lançador de venv do uv.
    Por isso o venv é criado com `python -m venv` e a transcrição só funciona com o Smart App Control desligado."""
    sac = smart_app_control()
    if sac in ("ligado", "avaliacao"):
        print(f"AVISO: o Smart App Control do Windows 11 está {'ligado' if sac == 'ligado' else 'em avaliação'}. Ele bloqueia o motor de transcrição (Whisper) e o PyTorch.\n"
              "       Desligue antes de usar o app: Segurança do Windows → Controle de aplicativos e navegador → Smart App Control → Desativado (não dá para religar depois).\n"
              "       A instalação continua; a transcrição só vai funcionar depois de desligar.")
    bin_ = plat.BIN_GS; bin_.mkdir(parents=True, exist_ok=True); dl = bin_ / "_downloads"; dl.mkdir(exist_ok=True)
    print("== 1/6 ferramentas portáteis em", bin_)
    if not (bin_ / "node" / "node.exe").exists():
        v = next(x["version"] for x in _json("https://nodejs.org/dist/index.json") if x["version"].startswith("v24."))
        _extrair_zip(_baixar(f"https://nodejs.org/dist/{v}/node-{v}-win-x64.zip", dl / "node.zip", f"Node {v}"), bin_ / "node")
    if not (bin_ / "ffmpeg" / "bin" / "ffmpeg.exe").exists():
        _extrair_zip(_baixar("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", dl / "ffmpeg.zip", "ffmpeg (gyan.dev)"), bin_ / "ffmpeg")
    # rclone só para quem usa o Google Drive (EDITOR_GS_COM_DRIVE=1 ou alguma variável DRIVE_* no .env); o produto não precisa
    quer_drive = os.environ.get("EDITOR_GS_COM_DRIVE") == "1" or any(k.startswith("DRIVE_") for k in os.environ)
    if quer_drive and not (bin_ / "rclone" / "rclone.exe").exists():
        _extrair_zip(_baixar("https://downloads.rclone.org/rclone-current-windows-amd64.zip", dl / "rclone.zip", "rclone"), bin_ / "rclone")
    if not (bin_ / "git" / "cmd" / "git.exe").exists() and not shutil.which("git"):
        rel = _json("https://api.github.com/repos/git-for-windows/git/releases/latest")
        url = next(a["browser_download_url"] for a in rel["assets"] if a["name"].startswith("PortableGit-") and a["name"].endswith("64-bit.7z.exe"))
        exe = _baixar(url, dl / "PortableGit.7z.exe", "Git portátil")
        _rodar([exe, f'-o{bin_ / "git"}', "-y"])
    plat.aplicar_path()
    for t in ("node", "ffmpeg", "rclone"):
        print("  ", t, "→", shutil.which(t) or "(não instalado)")
    shutil.rmtree(dl, ignore_errors=True)  # zips baixados (≈ 0,5 GB) não servem depois de extraídos

    print("== 2/6 Python 3.14 (uv) e venv em", VENV)
    uv = Path.home() / ".local" / "bin" / "uv.exe"
    if not uv.exists():
        _rodar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://astral.sh/uv/install.ps1 | iex"])
    _rodar([uv, "python", "install", "3.14"])
    base = _rodar([uv, "python", "find", "3.14"], capture_output=True, text=True).stdout.strip()
    if not PY.exists():
        _rodar([base, "-m", "venv", "--without-pip", VENV])  # não `uv venv`: o lançador que o uv gera é barrado pelo Smart App Control
    _rodar([uv, "pip", "install", "--python", PY, "-r", RAIZ / "requirements.txt"])
    if shutil.which("nvidia-smi"):
        try:
            _rodar([uv, "pip", "install", "--python", PY, "-r", RAIZ / "requirements-cuda.txt"])
        except SystemExit:
            print("   (CUDA opcional não instalou; a transcrição usa CPU)")
    r = subprocess.run([str(PY), "-c", "import faster_whisper, fastapi, mediapipe; print('python ok')"], capture_output=True, text=True)
    print("  ", (r.stdout or r.stderr).strip().splitlines()[-1])
    if "Controle de Aplicativo" in r.stderr or "Application Control" in r.stderr or "4551" in r.stderr:
        print("   AVISO: o Smart App Control bloqueou o motor do Whisper (CTranslate2). Desligue-o em Segurança do Windows → Controle de aplicativos e navegador → Smart App Control, e rode `instalar` de novo.")

    print("== 3/6 Node, app e Remotion")
    env = plat.preparar_path()
    npm = plat.node_bin() / "npm.cmd"; npx = plat.npx()
    _rodar([npm, "install", "--no-audit", "--no-fund"], cwd=RAIZ / "app", env=env)
    _rodar([npm, "run", "build"], cwd=RAIZ / "app", env=env)
    if HOME_GS:  # modo plugin: depois do build, as dependências de desenvolvimento do app (≈ 0,1 GB) não servem para nada
        shutil.rmtree(RAIZ / "app" / "node_modules", ignore_errors=True)
    _rodar([npm, "install", "--no-audit", "--no-fund"], cwd=RAIZ / "remotion", env=env)
    _rodar([npx, "remotion", "browser", "ensure"], cwd=RAIZ / "remotion", env=env)

    print("== 4/6 pastas de trabalho, .env e .mcp.json")
    pastas_dados()

    print("== 5/6 Claude Code")
    c = shutil.which("claude")
    print("  ", c and subprocess.run([c, "--version"], capture_output=True, text=True).stdout.strip() or "AVISO: claude.exe não está no PATH. Instale: irm https://claude.ai/install.ps1 | iex  e depois  claude login")

    print("== 6/6 conferência")
    env = ambiente_gateway()
    r = subprocess.run([str(PY), "-I", "-X", "utf8", str(RAIZ / "testes" / "teste_gateway_acesso.py")], capture_output=True, text=True, env=env, cwd=str(RAIZ))
    print("  ", (r.stdout.strip().splitlines() or [r.stderr.strip()[-300:]])[-1])
    print(f"== pronto. Próximo passo: scripts\\editor-gs.cmd subir  (abre o app em {URL}; o Claude Code logado nesta máquina é o motor)")
    return 0


def pastas_dados():
    """workspace/, estado/, logs/, .env, config.local.json e o .mcp.json do workspace (com o Python do venv, válido nos três sistemas)."""
    ws = DADOS / "workspace"
    for p in ("entrada", "saida", "_trabalho", "referencias", "materiais", "clipes", "banco"):
        (ws / p).mkdir(parents=True, exist_ok=True)
    (DADOS / "trilhas").mkdir(exist_ok=True)
    if HOME_GS:
        (HOME_GS / "estado").mkdir(exist_ok=True); (HOME_GS / "logs").mkdir(exist_ok=True)
        if not (ws / "AGENTS.md").exists() and (RAIZ / "workspace" / "AGENTS.md").exists():
            shutil.copy(RAIZ / "workspace" / "AGENTS.md", ws / "AGENTS.md")
        cl = HOME_GS / "estado" / "config.local.json"
        if not cl.exists():
            cl.write_text('{\n  "executor": {"modo": "local"}\n}\n', encoding="utf-8")
    env = DADOS / ".env"
    if not env.exists():
        shutil.copy(RAIZ / ".env.exemplo", env) if (RAIZ / ".env.exemplo").exists() else env.touch()
    if "EDITOR_GS_VENV=" not in env.read_text(encoding="utf-8", errors="replace"):
        with env.open("a", encoding="utf-8") as f:
            f.write(f"EDITOR_GS_VENV={VENV}\n")
    srv = RAIZ / "mcp" / "editor-de-video"
    mcp = {"command": str(PY), "args": ["-I", "-X", "utf8", str(srv / "servidor.py")]} if plat.WINDOWS else {"command": str(srv / "servidor.sh"), "args": []}
    (ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"editor-de-video": mcp}}, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print("   dados em", DADOS)


def instalar():
    LOGS.mkdir(parents=True, exist_ok=True)
    if plat.WINDOWS:
        log = LOGS / f"instalacao-{time.strftime('%Y-%m-%d-%H%M')}.log"
        sys.stdout = _Tee(log)
        print("log desta instalação:", log)
        try:
            return instalar_windows()
        except SystemExit as e:
            print(f"instalação interrompida: {e}. Rode de novo depois de resolver (o script só refaz o que falta)."); return 1
    args = ["--plugin"] if os.environ.get("CLAUDE_PLUGIN_ROOT") else sys.argv[2:3]
    return subprocess.call(["bash", str(RAIZ / "scripts" / "instalar.sh"), *args])


def chave():
    """Ativa a chave do produto (GS1-...) nesta instalação: `editor_gs.py chave GS1-...`."""
    if len(sys.argv) < 3 or not sys.argv[2].strip():
        print("uso: editor_gs.py chave GS1-..."); return 2
    r = subprocess.run([str(PY if PY.exists() else sys.executable), "-X", "utf8", str(RAIZ / "servico" / "licenca.py"), "ativar", sys.argv[2].strip()], cwd=str(RAIZ), env=ambiente_gateway())
    if r.returncode == 0:
        print("Chave ativada. Se o app estiver no ar, recarregue a página.")
    return r.returncode


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    acoes = {"instalar": instalar, "subir": subir, "parar": lambda: (0 if parar() or True else 1), "status": status, "abrir": abrir, "caminhos": caminhos, "checar": checar, "chave": chave, "garantir": garantir}
    if cmd not in acoes:
        print("uso: editor_gs.py instalar | subir | parar | status | abrir | caminhos | checar | chave GS1-... | garantir"); return 2
    return acoes[cmd]() or 0


if __name__ == "__main__":
    sys.exit(main())
