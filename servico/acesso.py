"""Porta de entrada do app quando ele é aberto de fora da máquina (Tailscale Funnel, link público ou rede do Tailscale).

Regra: pedido vindo de localhost (navegador desta máquina, ponte do GSI, MCP `editor-gs`, testes) nunca passa pela chave.
Qualquer outro host (o endereço público do Tailscale Funnel etc.) precisa do cookie `gs_acesso` com uma chave válida.
Chaves em `.env`: EDITOR_GS_CHAVES="thiago:<chave>,raphael:<chave>" (nome:chave, separados por vírgula; chave com 12+ caracteres).
Sem EDITOR_GS_CHAVES o app fica como antes (só a rede do Tailscale chega nele) — não ligue o Funnel nesse estado.
Quem entrou fica em QUEM (contextvar) durante o pedido: o gateway usa para escolher o agente da pessoa (`agentes_por_pessoa`)
e para anotar `por` no pedido."""
import contextvars
import html
import os

QUEM = contextvars.ContextVar("gs_quem", default="")
COOKIE = "gs_acesso"
DIAS_COOKIE = 365
# Só dados exigem a chave: a API (menos webhooks, que têm token próprio) e os arquivos de entrega. O resto (index, sw.js,
# assets, manifesto, ícones) é a casca do app, sem dado, e precisa carregar sem cookie para o PWA antigo do celular se atualizar.
EXIGEM = ("/api/", "/arquivos/")
LIVRES = ("/entrar", "/api/webhooks/")
HOSTS_LOCAIS = ("localhost", "127.0.0.1", "[::1]", "::1")


def chaves() -> dict:
    """{chave: nome} a partir de EDITOR_GS_CHAVES. Chave curta demais é ignorada (não vale como acesso)."""
    out = {}
    for par in os.environ.get("EDITOR_GS_CHAVES", "").split(","):
        par = par.strip()
        if ":" not in par:
            continue
        nome, ch = par.split(":", 1)
        nome, ch = nome.strip().lower(), ch.strip()
        if nome and len(ch) >= 12:
            out[ch] = nome
    return out


def ativo() -> bool:
    return bool(chaves())


def quem_da_chave(valor) -> str:
    return chaves().get((valor or "").strip(), "")


def local(host: str) -> bool:
    h = (host or "").strip().lower()
    if h.startswith("["):  # [::1]:3200
        return h.startswith("[::1]")
    return h.split(":")[0] in HOSTS_LOCAIS


def livre(caminho: str) -> bool:
    return caminho.startswith(LIVRES)


def exige_chave(caminho: str) -> bool:
    """API e arquivos de entrega pedem a chave; a casca do app não."""
    return caminho.startswith(EXIGEM) and not livre(caminho)


def pagina(erro: str = "") -> str:
    """Página mínima de entrada (sem o app): campo da chave. Cores do manual (marinho, laranja)."""
    aviso = f'<p class="erro">{html.escape(erro)}</p>' if erro else ""
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Editor GS — entrar</title><style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#000921;color:#fff;font:16px/1.5 Inter,system-ui,sans-serif}}
main{{background:#0B193D;border-radius:20px;padding:32px 28px;max-width:360px;width:calc(100% - 32px);box-sizing:border-box}}
h1{{font-size:22px;margin:0 0 6px}} h1 b{{color:#F79615}} p{{margin:0 0 18px;color:#A7ACBD}}
input{{width:100%;box-sizing:border-box;padding:12px 14px;border-radius:12px;border:1px solid #284CB8;background:#000921;color:#fff;font-size:16px}}
button{{margin-top:14px;width:100%;padding:12px;border:0;border-radius:999px;background:linear-gradient(90deg,#F79615,#E9760D);color:#000921;font-weight:700;font-size:16px}}
.erro{{color:#F79615;margin-top:12px}}
</style></head><body><main><h1>Editor <b>GS</b></h1><p>Cole a chave que o Raphael mandou. Ela fica guardada neste aparelho.</p>
<form method="get" action="/entrar"><input name="chave" placeholder="chave de acesso" autocomplete="off" autofocus required><button type="submit">Entrar</button></form>{aviso}</main></body></html>"""


def links(base: str = "") -> list[str]:
    """Links de entrada por pessoa (para o Raphael mandar). Lê EDITOR_GS_CHAVES e EDITOR_GS_URL_PUBLICA do ambiente."""
    base = (base or os.environ.get("EDITOR_GS_URL_PUBLICA", "") or "http://localhost:3200").rstrip("/")
    return [f"{nome}: {base}/entrar?chave={ch}" for ch, nome in chaves().items()]


if __name__ == "__main__":  # python3 servico/acesso.py links  (carrega o .env do projeto)
    import sys
    from pathlib import Path
    envf = Path(__file__).resolve().parents[1] / ".env"
    if envf.is_file():
        for ln in envf.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    if sys.argv[1:2] == ["links"]:
        print("\n".join(links()) or "EDITOR_GS_CHAVES vazio no .env")
    else:
        print("uso: python3 servico/acesso.py links")
