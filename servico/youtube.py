"""YouTube direto, sem Publora: app próprio do Google (OAuth uma vez), upload resumable da entrega, capa e agendamento (publishAt).
Credenciais em .env: YT_CLIENT_ID e YT_CLIENT_SECRET (docs/YOUTUBE-APP.md). Token em servico/youtube_token.json (fora do git).
Cota da Data API: 10.000 unidades/dia; um upload custa 1.600 (≈ 6 vídeos/dia). Nada é publicado sem clique humano no app."""
import json, os, secrets, time
from pathlib import Path
from urllib.parse import urlencode
import httpx

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"
ESCOPOS = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
from servico import caminhos as _cam
ARQ_TOKEN = _cam.estado("youtube_token.json")
PENDENTES: set[str] = set()
PRIVACIDADES = ("private", "unlisted", "public")
PEDACO = 8 * 1024 * 1024


class ErroYouTube(Exception):
    pass


def credenciais():
    return os.environ.get("YT_CLIENT_ID", "").strip(), os.environ.get("YT_CLIENT_SECRET", "").strip()


def _ler_token():
    try:
        return json.loads(ARQ_TOKEN.read_text(encoding="utf-8")) if ARQ_TOKEN.exists() else None
    except Exception:
        return None


def _gravar_token(d: dict):
    ant = _ler_token() or {}
    if "refresh_token" not in d and ant.get("refresh_token"):
        d["refresh_token"] = ant["refresh_token"]  # o refresh do Google não vem de novo
    if ant.get("canal") and "canal" not in d:
        d["canal"] = ant["canal"]
    d["obtido_em"] = time.time(); ARQ_TOKEN.write_text(json.dumps(d), encoding="utf-8")
    try:
        ARQ_TOKEN.chmod(0o600)
    except Exception:
        pass
    return d


def estado(redirect_uri: str):
    cid, sec = credenciais(); tok = _ler_token(); pend = []
    if not cid or not sec:
        pend.append("Faltam YT_CLIENT_ID e YT_CLIENT_SECRET no .env (app próprio no Google Cloud; ver docs/YOUTUBE-APP.md)")
    return {"configurado": bool(cid and sec), "conectado": bool(tok and tok.get("refresh_token")), "canal": (tok or {}).get("canal"), "redirect_uri": redirect_uri,
            "escopos": ESCOPOS, "pendencias": pend, "cota": "10.000 unidades/dia; cada upload gasta 1.600 (cerca de 6 vídeos por dia)"}


def url_autorizacao(redirect_uri: str):
    cid, _ = credenciais()
    if not cid:
        raise ErroYouTube("YT_CLIENT_ID ausente.")
    state = secrets.token_urlsafe(16); PENDENTES.add(state)
    q = {"client_id": cid, "redirect_uri": redirect_uri, "response_type": "code", "scope": ESCOPOS, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
    return AUTORIZAR + "?" + urlencode(q)


def trocar_codigo(code: str, state: str, redirect_uri: str, transport=None):
    if state not in PENDENTES:
        raise ErroYouTube("state desconhecido ou expirado: comece a conexão de novo.")
    PENDENTES.discard(state); cid, sec = credenciais()
    r = httpx.Client(transport=transport, timeout=30).post(TOKEN, data={"code": code, "client_id": cid, "client_secret": sec, "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    if r.status_code >= 400:
        raise ErroYouTube(f"Google token {r.status_code}: {r.text[:300]}")
    tok = _gravar_token(r.json())
    try:
        tok["canal"] = canal(transport); _gravar_token(tok)
    except ErroYouTube:
        pass
    return tok


def token_valido(transport=None):
    tok = _ler_token()
    if not tok or not tok.get("refresh_token"):
        raise ErroYouTube("YouTube não conectado: clique em Conectar YouTube.")
    if time.time() - tok.get("obtido_em", 0) < tok.get("expires_in", 3600) - 120:
        return tok["access_token"]
    cid, sec = credenciais()
    r = httpx.Client(transport=transport, timeout=30).post(TOKEN, data={"refresh_token": tok["refresh_token"], "client_id": cid, "client_secret": sec, "grant_type": "refresh_token"})
    if r.status_code >= 400:
        raise ErroYouTube(f"Google refresh {r.status_code}: {r.text[:200]} (reconecte o YouTube; em app em 'Testing' o token vence em 7 dias)")
    return _gravar_token(r.json())["access_token"]


def _j(r: httpx.Response, o_que: str):
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message") or r.text[:300]
        except Exception:
            msg = r.text[:300]
        raise ErroYouTube(f"YouTube {o_que} {r.status_code}: {msg}")
    return r.json() if r.content else {}


def canal(transport=None):
    tok = token_valido(transport)
    d = _j(httpx.Client(transport=transport, timeout=30).get(f"{API}/channels", params={"part": "snippet,statistics", "mine": "true"}, headers={"Authorization": f"Bearer {tok}"}), "channels")
    itens = d.get("items") or []
    if not itens:
        raise ErroYouTube("A conta conectada não tem canal do YouTube.")
    c = itens[0]
    return {"id": c["id"], "titulo": c["snippet"]["title"], "handle": c["snippet"].get("customUrl"), "inscritos": (c.get("statistics") or {}).get("subscriberCount"), "lido_em": time.strftime("%Y-%m-%dT%H:%M:%S")}


def publicar(video: Path, titulo: str, descricao: str = "", tags=None, privacidade: str = "private", publicar_em: str | None = None, capa: Path | None = None,
             categoria: str = "27", idioma: str = "pt-BR", transport=None):
    """Upload resumable + (opcional) capa. publicar_em (ISO 8601 UTC) agenda: o vídeo sobe privado e o YouTube publica na hora marcada.
    categoria 27 = Educação. Devolve id, url e o status que o YouTube informou."""
    video = Path(video)
    if not video.exists():
        raise ErroYouTube(f"Vídeo não encontrado: {video}")
    if privacidade not in PRIVACIDADES:
        raise ErroYouTube("privacidade deve ser private, unlisted ou public.")
    if not (titulo or "").strip():
        raise ErroYouTube("Título obrigatório (até 100 caracteres).")
    tok = token_valido(transport); c = httpx.Client(transport=transport, timeout=600)
    status = {"privacyStatus": "private" if publicar_em else privacidade, "selfDeclaredMadeForKids": False}
    if publicar_em:
        status["publishAt"] = publicar_em
    corpo = {"snippet": {"title": titulo.strip()[:100], "description": (descricao or "")[:5000], "tags": [t for t in (tags or []) if t][:30], "categoryId": categoria, "defaultLanguage": idioma, "defaultAudioLanguage": idioma}, "status": status}
    tam = video.stat().st_size
    r = c.post(f"{UPLOAD}/videos", params={"uploadType": "resumable", "part": "snippet,status"}, json=corpo,
               headers={"Authorization": f"Bearer {tok}", "X-Upload-Content-Type": "video/*", "X-Upload-Content-Length": str(tam)})
    _j(r, "upload (início)"); sessao = r.headers.get("Location")
    if not sessao:
        raise ErroYouTube("O YouTube não devolveu a sessão de upload.")
    enviado = 0; resp = None
    with video.open("rb") as f:
        while enviado < tam:
            pedaco = f.read(PEDACO); fim = enviado + len(pedaco) - 1
            resp = c.put(sessao, content=pedaco, headers={"Authorization": f"Bearer {tok}", "Content-Length": str(len(pedaco)), "Content-Range": f"bytes {enviado}-{fim}/{tam}", "Content-Type": "video/*"})
            if resp.status_code in (308,):
                enviado = fim + 1; continue
            if resp.status_code >= 400:
                _j(resp, "upload")
            enviado = tam
    d = resp.json() if resp is not None and resp.content else {}
    vid = d.get("id")
    if not vid:
        raise ErroYouTube(f"Upload terminou sem id de vídeo: {str(d)[:200]}")
    res = {"video_id": vid, "url": f"https://youtu.be/{vid}", "titulo": corpo["snippet"]["title"], "privacidade": status["privacyStatus"], "publishAt": publicar_em,
           "uploadStatus": (d.get("status") or {}).get("uploadStatus"), "capa": None, "quando": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if capa:
        capa = Path(capa)
        if capa.exists():
            mime = "image/png" if capa.suffix.lower() == ".png" else "image/jpeg"
            rc = c.post(f"{UPLOAD}/thumbnails/set", params={"uploadType": "media", "videoId": vid}, content=capa.read_bytes(), headers={"Authorization": f"Bearer {tok}", "Content-Type": mime})
            try:
                _j(rc, "capa"); res["capa"] = capa.name
            except ErroYouTube as e:
                res["capa_erro"] = str(e)  # capa personalizada exige canal verificado por telefone
    return res


def estado_video(video_id: str, transport=None):
    tok = token_valido(transport)
    d = _j(httpx.Client(transport=transport, timeout=30).get(f"{API}/videos", params={"part": "status,statistics,snippet", "id": video_id}, headers={"Authorization": f"Bearer {tok}"}), "videos")
    itens = d.get("items") or []
    if not itens:
        return {"status": "removido"}
    v = itens[0]; st = v.get("status") or {}; es = v.get("statistics") or {}
    return {"status": "agendado" if st.get("publishAt") and st.get("privacyStatus") == "private" else st.get("privacyStatus"), "uploadStatus": st.get("uploadStatus"), "publishAt": st.get("publishAt"),
            "views": es.get("viewCount"), "likes": es.get("likeCount"), "comentarios": es.get("commentCount"), "titulo": (v.get("snippet") or {}).get("title")}
