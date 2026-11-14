"""Caminhos do Editor GS (10/11/2026). Dois modos:
- desenvolvimento (padrão): tudo dentro da pasta do projeto, como sempre foi (workspace/, servico/*.json, docs/logs, .env);
- instalado como plugin do Claude Code: o código fica na pasta do plugin (trocada a cada atualização), então o que é DADO vive em
  `EDITOR_GS_HOME` (padrão quando a variável existe: ~/EditorGS): workspace/, estado/ (índices, tokens, config.local.json), logs/, trilhas/, .env.
Variáveis mais específicas vencem: EDITOR_GS_WORKSPACE, EDITOR_GS_ESTADO, EDITOR_GS_LOGS, EDITOR_GS_TRILHAS."""
import json, os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_home = os.environ.get("EDITOR_GS_HOME") or (str(Path.home() / "EditorGS") if (Path.home() / "EditorGS").is_dir() else "")
HOME = Path(_home).expanduser() if _home else None  # ~/EditorGS existe → instalação como plugin


def _p(var, padrao_home, padrao_raiz):
    v = os.environ.get(var)
    if v:
        return Path(v).expanduser()
    return (HOME / padrao_home) if HOME else padrao_raiz


WORKSPACE = _p("EDITOR_GS_WORKSPACE", "workspace", RAIZ / "workspace")
ESTADO = _p("EDITOR_GS_ESTADO", "estado", RAIZ / "servico")  # conversas.json, pastas.json, tokens, inscrições push, automações...
LOGS = _p("EDITOR_GS_LOGS", "logs", RAIZ / "docs" / "logs")
TRILHAS = _p("EDITOR_GS_TRILHAS", "trilhas", RAIZ / "trilhas")
ENV = (HOME / ".env") if HOME else RAIZ / ".env"
CONFIG = RAIZ / "servico" / "config.json"
CONFIG_LOCAL = ESTADO / "config.local.json"  # sobrepõe chaves do config.json nesta máquina (modo, porta, agentes, chaves de acesso...)


def estado(nome: str) -> Path:
    """Arquivo de estado (JSON) desta instalação."""
    return ESTADO / nome


def config() -> dict:
    """config.json do projeto com o config.local.json da instalação por cima (chaves de primeiro nível; `executor` é mesclado)."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    if CONFIG_LOCAL.exists():
        try:
            local = json.loads(CONFIG_LOCAL.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            local = {}
        for k, v in local.items():
            if k == "executor" and isinstance(v, dict) and isinstance(cfg.get("executor"), dict):
                cfg["executor"] = {**cfg["executor"], **v}
            else:
                cfg[k] = v
    return cfg


LIGADAS = ("fluxos", "estilos")  # pastas do código que o agente lê dentro do workspace (AGENTS.md: "fluxos/ ao lado de entrada/ e saida/")


def _ligar(link: Path, alvo: Path):
    """11/11/2026 (GRA-66): workspace/fluxos e workspace/estilos apontam para as pastas do código. Sem isso o agente não achava
    fluxos/reels-padrao.md e lia uma cópia velha do backup do WSL. Windows: junção (não pede administrador); POSIX: link simbólico.
    Refaz quando o código mudou de lugar (atualização do plugin). Pasta de verdade no lugar do link não é tocada."""
    if not alvo.is_dir():
        return "sem alvo"
    try:
        if link.is_symlink() or link.is_junction():
            if Path(os.path.realpath(link)) == alvo.resolve():
                return "ok"
            os.rmdir(link) if link.is_junction() else link.unlink()  # remove só o link (rmdir numa junção não apaga o alvo)
        elif link.exists():
            return "pasta própria"
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(alvo.resolve()), str(link))
        else:
            link.symlink_to(alvo.resolve(), target_is_directory=True)
        return "criado"
    except OSError as e:
        return f"erro: {e}"


def _instrucoes() -> str:
    """13/11/2026 (GRA-1 do Thiago: "Append system prompt file not found: ...\\EditorGS\\workspace\\AGENTS.md"): numa instalação limpa ninguém
    copiava o AGENTS.md do código para o workspace de dados; nesta máquina ele tinha sido copiado à mão na migração. O do código é o oficial:
    copia quando falta ou quando o plugin atualizou (conteúdo diferente)."""
    fonte, alvo = RAIZ / "workspace" / "AGENTS.md", WORKSPACE / "AGENTS.md"
    if not fonte.is_file() or fonte.resolve() == alvo.resolve():
        return "ok" if alvo.is_file() else "sem fonte"
    try:
        novo = fonte.read_bytes()
        if alvo.is_file() and alvo.read_bytes() == novo:
            return "ok"
        estado_ = "atualizado" if alvo.is_file() else "criado"
        alvo.write_bytes(novo)
        return estado_
    except OSError as e:
        return f"erro: {e}"


def _mcp() -> str:
    """O agente só tem as ferramentas de edição (MCP editor-de-video) se o workspace tiver um .mcp.json com o Python desta máquina e o caminho
    do código atual. O do repositório traz o caminho do WSL e não vai no pacote público: gera aqui e refaz quando o caminho mudou (atualização
    do plugin troca a pasta). Outros servidores que a pessoa pôs no arquivo ficam."""
    if WORKSPACE.resolve() == (RAIZ / "workspace").resolve():
        return "modo desenvolvimento"  # o .mcp.json do repositório é o da pasta do projeto: não mexe
    from servico import plataforma
    alvo = WORKSPACE / ".mcp.json"
    quer = {"command": str(plataforma.python_editor_gs()), "args": ["-I", "-X", "utf8", str(RAIZ / "mcp" / "editor-de-video" / "servidor.py")]}
    try:
        atual = json.loads(alvo.read_text(encoding="utf-8")) if alvo.is_file() else {}
    except (OSError, ValueError):
        atual = {}
    servidores = dict(atual.get("mcpServers") or {})
    if servidores.get("editor-de-video") == quer:
        return "ok"
    servidores["editor-de-video"] = quer
    try:
        alvo.write_text(json.dumps({**atual, "mcpServers": servidores}, ensure_ascii=False, indent=4), encoding="utf-8")
        return "atualizado" if atual else "criado"
    except OSError as e:
        return f"erro: {e}"


def _marca() -> dict:
    """13/11/2026: workspace/marca/ (manual, voz) é gerada do GSI, que só existe na máquina do Raphael; no PC do Thiago o agente editava sem
    manual. Decisão do Raphael: manual e voz (sem preço nem oferta) vão no plugin em marca-padrao/ e entram aqui quando faltam ou quando o
    arquivo é uma cópia antiga do padrão. Cópia gerada pelo GSI nunca é tocada."""
    fonte, destino, out = RAIZ / "marca-padrao", WORKSPACE / "marca", {}
    if not fonte.is_dir():
        return out
    for f in sorted(fonte.glob("*.md")):
        alvo = destino / f.name
        try:
            novo = f.read_bytes()
            if alvo.is_file() and (alvo.read_bytes() == novo or not alvo.read_text(encoding="utf-8", errors="replace").startswith("<!-- marca-padrao")):
                out[f.name] = "ok" if alvo.read_bytes() == novo else "do GSI"
                continue
            destino.mkdir(parents=True, exist_ok=True)
            out[f.name] = "atualizado" if alvo.is_file() else "criado"
            alvo.write_bytes(novo)
        except OSError as e:
            out[f.name] = f"erro: {e}"
    return out


def garantir():
    """Cria as pastas de dados quando estão fora do projeto (modo plugin), liga fluxos/ e estilos/ no workspace e deixa o AGENTS.md, o
    .mcp.json e a marca padrão do agente no lugar. Idempotente."""
    if HOME:
        for p in (WORKSPACE, WORKSPACE / "entrada", WORKSPACE / "saida", ESTADO, LOGS, TRILHAS):
            p.mkdir(parents=True, exist_ok=True)
    ligadas = {n: _ligar(WORKSPACE / n, RAIZ / n) for n in LIGADAS} if WORKSPACE.is_dir() else {}
    agente = {"AGENTS.md": _instrucoes(), ".mcp.json": _mcp(), "marca": _marca()} if WORKSPACE.is_dir() else {}
    return {"raiz": str(RAIZ), "home": str(HOME) if HOME else None, "workspace": str(WORKSPACE), "estado": str(ESTADO), "logs": str(LOGS), "env": str(ENV),
            "ligadas": ligadas, "agente": agente}


if __name__ == "__main__":
    print(json.dumps(garantir(), ensure_ascii=False, indent=1))
