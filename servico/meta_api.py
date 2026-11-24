"""Rotas da Meta (Instagram da conta própria) no gateway: /api/gs/meta/*. 10/11/2026.
Só leitura e renovação de token. Publicar NÃO tem rota aqui: entra depois no cartão da entrega, por clique humano.
Ligar em servico/api.py com `app.include_router(meta_api.router)`.
Sem credenciais: `situacao` responde 200 com META_PENDENTE; as outras rotas respondem 409. Erro da Graph API vira 502."""
from fastapi import APIRouter, HTTPException
import httpx
from servico import meta

router = APIRouter(prefix="/api/gs/meta", tags=["meta"])


def _cliente(qual: str | None = None) -> meta.Cliente:
    if not meta.configurada():
        raise HTTPException(409, "Meta não configurada: falta META_IG_TOKEN + META_IG_USER_ID (ou META_FB_TOKEN + META_FB_IG_USER_ID) no .env. Ver docs/META-APP.md.")
    try:
        return meta.Cliente(qual)
    except meta.ErroMeta as e:
        raise HTTPException(409, str(e))


def _executar(fn):
    try:
        return fn()
    except meta.ErroMeta as e:
        raise HTTPException(502, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(502, meta._limpar(f"Meta fora do ar ou sem rede: {type(e).__name__}: {e}"))


@router.get("/situacao")
def situacao():
    return meta.situacao()


@router.get("/conta")
def conta():
    c = _cliente()
    return _executar(c.conta)


@router.get("/midias")
def midias(n: int = 25):
    c = _cliente()
    return _executar(lambda: c.midias(n))


@router.get("/midias/{midia_id}/insights")
def insights_midia(midia_id: str):
    c = _cliente()
    return _executar(lambda: c.insights_midia(midia_id))


@router.get("/midias/{midia_id}/comentarios")
def comentarios(midia_id: str, n: int = 50):
    c = _cliente()
    return _executar(lambda: c.comentarios(midia_id, n))


@router.get("/insights")
def insights_conta(periodo: str = "day", dias: int = 7):
    c = _cliente()
    return _executar(lambda: c.insights_conta(periodo, dias))


@router.get("/limite")
def limite():
    c = _cliente()
    return _executar(c.limite_publicacao)


@router.get("/concorrente/{username}")
def concorrente(username: str, n: int = 25):
    cred = meta.credenciais()
    if not cred["fb"]:
        if not cred["ig"]:
            raise HTTPException(409, "Meta não configurada (ver docs/META-APP.md).")
        raise HTTPException(409, "Concorrentes precisam do Facebook Login com Página: META_FB_TOKEN + META_FB_IG_USER_ID no .env (docs/META-APP.md, seção 'Facebook Login com Página').")
    c = _cliente("fb")
    return _executar(lambda: c.business_discovery(username, n))


@router.post("/renovar")
def renovar():
    cred = meta.credenciais()
    if not cred["ig"]:
        if not cred["fb"]:
            raise HTTPException(409, "Meta não configurada (ver docs/META-APP.md).")
        raise HTTPException(409, "Só o token do Instagram Login (META_IG_TOKEN) renova por aqui; o token de Página do Facebook Login não expira.")
    c = _cliente("ig")
    return _executar(c.renovar_token)
