"""MCP editor-gs (03/11/2026): o Editor GS como ferramenta para outros agentes (Claude Code, Claude Desktop, agentes do GSI).
Fala com o gateway do app (padrão http://localhost:3200, ou EDITOR_GS_URL). Abre pedidos, acompanha, responde e consulta
acervo, ganchos, o que rende e campanhas. Não publica, não aprova e não mexe em conexões: isso continua sendo clique humano no app.
Cada pedido entra na mesma fila do app (um por vez): só abra pedido quando a pessoa pedir."""
import json, mimetypes, os
from pathlib import Path
import httpx
from mcp.server.fastmcp import FastMCP

URL = os.environ.get("EDITOR_GS_URL", "http://localhost:3200").rstrip("/")
mcp = FastMCP("editor-gs")
_cli = httpx.Client(base_url=URL, timeout=httpx.Timeout(60, read=900))


def _req(metodo, caminho, **kw):
    try:
        r = _cli.request(metodo, caminho, **kw)
    except httpx.HTTPError as e:
        return {"erro": f"Editor GS fora do ar em {URL} ({type(e).__name__}). Suba o app (servico/rodar.sh) e tente de novo."}
    if r.status_code >= 400:
        try:
            det = r.json().get("detail")
        except Exception:  # noqa
            det = r.text[:300]
        return {"erro": f"{r.status_code}: {det}"}
    return r.json() if r.content else {}


def _arquivos(caminhos):
    out = []
    for c in [x for x in (caminhos or []) if x]:
        p = Path(c).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"arquivo não encontrado: {c}")
        out.append(("arquivos", (p.name, p.open("rb"), mimetypes.guess_type(p.name)[0] or "application/octet-stream")))
    return out


def _link(cid):
    return f"{URL}/c/{cid}"


def _resumo_conversa(c):
    return {"id": c.get("id"), "codigo": c.get("codigo"), "titulo": c.get("titulo"), "status": c.get("status"), "executando": c.get("executando"), "pasta": c.get("pasta"), "link": _link(c.get("id"))}


@mcp.tool()
def novo_pedido(texto: str, fluxo: str = "", estilo: str = "padrao", arquivos: list[str] | None = None, campanha: str = "", pasta: str = "") -> dict:
    """Abre um pedido no Editor GS (entra na fila do app, um por vez). `texto`: o que fazer, como se fosse escrito no Novo pedido.
    `fluxo`: reels-padrao, carrossel, roteiro, video-locucao, gravo-eu-mesmo, apostila, legendar (vazio), traduzir-legenda, dublagem, minha-versao…
    (lista em `fluxos()`). `estilo`: padrao, tutorial, opiniao, bastidor, profissional, lista, pov ou um estilo montado na página Estilos.
    `arquivos`: caminhos locais (vídeo, áudio, imagem) enviados junto. `campanha`: nome de uma campanha do app (a peça já nasce com a etiqueta).
    Devolve o id, o código (GRA-N) e o link da conversa. Nada é publicado."""
    try:
        files = _arquivos(arquivos)
    except FileNotFoundError as e:
        return {"erro": str(e)}
    dados = {"pedido": texto, "fluxo": fluxo, "estilo": estilo or "padrao", "pasta": pasta, "origem": "mcp", "campanha": campanha}
    c = _req("POST", "/api/gs/conversas", data=dados, files=files or None)
    return c if c.get("erro") else _resumo_conversa(c)


@mcp.tool()
def kit_derivacao(video: str = "", link: str = "", nota: str = "", n_reels: int = 3, carrossel: bool = True, stories: bool = True, youtube: bool = True, tipo_origem: str = "aula") -> dict:
    """Kit de derivação: uma gravação longa (caminho local em `video` ou `link` do YouTube/live) vira N Reels editados (1 a 5),
    carrossel, 3 telas de Stories e descrição/capítulos do YouTube, num pedido só. `tipo_origem`: live, aula, youtube ou call.
    Pedido longo (30 a 60 min). Devolve o link da conversa."""
    if not video and not link:
        return {"erro": "Passe `video` (caminho local) ou `link`."}
    try:
        files = _arquivos([video] if video else [])
    except FileNotFoundError as e:
        return {"erro": str(e)}
    pecas = ",".join(["reels"] + [n for n, on in (("carrossel", carrossel), ("stories", stories), ("youtube", youtube)) if on])
    c = _req("POST", "/api/gs/clipes", data={"nota": nota, "url": link, "tipo_origem": tipo_origem, "modo": "kit", "n_reels": str(n_reels), "pecas": pecas}, files=files or None)
    return c if c.get("erro") else _resumo_conversa(c)


@mcp.tool()
def listar_pedidos(n: int = 15, so_abertos: bool = False) -> list | dict:
    """Pedidos mais recentes do Editor GS (código, título, status, se está rodando agora, link)."""
    d = _req("GET", "/api/gs/conversas")
    if isinstance(d, dict) and d.get("erro"):
        return d
    lista = [c for c in d if not so_abertos or c.get("status") not in ("done", "cancelled")]
    return [_resumo_conversa(c) for c in lista[:max(1, min(n, 100))]]


@mcp.tool()
def ver_pedido(id: str, mensagens: int = 3) -> dict:
    """Estado de um pedido: status, últimas mensagens (do Editor e suas), entregas com link para baixar e os textos da entrega (legenda, gancho…).
    `id` é o id da conversa (não o código GRA-N; use `listar_pedidos` para achar)."""
    c = _req("GET", f"/api/gs/conversas/{id}")
    if c.get("erro"):
        return c
    ents = [{"nome": e["nome"], "tipo": e["tipo"], "url": URL + e["url"], "principal": e.get("principal")} for e in (c.get("entregas") or [])]
    msgs = [{"autor": m["autor"], "quando": m.get("quando"), "texto": (m.get("texto") or "")[:4000]} for m in (c.get("mensagens") or [])[-max(1, mensagens):]]
    return {**_resumo_conversa(c), "mensagens": msgs, "entregas": [e for e in ents if e["principal"]] or ents[:20], "textos": c.get("textos"), "trabalho": c.get("trabalho")}


@mcp.tool()
def responder_pedido(id: str, texto: str, arquivos: list[str] | None = None) -> dict:
    """Manda uma mensagem na conversa do pedido (ajuste, aprovação do plano de cenas, resposta a uma pergunta do Editor), com anexos opcionais.
    Não aprova a entrega final nem publica: isso é clique no app."""
    try:
        files = _arquivos(arquivos)
    except FileNotFoundError as e:
        return {"erro": str(e)}
    r = _req("POST", f"/api/gs/conversas/{id}/mensagens", data={"texto": texto}, files=files or None)
    return r if r.get("erro") else {"ok": True, "link": _link(id)}


@mcp.tool()
def buscar_fala(q: str, limite: int = 10) -> dict:
    """Onde o Thiago fala de X: trechos das transcrições (YouTube, Instagram, lives e entregas do app) com instante e link no ponto exato."""
    d = _req("GET", "/api/gs/acervo", params={"q": q, "limite": max(1, min(limite, 50))})
    if d.get("erro"):
        return d
    return {"q": q, "resultados": [{"titulo": (r.get("fonte") or {}).get("titulo"), "plataforma": (r.get("fonte") or {}).get("plataforma"), "data": (r.get("fonte") or {}).get("data"),
                                    "trecho": r.get("trecho"), "instante_s": r.get("instante"), "instante_tipo": r.get("instante_tipo"), "link": r.get("link")} for r in d.get("resultados", [])]}


@mcp.tool()
def ganchos(tipo: str = "", so_medidos: bool = True, limite: int = 20) -> dict:
    """Ganchos já usados com desempenho (razão sobre a mediana do formato) e a mediana por tipo (pergunta, erro, número, contraste, segredo, novidade, como, história)."""
    d = _req("GET", "/api/gs/ganchos", params={"tipo": tipo, "medidos": "1" if so_medidos else ""})
    if d.get("erro"):
        return d
    return {"tipos": d.get("tipos"), "itens": (d.get("itens") or [])[:max(1, min(limite, 100))]}


@mcp.tool()
def o_que_rende() -> dict:
    """Perfil vivo do Thiago: o que rende por duração, formato, tipo de gancho e horário (números do GSI; faixa com pouca amostra é pista, não regra)."""
    return _req("GET", "/api/gs/perfil/rende")


@mcp.tool()
def campanhas() -> dict:
    """Campanhas e lançamentos do app com período, objetivo, mensagem-chave, peças e números somados."""
    d = _req("GET", "/api/gs/campanhas")
    if d.get("erro"):
        return d
    return {"campanhas": [{k: c.get(k) for k in ("id", "nome", "situacao", "inicio", "fim", "objetivo", "mensagem", "meta_pecas", "n_pecas", "n_publicadas", "views", "razao_mediana", "melhor")} for c in d.get("campanhas", [])]}


@mcp.tool()
def fluxos() -> list | dict:
    """Fluxos de trabalho do Editor (nome e título) para usar em `novo_pedido`."""
    d = _req("GET", "/api/gs/fluxos")
    return d if isinstance(d, dict) else [{"nome": f.get("nome"), "titulo": f.get("titulo")} for f in d]


@mcp.tool()
def fila() -> dict:
    """Estado da fila do Editor GS: o que está rodando agora e quantos pedidos esperam (o app faz um por vez)."""
    d = _req("GET", "/api/gs/conversas")
    if isinstance(d, dict) and d.get("erro"):
        return d
    rodando = [_resumo_conversa(c) for c in d if c.get("executando")]
    esperando = [_resumo_conversa(c) for c in d if c.get("status") == "todo" and not c.get("executando")]
    return {"rodando": rodando, "esperando": esperando[:20], "n_esperando": len(esperando)}


if __name__ == "__main__":
    mcp.run()
