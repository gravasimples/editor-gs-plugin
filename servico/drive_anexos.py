"""Anexar arquivos do Google Drive no pedido e na conversa (06/11/2026, como no Máquina): navegar pastas e escolher arquivos.
Só leitura no Drive: `rclone lsjson` (uma pasta por vez) e `rclone copyto` para `entrada/<slug>/`. Nada é renomeado, movido ou apagado lá.

Raízes em DRIVE_ANEXOS no .env: "Rótulo=remote:caminho;Outro=remote2:" (padrão: a Central pelo primeiro remote que existir, gsp2 → gsp → gs)."""
import json, os, re, subprocess
from pathlib import Path

EXT = {"video": {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mts"}, "audio": {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac"},
       "imagem": {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif", ".svg", ".arw"}, "pdf": {".pdf"}}
MAX_ITENS = 10
_CENTRAL = [("gsp2", "gsp2:"), ("gsp", "gsp:"), ("gs", "gs:Grava Simples - Central")]


class ErroDrive(Exception):
    pass


def tipo(nome: str) -> str:
    e = Path(nome).suffix.lower()
    return next((t for t, s in EXT.items() if e in s), "outro")


def _remotes(rclone: str) -> set:
    try:
        r = subprocess.run([rclone, "listremotes"], capture_output=True, text=True, timeout=20)
        return {l.strip().rstrip(":") for l in r.stdout.splitlines() if l.strip()}
    except Exception:  # noqa: BLE001
        return set()


def raizes(rclone: str, env: str | None = None) -> list[dict]:
    """Lista de {id, rotulo, remoto}. `id` é o índice (estável enquanto o .env não muda)."""
    env = (os.environ.get("DRIVE_ANEXOS", "") if env is None else env).strip()
    pares = []
    if env:
        for parte in env.split(";"):
            if "=" in parte:
                r, rem = parte.split("=", 1)
                if rem.strip():
                    pares.append((r.strip() or rem.strip(), rem.strip()))
    else:
        tem = _remotes(rclone)
        rem = next((x for n, x in _CENTRAL if n in tem), None)
        if rem:
            pares.append(("Grava Simples - Central", rem))
    return [{"id": str(i), "rotulo": r, "remoto": rem} for i, (r, rem) in enumerate(pares)]


def caminho_seguro(c: str) -> str:
    c = (c or "").strip().strip("/")
    partes = [p for p in c.split("/") if p]
    if any(p in (".", "..") for p in partes) or "\\" in c or "\x00" in c:
        raise ErroDrive("Caminho inválido.")
    return "/".join(partes)


def alvo(remoto: str, caminho: str) -> str:
    caminho = caminho_seguro(caminho)
    if not caminho:
        return remoto
    return remoto + caminho if remoto.endswith(":") else f"{remoto}/{caminho}"


def _raiz(rclone: str, raiz_id: str) -> dict:
    r = next((x for x in raizes(rclone) if x["id"] == str(raiz_id)), None)
    if not r:
        raise ErroDrive("Drive não configurado (DRIVE_ANEXOS) ou raiz desconhecida.")
    return r


def _erro_rclone(stderr: str) -> str:
    s = (stderr or "").strip()
    if "invalid_grant" in s or "token expired" in s:
        return "A conexão do rclone com o Drive expirou. No Ubuntu: rclone config reconnect <remote>: e entre na conta de novo."
    if "directory not found" in s:
        return "Pasta não encontrada no Drive."
    return s[-300:] or "rclone falhou"


def listar(rclone: str, raiz_id: str, caminho: str = "") -> dict:
    """Pastas e arquivos de uma pasta (sem descer). Arquivos do Google Docs/Planilhas/Slides vêm marcados como não baixáveis."""
    r = _raiz(rclone, raiz_id); caminho = caminho_seguro(caminho)
    p = subprocess.run([rclone, "lsjson", "--max-depth", "1", alvo(r["remoto"], caminho)], capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        raise ErroDrive(_erro_rclone(p.stderr))
    itens = json.loads(p.stdout or "[]")
    pastas = sorted(({"nome": i["Name"], "caminho": f"{caminho}/{i['Name']}".strip("/")} for i in itens if i.get("IsDir")), key=lambda x: x["nome"].lower())
    arquivos = []
    for i in itens:
        if i.get("IsDir"):
            continue
        mime = i.get("MimeType") or ""
        arquivos.append({"nome": i["Name"], "caminho": f"{caminho}/{i['Name']}".strip("/"), "tipo": tipo(i["Name"]), "tamanho_mb": round(max(0, i.get("Size") or 0) / 1e6, 1),
                         "modificado": i.get("ModTime"), "baixavel": not mime.startswith("application/vnd.google-apps")})
    arquivos.sort(key=lambda x: x["modificado"] or "", reverse=True)
    return {"raiz": r["id"], "rotulo": r["rotulo"], "caminho": caminho, "pastas": pastas, "arquivos": arquivos}


def selecao(bruto: str) -> list[dict]:
    """Campo `drive` do formulário: JSON [{raiz, caminho}]. Valida e limita a MAX_ITENS."""
    if not (bruto or "").strip():
        return []
    try:
        lst = json.loads(bruto)
    except ValueError:
        raise ErroDrive("Seleção do Drive inválida.")
    if not isinstance(lst, list):
        raise ErroDrive("Seleção do Drive inválida.")
    if len(lst) > MAX_ITENS:
        raise ErroDrive(f"No máximo {MAX_ITENS} arquivos do Drive por vez.")
    out = []
    for it in lst:
        if not isinstance(it, dict) or not caminho_seguro(str(it.get("caminho", ""))):
            raise ErroDrive("Seleção do Drive inválida.")
        out.append({"raiz": str(it.get("raiz", "0")), "caminho": caminho_seguro(str(it["caminho"]))})
    return out


def nomes_destino(sel: list[dict], pasta: Path) -> list[str]:
    """Nome local de cada item (saneado como os uploads), sem sobrescrever o que já está na pasta nem repetir dentro da seleção."""
    usados = {p.name for p in pasta.iterdir()} if pasta.is_dir() else set(); out = []
    for it in sel:
        base = re.sub(r"[^\w.\-]+", "_", it["caminho"].rsplit("/", 1)[-1]) or "arquivo"
        nome, k = base, 2
        while nome in usados:
            stem, suf = os.path.splitext(base); nome = f"{stem}-{k}{suf}"; k += 1
        usados.add(nome); out.append(nome)
    return out


def baixar(rclone: str, it: dict, destino: Path) -> Path:
    r = _raiz(rclone, it["raiz"]); destino.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run([rclone, "copyto", alvo(r["remoto"], it["caminho"]), str(destino)], capture_output=True, text=True, timeout=3 * 3600)
    if p.returncode != 0 or not destino.exists():
        raise ErroDrive(_erro_rclone(p.stderr) if p.returncode != 0 else "O arquivo não chegou.")
    return destino
