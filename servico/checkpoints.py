"""Checkpoints da pasta de entrega (10/11/2026, ideia 1 da pesquisa de referências, inspirada no Descript): antes de cada rodada do agente
numa conversa, o executor tira uma foto de `saida/<slug>/` em `saida/<slug>/_checkpoints/<n>-<timestamp>/`: manifesto JSON (arquivos, tamanho,
mtime) + cópia dos arquivos pequenos (json, srt, ass, md, png...) e hardlink dos grandes (vídeo, áudio; cópia se o hardlink falhar).
No máximo `MAXIMO` por conversa (o mais velho sai). "Desfazer" devolve a pasta ao estado de um checkpoint: antes, o estado atual vira um
checkpoint novo, para o desfazer ser desfazível. Pastas `_checkpoints/`, `_trabalho/` e `trabalho/` nunca entram na foto.

Limite conhecido do hardlink: se uma ferramenta regravar o vídeo NO MESMO caminho (abrir e truncar em vez de escrever um temporário e
renomear), a cópia do checkpoint muda junto, porque é o mesmo arquivo em disco. Os arquivos pequenos são sempre cópia de verdade."""
import filecmp, json, os, shutil
from datetime import datetime
from pathlib import Path

PASTA = "_checkpoints"
MAXIMO = 5
IGNORAR = {PASTA, "_trabalho", "trabalho"}
COPIAR = {".json", ".srt", ".ass", ".vtt", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".pptx", ".pdf", ".csv"}
LIMITE_COPIA = 5 * 1024 * 1024  # abaixo disto copia mesmo sem estar na lista (hardlink só vale a pena em arquivo grande)


def _agora():
    return datetime.now()


def _arquivos(pasta: Path):
    """Arquivos da entrega (caminho relativo posix → Path), fora das pastas ignoradas e dos arquivos ocultos."""
    out = {}
    if not pasta.is_dir():
        return out
    for p in sorted(pasta.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(pasta)
        if any(x in IGNORAR or x.startswith(".") for x in rel.parts[:-1]) or p.name.startswith("."):
            continue
        out[rel.as_posix()] = p
    return out


def _n_de(nome: str):
    try:
        return int(nome.split("-", 1)[0])
    except ValueError:
        return None


def _manifesto(d: Path):
    try:
        return json.loads((d / "manifesto.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _resumo(n_arq: int, total: int):
    mb = total / 1e6
    tam = f"{mb:.0f} MB" if mb >= 10 else f"{mb:.1f} MB" if mb >= 1 else f"{total / 1e3:.0f} KB"
    return f"{n_arq} arquivo{'s' if n_arq != 1 else ''}, {tam}"


def listar(pasta: Path):
    """Checkpoints de uma pasta de entrega, do mais novo ao mais velho: n, quando, rodada, motivo, arquivos, bytes, resumo."""
    raiz = pasta / PASTA
    if not raiz.is_dir():
        return []
    out = []
    for d in raiz.iterdir():
        if not d.is_dir() or _n_de(d.name) is None:
            continue
        m = _manifesto(d)
        if not m:
            continue
        out.append({"n": m["n"], "quando": m["quando"], "rodada": m.get("rodada"), "motivo": m.get("motivo"), "arquivos": len(m["arquivos"]),
                    "bytes": m.get("bytes", 0), "resumo": _resumo(len(m["arquivos"]), m.get("bytes", 0)), "pasta": f"{PASTA}/{d.name}"})
    out.sort(key=lambda x: -x["n"])
    return out


def _guardar(origem: Path, destino: Path):
    """Cópia para arquivos pequenos; hardlink para os grandes (cópia se o sistema de arquivos recusar). Devolve o modo usado."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.suffix.lower() in COPIAR or origem.stat().st_size <= LIMITE_COPIA:
        shutil.copy2(origem, destino); return "copia"
    try:
        os.link(origem, destino); return "hardlink"
    except OSError:
        shutil.copy2(origem, destino); return "copia"


def tirar(pasta: Path, rodada=None, motivo="antes da rodada", preservar=None, maximo=MAXIMO):
    """Tira um checkpoint da pasta de entrega. Pasta inexistente → None (não há a que voltar). Pasta vazia vale (desfazer apaga o que vier).
    Depois, mantém só os `maximo` mais novos, sem nunca apagar `preservar` (n de um checkpoint que vai ser restaurado em seguida)."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return None
    raiz = pasta / PASTA; raiz.mkdir(exist_ok=True)
    n = max([_n_de(d.name) or 0 for d in raiz.iterdir() if d.is_dir()] or [0]) + 1
    agora = _agora()
    d = raiz / f"{n}-{agora:%Y%m%d-%H%M%S}"
    if d.exists():  # dois checkpoints no mesmo segundo
        d = raiz / f"{n}-{agora:%Y%m%d-%H%M%S}-{agora.microsecond // 1000:03d}"
    d.mkdir(parents=True)
    itens, total = [], 0
    for rel, p in _arquivos(pasta).items():
        st = p.stat()
        modo = _guardar(p, d / rel)
        itens.append({"caminho": rel, "tamanho": st.st_size, "mtime": st.st_mtime, "modo": modo}); total += st.st_size
    m = {"n": n, "quando": agora.isoformat(timespec="seconds"), "rodada": rodada, "motivo": motivo, "arquivos": itens, "bytes": total}
    (d / "manifesto.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    podar(pasta, maximo=maximo, preservar=preservar)
    return {**{k: v for k, v in m.items() if k != "arquivos"}, "arquivos": len(itens), "resumo": _resumo(len(itens), total), "pasta": f"{PASTA}/{d.name}"}


def podar(pasta: Path, maximo=MAXIMO, preservar=None):
    """Apaga os checkpoints mais velhos além de `maximo` (nunca o `preservar`). Devolve os n apagados."""
    raiz = Path(pasta) / PASTA
    if not raiz.is_dir():
        return []
    dirs = sorted((d for d in raiz.iterdir() if d.is_dir() and _n_de(d.name) is not None), key=lambda d: _n_de(d.name))
    apagados = []
    while len(dirs) > maximo:
        alvo = next((d for d in dirs if _n_de(d.name) != preservar), None)
        if alvo is None:
            break
        shutil.rmtree(alvo, ignore_errors=True); apagados.append(_n_de(alvo.name)); dirs.remove(alvo)
    return apagados


def _mesmo_arquivo(a: Path, b: Path):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _igual(origem: Path, destino: Path, it: dict):
    """O arquivo atual já é o do checkpoint? Mesmo arquivo em disco (hardlink), ou conteúdo igual (pequenos), ou tamanho e mtime iguais (grandes)."""
    if _mesmo_arquivo(origem, destino):
        return True
    st = destino.stat()
    if st.st_size != it["tamanho"]:
        return False
    if st.st_size <= LIMITE_COPIA:
        return filecmp.cmp(origem, destino, shallow=False)
    return abs(st.st_mtime - it["mtime"]) < 0.001


def restaurar(pasta: Path, n=None):
    """Volta a pasta ao estado do checkpoint `n` (sem n: o mais novo). Antes, o estado atual vira um checkpoint novo (motivo "antes de desfazer").
    Arquivos do manifesto são copiados de volta; arquivos que existem agora e não existiam no checkpoint são apagados; pastas ignoradas ficam.
    Devolve {"n", "quando", "rodada", "restaurados", "apagados", "iguais", "faltando", "checkpoint_novo"} ou levanta ValueError/KeyError."""
    pasta = Path(pasta)
    lista = listar(pasta)
    if not lista:
        raise ValueError("Esta entrega ainda não tem checkpoint para voltar.")
    alvo = lista[0] if n is None else next((c for c in lista if c["n"] == int(n)), None)
    if alvo is None:
        raise KeyError(f"Checkpoint {n} não existe (há: {', '.join(str(c['n']) for c in lista)}).")
    d = pasta / alvo["pasta"]; m = _manifesto(d)
    novo = tirar(pasta, rodada=None, motivo=f"antes de desfazer (voltar ao {alvo['n']})", preservar=alvo["n"])
    atuais = _arquivos(pasta)
    restaurados, iguais, faltando = [], [], []
    for it in m["arquivos"]:
        rel = it["caminho"]; origem = d / rel; destino = pasta / rel
        if not origem.is_file():
            faltando.append(rel); continue
        if destino.is_file() and _igual(origem, destino, it):
            iguais.append(rel); continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            destino.unlink()  # nunca truncar: o destino pode ser hardlink da cópia de outro checkpoint
        shutil.copy2(origem, destino); restaurados.append(rel)
    apagados = []
    no_manifesto = {it["caminho"] for it in m["arquivos"]}
    for rel, p in atuais.items():
        if rel not in no_manifesto:
            try:
                p.unlink(); apagados.append(rel)
            except OSError:
                pass
    return {"n": alvo["n"], "quando": alvo["quando"], "rodada": alvo.get("rodada"), "restaurados": restaurados, "apagados": apagados, "iguais": iguais, "faltando": faltando, "checkpoint_novo": novo}
