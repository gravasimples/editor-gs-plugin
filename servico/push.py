"""Notificações push do PWA (Web Push, sem serviço de terceiros): chaves VAPID geradas uma vez em servico/push_vapid.json, inscrições dos
aparelhos em servico/push_inscricoes.json, e um vigia (api._laco_push) que a cada 30 s compara o status das issues do Paperclip e avisa:
entrega pronta (in_review/done), Editor precisa de decisão (interaction pendente), pedido travado (blocked). Só avisa mudanças depois da
primeira leitura; nunca manda conteúdo sensível, só título/código e o link da conversa. Espelho das "notificações push" do Máquina."""
import json, os, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
VAPID = _cam.estado("push_vapid.json")
INSCRICOES = _cam.estado("push_inscricoes.json")
ASSUNTO = "mailto:gravasimples@gmail.com"


def _json(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return padrao


def chaves(vapid: Path = None):
    """Par VAPID (gera e grava na primeira vez). Devolve {"publica": base64url, "privada": PEM}."""
    vapid = vapid or VAPID
    c = _json(vapid, None)
    if c and c.get("publica") and c.get("privada"):
        return c
    from py_vapid import Vapid
    import base64
    from cryptography.hazmat.primitives import serialization
    v = Vapid(); v.generate_keys()
    pub = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    priv = v.private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    c = {"publica": base64.urlsafe_b64encode(pub).decode().rstrip("="), "privada": priv, "criada_em": time.strftime("%Y-%m-%dT%H:%M")}
    vapid.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(vapid, 0o600)
    except OSError:
        pass
    return c


def chave_publica(vapid: Path = None):
    return chaves(vapid)["publica"]


def listar(arq: Path = None):
    return _json(arq or INSCRICOES, [])


def _gravar(lst, arq: Path = None):
    (arq or INSCRICOES).write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")


def inscrever(sub: dict, aparelho: str = "", arq: Path = None):
    """Guarda a inscrição (endpoint + chaves) do aparelho; o mesmo endpoint substitui o anterior."""
    if not isinstance(sub, dict) or not sub.get("endpoint") or not (sub.get("keys") or {}).get("p256dh"):
        raise ValueError("Inscrição inválida (falta endpoint ou chaves).")
    lst = [s for s in listar(arq) if s.get("endpoint") != sub["endpoint"]]
    lst.append({"endpoint": sub["endpoint"], "keys": sub["keys"], "expirationTime": sub.get("expirationTime"), "aparelho": (aparelho or "")[:120], "desde": time.strftime("%Y-%m-%dT%H:%M")})
    _gravar(lst, arq)
    return {"n": len(lst)}


def remover(endpoint: str, arq: Path = None):
    lst = [s for s in listar(arq) if s.get("endpoint") != endpoint]
    _gravar(lst, arq)
    return {"n": len(lst)}


def _enviar_raw(sub, payload: str, vapid: dict):
    from pywebpush import webpush
    webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=payload, vapid_private_key=vapid["privada"], vapid_claims={"sub": ASSUNTO}, ttl=3600)


def enviar(titulo: str, corpo: str = "", url: str = "/", tag: str = "", arq: Path = None, vapid: Path = None, _raw=None):
    """Manda a notificação a todos os aparelhos inscritos; inscrição morta (404/410) é removida. Devolve {"enviadas", "removidas", "erros"}."""
    lst = listar(arq)
    if not lst:
        return {"enviadas": 0, "removidas": 0, "erros": []}
    v = chaves(vapid)
    payload = json.dumps({"titulo": titulo[:80], "corpo": corpo[:160], "url": url, "tag": tag or url}, ensure_ascii=False)
    ok, mortas, erros = 0, [], []
    for s in lst:
        try:
            (_raw or _enviar_raw)(s, payload, v); ok += 1
        except Exception as e:  # noqa
            codigo = getattr(getattr(e, "response", None), "status_code", None)
            if codigo in (404, 410):
                mortas.append(s["endpoint"])
            else:
                erros.append(f"{type(e).__name__}: {str(e)[:120]}")
    if mortas:
        _gravar([s for s in lst if s["endpoint"] not in mortas], arq)
    return {"enviadas": ok, "removidas": len(mortas), "erros": erros}


class Vigia:
    """Guarda o último estado visto de cada issue e decide o que avisar. Sem rede: recebe as listas já lidas (testável)."""
    ESTADOS_PRONTO = ("in_review", "done")

    def __init__(self):
        self.visto = {}        # issue_id → status
        self.interacoes = {}   # issue_id → conjunto de ids de interactions pendentes já avisadas
        self.primeira = True

    def avaliar(self, issues, interacoes_por_issue=None):
        """issues: lista do Paperclip; interacoes_por_issue: {issue_id: [interactions pendentes]}. Devolve a lista de avisos (titulo, corpo, url, tag)."""
        avisos = []
        interacoes_por_issue = interacoes_por_issue or {}
        for it in issues:
            iid = it.get("id"); st = it.get("status"); cod = it.get("identifier") or ""; tit = (it.get("title") or "")[:70]
            antes = self.visto.get(iid)
            self.visto[iid] = st
            if self.primeira:
                continue
            if st in self.ESTADOS_PRONTO and antes not in self.ESTADOS_PRONTO and antes is not None:
                avisos.append(("Entrega pronta ✦ " + cod, tit, f"/c/{iid}", f"pronto-{iid}"))
            elif st == "blocked" and antes != "blocked" and antes is not None:
                avisos.append(("Pedido travado · " + cod, tit + " — abra para destravar", f"/c/{iid}", f"blocked-{iid}"))
        for iid, pend in interacoes_por_issue.items():
            ids = {p.get("id") for p in pend if p.get("id")}
            novas = ids - self.interacoes.get(iid, set())
            self.interacoes[iid] = ids
            if novas and not self.primeira:
                it = next((x for x in issues if x.get("id") == iid), {})
                avisos.append(("O Editor precisa da sua decisão · " + (it.get("identifier") or ""), (pend[-1].get("title") or (it.get("title") or ""))[:90], f"/c/{iid}", f"decisao-{iid}"))
        self.primeira = False
        return avisos
