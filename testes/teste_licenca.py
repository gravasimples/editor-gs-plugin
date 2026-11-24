"""Chave do produto: emitir/verificar com par de chaves temporário, vencida, alterada, revogada, outro produto; ativar em pasta temporária;
gateway em modo plugin sem chave responde 402 e com chave responde 200. Isolado (pasta temporária; o par de chaves real não é usado).
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_licenca.py"""
import json, os, sys, tempfile
from datetime import date, timedelta
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(RAIZ))
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from servico import licenca as lic
FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="licenca-")); priv = ed25519.Ed25519PrivateKey.generate()
pem = tmp / "priv.pem"; pem.write_bytes(priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
k = lic.emitir("Thiago Gomes", 365, pem, emitida=date(2026, 11, 10), id_="abc123")
r = lic.verificar(k, hoje=date(2027, 1, 1), publica_hex=pub)
check(r["ok"] and r["licenca"]["nome"] == "Thiago Gomes" and r["licenca"]["validade"] == "2027-11-10", f"emitir/verificar: {r}")
check(not lic.verificar(k, hoje=date(2027, 11, 11), publica_hex=pub)["ok"] and "vencida" in lic.verificar(k, hoje=date(2027, 11, 11), publica_hex=pub)["motivo"], "vencida")
check("revogada" in lic.verificar(k, hoje=date(2027, 1, 1), publica_hex=pub, revogadas=["abc123"])["motivo"], "revogada")
check("assinatura" in lic.verificar(k[:-3] + "AAA", hoje=date(2027, 1, 1), publica_hex=pub)["motivo"], "assinatura alterada")
check("assinatura" in lic.verificar(k, hoje=date(2027, 1, 1))["motivo"], "assinada por outra chave privada (pública real) não vale")
check(not lic.verificar("GS1-xx-yy", publica_hex=pub)["ok"] and "formato" in lic.verificar("ABC-1-2", publica_hex=pub)["motivo"] and not lic.verificar("", publica_hex=pub)["ok"], "chaves ilegíveis")
# ativar/situação com a pública real: usa a chave real do Raphael se existir, senão só confere o caminho sem chave
est = tmp / "estado"
s0 = lic.situacao(est, exigida=False); check(s0["ok"] and not s0["exigida"], "modo desenvolvimento: não exige")
s1 = lic.situacao(est, exigida=True); check(not s1["ok"] and "sem chave" in s1["motivo"], "modo plugin sem chave: motivo claro")
real = Path.home() / ".config" / "editor-gs" / "licenca-privada.pem"
if real.exists():
    kr = lic.emitir("Teste da suíte", 2, real)
    a = lic.ativar(est, kr); s2 = lic.situacao(est, exigida=True)
    check(a["ok"] and s2["ok"] and s2["nome"] == "Teste da suíte" and (est / "licenca.json").exists(), f"ativar com a chave real: {s2}")
    check(not lic.ativar(est, kr[:-2] + "zz")["ok"], "ativar recusa chave inválida sem apagar a válida")
    # gateway em modo plugin
    home = tmp / "EditorGS"; (home / "workspace").mkdir(parents=True); (home / "estado").mkdir()
    (home / "workspace" / "AGENTS.md").write_text("# x\n", encoding="utf-8"); (home / "estado" / "config.local.json").write_text('{"executor": {"modo": "local"}}', encoding="utf-8")
    os.environ["EDITOR_GS_HOME"] = str(home)
    from fastapi.testclient import TestClient
    from servico import api
    c = TestClient(api.app)
    check(api.LICENCA_EXIGIDA and c.get("/api/gs/estado").json()["licenca"]["ok"] is False, "gateway plugin: /estado diz que falta chave")
    r = c.get("/api/gs/conversas"); check(r.status_code == 402 and "sem chave" in r.json()["detail"], f"gateway plugin sem chave: 402 ({r.status_code})")
    r = c.post("/api/gs/licenca", data={"chave": "GS1-a-b"}); check(r.status_code == 400, "ativar chave inválida pelo app: 400")
    r = c.post("/api/gs/licenca", data={"chave": kr}); check(r.status_code == 200 and r.json()["ok"] and r.json()["nome"] == "Teste da suíte", "ativar pelo app: ok")
    r = c.get("/api/gs/conversas"); check(r.status_code == 200, "com chave: API liberada")
else:
    print("SKIP chave privada real ausente (~/.config/editor-gs/licenca-privada.pem)")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
