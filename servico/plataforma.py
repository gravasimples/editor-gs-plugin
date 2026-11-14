"""Diferenças entre Linux/macOS e Windows num lugar só (10/11/2026, migração para Windows nativo).
Tudo que antes supunha `~/.venvs/x/bin/python`, `~/.nvm`, `LD_LIBRARY_PATH`, `setsid`/`killpg` passa por aqui.
Ferramentas portáteis no Windows ficam em `~/EditorGS/bin` (ffmpeg/, node/, rclone/, git/): `preparar_path()` as põe no PATH do processo."""
import json, os, shutil, signal, subprocess, sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
TEXTO_CONSOLE = {"text": True, "encoding": "oem", "errors": "replace"} if WINDOWS else {"text": True}  # tasklist/netstat/taskkill falam na página de código OEM, não UTF-8
HOME_GS = Path(os.environ.get("EDITOR_GS_HOME") or (Path.home() / "EditorGS"))
BIN_GS = HOME_GS / "bin"  # ferramentas portáteis (só no Windows por enquanto; no Linux vêm do apt/nvm)


def exe(nome: str) -> str:
    """Nome de executável com `.exe` no Windows."""
    return f"{nome}.exe" if WINDOWS and not nome.endswith(".exe") else nome


def python_venv(venv) -> Path:
    """Interpretador de um venv: `Scripts\\python.exe` no Windows, `bin/python` no resto."""
    venv = Path(os.path.expanduser(str(venv)))
    return venv / "Scripts" / "python.exe" if WINDOWS else venv / "bin" / "python"


def exe_venv(venv, nome: str) -> Path:
    """Programa instalado num venv (yt-dlp, uvicorn...)."""
    venv = Path(os.path.expanduser(str(venv)))
    return venv / ("Scripts" if WINDOWS else "bin") / exe(nome)


def venv_editor_gs() -> Path:
    return Path(os.path.expanduser(os.environ.get("EDITOR_GS_VENV") or str(Path.home() / ".venvs" / "editor-gs")))


def python_editor_gs() -> Path:
    return python_venv(venv_editor_gs())


def python_sem_console(venv) -> Path:
    """`pythonw.exe` do venv (subsistema gráfico, sem console). NÃO serve para o gateway: filho sem console a herdar (ffprobe, node,
    claude…) ganha console novo, e com o Windows Terminal como terminal padrão cada um abre uma janela na tela (achado de 11/11/2026).
    Mantido para processos que não disparam programas de console. No POSIX devolve o python comum."""
    venv = Path(os.path.expanduser(str(venv)))
    if WINDOWS and (venv / "Scripts" / "pythonw.exe").exists():
        return venv / "Scripts" / "pythonw.exe"
    return python_venv(venv)


def pastas_bin() -> list:
    """Pastas de ferramentas portáteis que existem nesta máquina, na ordem em que entram no PATH."""
    cand = [BIN_GS / "ffmpeg" / "bin", BIN_GS / "node", BIN_GS / "rclone", BIN_GS / "git" / "cmd", BIN_GS, Path.home() / ".local" / "bin"]
    return [p for p in cand if p.is_dir()]


def preparar_path(env=None) -> dict:
    """Devolve um ambiente (cópia de `env` ou de os.environ) com as ferramentas portáteis e o Node no PATH. Idempotente."""
    e = dict(os.environ if env is None else env)
    extras = [str(p) for p in pastas_bin()]
    nb = node_bin()
    if nb and str(nb) not in extras:
        extras.insert(0, str(nb))
    atual = e.get("PATH", "")
    partes = [x for x in extras if x not in atual.split(os.pathsep)]
    if partes:
        e["PATH"] = os.pathsep.join(partes + ([atual] if atual else []))
    return e


def aplicar_path():
    """Mesma coisa, no processo atual (chamado no início do gateway e do MCP para `shutil.which` enxergar ffmpeg, rclone, claude, node)."""
    os.environ["PATH"] = preparar_path()["PATH"]


def node_bin():
    """Pasta do Node 24: EDITOR_GS_NODE_BIN, senão ~/EditorGS/bin/node, senão o node do PATH, senão a versão mais nova do nvm."""
    if os.environ.get("EDITOR_GS_NODE_BIN"):
        return Path(os.environ["EDITOR_GS_NODE_BIN"])
    if (BIN_GS / "node" / exe("node")).exists():
        return BIN_GS / "node"
    n = shutil.which("node")
    if n:
        return Path(n).resolve().parent
    vers = sorted((Path.home() / ".nvm/versions/node").glob("v*/bin"))
    return vers[-1] if vers else None


def node() -> Path:
    nb = node_bin()
    return (nb / exe("node")) if nb else Path(exe("node"))


def npx() -> str:
    """Comando do npx (no Windows é `npx.cmd`, que precisa de caminho completo para o CreateProcess)."""
    nb = node_bin()
    nome = "npx.cmd" if WINDOWS else "npx"
    return str(nb / nome) if nb else nome


def bash_bin():
    """bash para scripts `.sh` no Windows: o do Git portátil (~/EditorGS/bin/git) ou o do Git for Windows; nunca o bash.exe do System32 (é o WSL)."""
    if not WINDOWS:
        return shutil.which("bash") or "/bin/bash"
    cand = [BIN_GS / "git" / "bin" / "bash.exe", Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe", Path.home() / "AppData" / "Local" / "Programs" / "Git" / "bin" / "bash.exe"]
    g = shutil.which("git")
    if g:
        cand.insert(1, Path(g).resolve().parent.parent / "bin" / "bash.exe")
    for c in cand:
        if c.exists():
            return str(c)
    return None


def programa(nome: str) -> str:
    """Caminho de um programa do PATH. No Windows o CreateProcess só completa `.exe`: `codex`/`npx` são `.cmd` e precisam do caminho completo."""
    return shutil.which(nome) or nome


def claude_bin() -> str:
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / exe("claude"))


def ambiente_cuda(env=None, python=None) -> dict:
    """Ambiente com as bibliotecas CUDA do pip (cublas, cudnn) visíveis ao CTranslate2: LD_LIBRARY_PATH no Linux, PATH (pastas `bin`) no Windows.
    `python` é o interpretador cujo site-packages tem os pacotes nvidia-* (padrão: o atual)."""
    import sysconfig
    e = preparar_path(env)
    if python and Path(python) != Path(sys.executable):
        try:
            sp = subprocess.run([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:  # noqa: BLE001
            sp = ""
    else:
        sp = sysconfig.get_paths()["purelib"]
    if not sp:
        return e
    nv = Path(sp) / "nvidia"
    if WINDOWS:
        pastas = [str(p) for p in (nv / "cublas" / "bin", nv / "cudnn" / "bin", nv / "cuda_nvrtc" / "bin") if p.is_dir()]
        if pastas:
            e["PATH"] = os.pathsep.join(pastas + [e.get("PATH", "")])
    else:
        pastas = [str(nv / "cublas" / "lib"), str(nv / "cudnn" / "lib"), str(Path.home() / ".local/lib-chromium/usr/lib/x86_64-linux-gnu")]
        e["LD_LIBRARY_PATH"] = ":".join(pastas + ([e["LD_LIBRARY_PATH"]] if e.get("LD_LIBRARY_PATH") else []))
    return e


def registrar_dlls_cuda():
    """No processo atual (Windows): `os.add_dll_directory` para as DLLs CUDA do pip, que o Python 3.8+ não procura no PATH."""
    if not WINDOWS:
        return
    import sysconfig
    nv = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    pastas = [p for p in (nv / "cublas" / "bin", nv / "cudnn" / "bin", nv / "cuda_nvrtc" / "bin") if p.is_dir()]
    for p in pastas:
        try:
            os.add_dll_directory(str(p))
        except Exception:  # noqa: BLE001
            pass
    # o CTranslate2 carrega cublas/cudnn em tempo de execução pela busca padrão (PATH), não pelas pastas do add_dll_directory:
    # sem isto a transcrição "funciona" mas cai para CPU calada ao consumir o gerador
    atual = os.environ.get("PATH", "").split(os.pathsep)
    novas = [str(p) for p in pastas if str(p) not in atual]
    if novas:
        os.environ["PATH"] = os.pathsep.join(novas + atual)


def flags_processo_proprio() -> dict:
    """kwargs para Popen/create_subprocess_exec: o filho vira líder do próprio grupo, para `matar_arvore` derrubar ele e os netos
    (setsid no POSIX; CREATE_NEW_PROCESS_GROUP no Windows)."""
    if WINDOWS:
        # CREATE_NO_WINDOW (10/11/2026): console próprio e invisível para o filho. Sem isso ele herda (ou ganha) um console hospedado pelo
        # Windows Terminal, e quando esse host some o filho recebe CTRL_CLOSE e morre no meio (código 0xC000013A).
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


def flags_segundo_plano() -> dict:
    """kwargs para subir um processo desprendido do terminal, SEM console algum: no Windows DETACHED_PROCESS + grupo próprio; no POSIX setsid.
    Cuidado: os filhos de console desse processo ganham console novo (ver `flags_servico_console_oculto`)."""
    if WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


def flags_servico_console_oculto() -> dict:
    """kwargs para o gateway (serviço de longa duração que dispara ffprobe, ffmpeg, node, claude…): no Windows CREATE_NO_WINDOW + grupo próprio,
    sem DETACHED_PROCESS. O processo ganha um console próprio invisível num `conhost` comum (não hospedado pelo Windows Terminal, logo sem o
    CTRL_CLOSE que derrubava o gateway em 10/11/2026) e os filhos herdam esse console (sem janela nenhuma na tela, achado de 11/11/2026).
    No POSIX setsid."""
    if WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


def matar_arvore(pid: int, forcar: bool = False):
    """Encerra o processo e tudo que ele abriu. POSIX: SIGTERM/SIGKILL no grupo. Windows: taskkill /T (com /F quando `forcar`)."""
    if WINDOWS:
        cmd = ["taskkill", "/T", "/PID", str(pid)] + (["/F"] if forcar else [])
        subprocess.run(cmd, capture_output=True, timeout=30, **TEXTO_CONSOLE)
        return
    os.killpg(pid, signal.SIGKILL if forcar else signal.SIGTERM)


def descendentes(pid: int) -> list:
    """Processos abaixo de `pid` (filhos, netos…) como [{pid, ppid, cmd}], em ordem de profundidade. Vigia de ferramenta travada (11/11/2026).
    Win32_Process no Windows, `ps` no POSIX; lista vazia se a consulta falhar."""
    try:
        if WINDOWS:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"],
                               capture_output=True, timeout=30, **TEXTO_CONSOLE)
            dados = json.loads(r.stdout or "[]")
            todos = [{"pid": int(d["ProcessId"]), "ppid": int(d["ParentProcessId"] or 0), "cmd": d.get("CommandLine") or ""} for d in (dados if isinstance(dados, list) else [dados])]
        else:
            r = subprocess.run(["ps", "-eo", "pid=,ppid=,args="], capture_output=True, text=True, timeout=15)
            todos = []
            for linha in r.stdout.splitlines():
                c = linha.split(None, 2)
                if len(c) >= 2:
                    todos.append({"pid": int(c[0]), "ppid": int(c[1]), "cmd": c[2] if len(c) > 2 else ""})
    except Exception:  # noqa: BLE001
        return []
    filhos = {}
    for p in todos:
        if p["pid"] != p["ppid"]:
            filhos.setdefault(p["ppid"], []).append(p)
    out, fila = [], [int(pid)]
    while fila:
        for f in filhos.get(fila.pop(0), []):
            out.append(f); fila.append(f["pid"])
    return out


def pid_na_porta(porta: int):
    """PID do processo escutando em 127.0.0.1:porta (gateway), ou None."""
    try:
        if WINDOWS:
            r = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, timeout=15, **TEXTO_CONSOLE)
            for linha in r.stdout.splitlines():
                c = linha.split()
                if len(c) >= 5 and c[0] == "TCP" and c[1].endswith(f":{porta}") and c[3] == "LISTENING":
                    return int(c[4])
        else:
            r = subprocess.run(["ss", "-ltnp", f"sport = :{porta}"], capture_output=True, text=True, timeout=15)
            import re
            m = re.search(r"pid=(\d+)", r.stdout)
            if m:
                return int(m.group(1))
    except Exception:  # noqa: BLE001
        pass
    return None


def abrir_navegador(url: str):
    import webbrowser
    try:
        if not WINDOWS and os.environ.get("WSL_DISTRO_NAME") and shutil.which("cmd.exe"):
            subprocess.Popen(["cmd.exe", "/c", "start", "", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def processos_com(padroes: dict) -> dict:
    """Conta processos cuja linha de comando contém cada padrão (painel Operação). `ps` no POSIX, Win32_Process no Windows."""
    out = {k: 0 for k in padroes}
    try:
        if WINDOWS:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"], capture_output=True, timeout=20, **TEXTO_CONSOLE)
            linhas = r.stdout.splitlines()
        else:
            r = subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True, timeout=8)
            linhas = r.stdout.splitlines()[1:]
        for linha in linhas:
            if "ps -eo" in linha or "grep" in linha or "Win32_Process" in linha:
                continue
            for k, pat in padroes.items():
                if pat in linha:
                    out[k] += 1
    except Exception:  # noqa: BLE001
        pass
    return out


def memoria() -> dict:
    """RAM total/livre em GB e % usada; /proc/meminfo no Linux, GlobalMemoryStatusEx no Windows, vm_stat é ignorado no macOS."""
    out = {}
    try:
        if WINDOWS:
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS(); ms.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            out = {"ram_total_gb": round(ms.ullTotalPhys / 1e9, 1), "ram_livre_gb": round(ms.ullAvailPhys / 1e9, 1), "ram_usada_pct": int(ms.dwMemoryLoad)}
        else:
            mem = {}
            for linha in Path("/proc/meminfo").read_text().splitlines():
                k, v = linha.split(":", 1); mem[k] = int(v.strip().split()[0])
            out = {"ram_total_gb": round(mem["MemTotal"] / 1e6, 1), "ram_livre_gb": round(mem.get("MemAvailable", 0) / 1e6, 1), "ram_usada_pct": round(100 * (1 - mem.get("MemAvailable", 0) / max(1, mem["MemTotal"])))}
    except Exception:  # noqa: BLE001
        pass
    return out
