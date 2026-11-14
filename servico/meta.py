"""Cliente da API oficial da Meta para o Instagram da conta própria (@thiago.obsstudio). 10/11/2026.
Nada aqui roda sozinho: o gateway chama, e publicar só entra por clique humano no cartão da entrega.

Duas credenciais possíveis no .env (podem coexistir; o cliente escolhe a certa por função):
  (a) Instagram Login ........ META_IG_TOKEN + META_IG_USER_ID        host https://graph.instagram.com/<versão>
      Publica Reels, lê mídias, métricas e comentários da conta própria. Renova com ig_refresh_token (60 dias).
  (b) Facebook Login + Página  META_FB_TOKEN + META_FB_IG_USER_ID     host https://graph.facebook.com/<versão>
      Mesmo que (a) e, além disso, `business_discovery` (perfis públicos de concorrentes/referências). Só este host tem isso.
Opcionais: META_APP_ID + META_APP_SECRET (debug_token e appsecret_proof em (b)), META_GRAPH_VERSION (padrão v26.0).
Nomes META_IG_TOKEN/META_IG_USER_ID são os mesmos que o GSI espera em integracoes/instagram_fonte.py.

Regras: token só no cabeçalho Authorization (nunca na URL, salvo o endpoint de renovação, que exige query); toda mensagem de erro
passa por `_limpar` antes de sair; `ErroMeta` carrega code/subcode/tipo da Graph API. Cache em memória de 60 s para conta/mídias.
Token renovado fica em `caminhos.estado("meta_token.json")` (fora do git) e vale sobre o .env quando for mais novo.
Passo a passo das credenciais: docs/META-APP.md."""
import hashlib, hmac, json, os, re, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from servico import caminhos as cam

VERSAO_PADRAO = "v26.0"
HOST_IG = "https://graph.instagram.com"
HOST_FB = "https://graph.facebook.com"
CAMPOS_MIDIA = "id,media_type,media_product_type,permalink,caption,timestamp,thumbnail_url,media_url,like_count,comments_count"
CAMPOS_BD_PERFIL = "username,name,biography,website,followers_count,follows_count,media_count,profile_picture_url"
CAMPOS_BD_MIDIA = "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count,view_count"
# Nomes atuais (reference/instagram-media/insights, lido em 10/11/2026): plays e impressions foram descontinuados em 2025.
METRICAS_REELS = ["views", "reach", "saved", "shares", "likes", "comments", "total_interactions", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
METRICAS_FEED = ["views", "reach", "saved", "shares", "likes", "comments", "total_interactions"]
# Métricas da conta: lista "a confirmar" na doc (a página de referência não abriu); erro por métrica é tolerado.
METRICAS_CONTA = ["reach", "views", "total_interactions", "accounts_engaged", "profile_views", "follower_count"]
SEGREDO = re.compile(r"EAA[A-Za-z0-9]{20,}|IGAA[A-Za-z0-9_\-]{20,}|IGQ[A-Za-z0-9_\-]{20,}|access_token=[^&\"\s]+|appsecret_proof=[^&\"\s]+")
CACHE_S = 60
_cache: dict[str, tuple[float, dict]] = {}


class ErroMeta(Exception):
    """Erro da Graph API (ou de configuração), já sem token na mensagem."""

    def __init__(self, mensagem: str, code=None, subcode=None, tipo=None, http=None):
        super().__init__(_limpar(mensagem))
        self.code, self.subcode, self.tipo, self.http = code, subcode, tipo, http

    def dict(self):
        return {"erro": str(self), "code": self.code, "subcode": self.subcode, "tipo": self.tipo, "http": self.http}


def _limpar(t) -> str:
    return SEGREDO.sub("<removido>", str(t or ""))


# --- credenciais ----------------------------------------------------------------------------------

_CHAVES = ("META_IG_TOKEN", "META_IG_USER_ID", "META_FB_TOKEN", "META_FB_IG_USER_ID", "META_APP_ID", "META_APP_SECRET", "META_GRAPH_VERSION")


def _env_arquivo() -> dict:
    """Lê só as chaves META_* do .env quando o processo não as recebeu no ambiente. Nunca imprime o conteúdo."""
    out = {}
    try:
        for linha in Path(cam.ENV).read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, v = linha.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            if k in _CHAVES:
                out[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def _token_guardado() -> dict:
    try:
        return json.loads(cam.estado("meta_token.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_token(credencial: str, token: str, expira_em: datetime):
    arq = cam.estado("meta_token.json")
    d = _token_guardado()
    d[credencial] = {"token": token, "expira_em": expira_em.isoformat(timespec="seconds"), "renovado_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(arq, 0o600)
    except OSError:
        pass


def credenciais(env: dict | None = None) -> dict:
    """{'ig': {token,user_id}|None, 'fb': {token,user_id}|None, 'app_id','app_secret','versao'}. `env` serve para teste."""
    fonte = dict(env) if env is not None else {**_env_arquivo(), **{k: os.environ[k] for k in _CHAVES if os.environ.get(k)}}
    g = lambda k: (fonte.get(k) or "").strip()  # noqa: E731
    guard = _token_guardado() if env is None else {}
    ig_token = (guard.get("ig") or {}).get("token") or g("META_IG_TOKEN")
    return {
        "ig": {"token": ig_token, "user_id": g("META_IG_USER_ID"), "expira_em": (guard.get("ig") or {}).get("expira_em")} if ig_token and g("META_IG_USER_ID") else None,
        "fb": {"token": g("META_FB_TOKEN"), "user_id": g("META_FB_IG_USER_ID"), "expira_em": (guard.get("fb") or {}).get("expira_em")} if g("META_FB_TOKEN") and g("META_FB_IG_USER_ID") else None,
        "app_id": g("META_APP_ID"), "app_secret": g("META_APP_SECRET"), "versao": g("META_GRAPH_VERSION") or VERSAO_PADRAO,
    }


def configurada(env: dict | None = None) -> bool:
    c = credenciais(env)
    return bool(c["ig"] or c["fb"])


# --- cliente --------------------------------------------------------------------------------------

class Cliente:
    """Uma credencial por instância. `qual`: 'ig', 'fb' ou None (prefere 'ig'; 'fb' quando só ela existe)."""

    def __init__(self, qual: str | None = None, transport=None, env: dict | None = None, timeout: float = 40):
        self.cred = credenciais(env)
        if qual is None:
            qual = "ig" if self.cred["ig"] else "fb" if self.cred["fb"] else None
        if qual is None or not self.cred.get(qual):
            raise ErroMeta("META_PENDENTE: sem credenciais da Meta no .env (ver docs/META-APP.md).", code="META_PENDENTE")
        self.qual = qual
        self.token = self.cred[qual]["token"]
        self.user_id = self.cred[qual]["user_id"]
        self.host = HOST_IG if qual == "ig" else HOST_FB
        self.base = f"{self.host}/{self.cred['versao']}"
        self.transport, self.timeout = transport, timeout
        self.c = httpx.Client(base_url=self.base, headers={"Authorization": f"Bearer {self.token}"}, timeout=timeout, transport=transport)

    # -- transporte -------------------------------------------------------------------------------
    def _params(self, params: dict | None) -> dict:
        q = {k: v for k, v in (params or {}).items() if v is not None}
        if self.qual == "fb" and self.cred["app_secret"]:
            q["appsecret_proof"] = hmac.new(self.cred["app_secret"].encode(), self.token.encode(), hashlib.sha256).hexdigest()
        return q

    def _resposta(self, r: httpx.Response, caminho: str) -> dict:
        try:
            corpo = r.json() if r.content else {}
        except ValueError:
            corpo = {"error": {"message": f"resposta não é JSON (HTTP {r.status_code}): {r.text[:120]}"}}
        if isinstance(corpo, dict) and "error" in corpo:
            er = corpo["error"] if isinstance(corpo["error"], dict) else {"message": str(corpo["error"])}
            msg = er.get("error_user_msg") or er.get("message") or f"HTTP {r.status_code}"
            raise ErroMeta(f"Graph {caminho.split('?')[0]}: {msg}", code=er.get("code"), subcode=er.get("error_subcode"), tipo=er.get("type"), http=r.status_code)
        if r.status_code >= 400:
            raise ErroMeta(f"Graph {caminho}: HTTP {r.status_code} {r.text[:160]}", http=r.status_code)
        return corpo if isinstance(corpo, dict) else {"data": corpo}

    def get(self, caminho: str, params: dict | None = None) -> dict:
        caminho = "/" + caminho.lstrip("/")
        return self._resposta(self.c.get(caminho, params=self._params(params)), caminho)

    def post(self, caminho: str, dados: dict | None = None) -> dict:
        caminho = "/" + caminho.lstrip("/")
        return self._resposta(self.c.post(caminho, data=self._params(dados)), caminho)

    def _cache(self, chave: str, calc):
        chave = f"{self.qual}:{self.user_id}:{chave}"
        hit = _cache.get(chave)
        if hit and time.time() - hit[0] < CACHE_S:
            return hit[1]
        v = calc()
        _cache[chave] = (time.time(), v)
        return v

    # -- conta e mídias ----------------------------------------------------------------------------
    def conta(self) -> dict:
        def calc():
            campos = "id,username,name,account_type,profile_picture_url,followers_count,follows_count,media_count"
            if self.qual == "ig":
                campos = "id,user_id," + campos.split(",", 1)[1]
            d = self.get(self.user_id, {"fields": campos})
            return {"id": d.get("user_id") or d.get("id"), "usuario": d.get("username"), "nome": d.get("name"), "tipo": d.get("account_type"),
                    "foto": d.get("profile_picture_url"), "seguidores": d.get("followers_count"), "seguindo": d.get("follows_count"), "midias": d.get("media_count"), "credencial": self.qual}
        return self._cache("conta", calc)

    def midias(self, n: int = 25) -> dict:
        n = max(1, min(int(n or 25), 100))

        def calc():
            d = self.get(f"{self.user_id}/media", {"fields": CAMPOS_MIDIA, "limit": n})
            itens = [_midia(m) for m in d.get("data", [])]
            return {"itens": itens, "n": len(itens), "proxima": (d.get("paging") or {}).get("next") is not None}
        return self._cache(f"midias:{n}", calc)

    def midia(self, midia_id: str) -> dict:
        return _midia(self.get(midia_id, {"fields": CAMPOS_MIDIA}))

    # -- métricas ----------------------------------------------------------------------------------
    def insights_midia(self, midia_id: str, tipo_produto: str | None = None) -> dict:
        """Métricas de uma mídia. Pede todas de uma vez; se a Graph recusar alguma, repete uma a uma e registra o erro por métrica."""
        if tipo_produto is None:
            try:
                tipo_produto = self.get(midia_id, {"fields": "media_product_type,media_type"}).get("media_product_type")
            except ErroMeta:
                tipo_produto = None
        nomes = METRICAS_REELS if (tipo_produto or "").upper() == "REELS" else METRICAS_FEED
        metricas, erros = {}, {}
        try:
            metricas = _valores(self.get(f"{midia_id}/insights", {"metric": ",".join(nomes)}))
        except ErroMeta as e:
            if e.code not in (100, None) and "metric" not in str(e).lower():
                raise
            for nome in nomes:
                try:
                    metricas.update(_valores(self.get(f"{midia_id}/insights", {"metric": nome})))
                except ErroMeta as e2:
                    erros[nome] = str(e2)
        return {"id": midia_id, "tipo_produto": tipo_produto, "metricas": metricas, "erros": erros}

    def insights_conta(self, periodo: str = "day", dias: int = 7) -> dict:
        """Métricas da conta nos últimos `dias` (period=day, metric_type=total_value). Tolera erro por métrica."""
        dias = max(1, min(int(dias or 7), 30))
        ate = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        desde = ate - timedelta(days=dias)
        base = {"period": periodo, "metric_type": "total_value", "since": int(desde.timestamp()), "until": int(ate.timestamp())}
        metricas, erros = {}, {}
        try:
            metricas = _valores(self.get(f"{self.user_id}/insights", {**base, "metric": ",".join(METRICAS_CONTA)}))
        except ErroMeta as e:
            if e.code not in (100, None) and "metric" not in str(e).lower():
                raise
            for nome in METRICAS_CONTA:
                try:
                    metricas.update(_valores(self.get(f"{self.user_id}/insights", {**base, "metric": nome})))
                except ErroMeta as e2:
                    erros[nome] = str(e2)
        return {"periodo": periodo, "dias": dias, "desde": desde.date().isoformat(), "ate": ate.date().isoformat(), "metricas": metricas, "erros": erros}

    # -- comentários -------------------------------------------------------------------------------
    def comentarios(self, midia_id: str, n: int = 50, com_usuario: bool = False) -> dict:
        """Comentários de uma mídia própria (até 50 por chamada, mais recentes primeiro). Autor pseudonimizado por padrão;
        `com_usuario=True` só para a tela de responder (resposta é clique humano, fora daqui)."""
        d = self.get(f"{midia_id}/comments", {"fields": "id,text,timestamp,username,like_count,replies{id,text,timestamp,username,like_count}", "limit": max(1, min(int(n or 50), 50))})
        dono = None
        try:
            dono = (self.conta().get("usuario") or "").lower()
        except ErroMeta:
            pass
        itens = []
        for cm in d.get("data", []):
            item = _comentario(cm, dono, com_usuario)
            item["respostas"] = [_comentario(r, dono, com_usuario) for r in (cm.get("replies") or {}).get("data", [])]
            item["respondido"] = any(r["proprio"] for r in item["respostas"])
            itens.append(item)
        return {"id": midia_id, "itens": itens, "n": len(itens), "sem_resposta": sum(1 for i in itens if not i["respondido"] and not i["proprio"])}

    # -- publicação --------------------------------------------------------------------------------
    def limite_publicacao(self) -> dict:
        d = self.get(f"{self.user_id}/content_publishing_limit", {"fields": "quota_usage,config"})
        it = (d.get("data") or [{}])[0] if isinstance(d.get("data"), list) else d
        cfg = it.get("config") or {}
        usado, total = it.get("quota_usage"), cfg.get("quota_total")
        return {"usado": usado, "total": total, "restante": (total - usado) if isinstance(total, int) and isinstance(usado, int) else None, "janela_s": cfg.get("quota_duration")}

    def publicar_reel(self, video_url: str, legenda: str = "", cover_url: str | None = None, share_to_feed: bool = True, trial: bool = False,
                      thumb_offset_ms: int | None = None, intervalo_s: float = 10, maximo_s: float = 600, dormir=time.sleep) -> dict:
        """Container REELS → espera status_code=FINISHED → media_publish. Devolve {id, permalink, container_id, status}.
        O Instagram baixa `video_url` (precisa ser pública por alguns minutos). Quem registra em publicacoes.json é o gateway."""
        if not video_url or not str(video_url).startswith("http"):
            raise ErroMeta("publicar_reel: video_url precisa ser uma URL pública (http/https).")
        dados = {"media_type": "REELS", "video_url": video_url, "caption": (legenda or "")[:2200], "share_to_feed": "true" if share_to_feed else "false"}
        if cover_url:
            dados["cover_url"] = cover_url
        elif thumb_offset_ms is not None:
            dados["thumb_offset"] = int(thumb_offset_ms)
        if trial:
            dados["trial_params"] = json.dumps({"graduation_strategy": "MANUAL"})
        return self._publicar(dados, intervalo_s, maximo_s, dormir)

    def publicar_imagem(self, image_url: str, legenda: str = "", alt_text: str | None = None, intervalo_s: float = 5, maximo_s: float = 300, dormir=time.sleep) -> dict:
        """Post de imagem (JPEG público). Mesmo fluxo de container → publish."""
        if not image_url or not str(image_url).startswith("http"):
            raise ErroMeta("publicar_imagem: image_url precisa ser uma URL pública (JPEG).")
        dados = {"image_url": image_url, "caption": (legenda or "")[:2200]}
        if alt_text:
            dados["alt_text"] = alt_text[:1000]
        return self._publicar(dados, intervalo_s, maximo_s, dormir)

    def _publicar(self, dados: dict, intervalo_s: float, maximo_s: float, dormir) -> dict:
        cont = self.post(f"{self.user_id}/media", dados)
        cid = cont.get("id")
        if not cid:
            raise ErroMeta(f"container sem id: {json.dumps(cont)[:200]}")
        status, gasto = self.estado_container(cid), 0.0
        while status.get("status_code") in ("IN_PROGRESS", None) and gasto < maximo_s:
            dormir(intervalo_s); gasto += intervalo_s
            status = self.estado_container(cid)
        sc = status.get("status_code")
        if sc == "PUBLISHED":
            pass
        elif sc != "FINISHED":
            raise ErroMeta(f"container {cid} não ficou pronto: {sc or 'sem status'} {status.get('status') or ''}".strip(), code=sc)
        pub = self.post(f"{self.user_id}/media_publish", {"creation_id": cid})
        mid = pub.get("id")
        if not mid:
            raise ErroMeta(f"media_publish sem id: {json.dumps(pub)[:200]}")
        permalink = None
        try:
            permalink = self.get(mid, {"fields": "permalink"}).get("permalink")
        except ErroMeta:
            pass
        _cache.clear()
        return {"id": mid, "permalink": permalink, "container_id": cid, "status": "PUBLISHED"}

    def estado_container(self, container_id: str) -> dict:
        d = self.get(container_id, {"fields": "status_code,status"})
        return {"id": container_id, "status_code": d.get("status_code"), "status": d.get("status")}

    # -- concorrentes e referências ----------------------------------------------------------------
    def business_discovery(self, username: str, n: int = 25) -> dict:
        if self.qual != "fb":
            raise ErroMeta("business_discovery só existe no Facebook Login com Página (META_FB_TOKEN + META_FB_IG_USER_ID); a credencial do Instagram Login não dá acesso a perfis de terceiros. Ver docs/META-APP.md.", code="SEM_FB")
        u = (username or "").strip().lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", u):
            raise ErroMeta(f"username inválido: {username!r}")
        n = max(1, min(int(n or 25), 100))
        d = self.get(self.user_id, {"fields": f"business_discovery.username({u}){{{CAMPOS_BD_PERFIL},media.limit({n}){{{CAMPOS_BD_MIDIA}}}}}"})
        bd = d.get("business_discovery") or {}
        if not bd:
            raise ErroMeta(f"@{u}: sem dados (conta privada, pessoal, restrita por idade ou inexistente).")
        itens = [_midia(m) for m in (bd.get("media") or {}).get("data", [])]
        return {"perfil": {"usuario": bd.get("username"), "nome": bd.get("name"), "bio": bd.get("biography"), "site": bd.get("website"), "seguidores": bd.get("followers_count"),
                           "seguindo": bd.get("follows_count"), "midias": bd.get("media_count"), "foto": bd.get("profile_picture_url")},
                "itens": itens, "n": len(itens)}

    # -- token -------------------------------------------------------------------------------------
    def renovar_token(self) -> dict:
        """Só Instagram Login: GET /refresh_access_token?grant_type=ig_refresh_token (token com mais de 24 h e ainda válido).
        Guarda o token novo em estado/meta_token.json (vale sobre o .env). Devolve dias e data, nunca o token."""
        if self.qual != "ig":
            raise ErroMeta("renovar_token: só o token do Instagram Login (META_IG_TOKEN) renova por ig_refresh_token. O token de Página do Facebook Login não expira (ver docs/META-APP.md).", code="SEM_IG")
        # este endpoint exige o token na query (não aceita só o cabeçalho); a URL nunca é logada e erros passam por _limpar
        r = self.c.get(f"{self.host}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": self.token})
        d = self._resposta(r, "/refresh_access_token")
        novo, seg = d.get("access_token"), int(d.get("expires_in") or 0)
        if not novo or seg <= 0:
            raise ErroMeta(f"refresh_access_token sem access_token/expires_in: {json.dumps({k: v for k, v in d.items() if k != 'access_token'})[:160]}")
        expira = datetime.now(timezone.utc) + timedelta(seconds=seg)
        _guardar_token("ig", novo, expira)
        self.token = novo
        self.c.headers["Authorization"] = f"Bearer {novo}"
        return {"renovado": True, "credencial": "ig", "expira_em": expira.isoformat(timespec="seconds"), "dias": seg // 86400}

    def validar_token(self) -> dict:
        """Validade do token sem expor o valor. 'fb' com META_APP_ID/SECRET: /debug_token; senão, chamada leve à própria conta."""
        if self.qual == "fb" and self.cred["app_id"] and self.cred["app_secret"]:
            # sem o cabeçalho Bearer: o debug_token é autenticado pelo token do app (id|segredo)
            r = httpx.Client(timeout=self.timeout, transport=self.transport).get(f"{self.host}/debug_token", params={"input_token": self.token, "access_token": f"{self.cred['app_id']}|{self.cred['app_secret']}"})
            d = (self._resposta(r, "/debug_token").get("data") or {})
            exp = d.get("expires_at") or 0
            dias = None if not exp else max(0, int((datetime.fromtimestamp(exp, timezone.utc) - datetime.now(timezone.utc)).total_seconds() // 86400))
            return {"valido": bool(d.get("is_valid")), "expira_em": datetime.fromtimestamp(exp, timezone.utc).isoformat(timespec="seconds") if exp else None,
                    "dias": dias, "nunca_expira": not exp, "escopos": d.get("scopes") or [], "app_id": str(d.get("app_id") or "")}
        campos = "id,username" if self.qual == "fb" else "user_id,username"
        d = self.get("me" if self.qual == "ig" else self.user_id, {"fields": campos})
        guard = self.cred[self.qual].get("expira_em")
        dias = None
        if guard:
            try:
                dias = max(0, int((datetime.fromisoformat(guard) - datetime.now(timezone.utc)).total_seconds() // 86400))
            except ValueError:
                dias = None
        return {"valido": bool(d.get("username") or d.get("id") or d.get("user_id")), "usuario": d.get("username"), "expira_em": guard, "dias": dias, "nunca_expira": False}


# --- auxiliares -----------------------------------------------------------------------------------

def _midia(m: dict) -> dict:
    legenda = (m.get("caption") or "").strip()
    tipo = m.get("media_type")
    prod = (m.get("media_product_type") or "").upper() or None
    return {"id": m.get("id"), "tipo": "REELS" if prod == "REELS" else tipo, "tipo_midia": tipo, "tipo_produto": prod, "permalink": m.get("permalink"),
            "legenda": (legenda[:117] + "…") if len(legenda) > 120 else legenda, "quando": m.get("timestamp"),
            "thumbnail": m.get("thumbnail_url") or (m.get("media_url") if tipo == "IMAGE" else None),
            "likes": m.get("like_count"), "comentarios": m.get("comments_count"), "views": m.get("view_count")}


def _valores(d: dict) -> dict:
    out = {}
    for it in d.get("data", []):
        v = None
        if it.get("total_value") is not None:
            v = (it.get("total_value") or {}).get("value")
        elif it.get("values"):
            v = (it["values"][-1] or {}).get("value")
        out[it.get("name")] = v
    return out


def _pseudonimo(usuario: str | None) -> str:
    return hashlib.sha256(("instagram:" + (usuario or "").lower()).encode()).hexdigest()[:8] if usuario else ""


def _comentario(cm: dict, dono: str | None, com_usuario: bool) -> dict:
    u = (cm.get("username") or "")
    proprio = bool(dono) and u.lower() == dono
    item = {"id": cm.get("id"), "texto": cm.get("text"), "quando": cm.get("timestamp"), "likes": cm.get("like_count"), "proprio": proprio,
            "autor": (dono if proprio else _pseudonimo(u))}
    if com_usuario:
        item["usuario"] = u
    return item


# --- funções de módulo (uma chamada, uma credencial escolhida por função) ---------------------------

def situacao(transport=None, env: dict | None = None, validar: bool = True) -> dict:
    """Quais credenciais existem e se os tokens respondem. Nunca levanta exceção, nunca devolve token."""
    c = credenciais(env)
    if not c["ig"] and not c["fb"]:
        return {"configurada": False, "pendente": "META_PENDENTE", "como": "docs/META-APP.md", "versao": c["versao"],
                "credenciais": {"ig": False, "fb": False}, "business_discovery": False, "renovacao_automatica": False}
    out = {"configurada": True, "versao": c["versao"], "credenciais": {"ig": bool(c["ig"]), "fb": bool(c["fb"])},
           "business_discovery": bool(c["fb"]), "renovacao_automatica": bool(c["ig"]), "app_secret": bool(c["app_secret"]), "tokens": {}, "avisos": []}
    for qual in ("ig", "fb"):
        if not c[qual]:
            continue
        info = {"user_id": c[qual]["user_id"], "host": HOST_IG if qual == "ig" else HOST_FB, "guardado_em_estado": bool((_token_guardado().get(qual) or {}).get("token")) if env is None else False}
        if validar:
            try:
                info.update(Cliente(qual, transport=transport, env=env).validar_token())
            except (ErroMeta, httpx.HTTPError) as e:
                info.update({"valido": False, "erro": _limpar(str(e))})
        d = info.get("dias")
        if info.get("valido") is False:
            out["avisos"].append(f"{qual}: token não respondeu ({info.get('erro', 'inválido')})")
        elif isinstance(d, int) and d < 7:
            out["avisos"].append(f"{qual}: token expira em {d} dia(s)" + (" — rode a renovação (POST /api/gs/meta/renovar)" if qual == "ig" else ""))
        out["tokens"][qual] = info
    if not c["fb"]:
        out["avisos"].append("sem META_FB_TOKEN/META_FB_IG_USER_ID: concorrentes (business_discovery) indisponíveis")
    return out


def _cli(qual=None, **kw) -> Cliente:
    return Cliente(qual, **kw)


def conta(**kw) -> dict:
    return _cli(**kw).conta()


def midias(n: int = 25, **kw) -> dict:
    return _cli(**kw).midias(n)


def insights_midia(midia_id: str, **kw) -> dict:
    return _cli(**kw).insights_midia(midia_id)


def insights_conta(periodo: str = "day", dias: int = 7, **kw) -> dict:
    return _cli(**kw).insights_conta(periodo, dias)


def comentarios(midia_id: str, **kw) -> dict:
    return _cli(**kw).comentarios(midia_id)


def limite_publicacao(**kw) -> dict:
    return _cli(**kw).limite_publicacao()


def business_discovery(username: str, n: int = 25, **kw) -> dict:
    c = credenciais(kw.get("env"))
    return Cliente("fb" if c["fb"] else None, **kw).business_discovery(username, n)


def renovar_token(**kw) -> dict:
    c = credenciais(kw.get("env"))
    return Cliente("ig" if c["ig"] else None, **kw).renovar_token()


def publicar_reel(video_url: str, legenda: str = "", cover_url: str | None = None, share_to_feed: bool = True, trial: bool = False, **kw) -> dict:
    extra = {k: kw.pop(k) for k in ("thumb_offset_ms", "intervalo_s", "maximo_s", "dormir") if k in kw}
    return _cli(**kw).publicar_reel(video_url, legenda, cover_url, share_to_feed, trial, **extra)


def publicar_imagem(image_url: str, legenda: str = "", alt_text: str | None = None, **kw) -> dict:
    extra = {k: kw.pop(k) for k in ("intervalo_s", "maximo_s", "dormir") if k in kw}
    return _cli(**kw).publicar_imagem(image_url, legenda, alt_text, **extra)


if __name__ == "__main__":
    print(json.dumps(situacao(), ensure_ascii=False, indent=1))
