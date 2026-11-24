"""Atualização automática do Editor GS instalado como plugin (13/11/2026, pedido do Raphael: o Thiago e os testers não devem rodar comando
para receber versão nova). O auto-update do próprio Claude Code vem desligado para marketplace de terceiros, só a pessoa liga (`/plugin` →
Marketplaces), e mesmo ligado só troca os arquivos: o gateway continuaria no código velho. Aqui o próprio gateway:

1. a cada `intervalo_min` lê a versão publicada (plugin.json do repositório público) e compara com a desta pasta;
2. com versão nova e nenhum pedido rodando, segura a fila (PAUSA com motivo próprio), roda `claude plugin marketplace update` e
   `claude plugin update`, e sobe o gateway pela pasta da versão nova (`editor-gs.cmd subir`, que para este);
3. o gateway novo tira a PAUSA da atualização ao iniciar (`ao_iniciar`).
Só no modo plugin (código dentro de ~/.claude/plugins/cache). Desliga com `"atualizar_sozinho": false` no config.local.json.
Estado em estado/atualizacao.json. Erro em qualquer passo: tira a PAUSA, registra e tenta de novo no próximo intervalo."""
import json, os, re, subprocess, urllib.request
from datetime import datetime
from pathlib import Path

from servico import caminhos as cam, plataforma as plat

URL_REMOTA = "https://raw.githubusercontent.com/gravasimples/editor-gs-plugin/main/.claude-plugin/plugin.json"
PLUGIN, MARKETPLACE = "editor-gs", "editor-gs"
MOTIVO = "atualizacao automatica"


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def modo_plugin(raiz: Path = None) -> bool:
    partes = [p.lower() for p in (raiz or cam.RAIZ).resolve().parts]
    return "plugins" in partes and "cache" in partes


def ligado(cfg: dict) -> bool:
    return modo_plugin() and cfg.get("atualizar_sozinho", True) is not False


def versao_local(raiz: Path = None) -> str:
    try:
        return json.loads(((raiz or cam.RAIZ) / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version") or ""
    except (OSError, ValueError):
        return ""


def versao_remota(url: str = URL_REMOTA, timeout=15) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "editor-gs", "Cache-Control": "no-cache"}), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8")).get("version") or ""


def _num(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def mais_nova(remota: str, local: str) -> bool:
    return bool(remota) and _num(remota) > _num(local)


def estado() -> dict:
    try:
        return json.loads(cam.estado("atualizacao.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(**kw) -> dict:
    e = {**estado(), **kw}
    p = cam.estado("atualizacao.json"); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    return e


def _rodar(args, timeout=600):
    env = {**os.environ, "CLAUDE_CODE_PLUGIN_PREFER_HTTPS": "1"}  # sem chave SSH do GitHub a atualização falha sem cair para HTTPS
    env.pop("CLAUDECODE", None)
    r = subprocess.run([plat.claude_bin(), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env,
                       **plat.flags_processo_proprio())
    if r.returncode != 0:
        raise RuntimeError(f"claude {' '.join(args)}: {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout


def pasta_da_versao(versao: str, raiz: Path = None) -> Path | None:
    """O cache do Claude Code guarda uma pasta por versão: .../cache/<marketplace>/<plugin>/<versão>/."""
    p = (raiz or cam.RAIZ).resolve().parent / versao
    return p if (p / "scripts").is_dir() else None


def _subir_nova(nova: Path):
    """Sobe o gateway pela pasta nova num processo solto (o `subir` para este gateway antes de subir o outro)."""
    if plat.WINDOWS:
        cmd = ["cmd", "/c", str(nova / "scripts" / "editor-gs.cmd"), "subir"]
        base = plat.flags_processo_proprio()
        try:  # sair de um eventual Job do Agendador, que mataria o filho junto com o gateway velho
            return subprocess.Popen(cmd, cwd=str(nova), creationflags=base["creationflags"] | 0x01000000, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return subprocess.Popen(cmd, cwd=str(nova), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **base)
    return subprocess.Popen(["bash", str(nova / "scripts" / "editor-gs.sh"), "subir"], cwd=str(nova), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def checar(executor=None, cfg: dict = None, aplicar: bool = True, _remota=None, _rodar_=None, _subir_=None) -> dict:
    """Uma rodada. Devolve o estado gravado. `executor` (ExecutorLocal) dá a fila e a PAUSA; sem ele não aplica."""
    cfg = cfg or {}
    local = versao_local()
    try:
        remota = (_remota or versao_remota)()
    except Exception as e:  # noqa: BLE001  sem internet é normal: tenta no próximo intervalo
        return _gravar(checado_em=_agora(), local=local, erro=f"não consegui ler a versão publicada: {e}"[:300])
    e = _gravar(checado_em=_agora(), local=local, remota=remota, erro=None, disponivel=mais_nova(remota, local))
    if not e["disponivel"] or not aplicar or executor is None:
        return e
    if executor.rodando():
        return _gravar(aguardando="pedido em andamento; atualizo quando a fila esvaziar")
    if executor.pausada():
        return _gravar(aguardando="fila pausada à mão; atualizo quando retomar")
    rodar = _rodar_ or _rodar
    executor.pausar(MOTIVO, "Editor GS")
    try:
        if executor.rodando():  # um pedido começou entre a checagem e a PAUSA
            executor.retomar(); return _gravar(aguardando="pedido começou agora; tento no próximo intervalo")
        rodar(["plugin", "marketplace", "update", MARKETPLACE])
        rodar(["plugin", "update", f"{PLUGIN}@{MARKETPLACE}"])
        nova = pasta_da_versao(remota)
        if not nova:
            raise RuntimeError(f"atualizei, mas não achei a pasta da versão {remota} ao lado de {cam.RAIZ}")
        _gravar(aplicando={"de": local, "para": remota, "quando": _agora(), "pasta": str(nova)}, aguardando=None)
        (_subir_ or _subir_nova)(nova)
        return estado()
    except Exception as ex:  # noqa: BLE001
        executor.retomar()
        return _gravar(erro=str(ex)[:400], aguardando=None)


def ao_iniciar(executor=None) -> dict:
    """Gateway novo: tira a PAUSA que a atualização pôs e registra a versão que subiu."""
    e = estado(); ap = e.get("aplicando")
    if executor is not None and executor.pausada():
        try:
            motivo = json.loads((executor.pasta / "PAUSA").read_text(encoding="utf-8")).get("motivo")
        except (OSError, ValueError):
            motivo = None
        if motivo == MOTIVO:
            executor.retomar()
    if ap:
        ok = versao_local() == ap.get("para")
        hist = (e.get("historico") or [])[-19:] + [{**ap, "subiu_em": _agora(), "ok": ok}]
        return _gravar(aplicando=None, historico=hist, local=versao_local(), disponivel=False if ok else e.get("disponivel"),
                       erro=None if ok else f"subi a {versao_local()} em vez da {ap.get('para')}")
    return e
