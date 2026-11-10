"""Materiais da empresa no Google Drive (logo, fotos, takes, prints) disponíveis para o Editor:
espelho só leitura em workspace/materiais/ via rclone (remote `gs:`), índice em materiais/INDICE.md, e busca por link do Drive.
Nada é apagado no Drive; o espelho é refeito a cada sincronização."""
import json, os, re, subprocess
from datetime import datetime
from pathlib import Path
from servico import publicar as pub

EXT_VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4a", ".mp3", ".wav"}
EXT_IMG = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
ID_RE = re.compile(r"(?:/d/|/folders/|id=)([A-Za-z0-9_\-]{10,})")


class ErroMateriais(Exception):
    pass


def origem():
    return os.environ.get("DRIVE_MATERIAIS", "").strip()


def estado(pasta: Path):
    est = pub.drive_estado(); o = origem()
    pend = list(est["pendencias"]) if not est["configurado"] else []
    if not o:
        pend.append("DRIVE_MATERIAIS vazio no .env (ex.: gs:10. Mídias/Materiais do Editor)")
    idx = pasta / "indice.json"
    info = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    return {"configurado": bool(o) and est["configurado"], "origem": o, "pendencias": pend, "ultima_sincronizacao": info.get("quando"), "n_arquivos": info.get("n", 0), "pasta": str(pasta)}


def _ffprobe_dur(p: Path):
    try:
        r = subprocess.run([pub.shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 1) if r.stdout.strip() else None
    except Exception:
        return None


def indexar(pasta: Path):
    """Escreve materiais/INDICE.md e indice.json com cada arquivo, tipo, tamanho e duração, para o Editor consultar."""
    pasta.mkdir(parents=True, exist_ok=True); itens = []
    for p in sorted(pasta.rglob("*")):
        if not p.is_file() or p.name.startswith(".") or p.name in ("INDICE.md", "indice.json"):
            continue
        e = p.suffix.lower(); tipo = "video" if e in EXT_VIDEO else "imagem" if e in EXT_IMG else "arquivo"
        itens.append({"caminho": p.relative_to(pasta).as_posix(), "tipo": tipo, "tamanho_mb": round(p.stat().st_size / 1e6, 1), "duracao_s": _ffprobe_dur(p) if tipo == "video" else None, "modificado": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")})
    quando = datetime.now().isoformat(timespec="seconds")
    (pasta / "indice.json").write_text(json.dumps({"quando": quando, "n": len(itens), "itens": itens}, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# Materiais da Grava Simples (espelho do Drive, só leitura)", "", f"Sincronizado em {quando}. Origem: `{origem() or '?'}`. Use os caminhos abaixo relativos a `materiais/`. Fotos e takes são reais; logo oficial em `logo/` quando existir.", ""]
    por = {}
    for it in itens:
        por.setdefault(it["caminho"].split("/")[0] if "/" in it["caminho"] else "(raiz)", []).append(it)
    for grupo, lst in por.items():
        L += [f"## {grupo}", "", "| Arquivo | Tipo | MB | Duração |", "|---|---|---|---|"]
        L += [f"| {it['caminho']} | {it['tipo']} | {it['tamanho_mb']} | {it['duracao_s'] or ''} |" for it in lst]
        L.append("")
    (pasta / "INDICE.md").write_text("\n".join(L), encoding="utf-8")
    # logo oficial: primeiro arquivo chamado logo*.png|svg vira estilos/logo.png (cópia)
    logo = next((p for p in pasta.rglob("logo*") if p.suffix.lower() in (".png", ".svg") and p.is_file()), None)
    return {"n": len(itens), "quando": quando, "logo": str(logo) if logo else None, "indice": str(pasta / "INDICE.md")}


def sincronizar(pasta: Path, estilos_dir: Path | None = None):
    """rclone sync da pasta do Drive para materiais/ (espelho) + índice + logo oficial copiado para estilos/logo.png."""
    est = estado(pasta)
    if not est["configurado"]:
        raise ErroMateriais("Drive não configurado: " + "; ".join(est["pendencias"]))
    pasta.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([pub.RCLONE, "sync", origem(), str(pasta), "--exclude", "INDICE.md", "--exclude", "indice.json", "--max-size", "2G", "--fast-list"], capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise ErroMateriais(f"rclone sync falhou: {r.stderr[-300:]}")
    res = indexar(pasta)
    if res["logo"] and estilos_dir:
        src = Path(res["logo"]); dst = estilos_dir / "logo.png"
        if src.suffix.lower() == ".png":
            dst.write_bytes(src.read_bytes()); res["logo_copiado"] = str(dst)
    return res


def buscar_por_link(link: str, destino: Path):
    """Baixa um arquivo ou pasta do Drive pelo link (ID) para destino/, via rclone backend copyid. Devolve os caminhos."""
    m = ID_RE.search(link or "")
    if not m:
        raise ErroMateriais("Link do Drive sem ID reconhecível.")
    est = pub.drive_estado()
    if not est["configurado"]:
        raise ErroMateriais("Drive não configurado: " + "; ".join(est["pendencias"]))
    remoto = est["destino"].split(":", 1)[0] + ":"
    destino.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([pub.RCLONE, "backend", "copyid", remoto, m.group(1), str(destino) + "/"], capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise ErroMateriais(f"rclone copyid falhou: {r.stderr[-300:]}")
    return {"id": m.group(1), "arquivos": [p.name for p in sorted(destino.iterdir()) if p.is_file()], "pasta": str(destino)}
