"""Porta única do Editor GS nos três sistemas (10/11/2026). Uso:
    python scripts/editor_gs.py instalar | subir | parar | status | abrir | caminhos | checar
No Windows, `scripts\\editor-gs.cmd <comando>` chama este arquivo com o Python certo (e instala uv + Python 3.14 na primeira vez).
No Linux/macOS os `.sh` continuam valendo (editor-gs.sh delega `instalar` ao instalar.sh); aqui `subir`/`parar` funcionam nos três.
Dados em ~/EditorGS quando a pasta existe ou EDITOR_GS_HOME está definida (modo plugin); senão dentro do projeto (desenvolvimento)."""
import json, os, re, shutil, subprocess, sys, time, urllib.request, zipfile
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


def _linha_de_comando(pid: int) -> str:
    """Linha de comando de um processo (Windows: Win32_Process; POSIX: /proc), ou '' se não der."""
    try:
        if plat.WINDOWS:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}').CommandLine"], capture_output=True, timeout=20, **plat.TEXTO_CONSOLE)
            return r.stdout or ""
        return Path(f"/proc/{int(pid)}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def pid_gateway():
    """PID do gateway DESTA instalação. Pelo arquivo de PID; senão pela porta, mas só se a linha de comando for o uvicorn do `servico.api`
    desta mesma pasta (10/11/2026: uma cópia de teste em outra pasta ou porta nunca pode derrubar a produção)."""
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
    pid = plat.pid_na_porta(PORTA)
    if not pid:
        return None
    cmd = _linha_de_comando(pid)
    if "servico.api" in cmd and (not cmd.strip() or str(RAIZ).lower() in cmd.lower() or str(PY).lower() in cmd.lower()):
        return pid
    return None


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
    r = atualizar(auto=True)
    if r is not None:
        return r
    if not instalado() and modo_plugin() and raiz_anterior():
        # o Claude Code trocou a versão do plugin por conta própria: reaproveita a instalação anterior antes de subir
        r = pos_atualizacao()
        if r:
            return r
    if not instalado():
        print(f"não instalado (venv {VENV} ou app/dist ausentes). Rode: instalar"); return 1
    parar(silencioso=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"gateway-{time.strftime('%Y-%m-%d')}.log"
    # Windows (11/11/2026): python.exe com console próprio OCULTO (CREATE_NO_WINDOW, sem DETACHED). Com DETACHED (até 10/11) o uvicorn
    # ganhava um console hospedado pelo Windows Terminal e morria com CTRL_CLOSE (0xC000013A); com pythonw (10/11 à noite) ele não tinha
    # console e cada ffprobe/ffmpeg/node que o app chama abria uma janela do Windows Terminal na tela. Console oculto resolve os dois.
    cmd = [str(PY), "-m", "uvicorn", "servico.api:app", "--host", HOST, "--port", str(PORTA), "--log-level", "info"]
    with log.open("ab") as lg:
        proc = subprocess.Popen(cmd, cwd=str(RAIZ), env=ambiente_gateway(), stdin=subprocess.DEVNULL, stdout=lg, stderr=subprocess.STDOUT, **plat.flags_servico_console_oculto())
    PIDFILE.write_text(str(proc.pid))
    for _ in range(60):
        time.sleep(0.5)
        if saude(1):
            if modo_plugin():
                registrar_raiz()
            print(f"Editor GS: 200  → abra {URL}"); return 0
        if proc.poll() is not None:
            break
    print(f"Editor GS não respondeu em {URL}. Veja o log: {log}"); return 1


def garantir():
    """Vigia: se o app já responde, não faz nada; senão sobe. Para a tarefa agendada que roda a cada 5 min.
    (10–11/11/2026: a causa das mortes "sem aviso" era o console do uvicorn hospedado pelo Windows Terminal; `subir` agora dá a ele um console oculto próprio.)"""
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
    if not instalado() and modo_plugin() and raiz_anterior():
        print("Editor GS: o plugin foi atualizado. Peça /editor-gs:subir: ele reaproveita a instalação anterior e sobe a versão nova.")
    elif not instalado():
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


# ------------------------------------------------------------------ atualização automática do plugin (12/11/2026)
# Para plugin de terceiros o Claude Code não atualiza sozinho. Aqui `subir` confere (no máximo a cada 6 h) a versão publicada; se houver nova,
# roda `claude plugin update`, leva para a pasta da versão nova o que é pesado e não mudou (remotion/node_modules com o Chromium; app/dist se o
# app não mudou), refaz só o que falta e sobe por lá. Só no modo plugin instalado: a pasta de desenvolvimento nunca se atualiza sozinha.
URL_VERSAO = "https://raw.githubusercontent.com/gravasimples/editor-gs-plugin/main/.claude-plugin/plugin.json"
INTERVALO_CHECAGEM = 6 * 3600


def versao_de(raiz: Path) -> str:
    try:
        return str(json.loads((Path(raiz) / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version") or "")
    except (OSError, ValueError):
        return ""


def _tupla(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def modo_plugin(raiz: Path | None = None) -> bool:
    partes = [p.lower() for p in Path(raiz or RAIZ).parts]
    return any(partes[i] == ".claude" and partes[i + 1] == "plugins" for i in range(len(partes) - 1))


def _registro_raiz() -> Path | None:
    return (HOME_GS / "estado" / "raiz.json") if HOME_GS else None


def registrar_raiz():
    reg = _registro_raiz()
    if reg:
        reg.parent.mkdir(parents=True, exist_ok=True)
        reg.write_text(json.dumps({"raiz": str(RAIZ), "versao": versao_de(RAIZ), "quando": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n", encoding="utf-8")


def raiz_anterior() -> Path | None:
    """Pasta da instalação que rodou por último (gravada por `subir`/`instalar`), se ainda existe e não é esta."""
    p = Path(os.environ["EDITOR_GS_RAIZ_ANTERIOR"]) if os.environ.get("EDITOR_GS_RAIZ_ANTERIOR") else None
    reg = _registro_raiz()
    if not p and reg and reg.is_file():
        try:
            p = Path(json.loads(reg.read_text(encoding="utf-8")).get("raiz") or "")
        except (OSError, ValueError):
            p = None
    if p and str(p) and p.is_dir() and p.resolve() != RAIZ.resolve():
        return p
    return None


def _hash_arvore(pasta: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    if pasta.is_file():
        h.update(pasta.read_bytes()); return h.hexdigest()
    for f in sorted(p for p in pasta.rglob("*") if p.is_file()) if pasta.is_dir() else []:
        h.update(f.relative_to(pasta).as_posix().encode()); h.update(f.read_bytes())
    return h.hexdigest()


# o que é pesado, onde fica, e o que precisa ser igual nas duas versões para poder reaproveitar
REAPROVEITAVEL = {
    "remotion/node_modules": ("remotion/package.json", "remotion/package-lock.json"),
    "app/dist": ("app/package.json", "app/src", "app/index.html"),
}


def migrar_de_raiz_anterior(anterior: Path | None) -> list:
    """Move da pasta anterior para esta o que é pesado e continua igual. Nunca sobrescreve o que já existe aqui."""
    movidos = []
    if not anterior:
        return movidos
    for rel, iguais in REAPROVEITAVEL.items():
        de, para = anterior / rel, RAIZ / rel
        if para.exists() or not de.is_dir():
            continue
        if any(_hash_arvore(anterior / c) != _hash_arvore(RAIZ / c) for c in iguais):
            print(f"   {rel}: mudou na versão nova (refaz)"); continue
        _mover_ou_copiar(de, para); movidos.append(rel); print(f"   {rel} ← versão anterior")
    return movidos


def _claude() -> str | None:
    c = shutil.which("claude")
    if c:
        return c
    for nome in ("claude.exe", "claude"):
        p = Path.home() / ".local" / "bin" / nome
        if p.exists():
            return str(p)
    return None


def localizar_raiz_nova(versao: str) -> Path | None:
    """Pasta da versão `versao` do plugin depois do `claude plugin update`: pelo `claude plugin list`; senão procurando em ~/.claude/plugins."""
    claude = _claude()
    if claude:
        try:
            out = subprocess.run([claude, "plugin", "list"], capture_output=True, timeout=60, **plat.TEXTO_CONSOLE).stdout or ""
            m = re.search(r"editor-gs@editor-gs[\s\S]*?Path:\s*(\S+)", out)
            if m and versao_de(Path(m.group(1))) == versao:
                return Path(m.group(1))
        except Exception:  # noqa: BLE001
            pass
    base = Path.home() / ".claude" / "plugins"
    for raiz, dirs, arqs in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "dist", "workspace")]
        r = Path(raiz)
        if r.name == ".claude-plugin" and "plugin.json" in arqs:
            cand = r.parent
            if (cand / "scripts" / "editor_gs.py").exists() and versao_de(cand) == versao and cand.resolve() != RAIZ.resolve():
                return cand
    return None


def atualizar(auto: bool = False, buscar_versao=None):
    """Confere a versão publicada e, se houver nova, atualiza e sobe pela versão nova (devolve o código da subida).
    Devolve None quando não fez nada (sem versão nova, fora do modo plugin, sem rede, checado há pouco): quem chamou segue normalmente."""
    if os.environ.get("EDITOR_GS_SEM_ATUALIZAR") == "1" or not modo_plugin():
        if not auto:
            print("atualização automática só vale para o plugin instalado (esta pasta é de desenvolvimento).")
        return None
    marca = (HOME_GS / "estado" / "ultima-checagem-versao") if HOME_GS else None
    if auto and marca and marca.exists() and time.time() - marca.stat().st_mtime < INTERVALO_CHECAGEM:
        return None
    try:
        remota = (buscar_versao or (lambda: str(_json(URL_VERSAO).get("version") or "")))()
    except Exception:  # noqa: BLE001
        return None
    if marca:
        marca.parent.mkdir(parents=True, exist_ok=True); marca.write_text(remota + "\n", encoding="utf-8")
    local = versao_de(RAIZ)
    if not remota or _tupla(remota) <= _tupla(local):
        if not auto:
            print(f"Editor GS já está na versão mais nova ({local}).")
        return None
    print(f"Editor GS: versão nova {local} → {remota}. Atualizando (o que já está instalado é reaproveitado)…", flush=True)
    claude = _claude()
    if not claude:
        print("   não achei o claude no PATH; seguindo com a versão atual."); return None
    for args in (["plugin", "marketplace", "update", "editor-gs"], ["plugin", "update", "editor-gs@editor-gs"]):
        try:
            subprocess.run([claude, *args], capture_output=True, timeout=600, **plat.TEXTO_CONSOLE)
        except Exception as e:  # noqa: BLE001
            print(f"   claude {' '.join(args)} falhou ({e}); seguindo com a versão atual."); return None
    nova = localizar_raiz_nova(remota)
    if not nova:
        print("   não achei a pasta da versão nova; seguindo com a atual."); return None
    parar(silencioso=True)  # o gateway antigo solta os arquivos antes de mover o Remotion
    env = dict(os.environ, EDITOR_GS_SEM_ATUALIZAR="1", EDITOR_GS_RAIZ_ANTERIOR=str(RAIZ))
    script = str(nova / "scripts" / "editor_gs.py")
    r = subprocess.run([sys.executable, "-X", "utf8", script, "pos-atualizacao"], env=env)
    if r.returncode != 0:
        print("A preparação da versão nova parou no meio. Rode /editor-gs:subir de novo (ele continua de onde parou)."); return r.returncode
    return subprocess.run([sys.executable, "-X", "utf8", script, "subir"], env=env).returncode


def pos_atualizacao():
    """Roda na pasta da versão nova: reaproveita o pesado da anterior e só instala o que falta ou mudou."""
    anterior = raiz_anterior()
    print(f"== preparando a versão {versao_de(RAIZ)}" + (f" (anterior: {anterior})" if anterior else ""))
    migrar_de_raiz_anterior(anterior)
    req_mudou = bool(anterior) and any(_hash_arvore(anterior / f) != _hash_arvore(RAIZ / f) for f in ("requirements.txt", "requirements-cuda.txt"))
    if req_mudou or not instalado() or not (RAIZ / "remotion" / "node_modules").is_dir():
        print("   " + ("bibliotecas do motor mudaram" if req_mudou else "faltam partes") + ": rodando a instalação (só o que falta)")
        return instalar()
    pastas_dados()  # o .mcp.json do workspace aponta para a pasta da versão nova
    registrar_raiz()
    print("   pronto")
    return 0


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


# ------------------------------------------------------------------ pacote pré-montado (Windows x64, 10/11/2026)
REPO_PACOTE = "gravasimples/editor-gs-plugin"
# 12/11/2026: lista das releases (não só a "latest"): uma release nova sem os zips do pacote não pode derrubar todo mundo para o caminho lento.
URL_RELEASE = f"https://api.github.com/repos/{REPO_PACOTE}/releases?per_page=20"


def escolher_asset(release: dict) -> dict:
    """Dos assets de uma release do GitHub, o zip base `editor-gs-win64-<versao>.zip` e, se houver, o `editor-gs-win64-cuda-<versao>.zip`.
    Devolve {"base": url|None, "cuda": url|None, "nome": nome do zip base, "versao": tag}. Sem zip base → base=None."""
    out = {"base": None, "cuda": None, "nome": None, "versao": str((release or {}).get("tag_name") or "")}
    for a in (release or {}).get("assets") or []:
        n = str(a.get("name") or ""); u = a.get("browser_download_url")
        if not (n.startswith("editor-gs-win64-") and n.endswith(".zip") and u):
            continue
        if n.startswith("editor-gs-win64-cuda-"):
            out["cuda"] = out["cuda"] or u
        elif not out["base"]:
            out["base"], out["nome"] = u, n
    return out


def escolher_release(dados) -> dict:
    """Da lista de releases (mais nova primeiro; aceita também uma release só), a mais nova publicada que tem o zip base do pacote.
    Rascunho e pré-lançamento ficam de fora. Nenhuma com pacote → o resultado de escolher_asset da primeira (base=None)."""
    lista = dados if isinstance(dados, list) else [dados]
    for rel in lista:
        if not rel or rel.get("draft") or rel.get("prerelease"):
            continue
        esc = escolher_asset(rel)
        if esc["base"]:
            return esc
    return escolher_asset(lista[0] if lista else None)


def verificar_pacote(pasta: Path) -> bool:
    """Pacote extraído é válido quando tem VERSAO.txt com `versao=` e o Python standalone dentro."""
    v = Path(pasta) / "VERSAO.txt"
    try:
        return v.is_file() and "versao=" in v.read_text(encoding="utf-8", errors="replace") and (Path(pasta) / "python" / "python.exe").is_file()
    except OSError:
        return False


def _baixar_progresso(url: str, destino: Path, rotulo: str) -> Path:
    """Download grande com progresso no log (MB baixados a cada ~50 MB)."""
    print(f"   baixando {rotulo}…", flush=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "editor-gs-instalador", "Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=120) as r, destino.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0); lidos = 0; marco = 0; t0 = time.time()
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco); lidos += len(bloco)
            if lidos - marco >= 50 << 20:
                marco = lidos
                print(f"   … {lidos >> 20} MB" + (f" de {total >> 20} MB" if total else "") + f" ({int(time.time() - t0)} s)", flush=True)
    print(f"   {rotulo}: {lidos >> 20} MB em {int(time.time() - t0)} s", flush=True)
    return destino


def _extrair_pacote(zip_: Path, pasta_final: Path):
    """Extrai o zip do pacote (uma pasta raiz) em `pasta_final`. tar.exe do Windows quando existe (bem mais rápido que zipfile em 25 mil arquivos)."""
    tmp = pasta_final.with_name(pasta_final.name + "_tmp")
    shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    # 12/11/2026: no Windows, sempre o tar.exe do sistema (bsdtar abre zip). Pelo Git Bash (/editor-gs:instalar) o PATH traz antes o GNU tar
    # do Git, que não abre zip: a extração falhava e a instalação caía calada no caminho lento.
    tar_sis = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
    tar = str(tar_sis) if plat.WINDOWS and tar_sis.exists() else shutil.which("tar")
    if tar:
        r = subprocess.run([tar, "-xf", str(zip_), "-C", str(tmp)], capture_output=True, **plat.TEXTO_CONSOLE)
        if r.returncode != 0:
            raise RuntimeError(f"tar falhou ({r.returncode}): {r.stderr.strip()[-300:]}")
    else:
        with zipfile.ZipFile(zip_) as z:
            z.extractall(tmp)
    sub = [p for p in tmp.iterdir() if p.is_dir()]
    shutil.rmtree(pasta_final, ignore_errors=True)
    (sub[0] if len(sub) == 1 and not any(p.is_file() for p in tmp.iterdir()) else tmp).rename(pasta_final)
    shutil.rmtree(tmp, ignore_errors=True)


def obter_pacote(home: Path, buscar_json=None, baixar=None, extrair=None):
    """Caminho rápido: baixa o pacote pré-montado da release mais nova (ou de EDITOR_GS_PACOTE_URL) e extrai em <home>/pacote.
    Devolve {"pasta": Path, "cuda": url|None, "origem": "release"|"url"|"ja_extraido"} ou None (sem pacote → o instalador segue pelo caminho antigo).
    EDITOR_GS_SEM_PACOTE=1 desliga. Nunca levanta exceção: qualquer falha vira aviso no log."""
    if os.environ.get("EDITOR_GS_SEM_PACOTE") == "1":
        print("   EDITOR_GS_SEM_PACOTE=1: sem pacote pré-montado (tudo pela rede)."); return None
    buscar_json = buscar_json or _json; baixar = baixar or _baixar_progresso; extrair = extrair or _extrair_pacote
    pasta = home / "pacote"; dl = home / "_downloads"
    if verificar_pacote(pasta):
        print(f"   pacote já extraído em {pasta} (apague a pasta para baixar de novo)."); return {"pasta": pasta, "cuda": None, "origem": "ja_extraido"}
    try:
        url = os.environ.get("EDITOR_GS_PACOTE_URL"); cuda = None; origem = "url"
        if url:
            nome = url.rsplit("/", 1)[-1].split("?")[0] or "pacote.zip"
        else:
            rel = buscar_json(URL_RELEASE); esc = escolher_release(rel); origem = "release"
            if not esc["base"]:
                print(f"   nenhum pacote Windows nas releases de {REPO_PACOTE}."); return None
            url, nome, cuda = esc["base"], esc["nome"], esc["cuda"]
            print(f"   release {esc['versao']}: {nome}")
        zip_ = dl / nome
        baixar(url, zip_, f"pacote pré-montado ({nome})")
        extrair(zip_, pasta)
        zip_.unlink(missing_ok=True)
        if not verificar_pacote(pasta):
            print("   pacote sem VERSAO.txt ou sem python\\: ignorado (caminho antigo)."); shutil.rmtree(pasta, ignore_errors=True); return None
        print("   " + (pasta / "VERSAO.txt").read_text(encoding="utf-8", errors="replace").strip().replace("\n", " | "))
        return {"pasta": pasta, "cuda": cuda, "origem": origem}
    except Exception as e:  # noqa: BLE001
        print(f"   pacote pré-montado indisponível ({type(e).__name__}: {str(e)[:200]}); seguindo pelo caminho antigo (pip/npm pela rede).")
        shutil.rmtree(pasta, ignore_errors=True)
        return None


def _mover_ou_copiar(de: Path, para: Path):
    """Mesma unidade: rename instantâneo; senão copia (robocopy multi-thread no Windows) e apaga a origem."""
    para.parent.mkdir(parents=True, exist_ok=True)
    try:
        de.rename(para); return
    except OSError:
        pass
    if plat.WINDOWS and shutil.which("robocopy"):
        r = subprocess.run(["robocopy", str(de), str(para), "/E", "/MT:16", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True, **plat.TEXTO_CONSOLE)
        if r.returncode >= 8:
            raise SystemExit(f"robocopy falhou ({r.returncode}): {de} → {para}")
    else:
        shutil.copytree(de, para, dirs_exist_ok=True)
    shutil.rmtree(de, ignore_errors=True)


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
    Caminho rápido (10/11/2026): se a release mais nova de gravasimples/editor-gs-plugin tem o pacote pré-montado (scripts/empacotar_windows.ps1),
    tudo vem dele (download + extrair + pip offline, poucos minutos); se não tem ou falha, cada etapa segue pela rede como antes. O log diz de onde veio cada parte.
    Observação (10/11/2026): o Smart App Control do Windows 11 bloqueia DLLs sem reputação (CTranslate2/Whisper, PyTorch) e o lançador de venv do uv.
    Por isso o venv é criado com `python -m venv` e a transcrição só funciona com o Smart App Control desligado."""
    sac = smart_app_control()
    if sac in ("ligado", "avaliacao"):
        print(f"AVISO: o Smart App Control do Windows 11 está {'ligado' if sac == 'ligado' else 'em avaliação'}. Ele bloqueia o motor de transcrição (Whisper) e o PyTorch.\n"
              "       Desligue antes de usar o app: Segurança do Windows → Controle de aplicativos e navegador → Smart App Control → Desativado (não dá para religar depois).\n"
              "       A instalação continua; a transcrição só vai funcionar depois de desligar.")
    bin_ = plat.BIN_GS; bin_.mkdir(parents=True, exist_ok=True); dl = bin_ / "_downloads"; dl.mkdir(exist_ok=True)
    home = HOME_GS or plat.HOME_GS
    print("== 0/6 pacote pré-montado (release mais nova de", REPO_PACOTE + ")")
    pac = obter_pacote(home)
    pasta = pac["pasta"] if pac else None
    de = lambda sub: (pasta / sub) if pasta and (pasta / sub).is_dir() else None  # noqa: E731  parte do pacote ainda disponível

    print("== 1/6 ferramentas portáteis em", bin_)
    if not (bin_ / "node" / "node.exe").exists():
        if de("node"):
            _mover_ou_copiar(de("node"), bin_ / "node"); print("   node ← pacote")
        else:
            v = next(x["version"] for x in _json("https://nodejs.org/dist/index.json") if x["version"].startswith("v24."))
            _extrair_zip(_baixar(f"https://nodejs.org/dist/{v}/node-{v}-win-x64.zip", dl / "node.zip", f"Node {v}"), bin_ / "node"); print("   node ← rede")
    if not (bin_ / "ffmpeg" / "bin" / "ffmpeg.exe").exists():
        if de("ffmpeg"):
            _mover_ou_copiar(de("ffmpeg"), bin_ / "ffmpeg"); print("   ffmpeg ← pacote")
        else:
            _extrair_zip(_baixar("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", dl / "ffmpeg.zip", "ffmpeg (gyan.dev)"), bin_ / "ffmpeg"); print("   ffmpeg ← rede")
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

    print("== 2/6 Python 3.14 e venv em", VENV)
    uv = Path.home() / ".local" / "bin" / "uv.exe"
    py_pacote = (pasta / "python" / "python.exe") if pasta else None
    wheelhouse = de("wheelhouse")
    if py_pacote and py_pacote.exists():
        base = py_pacote; print("   Python ← pacote:", base)
    else:
        if not uv.exists():
            _rodar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://astral.sh/uv/install.ps1 | iex"])
        _rodar([uv, "python", "install", "3.14"])
        base = Path(_rodar([uv, "python", "find", "3.14"], capture_output=True, text=True).stdout.strip()); print("   Python ← rede (uv):", base)
    if not PY.exists():
        _rodar([base, "-m", "venv", "--without-pip", VENV])  # não `uv venv`: o lançador que o uv gera é barrado pelo Smart App Control

    def pip_install(req: Path, offline: Path | None, rotulo: str):
        """Instala no venv: do wheelhouse (sem rede, sem resolução) quando há; senão do PyPI. uv quando existe, senão o pip do Python standalone."""
        if offline:
            print(f"   {rotulo} ← pacote (wheelhouse)")
            if uv.exists():
                _rodar([uv, "pip", "install", "--python", PY, "--no-index", "--find-links", offline, "-r", req])
            else:
                _rodar([base, "-m", "pip", "--python", PY, "install", "--no-index", "--find-links", offline, "-r", req, "--disable-pip-version-check"])
        else:
            print(f"   {rotulo} ← rede (PyPI)")
            if uv.exists():
                _rodar([uv, "pip", "install", "--python", PY, "-r", req])
            else:
                _rodar([base, "-m", "pip", "--python", PY, "install", "-r", req, "--disable-pip-version-check"])

    pip_install(RAIZ / "requirements.txt", wheelhouse, "requirements.txt")
    if wheelhouse:
        shutil.rmtree(wheelhouse, ignore_errors=True)  # instalado; as wheels (≈ 0,5 GB) não servem mais
    if shutil.which("nvidia-smi"):
        wh_cuda = None
        if pac and pac.get("cuda"):
            try:
                nome = pac["cuda"].rsplit("/", 1)[-1]
                z = _baixar_progresso(pac["cuda"], home / "_downloads" / nome, f"wheels CUDA ({nome})")
                _extrair_pacote(z, pasta / "cuda"); z.unlink(missing_ok=True)
                wh_cuda = de("cuda/wheelhouse-cuda")
            except Exception as e:  # noqa: BLE001
                print(f"   zip CUDA indisponível ({e}); instalando do PyPI")
        try:
            pip_install(RAIZ / "requirements-cuda.txt", wh_cuda, "requirements-cuda.txt (NVIDIA)")
        except SystemExit:
            print("   (CUDA opcional não instalou; a transcrição usa CPU)")
        if pasta:
            shutil.rmtree(pasta / "cuda", ignore_errors=True)
    r = subprocess.run([str(PY), "-c", "import faster_whisper, fastapi, mediapipe; print('python ok')"], capture_output=True, text=True)
    print("  ", (r.stdout or r.stderr).strip().splitlines()[-1])
    if "Controle de Aplicativo" in r.stderr or "Application Control" in r.stderr or "4551" in r.stderr:
        print("   AVISO: o Smart App Control bloqueou o motor do Whisper (CTranslate2). Desligue-o em Segurança do Windows → Controle de aplicativos e navegador → Smart App Control, e rode `instalar` de novo.")

    print("== 3/6 Node, app e Remotion")
    env = plat.preparar_path()
    npm = plat.node_bin() / "npm.cmd"; npx = plat.npx()
    if (RAIZ / "app" / "dist" / "index.html").exists():
        print("   app/dist já existe (mantido)")
    elif de("app-dist"):
        shutil.rmtree(RAIZ / "app" / "dist", ignore_errors=True); _mover_ou_copiar(de("app-dist"), RAIZ / "app" / "dist"); print("   app/dist ← pacote")
    else:
        print("   app/dist ← rede (npm install + build)")
        _rodar([npm, "install", "--no-audit", "--no-fund"], cwd=RAIZ / "app", env=env)
        _rodar([npm, "run", "build"], cwd=RAIZ / "app", env=env)
        if HOME_GS:  # modo plugin: depois do build, as dependências de desenvolvimento do app (≈ 0,1 GB) não servem para nada
            shutil.rmtree(RAIZ / "app" / "node_modules", ignore_errors=True)
    nm = RAIZ / "remotion" / "node_modules"
    if (nm / ".remotion" / "chrome-headless-shell").is_dir() and (nm / "remotion").is_dir():
        print("   remotion/node_modules já existe (mantido)")
    elif de("remotion-node_modules"):
        shutil.rmtree(nm, ignore_errors=True); _mover_ou_copiar(de("remotion-node_modules"), nm); print("   remotion/node_modules (com Chromium) ← pacote")
    else:
        print("   remotion/node_modules ← rede (npm install + remotion browser ensure)")
        _rodar([npm, "install", "--no-audit", "--no-fund"], cwd=RAIZ / "remotion", env=env)
        _rodar([npx, "remotion", "browser", "ensure"], cwd=RAIZ / "remotion", env=env)
    if pasta:
        shutil.rmtree(home / "_downloads", ignore_errors=True)
        print(f"   pacote: fica só {pasta}\\python (o venv depende dele); o resto foi movido para o lugar")

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
    if modo_plugin():
        migrar_de_raiz_anterior(raiz_anterior())
    if plat.WINDOWS:
        log = LOGS / f"instalacao-{time.strftime('%Y-%m-%d-%H%M')}.log"
        sys.stdout = _Tee(log)
        print("log desta instalação:", log)
        try:
            rc = instalar_windows()
            if rc == 0 and modo_plugin():
                registrar_raiz()
            return rc
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
    for s in (sys.stdout, sys.stderr):  # 11/11/2026: console em cp1252 derrubava o print com "→" depois do gateway já ter subido
        try:
            s.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001
            pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    acoes = {"instalar": instalar, "subir": subir, "parar": lambda: (0 if parar() or True else 1), "status": status, "abrir": abrir, "caminhos": caminhos, "checar": checar, "chave": chave, "garantir": garantir,
             "atualizar": lambda: (atualizar() or 0), "pos-atualizacao": pos_atualizacao}
    if cmd not in acoes:
        print("uso: editor_gs.py instalar | subir | parar | status | abrir | caminhos | checar | chave GS1-... | garantir | atualizar"); return 2
    return acoes[cmd]() or 0


if __name__ == "__main__":
    sys.exit(main())
