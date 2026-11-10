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


def garantir():
    """Cria as pastas de dados quando estão fora do projeto (modo plugin). Idempotente."""
    if HOME:
        for p in (WORKSPACE, WORKSPACE / "entrada", WORKSPACE / "saida", ESTADO, LOGS, TRILHAS):
            p.mkdir(parents=True, exist_ok=True)
    return {"raiz": str(RAIZ), "home": str(HOME) if HOME else None, "workspace": str(WORKSPACE), "estado": str(ESTADO), "logs": str(LOGS), "env": str(ENV)}


if __name__ == "__main__":
    print(json.dumps(garantir(), ensure_ascii=False, indent=1))
