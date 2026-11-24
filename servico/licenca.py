"""Chave do produto Editor GS (10/11/2026). Verificação local, sem servidor.

Formato: `GS1-<payload>-<assinatura>` (base64url sem `=`). payload = JSON compacto {"id", "nome", "produto", "emitida", "validade"};
assinatura Ed25519 do payload com a chave privada do Raphael (`~/.config/editor-gs/licenca-privada.pem`, fora do repositório).
A chave pública fica aqui no código: quem tem o plugin consegue verificar, não emitir. Como o código roda no computador do cliente, a chave é
uma formalidade de vínculo (nome, validade, revogação), não DRM: o controle real de acesso é o repositório privado.

Quando é exigida: só no modo plugin (dados em EDITOR_GS_HOME / ~/EditorGS). No modo desenvolvimento (tudo dentro do projeto) não é.
Estado: `<estado>/licenca.json`. Revogação: `config.json → licenca.revogadas` (lista de ids)."""
import base64, json
from datetime import date
from pathlib import Path

PUBLICA_HEX = "0d12ee312f48cab5377e43e2cb8ca2e85d7bfb5ff2a11dc47b69a3992168e993"
PRODUTO = "editor-gs"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verificar(chave: str, hoje: date | None = None, revogadas=None, publica_hex: str | None = None) -> dict:
    """Devolve {"ok": True, "licenca": {...}} ou {"ok": False, "motivo": "..."}. Nunca levanta exceção."""
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.exceptions import InvalidSignature
    hoje = hoje or date.today()
    try:
        chave = (chave or "").strip()
        pref, payload_b, sig_b = chave.split("-", 2)
        if pref != "GS1":
            return {"ok": False, "motivo": "formato desconhecido"}
        payload = _b64d(payload_b); sig = _b64d(sig_b)
        ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(publica_hex or PUBLICA_HEX)).verify(sig, payload)
        lic = json.loads(payload)
    except InvalidSignature:
        return {"ok": False, "motivo": "assinatura inválida (chave alterada ou de outra origem)"}
    except Exception:  # noqa: BLE001
        return {"ok": False, "motivo": "chave ilegível"}
    if lic.get("produto") != PRODUTO:
        return {"ok": False, "motivo": f"chave de outro produto ({lic.get('produto')})"}
    if lic.get("id") in set(revogadas or []):
        return {"ok": False, "motivo": "chave revogada"}
    try:
        if date.fromisoformat(lic["validade"]) < hoje:
            return {"ok": False, "motivo": f"chave vencida em {lic['validade']}"}
    except Exception:  # noqa: BLE001
        return {"ok": False, "motivo": "validade ilegível"}
    return {"ok": True, "licenca": lic}


def emitir(nome: str, dias: int, privada_pem: Path, emitida: date | None = None, id_: str | None = None) -> str:
    """Só na máquina do Raphael (precisa da chave privada)."""
    import secrets
    from datetime import timedelta
    from cryptography.hazmat.primitives import serialization
    priv = serialization.load_pem_private_key(Path(privada_pem).read_bytes(), password=None)
    emitida = emitida or date.today()
    lic = {"id": id_ or secrets.token_hex(3), "nome": nome.strip()[:60], "produto": PRODUTO, "emitida": emitida.isoformat(), "validade": (emitida + timedelta(days=int(dias))).isoformat()}
    payload = json.dumps(lic, ensure_ascii=False, separators=(",", ":")).encode()
    return f"GS1-{_b64e(payload)}-{_b64e(priv.sign(payload))}"


def arquivo(estado_dir: Path) -> Path:
    return Path(estado_dir) / "licenca.json"


def ler(estado_dir: Path) -> dict | None:
    p = arquivo(estado_dir)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


def ativar(estado_dir: Path, chave: str, revogadas=None) -> dict:
    r = verificar(chave, revogadas=revogadas)
    if not r["ok"]:
        return r
    Path(estado_dir).mkdir(parents=True, exist_ok=True)
    arquivo(estado_dir).write_text(json.dumps({"chave": chave.strip(), "licenca": r["licenca"], "ativada": date.today().isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


def situacao(estado_dir: Path, exigida: bool, revogadas=None) -> dict:
    """O que o app e o hook mostram: exigida?, válida?, nome, validade, motivo."""
    if not exigida:
        return {"exigida": False, "ok": True, "motivo": "modo desenvolvimento"}
    d = ler(estado_dir)
    if not d:
        return {"exigida": True, "ok": False, "motivo": "sem chave: peça /editor-gs:chave <chave> no Claude Code (ou bash scripts/editor-gs.sh chave <chave>)"}
    r = verificar(d.get("chave", ""), revogadas=revogadas)
    if not r["ok"]:
        return {"exigida": True, "ok": False, "motivo": r["motivo"]}
    return {"exigida": True, "ok": True, "nome": r["licenca"]["nome"], "validade": r["licenca"]["validade"], "id": r["licenca"]["id"]}


if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser(description="Chave do produto Editor GS")
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("emitir", help="gera uma chave (só com a chave privada do Raphael)"); x.add_argument("--nome", required=True); x.add_argument("--dias", type=int, default=365)
    x.add_argument("--privada", default=str(Path.home() / ".config" / "editor-gs" / "licenca-privada.pem"))
    x = sub.add_parser("verificar"); x.add_argument("chave")
    x = sub.add_parser("ativar", help="grava a chave na instalação (estado/licenca.json)"); x.add_argument("chave"); x.add_argument("--estado")
    a = p.parse_args()
    if a.cmd == "emitir":
        print(emitir(a.nome, a.dias, Path(a.privada)))
    elif a.cmd == "verificar":
        print(json.dumps(verificar(a.chave), ensure_ascii=False))
    elif a.cmd == "ativar":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from servico import caminhos as cam
        r = ativar(Path(a.estado) if a.estado else cam.ESTADO, a.chave, revogadas=(cam.config().get("licenca") or {}).get("revogadas"))
        print(json.dumps(r, ensure_ascii=False)); sys.exit(0 if r["ok"] else 1)
