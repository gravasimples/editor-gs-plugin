"""Anotações rápidas e atalho do celular. As anotações (texto, link, arquivo) ficam em workspace/anotacoes/anotacoes.json e aparecem na aba
"Anotações do celular" em Ideias; viram pedido só quando o Raphael clica. O atalho do celular é um link com token
(`/api/webhooks/compartilhar/<token>`) para o Atalho do iPhone ou o HTTP Shortcuts do Android mandarem material sem abrir o app.
Nada aqui escreve no Notion nem no GSI."""
import json, re, secrets, shutil
from datetime import datetime
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9\-]{6,40}$")
ESTADOS = ("a_fazer", "em_producao", "feita")  # ciclo próprio das ideias anotadas: A fazer → Em produção (virou pedido) → Feita


def _arq(pasta: Path):
    return pasta / "anotacoes.json"


def listar(pasta: Path):
    a = _arq(pasta)
    if not a.exists():
        return []
    return sorted(json.loads(a.read_text(encoding="utf-8")), key=lambda x: x.get("quando", ""), reverse=True)


def _gravar(pasta: Path, lista):
    pasta.mkdir(parents=True, exist_ok=True)
    _arq(pasta).write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def criar(pasta: Path, texto: str = "", arquivos: list[str] | None = None, origem: str = "app"):
    texto = (texto or "").strip()
    if not texto and not arquivos:
        raise ValueError("Anotação vazia: mande um texto, link ou arquivo.")
    links = re.findall(r"https?://\S+", texto)
    nota = {"id": f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}", "quando": datetime.now().isoformat(timespec="seconds"), "texto": texto, "links": links,
            "arquivos": arquivos or [], "origem": origem, "titulo": (texto.splitlines()[0][:80] if texto else (arquivos or ["anotação"])[0].split("/")[-1]), "status": "a_fazer", "pedido": None}
    lista = listar(pasta); lista.insert(0, nota); _gravar(pasta, lista)
    return nota


def mudar_status(pasta: Path, nid: str, status: str, pedido: str | None = None):
    """Muda a anotação de coluna (a_fazer | em_producao | feita). `pedido` guarda o link do Novo pedido/conversa quando ela vira pedido."""
    if status not in ESTADOS:
        raise ValueError(f"status inválido: {status} (use {', '.join(ESTADOS)})")
    lista = listar(pasta); nota = next((n for n in lista if n["id"] == nid), None)
    if not nota:
        raise KeyError(nid)
    nota["status"] = status; nota["mudou_em"] = datetime.now().isoformat(timespec="seconds")
    if pedido is not None:
        nota["pedido"] = pedido
    _gravar(pasta, lista)
    return nota


def apagar(pasta: Path, nid: str):
    if not ID_RE.match(nid or ""):
        raise ValueError("id inválido")
    lista = listar(pasta); nova = [n for n in lista if n["id"] != nid]
    if len(nova) == len(lista):
        raise KeyError(nid)
    for n in lista:
        if n["id"] == nid:
            d = pasta / nid
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
    _gravar(pasta, nova)
    return True


# --- atalho do celular ---------------------------------------------------------------------------

def token_atalho(arquivo: Path, novo=False):
    """Token do link secreto (gerado uma vez; `novo=True` troca e invalida o anterior)."""
    if arquivo.exists() and not novo:
        t = json.loads(arquivo.read_text(encoding="utf-8")).get("token")
        if t:
            return t
    t = secrets.token_urlsafe(18)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"token": t, "criado": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    return t


def token_valido(arquivo: Path, token: str):
    if not arquivo.exists() or not token:
        return False
    return secrets.compare_digest(json.loads(arquivo.read_text(encoding="utf-8")).get("token", ""), token)
