"""Canva Connect (API oficial) para o Editor GS: OAuth PKCE uma vez, depois importa o PPTX/PDF do carrossel e devolve o link de edição.
Credenciais em .env: CANVA_CLIENT_ID e CANVA_CLIENT_SECRET (integração criada em canva.com/developers). Tokens em servico/canva_token.json (fora do git)."""
import base64, hashlib, json, os, secrets, time
from pathlib import Path
import httpx

AUTORIZAR = "https://www.canva.com/api/oauth/authorize"
TOKEN = "https://api.canva.com/rest/v1/oauth/token"
API = "https://api.canva.com/rest/v1"
ESCOPOS = "design:content:write design:meta:read"
from servico import caminhos as _cam
ARQ_TOKEN = _cam.estado("canva_token.json")
PENDENTES: dict[str, str] = {}  # state -> code_verifier


class ErroCanva(Exception):
    pass


def credenciais():
    return os.environ.get("CANVA_CLIENT_ID", "").strip(), os.environ.get("CANVA_CLIENT_SECRET", "").strip()


def _ler_token():
    return json.loads(ARQ_TOKEN.read_text(encoding="utf-8")) if ARQ_TOKEN.exists() else None


def _gravar_token(d: dict):
    d["obtido_em"] = time.time(); ARQ_TOKEN.write_text(json.dumps(d), encoding="utf-8")
    try:
        ARQ_TOKEN.chmod(0o600)
    except Exception:
        pass
    return d


def estado(redirect_uri: str):
    cid, sec = credenciais(); tok = _ler_token()
    pend = []
    if not cid or not sec:
        pend.append("Faltam CANVA_CLIENT_ID e CANVA_CLIENT_SECRET no .env (criar a integração em canva.com/developers; ver docs/CANVA-CONNECT.md)")
    return {"configurado": bool(cid and sec), "conectado": bool(tok and tok.get("refresh_token")), "redirect_uri": redirect_uri, "escopos": ESCOPOS, "pendencias": pend,
            "token_obtido_em": tok.get("obtido_em") if tok else None}


def url_autorizacao(redirect_uri: str):
    cid, _ = credenciais()
    if not cid:
        raise ErroCanva("CANVA_CLIENT_ID ausente.")
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16); PENDENTES[state] = verifier
    q = {"client_id": cid, "response_type": "code", "scope": ESCOPOS, "code_challenge": challenge, "code_challenge_method": "S256", "state": state, "redirect_uri": redirect_uri}
    from urllib.parse import urlencode
    return AUTORIZAR + "?" + urlencode(q)


def _basic():
    cid, sec = credenciais(); return "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode()


def trocar_codigo(code: str, state: str, redirect_uri: str, transport=None):
    verifier = PENDENTES.pop(state, None)
    if not verifier:
        raise ErroCanva("state desconhecido ou expirado: comece a conexão de novo.")
    r = httpx.Client(transport=transport, timeout=30).post(TOKEN, headers={"Authorization": _basic(), "Content-Type": "application/x-www-form-urlencoded"},
                                                            data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier, "redirect_uri": redirect_uri})
    if r.status_code >= 400:
        raise ErroCanva(f"Canva token {r.status_code}: {r.text[:300]}")
    return _gravar_token(r.json())


def token_valido(transport=None):
    tok = _ler_token()
    if not tok:
        raise ErroCanva("Canva não conectado: clique em Conectar Canva.")
    if time.time() - tok.get("obtido_em", 0) < tok.get("expires_in", 14400) - 120:
        return tok["access_token"]
    r = httpx.Client(transport=transport, timeout=30).post(TOKEN, headers={"Authorization": _basic(), "Content-Type": "application/x-www-form-urlencoded"},
                                                            data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    if r.status_code >= 400:
        raise ErroCanva(f"Canva refresh {r.status_code}: {r.text[:200]} (reconecte o Canva)")
    return _gravar_token(r.json())["access_token"]


def importar(arquivo: Path, titulo: str, transport=None, esperar_s=90):
    """POST /imports com o binário (PPTX ou PDF) e espera o job; devolve design id e urls (edit_url vale 30 dias)."""
    arquivo = Path(arquivo)
    if not arquivo.exists():
        raise ErroCanva(f"Arquivo não encontrado: {arquivo}")
    mime = {".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pdf": "application/pdf"}.get(arquivo.suffix.lower(), "application/octet-stream")
    tok = token_valido(transport)
    meta = base64.b64encode(json.dumps({"title_base64": base64.b64encode(titulo[:50].encode()).decode(), "mime_type": mime}).encode()).decode()
    c = httpx.Client(transport=transport, timeout=300)
    with arquivo.open("rb") as f:
        r = c.post(f"{API}/imports", headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/octet-stream", "Import-Metadata": json.dumps({"title_base64": base64.b64encode(titulo[:50].encode()).decode(), "mime_type": mime})}, content=f.read())
    if r.status_code >= 400:
        raise ErroCanva(f"Canva import {r.status_code}: {r.text[:300]}")
    job = r.json().get("job", {}); jid = job.get("id"); t0 = time.time()
    while job.get("status") == "in_progress" and time.time() - t0 < esperar_s:
        time.sleep(2)
        rr = c.get(f"{API}/imports/{jid}", headers={"Authorization": f"Bearer {tok}"})
        if rr.status_code >= 400:
            raise ErroCanva(f"Canva job {rr.status_code}: {rr.text[:200]}")
        job = rr.json().get("job", {})
    if job.get("status") != "success":
        raise ErroCanva(f"Importação não concluiu: {job.get('status')} {json.dumps(job.get('error') or {})[:200]}")
    d = (job.get("result") or {}).get("designs", [{}])[0]
    return {"design_id": d.get("id"), "edit_url": (d.get("urls") or {}).get("edit_url"), "view_url": (d.get("urls") or {}).get("view_url"), "titulo": titulo, "arquivo": arquivo.name, "quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "job_id": jid}
