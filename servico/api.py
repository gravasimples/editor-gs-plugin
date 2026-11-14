"""Gateway do Editor GS: liga o app (PWA) ao Paperclip e aos arquivos do workspace.
Rodar: ~/.venvs/editor-gs/bin/python -m uvicorn servico.api:app --host 127.0.0.1 --port 3200 (na raiz do projeto)."""
import asyncio, json, os, re, secrets, shutil, sqlite3, subprocess, time, unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import httpx
import urllib.request, urllib.error
import logging
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

log = logging.getLogger("editor-gs")
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from servico import plataforma as _plat; _plat.aplicar_path()  # Windows: ffmpeg/node/rclone portáteis de ~/EditorGS/bin no PATH
from servico import publicar as pub
from servico import referencias as refs
from servico import clipes as clp
from servico import estilos_biblioteca as eb
from servico import perfil as prf
from servico import pasta_vigiada as pv
from servico import skills_banco as sb
from servico import skills_demos as sdm
from servico import editor_manual as edm
from servico import meta_api
from servico import campanhas as cmp
from servico import materiais as mat
from servico import canva_connect as cv
from servico import redes as rds
from servico import arquivos as arq
from servico import anotacoes as ant
from servico import novidades as nov
from servico import marca as mrc
from servico import textos as txt
from servico import youtube as yt
from servico import voz as vz
from servico import push as pushn
from servico import operacao as opr
from servico import progresso as prg
from servico import pecas as pcs
from servico import metricas as mtr
from servico import automacoes as aut
from servico import automacoes_dados as ad
from servico import acervo as acv
from servico import ganchos as gch
from servico import marca_revisor as mrev
from servico import aprovacoes as aprv
from servico import estilo_criativo as ecr
from servico import atualizador as atz
from servico import drive_anexos as dra
from servico import checkpoints as ckp
from fastapi import Request
from fastapi.responses import RedirectResponse as _Redir
from fastapi import BackgroundTasks

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as cam  # 10/11/2026: pastas de dados fora do código no modo plugin (EDITOR_GS_HOME)
CFG = cam.config()
cam.garantir()
# GSI (grava-simples-intelligence): config.json gsi_db/gsi_raiz → .env GSI_DB/GSI_RAIZ → ~/Desktop/Claude/Claude Code/grava-simples-intelligence.
# 11/11/2026: o padrão era /mnt/c/... (WSL removido) e Ideias/Notion/Automações/Acervo davam 503.
GSI_PADRAO = Path.home() / "Desktop" / "Claude" / "Claude Code" / "grava-simples-intelligence"
GSI_DB = Path(CFG.get("gsi_db") or os.environ.get("GSI_DB", "").strip() or (GSI_PADRAO / "dados" / "gs.db"))
GSI_RAIZ = Path(CFG.get("gsi_raiz") or os.environ.get("GSI_RAIZ", "").strip() or GSI_DB.parents[1])
from servico import acesso as acs  # porta de entrada por chave (acesso de fora da máquina)
from servico import licenca as lic  # chave do produto (só exigida no modo plugin: dados em EDITOR_GS_HOME)
LICENCA_EXIGIDA = bool(cam.HOME) and bool((CFG.get("licenca") or {}).get("exigir", True))
LICENCA_LIVRE = ("/api/gs/estado", "/api/gs/quem", "/api/gs/licenca", "/api/gs/versao")


def _licenca_situacao():
    return lic.situacao(cam.ESTADO, LICENCA_EXIGIDA, revogadas=(CFG.get("licenca") or {}).get("revogadas"))
WORKSPACE = cam.WORKSPACE; ENTRADA, SAIDA = WORKSPACE / "entrada", WORKSPACE / "saida"
REFERENCIAS = WORKSPACE / "referencias"
CLIPES = WORKSPACE / "clipes"
MATERIAIS = WORKSPACE / "materiais"
RECEBIDOS = ENTRADA / "_recebidos"  # material compartilhado do celular, à espera do pedido
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{6,40}$")
INDICE = cam.estado("conversas.json")
NOTION_ESCRITA = bool(CFG.get("notion_escrita", False))  # 31/10/2026: só Notion → app; o Editor não escreve nem edita cartões
DIST = RAIZ / "app" / "dist"
PC = httpx.AsyncClient(base_url=CFG.get("paperclip_url", "http://localhost:3100"), timeout=30)
from servico import executor_local as exl  # 10/11/2026: executor local (sem Paperclip), ligado por config.json → executor.modo = "local"
EXECUTOR_CFG = CFG.get("executor") or {}
MODO_EXECUTOR = EXECUTOR_CFG.get("modo", "paperclip")
_pasta_exec = EXECUTOR_CFG.get("pasta") or ""
_pasta_exec = _pasta_exec if Path(_pasta_exec).is_absolute() else str(cam.WORKSPACE / "executor")  # relativo → sempre dentro do workspace da instalação
EXECUTOR = exl.Executor(RAIZ, {**EXECUTOR_CFG, "pasta": _pasta_exec, "company_id": CFG.get("company_id")}, porta=int(os.environ.get("EDITOR_GS_PORTA") or CFG.get("porta", 3200)), workspace=cam.WORKSPACE) if MODO_EXECUTOR == "local" else None
app = FastAPI(title="Editor GS", version="0.1.0")
app.include_router(meta_api.router)  # Meta/Instagram (10/11/2026): situação, conta, mídias, insights, comentários, concorrentes; sem rota de publicar
EXT_VIDEO, EXT_AUDIO, EXT_IMG = {".mp4", ".mov", ".webm", ".mkv"}, {".m4a", ".mp3", ".wav", ".aac"}, {".png", ".jpg", ".jpeg", ".webp"}


def _slug(texto, n=40):
    t = unicodedata.normalize("NFKD", texto.lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n].strip("-")
    return f"{datetime.now():%Y-%m-%d}-{t or 'pedido'}"


def _indice():
    return json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else {}


def _salvar_indice(d):
    INDICE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _indice_atualizar(issue_id: str, **campos):
    """Grava campos de um pedido relendo o índice na hora (os laços do gateway esperam o Paperclip entre ler e gravar; gravar um
    dicionário lido antes apagava pedidos criados nesse meio-tempo, como aconteceu com o GRA-26)."""
    idx = _indice(); ent = idx.get(issue_id) or {}; ent.update(campos); idx[issue_id] = ent; _salvar_indice(idx); return ent


# Pastas (projetos): agrupam pedidos por campanha, semana ou cliente. Lista em servico/pastas.json; cada pedido guarda `pasta` no índice.
PASTAS = cam.estado("pastas.json")
TEXTOS_CACHE = cam.estado("textos.json")  # entregas em texto por conversa (cache da página Textos e da busca)
TEXTOS_DIR = REFERENCIAS / "_textos"  # .md só do que o Raphael guardou como referência
INICIO = datetime.now().isoformat(timespec="seconds")
URL_PADRAO = os.environ.get("EDITOR_GS_URL_PUBLICA", "").strip() or "http://localhost:3200"  # endereço do app de fora (Tailscale Funnel) vem do .env; sem ele, local
PASTAS_POR_ORIGEM = {"pulso": "Pulso do GSI", "redes": "Redes", **CFG.get("pastas_por_origem", {})}


def _pastas():
    return json.loads(PASTAS.read_text(encoding="utf-8")) if PASTAS.exists() else []


def _salvar_pastas(lista):
    PASTAS.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def _pasta_nome(nome):
    if not isinstance(nome, str):  # chamada interna de nova_conversa sem o campo: chega o objeto Form, não texto
        return ""
    return re.sub(r"\s+", " ", nome).strip()[:40].strip()


def _garantir_pasta(nome):
    """Cria a pasta se não existir e devolve o nome canônico (sem diferenciar maiúsculas)."""
    lista = _pastas()
    for p in lista:
        if p["nome"].lower() == nome.lower():
            return p["nome"]
    usados = {m["pasta"] for m in _indice().values() if m.get("pasta")}  # pasta que só existe no índice (pedidos antigos) mantém a grafia de lá
    canon = next((u for u in usados if u.lower() == nome.lower()), nome)
    lista.append({"nome": canon, "criada": datetime.now().isoformat(timespec="seconds")}); _salvar_pastas(lista)
    return canon


def _tipo(p: Path):
    e = p.suffix.lower()
    return "video" if e in EXT_VIDEO else "audio" if e in EXT_AUDIO else "imagem" if e in EXT_IMG else "legenda" if e in {".ass", ".srt"} else "texto" if e in {".md", ".txt", ".json"} else "editavel" if e in {".pptx", ".pdf"} else "arquivo"


def _entregas(slug):
    pasta = SAIDA / slug
    if not slug or not pasta.exists():
        return []
    itens = []
    for p in sorted(pasta.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            rel = p.relative_to(SAIDA).as_posix()
            partes = p.relative_to(pasta).parts[:-1]
            if any(x.startswith(("_", ".")) or x in ("trabalho", "anteriores") for x in partes):
                continue  # pastas de trabalho e versões anteriores não aparecem no cartão
            if p.suffix in (".py", ".sh") or (p.suffix == ".json" and p.name != "capcut.json") or p.name == "post.txt":
                continue  # scripts, dados de trabalho e o post.txt gerado para o Drive não são entrega
            itens.append({"nome": p.name, "caminho": rel, "url": f"/arquivos/{rel}", "tipo": _tipo(p), "tamanho_mb": round(p.stat().st_size / 1e6, 1),
                          "modificado": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"), "principal": p.name.startswith("final_") or p.name in ("relatorio.md", "post.md", "capa.png", "capcut.json", "carrossel.pptx", "carrossel.pdf")})
    return itens


def _post(md):
    """Separa post.md em seções: descricao, hashtags, titulo, gancho."""
    secoes, atual = {}, None
    for linha in md.splitlines():
        m = re.match(r"^##\s+(.+)$", linha.strip())
        if m:
            nome = unicodedata.normalize("NFKD", m.group(1).lower()); nome = "".join(c for c in nome if not unicodedata.combining(c))
            atual = "descricao" if "descri" in nome else "hashtags" if "hashtag" in nome else "titulo" if "titulo" in nome else "gancho" if "gancho" in nome else nome
            secoes[atual] = []
        elif atual:
            secoes[atual].append(linha)
    return {k: "\n".join(v).strip() for k, v in secoes.items() if "\n".join(v).strip()}


async def _pc(metodo, url, **kw):
    if EXECUTOR is not None:  # modo local: mesmas rotas e campos, em processo
        return await EXECUTOR.chamar(metodo, url, json=kw.get("json"))
    r = await PC.request(metodo, url, **kw)
    if r.status_code >= 400:
        raise HTTPException(502, f"Paperclip {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else None


_MODELOS_BASE = {"padrao": {"chave": "agent_id", "rotulo": "Opus 5.5"}, "fable": {"chave": "agent_fable_id", "rotulo": "Fable 5.1"}, "codex": {"chave": "agent_codex_id", "rotulo": "Codex (ChatGPT)"}, "gemini": {"chave": "agent_gemini_id", "rotulo": "Gemini (Antigravity)"}, "thiago": {"chave": "agent_thiago_id", "rotulo": "Opus 5.5 (conta do Thiago)"}}


def _modelos_de(cfg):
    """Mapa de modelos: a base acima, sobreposta por config.json → modelos (10/11/2026): {"padrao": {"agente": "agent_fable_id", "rotulo": "Fable 5.1
    (esforço baixo)"}, "opus": {"agente": "agent_id", ...}}. Assim o padrão pode ser o Fable em esforço baixo (decisão do Raphael) sem mexer no
    código, e "opus" vira chave própria quando configurada. Testes chamam com config sem `modelos` para ter o mapa base."""
    m = {k: dict(v) for k, v in _MODELOS_BASE.items()}
    for k, v in (cfg.get("modelos") or {}).items():
        if isinstance(v, dict) and v.get("agente"):
            m[k] = {"chave": v["agente"], "rotulo": v.get("rotulo") or m.get(k, {}).get("rotulo") or k}
    return m


MODELOS = _modelos_de(CFG)
_PEDE_FABLE = re.compile(r"\b(usa|use|usar|troca|trocar|mud[ae]|mudar|passa|passar|faz|faça|refa[zç]|com)\b[^.\n]{0,40}\b(fable)\b|\bfable\b[^.\n]{0,30}\b(edição|edicao|modelo|robust)", re.I)
_PEDE_OPUS = re.compile(r"\b(usa|use|usar|troca|trocar|mud[ae]|mudar|volta|voltar|passa|passar|com)\b[^.\n]{0,40}\b(opus|modelo (padr[aã]o|normal))\b", re.I)
_PEDE_CODEX = re.compile(r"\b(usa|use|usar|troca|trocar|mud[ae]|mudar|passa|passar|com)\b[^.\n]{0,40}\b(codex|chatgpt|gpt)\b", re.I)
_PEDE_GEMINI = re.compile(r"\b(usa|use|usar|troca|trocar|mud[ae]|mudar|passa|passar|com)\b[^.\n]{0,40}\b(gemini|antigravity|agy|google)\b", re.I)
_PEDE_SONNET = re.compile(r"\b(usa|use|usar|troca|trocar|mud[ae]|mudar|passa|passar|com)\b[^.\n]{0,40}\b(sonnet)\b", re.I)


_INSTRUCOES_SINC = {"quando": 0.0}


async def _sincronizar_instrucoes(forcar: bool = False):
    """Copia `workspace/AGENTS.md` para o arquivo de instruções gerenciado de cada agente do Paperclip quando o conteúdo
    difere. O Paperclip recusa link simbólico nos adaptadores Codex/Gemini e o Claude já mandou instrução congelada uma vez;
    a cópia sincronizada a cada pedido evita os dois. Nunca derruba o pedido: erro vira aviso no log."""
    import time as _t
    if EXECUTOR is not None:  # o executor local lê workspace/AGENTS.md direto; nada a copiar
        return []
    if not forcar and _t.monotonic() - _INSTRUCOES_SINC["quando"] < 30:
        return []
    _INSTRUCOES_SINC["quando"] = _t.monotonic()
    fonte = WORKSPACE / "AGENTS.md"
    if not fonte.is_file():
        return []
    conteudo = fonte.read_bytes(); feitos = []
    try:
        agentes = await _pc("GET", f"/api/companies/{CFG['company_id']}/agents")
    except Exception as e:
        log.warning("sincronizar instruções: Paperclip indisponível (%s)", e); return []
    ids = {CFG.get(m["chave"]) for m in MODELOS.values()} - {None}
    for a in agentes:
        if a.get("id") not in ids:
            continue
        alvo = (a.get("adapterConfig") or {}).get("instructionsFilePath")
        if not alvo:
            continue
        try:
            p = Path(alvo)
            if p.is_symlink():
                p.unlink()
            if not p.exists() or p.read_bytes() != conteudo:
                p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(conteudo); feitos.append(a.get("name"))
        except Exception as e:
            log.warning("sincronizar instruções de %s: %s", a.get("name"), e)
    # A pasta de trabalho do projeto (cwd dos agentes) tem um AGENTS.md próprio que o Codex e o agy leem sozinhos; se existir, fica igual ao do workspace.
    try:
        pj = Path.home() / ".paperclip" / "instances" / "default" / "projects" / CFG["company_id"] / CFG["project_id"] / "_default" / "AGENTS.md"
        if pj.is_file() and not pj.is_symlink() and pj.read_bytes() != conteudo:
            pj.write_bytes(conteudo); feitos.append("pasta do projeto")
    except Exception as e:
        log.warning("sincronizar AGENTS.md da pasta do projeto: %s", e)
    if feitos:
        log.info("instruções sincronizadas: %s", ", ".join(feitos))
    return feitos


def _agente_do_modelo(modelo: str):
    """Agente do modelo pedido. Com `modelo` vazio/"padrao", quem entrou pela chave (acesso.QUEM) pode ter agente próprio em
    config `agentes_por_pessoa` ({"thiago": "agent_thiago_id"}): o pedido do Thiago vai para o agente logado na conta Claude dele."""
    quem = acs.QUEM.get()
    if (modelo or "padrao").lower() == "padrao" and quem:
        chave = (CFG.get("agentes_por_pessoa") or {}).get(quem)
        if chave and CFG.get(chave):
            return CFG[chave]
    m = MODELOS.get((modelo or "padrao").lower()) or MODELOS["padrao"]
    aid = CFG.get(m["chave"])
    if not aid:
        raise HTTPException(503, f"Modelo {m['rotulo']} não configurado (falta {m['chave']} em servico/config.json).")
    return aid


def _modelo_padrao_do_fluxo(fluxo: str):
    """Roteamento por fluxo (config `fluxo_modelo`): tarefas mecânicas podem ir para outro agente/cota. O valor pode ser um
    modelo ou uma lista em ordem de preferência (["codex", "gemini"]); o primeiro com agente configurado vence, senão o padrão."""
    pref = (CFG.get("fluxo_modelo") or {}).get(fluxo or "", "padrao")
    for m in (pref if isinstance(pref, (list, tuple)) else [pref]):
        if m in MODELOS and CFG.get(MODELOS[m]["chave"]):
            return m
    return "padrao"


def _linha_estilo(estilo: str) -> str:
    """Linha do pedido sobre o estilo. Estilos por tema (tutorial, opiniao, bastidor...) têm `descricao` e um bloco `montagem` com o que ligar
    (terço inferior, vinheta, J-cut, fundo dos slides): o agente precisa saber que deve aplicar isso nas ferramentas de montagem, em qualquer fluxo."""
    try:
        e = json.loads((RAIZ / "estilos" / f"{estilo}.json").read_text(encoding="utf-8"))
    except Exception:
        return f"Estilo de legenda: `{estilo}`."
    m = e.get("montagem") or {}
    ligados = [k for k in ("terco_inferior", "vinheta", "jcut_s", "slides_fundo", "zoom_por_frase", "clarao_transicao", "tela_final_cta", "sfx", "barra_progresso") if m.get(k)]
    # 13/11/2026: a linha sempre diz o que o estilo DESLIGA. Antes o `padrao` ia só com o nome e o agente montava com zoom, clarão e tela final.
    rot = {"zoom_por_frase": "zoom", "clarao_transicao": "clarão", "tela_final_cta": "tela final", "sfx": "efeitos sonoros", "barra_progresso": "barra de progresso"}
    desligados = [rot[k] for k in rot if not m.get(k)] + (["gráficos"] if not m.get("grafismos") and not m.get("palavras_chave") else [])
    nivel = m.get("nivel")
    return (f"Estilo: `{estilo}`{f' (nível {nivel})' if nivel else ''}" + (f" — {e['descricao'].split('. ')[0].rstrip('.')}" if e.get("descricao") else "") + ". "
            f"Desligado neste estilo, não acrescente sem pedido: {', '.join(desligados) or 'nada'}. "
            + (f"Ligado: {', '.join(ligados)}; aplique o bloco `montagem` de `estilos/{estilo}.json` (terço = `terco_texto`/`terco_sub`, vinheta = `vinheta=True`, "
               "J-cut = `jcut_s` no `montar_locucao`, fundo dos slides = `slides_fundo`). " if ligados else "")
            + "Em `montar_remotion`, parâmetro em branco já segue o estilo.")


# Conversa para quem não é técnico (11/11/2026): a fala "Você" mostra só o que o usuário escreveu; o pedido completo que vai para o agente
# (fluxo, estilo, caminhos saida/, nomes de ferramenta) fica em "detalhes técnicos". O título vira o pedido curto, sem GRA-NN.
_BLOCOS_DO_APP = re.compile(r"\n\s*\n(?=Arquivos enviados:|Referência: `referencias/|Fluxo: `fluxos/|Estilo do criativo \(painel\)|Estilo de legenda: `|Estilo: `|Entregue os arquivos em `saida/"
                            r'|Siga a ficha de marca:|Modo automático:|Narre com a voz clonada|Peça da campanha ")')
PASTA_TESTES = "Testes do sistema"
_TESTE_RE = re.compile(r"teste[\s\-_]*t[eé]cnico[\s\-_]*do[\s\-_]*sistema|(^|/)_teste", re.I)


def _pedido_do_usuario(descricao: str) -> str:
    """Parte do pedido escrita pelo usuário: o que vem antes do primeiro bloco montado pelo app (pedidos antigos, sem `pedido_usuario` no índice)."""
    t = re.sub(r"<!--.*?-->", "", descricao or "", flags=re.S).strip()
    return _BLOCOS_DO_APP.split(t, 1)[0].strip()


def _titulo_curto(texto: str, n: int = 60) -> str:
    """Título curto do pedido: o que o usuário escreveu, sem GRA-NN, crases e o cabeçalho de "Continuação de…", cortado em ~n caracteres."""
    t = re.sub(r"<!--.*?-->", "", texto or "", flags=re.S)
    if "Agora quero:" in t and t.split("Agora quero:", 1)[1].strip():
        t = t.split("Agora quero:", 1)[1]
    t = re.sub(r'^\s*Continuação de [A-Z]+-\d+\s*(\("[^\n]*?"\))?\.?', "", t)
    t = re.sub(r"\b[A-Z]{2,5}-\d+\b", "", t); t = re.sub(r"[`*#]+", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .:;,-–—…")
    if not t:
        return (texto or "").strip()[:n]
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(" ", 1)[0] if " " in t[:n] else t[:n]
    return corte.rstrip(" .,;:-–—") + "…"


def _eh_teste(pasta, *textos) -> bool:
    """Conversa/entrega de teste do sistema (pasta "Testes do sistema", título "Teste técnico do sistema", pasta de saída _teste…): escondidas por padrão."""
    return (pasta or "") == PASTA_TESTES or any(_TESTE_RE.search(x or "") for x in textos)


def _modelo_do_agente(aid: str):
    for nome, m in MODELOS.items():
        if CFG.get(m["chave"]) == aid:
            return {"id": nome, "rotulo": m["rotulo"]}
    return {"id": "outro", "rotulo": "outro agente"}


def _modelo_pedido_no_texto(texto: str):
    """Pedido de troca de modelo escrito no chat ("usa o Fable", "volta para o Opus"). None quando não há."""
    t = texto or ""
    if _PEDE_FABLE.search(t):
        return "fable"
    if _PEDE_OPUS.search(t):
        # com o Fable como padrão, "usa o Opus" vai para a chave "opus" (quando configurada); "modelo padrão/normal" continua "padrao"
        return "opus" if ("opus" in MODELOS and CFG.get(MODELOS["opus"]["chave"]) and re.search(r"\bopus\b", t, re.I)) else "padrao"
    if _PEDE_SONNET.search(t) and "sonnet" in MODELOS and CFG.get(MODELOS["sonnet"]["chave"]):
        return "sonnet"
    if _PEDE_CODEX.search(t):
        return "codex"
    if _PEDE_GEMINI.search(t):
        return "gemini"
    return None


def _conversa(issue, idx):
    slug = idx.get(issue["id"], {}).get("slug")
    if not slug:
        m = re.search(r"gs-slug:\s*([\w\-]+)", issue.get("description") or "")
        slug = m.group(1) if m else None
    ent = idx.get(issue["id"], {})
    titulo = _titulo_curto(issue.get("title") or "") or issue.get("title")  # pedidos antigos têm o começo do prompt como título
    return {"id": issue["id"], "codigo": issue.get("identifier"), "titulo": titulo, "titulo_completo": issue.get("title"), "status": issue.get("status"),
            "teste": _eh_teste(ent.get("pasta"), issue.get("title"), slug),
            "atualizado": issue.get("updatedAt"), "criado": issue.get("createdAt"), "slug": slug, "executando": bool(issue.get("activeRun")),
            "pasta": idx.get(issue["id"], {}).get("pasta"), "notion_page": idx.get(issue["id"], {}).get("notion_page"), "modelo": _modelo_do_agente(issue.get("assigneeAgentId")),
            "reservas": idx.get(issue["id"], {}).get("reservas") or [], "drive": idx.get(issue["id"], {}).get("drive"),
            "excluida": idx.get(issue["id"], {}).get("excluida")}


def _proximo_modelo(atual: str, fluxo: str | None, tentados: list[str]) -> str | None:
    """Próximo modelo de reserva: a lista do fluxo (`fluxo_modelo`) e depois o padrão; pula o atual, os já tentados e os sem agente.
    Compara também o agente: "padrao" e "opus" podem ser o mesmo agente (11/11/2026), e trocar para ele mesmo não é reserva."""
    pref = (CFG.get("fluxo_modelo") or {}).get(fluxo or "", [])
    pref = list(pref if isinstance(pref, (list, tuple)) else [pref])
    usados = {CFG.get(MODELOS[x]["chave"]) for x in [atual, *tentados] if x in MODELOS} - {None}
    for m in pref + ["padrao"]:
        aid = CFG.get(MODELOS[m]["chave"]) if m in MODELOS else None
        if aid and m != atual and m not in tentados and aid not in usados:
            return m
    return None


def _trocar_por_limite(issue: dict, agente: dict, motivo: str):
    """Gancho do executor local (11/11/2026): a rodada falhou por limite de uso/cota da conta. Devolve o id do próximo agente da lista
    do fluxo (via `_proximo_modelo`) e registra a troca em `reservas` no índice; None quando não há próximo (todos já tentados, sem
    índice ou `reserva_max` atingido): o executor bloqueia o pedido, sem laço."""
    ent = _indice().get(issue["id"])
    if not ent or not CFG.get("reserva_automatica", True):
        return None
    reservas = ent.get("reservas") or []
    if len(reservas) >= int(CFG.get("reserva_max", 2)):
        return None
    atual = _modelo_do_agente(agente["id"])["id"]
    prox = _proximo_modelo(atual, ent.get("fluxo"), [r["de"] for r in reservas] + [r["para"] for r in reservas] + [atual])
    if not prox:
        return None
    reg = {"de": atual, "para": prox, "quando": datetime.now().isoformat(timespec="seconds"), "motivo": f"limite de uso: {motivo}"[:240], "imediata": True}
    _indice_atualizar(issue["id"], reservas=reservas + [reg])
    log.info("limite de uso: %s %s → %s (%s)", issue.get("identifier"), atual, prox, motivo)
    return CFG[MODELOS[prox]["chave"]]


async def _motivo_travado(cid: str) -> str:
    """Motivo curto do travamento: erro da última execução ou a última mensagem do agente (ações negadas, cota...)."""
    partes = []
    try:
        runs = await _pc("GET", f"/api/issues/{cid}/runs"); runs = runs if isinstance(runs, list) else runs.get("runs", runs.get("items", []))
        for r in sorted(runs, key=lambda r: r.get("createdAt") or "", reverse=True)[:3]:
            e = r.get("error") or r.get("errorCode") or r.get("retryExhaustedReason")
            if e:
                partes.append(str(e)[:160]); break
    except Exception:
        pass
    try:
        cm = await _pc("GET", f"/api/issues/{cid}/comments"); cm = cm if isinstance(cm, list) else cm.get("comments", cm.get("items", []))
        ag = [m for m in sorted(cm, key=lambda m: m.get("createdAt", "")) if m.get("authorAgentId") and "Paperclip exhausted" not in (m.get("body") or "")]
        if ag:
            linhas = [l.strip() for l in (ag[-1].get("body") or "").splitlines() if l.strip() and not l.strip().startswith("#")]
            pista = next((l for l in linhas if re.search(r"negad|erro|error|cota|limit|falh|não consegu|nao consegu|denied|quota", l, re.I)), linhas[0] if linhas else "")
            if pista:
                partes.append(pista[:200])
    except Exception:
        pass
    return " | ".join(partes) or "o agente parou sem entregar"


async def _travado_de_verdade(issue: dict) -> bool:
    """O Paperclip marca `blocked` e ainda pode rodar uma última tentativa (reparo), e o agente pode entregar antes de o status mudar.
    Só vale trocar quando: a trava tem idade (`reserva_espera_s`), nenhuma execução está ativa ou terminou há pouco, e a última
    mensagem do agente não é uma entrega (`## Resumo`/`## Arquivos`)."""
    espera = int(CFG.get("reserva_espera_s", 180))
    try:
        upd = datetime.fromisoformat((issue.get("updatedAt") or "").replace("Z", "+00:00"))
        if (datetime.now(upd.tzinfo) - upd).total_seconds() < espera:
            return False
    except Exception:
        pass
    try:
        runs = await _pc("GET", f"/api/issues/{issue['id']}/runs"); runs = runs if isinstance(runs, list) else runs.get("runs", runs.get("items", []))
        for r in runs:
            if r.get("status") in ("running", "queued", "pending", "scheduled_retry", "starting"):
                return False
            fim = r.get("finishedAt")
            if fim:
                f = datetime.fromisoformat(fim.replace("Z", "+00:00"))
                if (datetime.now(f.tzinfo) - f).total_seconds() < espera:
                    return False
    except Exception:
        pass
    try:
        cm = await _pc("GET", f"/api/issues/{issue['id']}/comments"); cm = cm if isinstance(cm, list) else cm.get("comments", cm.get("items", []))
        ag = [m for m in sorted(cm, key=lambda m: m.get("createdAt", "")) if m.get("authorAgentId")]
        if ag and re.search(r"^## (Resumo|Arquivos)", ag[-1].get("body") or "", re.M):
            return False
    except Exception:
        pass
    return True


async def reservar_travados() -> list[dict]:
    """Reserva automática: pedido `blocked` (o Paperclip desistiu depois das tentativas) passa para o próximo modelo da lista do fluxo
    e, por fim, para o padrão (Opus). Até `reserva_max` trocas por pedido; cada troca vira comentário na conversa e fica no índice."""
    if not CFG.get("reserva_automatica", True):
        return []
    try:
        issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
    except Exception as e:
        log.warning("reserva automática: Paperclip indisponível (%s)", e); return []
    idx = _indice(); feitas = []
    for i in issues:
        ent = idx.get(i["id"])
        if i.get("status") != "blocked" or not ent or i.get("activeRun"):
            continue
        reservas = ent.get("reservas") or []
        if len(reservas) >= int(CFG.get("reserva_max", 2)):
            continue
        atual = _modelo_do_agente(i.get("assigneeAgentId"))["id"]
        prox = _proximo_modelo(atual, ent.get("fluxo"), [r["de"] for r in reservas] + [atual])
        if not prox or not await _travado_de_verdade(i):
            continue
        motivo = await _motivo_travado(i["id"])
        de, para = MODELOS.get(atual, {}).get("rotulo", atual), MODELOS[prox]["rotulo"]
        try:
            await _pc("POST", f"/api/issues/{i['id']}/comments", json={"body": f"Reserva automática: o {de} não conseguiu concluir ({motivo}). Passando o pedido para o {para}: leia a conversa inteira e os arquivos já em `saida/` antes de continuar; não repita o que já está bom."})
            await _pc("PATCH", f"/api/issues/{i['id']}", json={"status": "todo", "assigneeAgentId": _agente_do_modelo(prox)})
        except Exception as e:
            log.warning("reserva automática de %s: %s", i.get("identifier"), e); continue
        reg = {"de": atual, "para": prox, "quando": datetime.now().isoformat(timespec="seconds"), "motivo": motivo}
        _indice_atualizar(i["id"], reservas=reservas + [reg]); feitas.append({"id": i["id"], "codigo": i.get("identifier"), **reg})
        log.info("reserva automática: %s %s → %s (%s)", i.get("identifier"), atual, prox, motivo)
    return feitas


RUN_LOGS = EXECUTOR.logs if EXECUTOR is not None else Path.home() / ".paperclip" / "instances" / "default" / "data" / "run-logs"
MARCA_RECUPERADA = "_(Mensagem final recuperada pelo app do registro da rodada: o agente terminou sem postá-la na conversa.)_"


def _texto_final_do_log(conteudo: str):
    """Último evento `result` de um log de rodada do Paperclip (linhas ndjson com `chunk` em stream-json do Claude Code; a ponte do
    Gemini manda `response`) cujo texto tenha seções `## ` (a entrega em texto). None se não houver."""
    achado = None
    for linha in (conteudo or "").splitlines():
        try:
            e = json.loads(linha)
        except Exception:
            continue
        ch = e.get("chunk") if isinstance(e, dict) and "chunk" in e else linha
        if not isinstance(ch, str) or '"result"' not in ch:
            continue
        try:
            ev = json.loads(ch)
        except Exception:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            t = ev.get("result") if isinstance(ev.get("result"), str) else ev.get("response")
            if isinstance(t, str) and re.search(r"^## ", t, re.M):
                achado = t.strip()
    return achado


async def _log_da_rodada(run_id: str) -> str:
    """Log da rodada: o arquivo em disco (`logRef`, sem limite de tamanho) ou o conteúdo que a API devolve."""
    try:
        d = await _pc("GET", f"/api/heartbeat-runs/{run_id}/log")
    except Exception:
        return ""
    ref = d.get("logRef") if isinstance(d, dict) else None
    if ref:
        arq = RUN_LOGS / ref
        if arq.is_file():
            try:
                return arq.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return (d or {}).get("content") or "" if isinstance(d, dict) else ""


async def recuperar_mensagens_finais(horas: int = 48) -> list[dict]:
    """Rede de segurança: o agente às vezes termina a rodada escrevendo a entrega (`## Resumo`...) como texto final do processo em vez
    de postar na conversa (aconteceu com o Opus no GRA-26). Para pedidos entregues sem nenhuma mensagem do agente com `## Resumo`/
    `## Arquivos`, o gateway procura esse texto no log da última rodada concluída e posta como comentário, marcado. Cada rodada é lida
    uma vez (`recuperados` no índice)."""
    try:
        issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
    except Exception as e:
        log.warning("recuperar mensagens finais: Paperclip indisponível (%s)", e); return []
    idx = _indice(); feitas = []; agora = datetime.now().astimezone()
    for i in issues:
        ent = idx.get(i["id"])
        if not ent or i.get("status") not in ("in_review", "done") or i.get("activeRun"):
            continue
        try:
            upd = datetime.fromisoformat((i.get("updatedAt") or "").replace("Z", "+00:00"))
            if (agora - upd).total_seconds() > horas * 3600:
                continue
        except Exception:
            continue
        try:
            cm = await _pc("GET", f"/api/issues/{i['id']}/comments"); cm = cm if isinstance(cm, list) else cm.get("comments", cm.get("items", []))
        except Exception:
            continue
        if any(re.search(r"^## (Resumo|Arquivos)", m.get("body") or "", re.M) for m in cm):
            continue
        try:
            runs = await _pc("GET", f"/api/issues/{i['id']}/runs"); runs = runs if isinstance(runs, list) else runs.get("runs", runs.get("items", []))
        except Exception:
            continue
        if any(r.get("status") in ("running", "queued", "pending", "starting") for r in runs):
            continue
        ok = sorted([r for r in runs if r.get("status") == "succeeded" and r.get("finishedAt")], key=lambda r: r["finishedAt"], reverse=True)
        if not ok:
            continue
        try:
            fim = datetime.fromisoformat(ok[0]["finishedAt"].replace("Z", "+00:00"))
            if (agora - fim).total_seconds() < 120:
                continue
        except Exception:
            pass
        vistos = ent.get("recuperados") or []
        texto = None; lidos = []
        for r in ok[:3]:
            if r["runId"] in vistos:
                continue
            lidos.append(r["runId"])
            texto = _texto_final_do_log(await _log_da_rodada(r["runId"]))
            if texto:
                break
        if not lidos:
            continue
        _indice_atualizar(i["id"], recuperados=vistos + lidos)
        if texto:
            try:
                await _pc("POST", f"/api/issues/{i['id']}/comments", json={"body": texto + "\n\n" + MARCA_RECUPERADA})
                feitas.append({"id": i["id"], "codigo": i.get("identifier"), "run": lidos[-1], "chars": len(texto)})
                log.info("mensagem final recuperada: %s (rodada %s)", i.get("identifier"), lidos[-1][:8])
            except Exception as e:
                log.warning("recuperar mensagem final de %s: %s", i.get("identifier"), e)
    return feitas


def _autor_comentario(m: dict) -> str:
    b = m.get("body") or ""
    if m.get("authorAgentId") or MARCA_RECUPERADA in b:
        return "editor"
    if b.startswith("Reserva automática:") or b.startswith("↶ Desfeito:"):
        return "app"
    return "voce"


async def _laco_reserva():
    import asyncio
    while True:
        try:
            await reservar_travados()
            await recuperar_mensagens_finais()
        except Exception as e:
            log.warning("laço da reserva automática: %s", e)
        await asyncio.sleep(int(CFG.get("reserva_intervalo_s", 60)))


PUSH_VIGIA = pushn.Vigia()


async def _laco_push():
    """Vigia das notificações push: a cada 30 s lê as issues (e as interactions pendentes das que estão em andamento) e avisa os aparelhos inscritos."""
    import asyncio as _a
    while True:
        try:
            if pushn.listar():
                issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
                issues = [i for i in issues if i.get("status") != "cancelled"]
                pend = {}
                for it in issues:
                    if it.get("status") in ("in_progress", "todo", "blocked"):
                        try:
                            lst = await _pc("GET", f"/api/issues/{it['id']}/interactions")
                            lst = lst if isinstance(lst, list) else lst.get("interactions", [])
                            abertas = [x for x in lst if x.get("status") in ("pending", "open", "waiting", None) and not x.get("resolvedAt")]
                            if abertas:
                                pend[it["id"]] = abertas
                        except Exception:  # noqa
                            pass
                for titulo, corpo, url, tag in PUSH_VIGIA.avaliar(issues, pend):
                    r = pushn.enviar(titulo, corpo, url, tag)
                    log.info("push: %s → %s", titulo, r)
            else:
                PUSH_VIGIA.primeira = True  # sem aparelho inscrito, não acumula estado antigo
        except Exception as e:  # noqa
            log.warning("vigia push: %s", e)
        await _a.sleep(30)


# --- Peças: ficha única e etiquetas (base da aba Métricas e Automações) ------------------------------------------------
@app.get("/api/gs/pecas")
def pecas_listar(q: str = "", campanha: str = "", pilar: str = "", formato: str = "", voz: str = "", origem: str = "", estado: str = ""):
    """Uma linha por entrega com etiquetas efetivas (humanas por cima das inferidas), estado de uso e última métrica do GSI."""
    cache = txt.cache_ler(TEXTOS_CACHE)
    linhas = pcs.listar(SAIDA, GSI_DB, cache, {"q": q, "campanha": campanha, "pilar": pilar, "formato": formato, "voz": voz, "origem": origem, "estado": estado})
    todas = pcs.listar(SAIDA, GSI_DB, cache) if any((q, campanha, pilar, formato, voz, origem, estado)) else linhas
    return {"itens": linhas, "resumo": pcs.resumo(todas), "opcoes": {**pcs.config(), "formatos": pcs.FORMATOS, "vozes": pcs.VOZES, "origens": pcs.ORIGENS, "redes": pcs.REDES}}


@app.get("/api/gs/pecas/{slug}")
def peca_ficha(slug: str):
    if not re.match(r"^[\w\-]{1,120}$", slug) or not (SAIDA / slug).is_dir():
        raise HTTPException(404, "Peça não encontrada.")
    idx = _indice(); cid = next((k for k, v in idx.items() if v.get("slug") == slug), None)
    conv = {"id": cid, **({k: idx[cid].get(k) for k in ("pasta", "notion_page", "corte_de", "referencia")} if cid else {})}
    return pcs.ficha(slug, SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE), _entregas(slug), conv)


@app.post("/api/gs/pecas/{slug}/etiquetas")
def peca_etiquetas(slug: str, campanha: str = Form(None), pilar: str = Form(None), gancho: str = Form(None), formato: str = Form(None), cta: str = Form(None), voz: str = Form(None), origem: str = Form(None), redes: str = Form(None), nota: str = Form(None), limpar: str = Form("")):
    """Grava as etiquetas escolhidas pelo humano (só os campos enviados). `limpar=formato,gancho` apaga a escolha humana desses campos (volta ao inferido). Listas: GET /api/gs/pecas → opcoes."""
    if not re.match(r"^[\w\-]{1,120}$", slug) or not (SAIDA / slug).is_dir():
        raise HTTPException(404, "Peça não encontrada.")
    campos = {k: v for k, v in dict(campanha=campanha, pilar=pilar, gancho=gancho, formato=formato, cta=cta, voz=voz, origem=origem, redes=redes, nota=nota).items() if v not in (None, "")}
    for k in (x.strip() for x in limpar.split(",") if x.strip()):
        campos[k] = ""
    try:
        pcs.gravar(SAIDA / slug, campos)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return pcs.etiquetas(SAIDA / slug)


@app.post("/api/gs/pecas/opcoes")
def peca_opcoes(campo: str = Form(...), valor: str = Form(...)):
    """Acrescenta uma campanha, um pilar ou um CTA às listas de etiquetas."""
    try:
        return pcs.config_adicionar(campo, valor)
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- Campanhas e lançamentos (03/11/2026): peças agrupadas pela etiqueta "campanha", com período, objetivo e números do GSI -----
def _campanhas_resumo():
    linhas = pcs.listar(SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE))
    return [cmp.resumo(c, linhas) for c in cmp.listar_bruto()]


@app.get("/api/gs/campanhas")
def campanhas_listar():
    """Campanhas com o resumo de cada uma (peças, publicadas, views, mediana da razão, melhor peça, progresso da meta)."""
    ordem = {"no ar": 0, "planejada": 1, "sem data": 2, "encerrada": 3}
    lista = sorted(_campanhas_resumo(), key=lambda r: (ordem.get(r["situacao"], 9), r.get("inicio") or ""), reverse=False)
    return {"campanhas": lista, "redes": pcs.REDES}


@app.post("/api/gs/campanhas")
def campanhas_salvar(nome: str = Form(...), id: str = Form(""), inicio: str = Form(""), fim: str = Form(""), objetivo: str = Form(""), mensagem: str = Form(""), meta_pecas: str = Form(""), redes: str = Form(""), notas: str = Form("")):
    """Cria ou atualiza uma campanha; o nome entra também na lista de etiquetas das peças."""
    try:
        c = cmp.salvar(dict(id=id or None, nome=nome, inicio=inicio, fim=fim, objetivo=objetivo, mensagem=mensagem, meta_pecas=meta_pecas, redes=redes, notas=notas))
        pcs.config_adicionar("campanhas", c["nome"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return c


@app.delete("/api/gs/campanhas/{cid}")
def campanhas_apagar(cid: str):
    """Apaga o registro da campanha; as peças continuam com a etiqueta."""
    try:
        cmp.apagar(cid)
    except KeyError:
        raise HTTPException(404, "Campanha não encontrada.")
    return {"ok": True}


@app.post("/api/gs/campanhas/{cid}/ligar")
def campanhas_ligar(cid: str, slugs: str = Form(...)):
    """Liga peças à campanha (etiqueta campanha = nome). Clique humano na sugestão."""
    c = next((x for x in cmp.listar_bruto() if x["id"] == cid), None)
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    feitos = []
    for slug in [x.strip() for x in slugs.split(",") if x.strip()]:
        if re.match(r"^[\w\-]{1,120}$", slug) and (SAIDA / slug).is_dir():
            pcs.gravar(SAIDA / slug, {"campanha": c["nome"]}); feitos.append(slug)
    return {"ligadas": feitos}


@app.post("/api/gs/campanhas/{cid}/analise")
async def campanhas_analise(cid: str):
    """Pede ao Editor a análise da campanha (fluxo analise-resultados), com a tabela das peças."""
    r = next((x for x in _campanhas_resumo() if x["id"] == cid), None)
    if not r:
        raise HTTPException(404, "Campanha não encontrada.")
    return await nova_conversa(pedido=cmp.pedido_analise(r), fluxo="analise-resultados", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="campanha", pasta=f"Campanha {r['nome']}"[:60], modelo="")


# --- Central de aprovação e revisor de marca (item 3 da ordem de 31/10/2026) ---------------------------------------------
def _revisao_marca_de(textos_secoes, slug=None):
    t = {s.get("chave"): s.get("conteudo") for s in (textos_secoes or [])}
    campos = {k: t.get(k) for k in ("descricao", "roteiro", "titulo", "gancho", "hashtags", "gravar", "resumo")}
    if slug:
        srt = next(iter((SAIDA / slug).glob("*.srt")), None) if (SAIDA / slug).is_dir() else None
        if srt:
            try:
                campos["srt"] = re.sub(r"(?m)^\d+$|^\d\d:\d\d:\d\d,\d+ --> .*$", "", srt.read_text(encoding="utf-8", errors="ignore"))[:20000]
            except Exception:  # noqa
                pass
    return mrev.revisar(campos)


@app.get("/api/gs/conversas/{cid}/revisao-marca")
async def revisao_marca(cid: str):
    """Avisos do revisor de marca sobre os textos da última entrega desta conversa (e o SRT, se houver)."""
    issue = await _pc("GET", f"/api/issues/{cid}"); c = _conversa(issue, _indice())
    coments = await _pc("GET", f"/api/issues/{cid}/comments"); itens = coments if isinstance(coments, list) else coments.get("comments", coments.get("items", []))
    msgs = [{"autor": _autor_comentario(m), "texto": m.get("body") or ""} for m in sorted(itens, key=lambda m: m.get("createdAt", ""))]
    ent = txt.entrega_de_mensagens(msgs)
    return {**_revisao_marca_de(ent["secoes"] if ent else [], c.get("slug")), "conversa": c.get("id"), "codigo": c.get("codigo")}


@app.get("/api/gs/aprovacoes")
async def aprovacoes_listar():
    """Fila única do que espera o Raphael: entregas em revisão (in_review, ou done ainda sem aprovação registrada no app) e decisões pendentes do Editor."""
    issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues"); idx = _indice(); cache = txt.cache_ler(TEXTOS_CACHE)
    entregas_fila, decisoes = [], []; antigas = 0
    limite = (datetime.now(timezone.utc) - timedelta(days=int(CFG.get("aprovacoes_dias_done", 3)))).isoformat()
    for i in issues:
        if i.get("status") == "cancelled" or i.get("identifier") in CFG.get("ocultar_issues", []):
            continue
        c = _conversa(i, idx)
        if i.get("status") in ("in_progress", "todo", "blocked"):
            try:
                lst = await _pc("GET", f"/api/issues/{i['id']}/interactions"); lst = lst if isinstance(lst, list) else lst.get("interactions", [])
                for it in lst:
                    if it.get("status") in ("pending", "open", "waiting", None) and not it.get("resolvedAt"):
                        decisoes.append(aprv.item_decisao(c, it))
            except HTTPException:
                pass
            continue
        if i.get("status") not in ("in_review", "done") or not c.get("slug"):
            continue
        pasta = SAIDA / c["slug"]
        if not pasta.is_dir() or aprv.aprovada(pasta):
            continue
        if i.get("status") == "done" and str(i.get("updatedAt") or "") < limite:
            antigas += 1; continue  # entregas antigas sem aprovação registrada não entopem a fila; ficam na página Peças
        ents = _entregas(c["slug"])
        if not any(e.get("principal") for e in ents) and not any(e.get("tipo") in ("video", "imagem") for e in ents):
            continue
        item = cache.get(i["id"]) or {}; secoes = item.get("secoes") or []
        rev = _revisao_marca_de(secoes, c["slug"])
        peca = pcs.etiquetas(pasta, secoes, c)
        entregas_fila.append(aprv.item_entrega(c, ents, secoes, peca, rev))
    entregas_fila.sort(key=lambda x: x.get("atualizado") or "", reverse=True)
    return {"entregas": entregas_fila, "decisoes": decisoes, "n": len(entregas_fila) + len(decisoes), "antigas_sem_aprovacao": antigas, "dias_done": int(CFG.get("aprovacoes_dias_done", 3))}


@app.post("/api/gs/aprovacoes/lote")
async def aprovacoes_lote(ids: str = Form(...), comentario: str = Form("Ficou bom.")):
    """Aprova várias entregas de uma vez (mesmo caminho do botão Aprovar de cada conversa)."""
    feitos, erros = [], []
    for cid in [x.strip() for x in ids.split(",") if x.strip()]:
        try:
            await aprovar(cid, comentario); feitos.append(cid)
        except Exception as e:  # noqa
            erros.append({"id": cid, "erro": str(e)[:160]})
    return {"aprovadas": feitos, "erros": erros}


@app.post("/api/gs/aprovacoes/vistas")
def aprovacoes_vistas(ids: str = Form(...)):
    """Tira entregas da fila sem aprovar nem reprovar (só registro local: aprovacao.json com tipo "vista"). Nada vai ao Paperclip nem ao Notion."""
    idx = _indice(); feitos = []
    for cid in [x.strip() for x in ids.split(",") if x.strip()]:
        slug = (idx.get(cid) or {}).get("slug")
        if slug and (SAIDA / slug).is_dir():
            aprv.registrar(SAIDA / slug, comentario="vista na central, sem aprovar", tipo="vista"); feitos.append(cid)
    return {"vistas": feitos}


@app.post("/api/gs/conversas/{cid}/ajuste")
async def pedir_ajuste(cid: str, texto: str = Form(...), segundo: str = Form(""), arquivo: str = Form("")):
    """Pedido de ajuste com o instante do vídeo (o player manda o segundo): vira mensagem na conversa e reabre o pedido."""
    seg = float(segundo) if segundo.strip() else None
    return await mensagem(cid, aprv.pedido_ajuste(texto, seg, arquivo or None), "", [])


# --- Métricas e Automações (v1, sem credencial nova) ------------------------------------------------------------------
RELATORIOS = WORKSPACE / "relatorios"


@app.get("/api/gs/metricas")
def metricas_painel(dias: int = 30):
    """Painel: Resultados do GSI (7/30/90), resumo das peças, pós-mortens pendentes e feitos, automações."""
    cache = txt.cache_ler(TEXTOS_CACHE)
    linhas = pcs.listar(SAIDA, GSI_DB, cache)
    return {"painel": rds.resultados(GSI_DB, dias), "pecas": pcs.resumo(linhas), "posmortem": {"pendentes": mtr.pendentes(SAIDA, GSI_DB, cache), "feitos": mtr.feitos(SAIDA)[:30], "dias": mtr.D_POSMORTEM},
            "automacoes": aut.listar(GSI_RAIZ, len(pushn.listar()))}


@app.post("/api/gs/metricas/posmortem")
def metricas_posmortem(slug: str = Form("")):
    """Gera o pós-mortem D+7 das peças pendentes (ou de uma peça), sem modelo de linguagem; grava saida/<slug>/posmortem.json."""
    if slug and (not re.match(r"^[\w\-]{1,120}$", slug) or not (SAIDA / slug).is_dir()):
        raise HTTPException(404, "Peça não encontrada.")
    g = mtr.gerar(SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE), slug or None)
    return {"gerados": g, "n": len(g)}


@app.get("/api/gs/metricas/relatorio-semana")
def metricas_relatorio_semana(fim: str = ""):
    """Relatório da semana (7 dias até `fim`, padrão hoje) em Markdown, gravado em workspace/relatorios/."""
    try:
        f = date.fromisoformat(fim) if fim else None
    except ValueError:
        raise HTTPException(400, "fim deve ser AAAA-MM-DD")
    return mtr.relatorio_semana(GSI_DB, SAIDA, RELATORIOS, f, txt.cache_ler(TEXTOS_CACHE))


@app.get("/api/gs/automacoes")
def automacoes_listar():
    return {"itens": aut.listar(GSI_RAIZ, len(pushn.listar())), "gsi": str(GSI_RAIZ)}


# --- Automações do Editor GS (01/11/2026) ------------------------------------------------------------------------------------
# 1 · Série recorrente de Stories: rodada = pedido no Editor (fluxo stories-serie) → entrega → rascunho de Story na Publora.
# 2 · Reel reciclado com gancho novo: rodada = evergreen próprio acima da mediana → download do original → pedido (fluxo reel-reciclado)
#     → entrega → rascunho de Reels na Publora + experimento.json ("mesma peça, outro gancho").
# Nenhuma agenda nem publica; nenhuma escreve no Notion nem no GSI. Laço a cada 10 min; "Rodar agora" ignora o dia/intervalo.
async def _automacao_stories_criar(por="laço"):
    cfg = aut.stories_config(); rods = aut.rodadas()
    fonte = aut.stories_fonte(GSI_DB, aut.stories_fontes_usadas(rods), cfg)
    agora = datetime.now()
    if not fonte:
        rod = {"id": aut.rodada_id(agora), "automacao": "stories_serie", "serie": cfg.get("serie"), "quando": agora.isoformat(timespec="seconds"), "semana": aut._semana(agora), "por": por, "fonte": None, "historico": []}
        return aut.rodada_estado(rod, "sem_fonte", "nenhuma dúvida nova classificada no GSI (QUESTION) fora as já usadas")
    texto = aut.stories_pedido(fonte, cfg)
    c = await nova_conversa(pedido=texto, fluxo="stories-serie", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="automacao", pasta="Automações", modelo="")
    rod = aut.rodada_nova(fonte, c, por, agora)
    log.info("automação stories: pedido %s criado (%s)", rod.get("codigo"), fonte["plataforma"])
    return rod


async def _automacao_reciclado_criar(por="laço", gancho: str = ""):
    """Escolhe o evergreen, baixa o original (numa thread; pode levar um minuto) e abre o pedido. Se o download falhar, tenta o próximo
    candidato até `tentativas`; sem nenhum, registra sem_fonte/sem_video_origem."""
    import asyncio as _a
    cfg = aut.reciclado_config(); rods = aut.rodadas(); agora = datetime.now()
    cands = aut.reciclado_candidatos(GSI_DB, SAIDA, aut.reciclado_usados(rods), cfg, agora, txt.cache_ler(TEXTOS_CACHE))
    if not cands:
        rod = {"id": aut.rodada_id(agora, "reciclado"), "automacao": "reel_reciclado", "quando": agora.isoformat(timespec="seconds"), "por": por, "fonte": None, "historico": []}
        return aut.rodada_estado(rod, "sem_fonte", f"nenhum evergreen próprio com razão ≥ {cfg['min_razao']}× e {cfg['min_idade_dias']}+ dias fora os já reciclados")
    erros = []
    for fonte in cands[:int(cfg.get("tentativas", 3))]:
        try:
            arquivo = await _a.to_thread(aut.reciclado_baixar, fonte, ENTRADA)
        except aut.ErroReciclagem as e:
            erros.append(f"{fonte['plataforma']}:{fonte['id']}: {e}"); log.warning("automação reciclado: %s", erros[-1]); continue
        texto = aut.reciclado_pedido(fonte, arquivo, cfg, gancho_sugerido=gancho)
        c = await nova_conversa(pedido=texto, fluxo="reel-reciclado", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="automacao", pasta="Automações", modelo="")
        rod = aut.rodada_nova(fonte, c, por, agora, automacao="reel_reciclado", arquivo=arquivo)
        log.info("automação reciclado: pedido %s criado (%s %s, %s×)", rod.get("codigo"), fonte["plataforma"], fonte["id"], fonte.get("razao"))
        return rod
    rod = {"id": aut.rodada_id(agora, "reciclado"), "automacao": "reel_reciclado", "quando": agora.isoformat(timespec="seconds"), "por": por, "fonte": cands[0], "historico": []}
    rod = aut.rodada_estado(rod, "sem_video_origem", "; ".join(erros)[:400])
    pushn.enviar("Reel reciclado: original não baixou", erros[0][:120], "/metricas", f"auto-{rod['id']}")
    return rod


_AUTOMACOES = {
    "stories_serie": {"nome": "Stories da semana", "video_de": aut.stories_video_de, "sem_video": "pedido concluído, mas sem final_stories_9x16.mp4 em saida/", "legenda_de": aut.stories_legenda_de,
                      "tipo_instagram": "STORIES", "capa_de": None, "config": aut.stories_config, "experimento": False, "aviso_rascunho": "virou rascunho de Story; confira e agende."},
    "reel_reciclado": {"nome": "Reel reciclado", "video_de": aut.reciclado_video_de, "sem_video": "pedido concluído, mas sem final_9x16.mp4 em saida/", "legenda_de": aut.reciclado_legenda_de,
                       "tipo_instagram": "REELS", "capa_de": aut.reciclado_capa_de, "config": aut.reciclado_config, "experimento": True, "aviso_rascunho": "virou rascunho de Reels; confira o gancho novo e agende."},
}


async def _automacao_concluir(aid: str):
    """Rodadas com pedido aberto: quando o Editor termina, manda o vídeo à Publora como RASCUNHO (Story ou Reels) ou registra por que não;
    no Reel reciclado grava também saida/<slug>/experimento.json."""
    from servico import marca_revisor as _mrev
    spec = _AUTOMACOES[aid]; nome = spec["nome"]; feitas = []
    for rod in aut.rodadas():
        if rod.get("automacao") != aid or rod.get("estado") != "pedido_aberto" or not rod.get("issue"):
            continue
        try:
            issue = await _pc("GET", f"/api/issues/{rod['issue']}")
        except HTTPException as e:
            log.warning("automação %s: issue %s indisponível (%s)", aid, rod.get("codigo"), e.detail); continue
        st = (issue or {}).get("status")
        if st == "cancelled":
            feitas.append(aut.rodada_estado(rod, "cancelado", "pedido cancelado no Editor")); continue
        if st != "done":
            continue
        pasta = SAIDA / (rod.get("slug") or "")
        video = spec["video_de"](pasta) if rod.get("slug") else None
        if not video:
            feitas.append(aut.rodada_estado(rod, "entregue_sem_video", spec["sem_video"]))
            pushn.enviar(f"{nome}: sem vídeo", f"{rod.get('codigo')} terminou sem o vídeo; veja a conversa.", f"/c/{rod['issue']}", f"auto-{rod['id']}"); continue
        try:
            coments = await _pc("GET", f"/api/issues/{rod['issue']}/comments")
            itens = coments if isinstance(coments, list) else coments.get("comments", coments.get("items", []))
            msgs = [{"id": m.get("id"), "autor": _autor_comentario(m), "texto": m.get("body") or "", "quando": m.get("createdAt")} for m in sorted(itens, key=lambda m: m.get("createdAt", ""))]
        except HTTPException:
            msgs = []
        ent = txt.entrega_de_mensagens(msgs); secoes = ent["secoes"] if ent else []
        legenda = spec["legenda_de"](secoes, rod.get("fonte"))
        rev = _mrev.revisar({"descricao": legenda, **{s["chave"]: s["conteudo"] for s in secoes if s["chave"] in ("roteiro", "hashtags", "gancho")}})
        if rev.get("resumo", {}).get("alta"):
            feitas.append(aut.rodada_estado(rod, "bloqueado_revisor", "; ".join(a["msg"] for a in rev["avisos"] if a["gravidade"] == "alta")[:300], revisao=rev["resumo"]))
            pushn.enviar(f"{nome}: revisor segurou", f"{rod.get('codigo')}: {rev['avisos'][0]['msg']}", f"/c/{rod['issue']}", f"auto-{rod['id']}"); continue
        def _experimento(publora=None):
            if spec["experimento"]:
                exp = aut.reciclado_experimento(rod, secoes, publora, legenda)
                (pasta / "experimento.json").write_text(json.dumps(exp, ensure_ascii=False, indent=1), encoding="utf-8")
                return {"gancho_novo": exp["gancho_novo"], "gancho_original": exp["gancho_original"]}
            return {}
        if not os.environ.get("PUBLORA_API_KEY", "").strip():
            feitas.append(aut.rodada_estado(rod, "entregue_sem_publora", "PUBLORA_API_KEY ausente: publique pelo cartão quando quiser", legenda=legenda, **_experimento()))
            pushn.enviar(f"{nome} prontos" if aid == "stories_serie" else f"{nome} pronto", f"{rod.get('codigo')} entregue; Publora não configurada, publique pelo cartão.", f"/c/{rod['issue']}", f"auto-{rod['id']}"); continue
        try:
            p = pub.Publora(); cfg = spec["config"]()
            contas = cfg.get("contas") or [c["platformId"] for c in p.contas() if c["plataforma"] == "instagram" and c.get("status") in (None, "active")]
            if not contas:
                raise pub.ErroPublicacao("nenhuma conta do Instagram ligada na Publora")
            capa = spec["capa_de"](pasta) if spec["capa_de"] else None
            res = p.publicar(video, legenda, contas, None, None, capa, tipo_instagram=spec["tipo_instagram"])
            pub.registrar(pasta, {"tipo": "publora", "arquivo": video.name, "plataformas": contas, "legenda": legenda, "tipo_instagram": spec["tipo_instagram"], "automacao": aid, "rodada": rod["id"], **res})
            publora = {"postGroupId": res.get("postGroupId"), "status": res.get("status"), "contas": contas}
            feitas.append(aut.rodada_estado(rod, "rascunho_publora", f"rascunho {res.get('postGroupId')} ({'Story' if spec['tipo_instagram'] == 'STORIES' else 'Reels'}) na Publora; agendar é clique humano", publora=publora, legenda=legenda, **_experimento(publora)))
            pushn.enviar(f"{nome}: rascunho na Publora", f"{rod.get('codigo')} {spec['aviso_rascunho']}", f"/c/{rod['issue']}", f"auto-{rod['id']}")
        except pub.ErroPublicacao as e:
            feitas.append(aut.rodada_estado(rod, "entregue_sem_publora", f"Publora: {e}"[:300], legenda=legenda, **_experimento()))
            pushn.enviar(f"{nome} prontos" if aid == "stories_serie" else f"{nome} pronto", f"{rod.get('codigo')} entregue; Publora recusou o rascunho: {str(e)[:80]}", f"/c/{rod['issue']}", f"auto-{rod['id']}")
    return feitas


async def _automacao_stories_concluir():
    return await _automacao_concluir("stories_serie")


async def _automacao_reciclado_concluir():
    return await _automacao_concluir("reel_reciclado")


async def _laco_automacoes():
    import asyncio as _a
    while True:
        try:
            if aut.stories_devida(datetime.now())[0]:
                await _automacao_stories_criar("laço")
            await _automacao_stories_concluir()
        except Exception as e:  # noqa
            log.warning("laço das automações (stories): %s", e)
        try:
            if aut.reciclado_devida(datetime.now())[0]:
                await _automacao_reciclado_criar("laço")
            await _automacao_reciclado_concluir()
            for e in aut.experimentos_fechar(SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE)):
                pushn.enviar(f"Experimento de gancho: {e['status']}", f"{e.get('codigo')}: \"{e.get('gancho_novo', '')[:50]}\" {e['resultado']['leitura']}", f"/pecas/{e['slug']}", f"exp-{e['slug']}")
        except Exception as e:  # noqa
            log.warning("laço das automações (reciclado): %s", e)
        try:
            await _automacoes_dados("laço")
        except Exception as e:  # noqa
            log.warning("laço das automações (dados): %s", e)
        try:
            arq = REFERENCIAS / "_perfil-thiago" / "rende.json"
            if not arq.exists() or time.time() - arq.stat().st_mtime > 86400:  # perfil vivo: uma vez por dia, sem chave (só escreve o arquivo que o Editor lê)
                await _a.to_thread(_perfil_escrever)
        except Exception as e:  # noqa
            log.warning("laço das automações (perfil): %s", e)
        try:
            if _ligada("pasta_vigiada"):
                await _pasta_vigiada("laço")
        except Exception as e:  # noqa
            log.warning("laço das automações (pasta vigiada): %s", e)
        try:
            if _ligada("skills_garimpo") and sb.pesquisa_devida()[0] and not any(r.get("estado") == "pedido_aberto" for r in sb.rodadas()[-3:]):
                await _skills_pesquisar("laço")
            await _skills_rodadas_conferir()
        except Exception as e:  # noqa
            log.warning("laço das automações (banco de skills): %s", e)
        await _a.sleep(int(CFG.get("automacoes_intervalo_s", 600)))


def _ligada(id_):
    return bool((aut.registro().get(id_) or {}).get("ligada"))


async def _automacoes_dados(por="laço", so: str = ""):
    """Automações 3, 5, 6 e 7 (03/11/2026). No laço, cada uma só roda ligada e quando devida; "Rodar agora" (so=<id>) roda aquela na hora."""
    agora = datetime.now(ad.BRT); est = ad.estado(); reg = aut.registro(); cache = txt.cache_ler(TEXTOS_CACHE); feito = {}
    if so == "posmortem" or (not so and _ligada("posmortem") and ad.posmortem_devido(agora, est, ad.config("posmortem", reg))):
        gerados = mtr.gerar(SAIDA, GSI_DB, cache)
        est["posmortem"] = {"ultimo_dia": agora.date().isoformat(), "quando": agora.isoformat(timespec="minutes"), "por": por, "gerados": [g["slug"] for g in gerados]}
        for g in gerados:
            pushn.enviar(f"Pós-mortem D+7: {g['veredito']}", f"{g.get('codigo') or g['slug']}: {g.get('razao')}× a mediana", f"/pecas/{g['slug']}", f"pm-{g['slug']}")
        feito["posmortem"] = {"gerados": len(gerados)}
    if so == "variacao_vencedor" or (not so and _ligada("variacao_vencedor")):
        cfg = ad.config("variacao_vencedor", reg); criados = []
        for pm in ad.variacao_candidatos(mtr.feitos(SAIDA), est, cfg, agora)[:1]:
            mat = ad.material_da_peca(SAIDA, ENTRADA, pm["slug"])
            if not mat:
                est.setdefault("variacoes", {})[pm["slug"]] = {"quando": agora.isoformat(timespec="minutes"), "estado": "sem_material", "por": por}; continue
            c = await nova_conversa(pedido=ad.variacao_pedido(pm, mat), fluxo="reels-padrao", estilo="profissional", arquivos=[], recebido="", referencia="", notion_page="", origem="automacao", pasta="Automações", modelo="")
            est.setdefault("variacoes", {})[pm["slug"]] = {"quando": agora.isoformat(timespec="minutes"), "estado": "pedido", "conversa": c.get("id"), "codigo": c.get("codigo"), "razao": pm["razao"], "por": por}
            pushn.enviar("Variação do vencedor", f"{pm.get('codigo') or pm['slug']} ({pm['razao']}×): pedido {c.get('codigo') or ''} aberto", f"/c/{c.get('id')}", f"var-{pm['slug']}")
            criados.append(c.get("codigo"))
        feito["variacao_vencedor"] = {"pedidos": criados}
    if so == "alertas" or (not so and _ligada("alertas")):
        novos = ad.alertas(GSI_DB, est, ad.config("alertas", reg))
        for a in novos:
            t, corpo = ad.texto_alerta(a); pushn.enviar(t, corpo, "/metricas", a["chave"])
        est["alertas_enviados"] = (est.get("alertas_enviados") or []) + [a["chave"] for a in novos]
        est["alertas"] = (novos + (est.get("alertas") or []))[:50]; est["alertas_quando"] = agora.isoformat(timespec="minutes")
        feito["alertas"] = {"novos": len(novos)}
    if so == "melhor_horario" or (not so and _ligada("melhor_horario") and ad.melhor_horario_devido(agora, est, ad.config("melhor_horario", reg))):
        est["melhor_horario"] = ad.melhor_horario(GSI_DB, ad.config("melhor_horario", reg)); feito["melhor_horario"] = {"ok": bool(est["melhor_horario"])}
    if feito:
        ad.gravar(est)
    return feito


async def _pasta_vigiada(por="laço"):
    """Pasta vigiada do Drive (03/11/2026): lê a pasta, abre um pedido por gravação nova pronta (no máximo 2 por volta). Só lê o Drive."""
    import asyncio
    from servico import materiais as _mat
    est = pv.estado(); agora = datetime.now(timezone.utc)
    try:
        itens = await asyncio.to_thread(pv.listar, pub.RCLONE)
    except Exception as e:  # noqa
        est["erro"] = str(e)[:300]; est["lido_em"] = agora.isoformat(timespec="minutes"); pv.gravar(est)
        return {"erro": est["erro"]}
    est.pop("erro", None)
    lista, est = pv.prontos(itens, est, agora)
    est["lido_em"] = agora.isoformat(timespec="minutes"); est["n_arquivos"] = sum(1 for i in itens if Path(i["Path"]).suffix.lower() in pv.EXT_VIDEO)
    pv.gravar(est); criados = []
    for it in lista[:2]:
        token = pv.novo_token(); pasta_r = RECEBIDOS / token
        try:
            arq = await asyncio.to_thread(pv.baixar, pub.RCLONE, it["Path"], pasta_r)
            instr = await asyncio.to_thread(pv.ler_texto, pub.RCLONE, it["instrucao_arquivo"]) if it.get("instrucao_arquivo") else ""
            texto, regra = pv.texto_pedido(it, instr, _mat._ffprobe_dur(arq))
            (pasta_r / "recebido.json").write_text(json.dumps({"texto": texto, "quando": datetime.now().isoformat(timespec="seconds"), "drive": it["Path"]}, ensure_ascii=False), encoding="utf-8")
            if regra["modo"] in ("kit", "clipador"):
                c = await clipes_criar(BackgroundTasks(), nota=(instr or it["Path"].rsplit("/", 1)[-1].rsplit(".", 1)[0])[:200], url="", tipo_origem="aula", n=10, arquivos=[], recebido=token, referencia="",
                                       modo="kit" if regra["modo"] == "kit" else "propor", n_reels=3, pecas="reels,carrossel,stories,youtube", estilo="")
            else:
                c = await nova_conversa(pedido=texto, fluxo="reels-padrao" if regra["modo"] == "reel" else "", estilo=regra.get("estilo", "padrao"), arquivos=[], recebido=token, referencia="", notion_page="", origem="drive", pasta="Pasta vigiada do Drive", modelo="")
            est = pv.estado(); est.setdefault("vistos", {})[it["chave"]] = {"caminho": it["Path"], "estado": "pedido", "modo": regra["modo"], "estilo": regra.get("estilo"), "conversa": c.get("id"), "codigo": c.get("codigo"), "quando": datetime.now(ad.BRT).isoformat(timespec="minutes"), "por": por}
            pv.gravar(est); criados.append(c.get("codigo"))
            pushn.enviar("Gravação nova do Drive", f"{it['Path'].rsplit('/', 1)[-1]} virou o pedido {c.get('codigo') or ''}", f"/c/{c.get('id')}", f"drive-{it['chave']}")
        except Exception as e:  # noqa
            shutil.rmtree(pasta_r, ignore_errors=True)
            est = pv.estado(); est.setdefault("vistos", {})[it["chave"]] = {"caminho": it["Path"], "estado": "erro", "erro": str(e)[:200], "quando": datetime.now(ad.BRT).isoformat(timespec="minutes")}; pv.gravar(est)
            log.warning("pasta vigiada: %s", e)
    return {"pedidos": criados, "na_pasta": est.get("n_arquivos"), "aguardando": len(lista) - len(criados)}


# ----------------------------------------------------------------------------------------------- Banco de skills (10/11/2026)
# Catálogo do que existe fora (skills, plugins, repos, presets, criadores) + "Ensinar o Editor" + pesquisa recorrente (fluxo pesquisa-skills).
# Decisão é humana; instalar e reproduzir são cliques; a pesquisa semanal só roda com a chave `skills_garimpo` ligada em Métricas › Automações.
async def _skills_pesquisar(por: str, foco: str = ""):
    texto = sb.pedido_pesquisa(foco)
    c = await nova_conversa(pedido=texto, fluxo="pesquisa-skills", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="automacao" if por == "laço" else "app", pasta="Banco de skills", modelo="")
    rod = {"id": f"skills-{datetime.now():%Y%m%d-%H%M%S}", "quando": datetime.now().isoformat(timespec="seconds"), "por": por, "foco": foco, "issue": c.get("id"), "codigo": c.get("codigo"), "estado": "pedido_aberto"}
    sb.rodada_gravar(rod); return {"rodada": rod, "conversa": c}


async def _skills_rodadas_conferir():
    """Rodada com pedido entregue ou concluído muda de estado (o catálogo em si entra pelo arquivo de achados, lido no GET)."""
    feitas = []
    for r in [x for x in sb.rodadas() if x.get("estado") == "pedido_aberto" and x.get("issue")]:
        try:
            i = await _pc("GET", f"/api/issues/{r['issue']}")
        except Exception:  # noqa: BLE001
            continue
        if i.get("status") in ("in_review", "done"):
            antes = sb.estado()["n"]; sb.importar_achados(); r.update(estado="entregue", entregue_em=datetime.now().isoformat(timespec="seconds"), novos=sb.estado()["n"] - antes); sb.rodada_gravar(r); feitas.append(r["id"])
        elif i.get("status") == "blocked":
            r.update(estado="falhou"); sb.rodada_gravar(r)
    return feitas


@app.get("/api/gs/skills")
async def skills_listar(estado: str = "", tipo: str = "", q: str = ""):
    await _skills_rodadas_conferir()
    return {"itens": sb.catalogo(estado, tipo, q), "estado": sb.estado(), "garimpo_ligado": _ligada("skills_garimpo")}


@app.post("/api/gs/skills/registrar")
def skills_registrar(url: str = Form(""), nome: str = Form(""), tipo: str = Form("outro"), resumo: str = Form(""), autor: str = Form(""), licenca: str = Form(""), preco: str = Form(""), o_que_aproveitar: str = Form("")):
    if not url.strip() and not nome.strip():
        raise HTTPException(400, "Informe o link ou o nome.")
    r = sb.registrar([{"url": url, "nome": nome, "tipo": tipo, "resumo": resumo, "autor": autor, "licenca": licenca, "preco": preco, "o_que_aproveitar": o_que_aproveitar}], por=acs.QUEM.get() or "Raphael", fonte="manual")
    return {**r, "item": sb.item((r["novos"] or r["ja_tinha"])[0])}


@app.post("/api/gs/skills/pesquisar")
async def skills_pesquisar(foco: str = Form("")):
    return await _skills_pesquisar(acs.QUEM.get() or "Raphael", foco)


@app.post("/api/gs/skills/ensinar")
async def skills_ensinar(tipo: str = Form("conhecimento"), titulo: str = Form(""), texto: str = Form(""), fonte: str = Form(""), arquivo: UploadFile | None = File(default=None)):
    """Ensinar o Editor: regra (memória) ou conhecimento (texto ou arquivo .txt/.md/.srt). Vídeo e link de referência vão pela página Referências."""
    if arquivo is not None and arquivo.filename:
        if not arquivo.filename.lower().endswith((".txt", ".md", ".srt", ".vtt")):
            raise HTTPException(400, "Arquivo de texto (.txt, .md, .srt, .vtt). Vídeo: página Referências.")
        corpo = (await arquivo.read())[:400_000].decode("utf-8", errors="replace")
        texto = (texto.strip() + "\n\n" + corpo).strip(); titulo = titulo or Path(arquivo.filename).stem
    try:
        return sb.ensinar(tipo, titulo, texto, por=acs.QUEM.get() or "Raphael", fonte=fonte)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/gs/skills/conhecimento/{arquivo}")
def skills_conhecimento_apagar(arquivo: str):
    return {"ok": sb.conhecimento_apagar(arquivo)}


@app.post("/api/gs/skills/{sid}/decidir")
def skills_decidir(sid: str, estado: str = Form(...), nota: str = Form("")):
    try:
        return sb.decidir(sid, estado, acs.QUEM.get() or "Raphael", nota)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/{sid}/anotar")
def skills_anotar(sid: str, texto: str = Form(...)):
    try:
        return sb.anotar(sid, texto, acs.QUEM.get() or "Raphael")
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/{sid}/editar")
def skills_editar(sid: str, nome: str = Form(None), tipo: str = Form(None), url: str = Form(None), autor: str = Form(None), licenca: str = Form(None), preco: str = Form(None), resumo: str = Form(None), como_reproduzir: str = Form(None), evidencia: str = Form(None), o_que_aproveitar: str = Form(None)):
    try:
        return sb.editar(sid, {k: v for k, v in dict(nome=nome, tipo=tipo, url=url, autor=autor, licenca=licenca, preco=preco, resumo=resumo, como_reproduzir=como_reproduzir, evidencia=evidencia, o_que_aproveitar=o_que_aproveitar).items() if v is not None})
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/gs/skills/{sid}/instalar")
async def skills_instalar(sid: str):
    try:
        return await asyncio.to_thread(sb.instalar, sid, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/{sid}/desinstalar")
def skills_desinstalar(sid: str):
    try:
        return sb.desinstalar(sid, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))


# 13/11/2026: quarentena (skills_biblioteca/, o agente não carrega), raio-x sem modelo, dissecar em 4 caixas e fila de absorção.
@app.post("/api/gs/skills/pasta/{pasta}/ativar")
def skills_ativar(pasta: str):
    try:
        return sb.ativar(pasta, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/pasta/{pasta}/desativar")
def skills_desativar(pasta: str):
    try:
        return sb.desativar(pasta, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/pasta/{pasta}/raiox")
async def skills_raiox(pasta: str):
    try:
        return await asyncio.to_thread(sb.raio_x, pasta)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/gs/skills/pasta/{pasta}/liberar")
async def skills_liberar(pasta: str):
    """Apaga .venv/node_modules/.git de uma skill da biblioteca (a skill recria se um dia rodar)."""
    try:
        return await asyncio.to_thread(sb.liberar_espaco, pasta)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/gs/skills/quarentena")
def skills_quarentena():
    """Tira do agente todas as skills ativas que não são nossas (gs-*). Não apaga nada."""
    return sb.quarentena_tudo(acs.QUEM.get() or "Raphael")


@app.get("/api/gs/skills/fila_absorcao")
def skills_fila():
    return {"fila": sb.absorver()}


@app.post("/api/gs/skills/fila_absorcao/marcar")
def skills_fila_marcar(chave: str = Form(...), estado: str = Form(...), nota: str = Form("")):
    try:
        return sb.absorvido(chave, estado, acs.QUEM.get() or "Raphael", nota)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/gs/skills/{sid}/dissecacao")
def skills_dissecacao(sid: str):
    sb.importar_dissecacoes()
    return sb.dissecacao(sid) or {"id": sid, "pecas": []}


@app.post("/api/gs/skills/{sid}/dissecar")
async def skills_dissecar(sid: str, modelo: str = Form("")):
    """Abre um pedido (fluxo dissecar-skill): o agente lê a skill da biblioteca e separa as peças em regra, ativo, código e descartar."""
    try:
        it = sb.item(sid)
    except KeyError as e:
        raise HTTPException(404, str(e))
    c = await nova_conversa(pedido=sb.pedido_dissecar(it), fluxo="dissecar-skill", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="app", pasta="Banco de skills", modelo=modelo,
                            pedido_usuario=f"Dissecar {it['nome']}")
    sb.anotar(sid, f"pedido {c.get('codigo') or ''} aberto (dissecar)", acs.QUEM.get() or "Raphael")
    return c


@app.post("/api/gs/skills/{sid}/peca")
def skills_peca(sid: str, n: int = Form(...), decisao: str = Form(...)):
    try:
        return sb.decidir_peca(sid, n, decisao, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/{sid}/peca_conhecimento")
def skills_peca_conhecimento(sid: str, n: int = Form(...)):
    """Peça de regra vira texto em conhecimento/ (o Editor lê quando o pedido tocar no assunto)."""
    try:
        return sb.peca_para_conhecimento(sid, n, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/skills/{sid}/reproduzir")
async def skills_reproduzir(sid: str, modo: str = Form("reproduzir")):
    """Abre um pedido no Editor (fluxo reproduzir-skill) para estudar o item e traduzi-lo em estilo/fluxo/grafismos; modo avaliar só analisa."""
    try:
        it = sb.item(sid)
    except KeyError as e:
        raise HTTPException(404, str(e))
    modo = "avaliar" if modo == "avaliar" else "reproduzir"
    c = await nova_conversa(pedido=sb.pedido_reproduzir(it, modo), fluxo="reproduzir-skill", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="app", pasta="Banco de skills", modelo="")
    sb.anotar(sid, f"pedido {c.get('codigo') or ''} aberto ({modo})", acs.QUEM.get() or "Raphael")
    if modo == "avaliar" and it["estado"] == "achado":
        sb.decidir(sid, "avaliar", acs.QUEM.get() or "Raphael")
    return c


def _skills_instaladas_com_nome():
    cat = {i["id"]: i for i in sb.catalogo()}
    return [{**s, "nome": (cat.get(s["pasta"]) or {}).get("nome") or s["pasta"], "url": (cat.get(s["pasta"]) or {}).get("url")} for s in sb.instaladas()]


@app.get("/api/gs/skills/demos")
async def skills_demos():
    """Demos das skills instaladas (12/11/2026): três edições de amostra por skill (Reels, ADS, aula) com os mesmos brutos."""
    d = sdm.ler(WORKSPACE); status = {}
    for por_fmt in d.values():
        for r in por_fmt.values():
            try:
                status[r["issue_id"]] = (await _pc("GET", f"/api/issues/{r['issue_id']}")).get("status")
            except Exception:  # noqa: BLE001
                status[r["issue_id"]] = "sumiu"
    return {"formatos": sdm.FORMATOS, "brutos_faltando": sdm.brutos_faltando(WORKSPACE), "skills": sdm.estado(WORKSPACE, _skills_instaladas_com_nome(), _entregas, status)}


@app.post("/api/gs/skills/{sid}/demos")
async def skills_demos_gerar(sid: str, formatos: str = Form("reels,ads,aula"), modelo: str = Form("")):
    """Abre um pedido de demo por formato (só por clique). Formato que já tem demo em andamento não é duplicado."""
    inst = {s["pasta"]: s for s in _skills_instaladas_com_nome()}
    if sid not in inst:
        raise HTTPException(404, "Skill não instalada.")
    falta = sdm.brutos_faltando(WORKSPACE)
    if falta:
        raise HTTPException(400, f"Faltam os brutos de teste em {sdm.PASTA_BRUTOS}: {', '.join(falta)}")
    atuais = sdm.ler(WORKSPACE).get(sid) or {}; criados = []
    for f in [x.strip() for x in formatos.split(",") if x.strip() in sdm.FORMATOS]:
        r = atuais.get(f)
        if r:
            try:
                if (await _pc("GET", f"/api/issues/{r['issue_id']}")).get("status") in ("todo", "in_progress", "backlog"):
                    continue
            except Exception:  # noqa: BLE001
                pass
        c = await nova_conversa(pedido=sdm.pedido(sid, inst[sid]["nome"], f), fluxo="", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="app",
                                pasta="Demos de skills", modelo=modelo, pedido_usuario=f"Demo {inst[sid]['nome']} · {sdm.FORMATOS[f]['rotulo']}")
        sdm.registrar(WORKSPACE, sid, f, c); criados.append(c)
    return {"criados": criados}


@app.get("/api/gs/pasta_vigiada")
def pasta_vigiada_estado():
    """Estado da pasta vigiada: origem no Drive, última leitura, pedidos abertos e erros."""
    est = pv.estado(); vistos = est.get("vistos") or {}
    itens = sorted([{"chave": k, **v} for k, v in vistos.items() if v.get("estado") != "ja_estavam"], key=lambda x: x.get("quando") or "", reverse=True)[:30]
    return {"origem": pv.origem(), "ligada": _ligada("pasta_vigiada"), "lido_em": est.get("lido_em"), "erro": est.get("erro"), "n_arquivos": est.get("n_arquivos"),
            "ja_estavam": sum(1 for v in vistos.values() if v.get("estado") == "ja_estavam"), "itens": itens, "regras": [{"subpasta": k, **r} for k, r in pv.REGRAS], "config": pv.CONFIG}


@app.post("/api/gs/pasta_vigiada/rodar")
async def pasta_vigiada_rodar():
    """Ler a pasta agora (clique humano), mesmo com a chave desligada."""
    return await _pasta_vigiada("Raphael")


@app.get("/api/gs/automacoes/dados")
def automacoes_dados_estado():
    """Estado das automações 3, 5, 6 e 7: último pós-mortem automático, variações abertas, alertas recentes e o melhor horário calculado."""
    est = ad.estado(); reg = aut.registro()
    return {"posmortem": est.get("posmortem"), "variacoes": est.get("variacoes") or {}, "alertas": est.get("alertas") or [], "alertas_quando": est.get("alertas_quando"),
            "melhor_horario": est.get("melhor_horario"), "config": {k: ad.config(k, reg) for k in ad.PADRAO}, "ligadas": {k: _ligada(k) for k in ad.PADRAO}}


@app.post("/api/gs/automacoes/{aid}/rodar_dados")
async def automacoes_dados_rodar(aid: str):
    """Rodar agora (clique humano) uma das automações 3, 5, 6, 7, mesmo desligada."""
    if aid not in ad.PADRAO:
        raise HTTPException(404, "automação desconhecida")
    return await _automacoes_dados("Raphael", so=aid)


@app.get("/api/gs/automacoes/rodadas")
def automacoes_rodadas():
    rods = aut.rodadas(); cfg = aut.stories_config(); agora = datetime.now()
    devida, motivo = aut.stories_devida(agora, cfg=cfg, rods=rods)
    rcfg = aut.reciclado_config(); rdev, rmot = aut.reciclado_devida(agora, cfg=rcfg, rods=rods)
    try:
        cands = aut.reciclado_candidatos(GSI_DB, SAIDA, aut.reciclado_usados(rods), rcfg, agora, txt.cache_ler(TEXTOS_CACHE), limite=5)
    except Exception as e:  # noqa
        log.warning("candidatos da reciclagem: %s", e); cands = []
    return {"rodadas": list(reversed(rods))[:40], "config": cfg, "dias": aut.DIAS, "proxima": aut.stories_proxima(agora, cfg, rods), "devida": devida, "motivo": motivo, "series": aut.SERIES,
            "publora": bool(os.environ.get("PUBLORA_API_KEY", "").strip()),
            "reciclado": {"config": rcfg, "proxima": aut.reciclado_proxima(agora, rcfg, rods), "devida": rdev, "motivo": rmot, "candidatos": cands}}


@app.post("/api/gs/automacoes/stories_serie/rodar")
async def automacoes_stories_rodar():
    """Rodada agora (clique humano): abre o pedido no Editor mesmo fora do dia; continua só rascunho."""
    return await _automacao_stories_criar("Raphael")


@app.post("/api/gs/automacoes/stories_serie/concluir")
async def automacoes_stories_concluir():
    """Confere agora as rodadas abertas (o laço faz isso a cada 10 min)."""
    return {"feitas": await _automacao_stories_concluir()}


@app.post("/api/gs/automacoes/stories_serie/config")
def automacoes_stories_config(dia_semana: str = Form(""), hora: str = Form(""), contas: str = Form(""), plataformas: str = Form("")):
    campos = {k: v for k, v in (("dia_semana", dia_semana), ("hora", hora), ("contas", contas), ("plataformas", plataformas)) if v != ""}
    try:
        return aut.stories_configurar(campos)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/gs/automacoes/experimentos")
def automacoes_experimentos(fechar: str = ""):
    """Experimentos "mesma peça, outro gancho": lista com status; fechar=sim compara agora as peças com 7+ dias e métrica."""
    fechados = aut.experimentos_fechar(SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE)) if fechar.lower() in ("1", "sim", "true") else []
    return {**aut.experimentos_resumo(SAIDA), "fechados_agora": len(fechados), "regra": f"ganhou ≥ {aut.GANHOU}× a razão da original, perdeu ≤ {aut.PERDEU}×, fecha com {aut.DIAS_FECHAR}+ dias de publicada e métrica do GSI"}


@app.post("/api/gs/automacoes/reel_reciclado/rodar")
async def automacoes_reciclado_rodar(gancho: str = Form("")):
    """Rodada agora (clique humano): escolhe o evergreen, baixa o original e abre o pedido; continua só rascunho. `gancho` (da biblioteca de ganchos) vira a base do gancho novo."""
    return await _automacao_reciclado_criar("Raphael", gancho=gancho)


@app.post("/api/gs/automacoes/reel_reciclado/concluir")
async def automacoes_reciclado_concluir():
    return {"feitas": await _automacao_reciclado_concluir()}


@app.post("/api/gs/automacoes/reel_reciclado/config")
def automacoes_reciclado_config(cada_dias: str = Form(""), hora: str = Form(""), min_razao: str = Form(""), min_idade_dias: str = Form(""), contas: str = Form(""), plataformas: str = Form(""), voz_clonada: str = Form("")):
    campos = {k: v for k, v in (("cada_dias", cada_dias), ("hora", hora), ("min_razao", min_razao), ("min_idade_dias", min_idade_dias), ("contas", contas), ("plataformas", plataformas), ("voz_clonada", voz_clonada)) if v != ""}
    try:
        return aut.reciclado_configurar(campos)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/automacoes/{id_}")
def automacoes_alternar(id_: str, ligada: str = Form("")):
    """Chave das automações planejadas do Editor GS (registra a decisão; nada roda até existir). As do GSI se ligam no GSI."""
    try:
        return aut.alternar(id_, ligada.lower() in ("1", "true", "sim"))
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- Busca no acervo por fala (01/11/2026): transcrições do GSI (só leitura) + do próprio app; "virar corte" → pedido no Clipador (EDITAR).
CLIPES_DIR = WORKSPACE / "clipes"


def _acervo_fontes():
    return acv.fontes(GSI_RAIZ, SAIDA, txt.cache_ler(TEXTOS_CACHE))


@app.get("/api/gs/acervo")
def acervo_buscar(q: str = "", origem: str = "tudo", limite: int = 40):
    """Onde o Thiago fala de X: trechos com instante, contexto, link no instante (YouTube) e sugestão de corte. Sem modelo de linguagem."""
    lista = _acervo_fontes()
    res = acv.buscar(q, lista, limite=max(1, min(int(limite), 200)), origem=origem) if q.strip() else []
    return {"q": q, "resultados": res, "fontes": acv.resumo(lista), "nota": "GSI: transcrições de dados/transcricoes (YouTube e Instagram, lives inclusive); app: entregas transcritas aqui. Instante aproximado (segmento da transcrição)."}


@app.get("/api/gs/acervo/video")
def acervo_video(fonte_id: str):
    """Vídeo local de uma entrega do acervo, para o player do trecho na página Busca por fala (aceita Range: o navegador pula direto ao instante)."""
    f = next((x for x in _acervo_fontes() if x["id"] == fonte_id), None)
    if not f or not f.get("video_local") or not Path(f["video_local"]).exists():
        raise HTTPException(404, "Esta fonte não tem vídeo local.")
    return FileResponse(f["video_local"])


@app.post("/api/gs/acervo/corte")
async def acervo_corte(fonte_id: str = Form(...), inicio: str = Form(...), fim: str = Form(...), titulo: str = Form(""), gancho: str = Form(""), q: str = Form("")):
    """Vira o trecho em pedido do Clipador (fase EDITAR, reels-padrao do passo 3). Vídeo local (entrega do app) é usado direto; fonte do GSI
    baixa só a janela do original (margem de 5 s) para clipes/. Só por clique humano; nada publica."""
    import asyncio as _a
    try:
        a, b = float(inicio.replace(",", ".")), float(fim.replace(",", "."))
    except ValueError:
        raise HTTPException(400, "início e fim em segundos")
    if b <= a or b - a > 180:
        raise HTTPException(400, "o corte precisa ter entre 1 s e 3 min")
    f = next((x for x in _acervo_fontes() if x["id"] == fonte_id), None)
    if not f:
        raise HTTPException(404, "Fonte não encontrada no acervo.")
    titulo = (titulo or "").strip()[:80] or f["titulo"][:80]
    gancho = (gancho or "").strip()[:120]
    tipo_origem = "live" if (f.get("formato") or "").startswith("live") else ("youtube" if f["plataforma"] == "youtube" else "outro")
    if f["origem"] == "app":
        if not f.get("video_local"):
            raise HTTPException(400, "Esta entrega não tem mais o vídeo de origem em entrada/.")
        v = Path(f["video_local"]).resolve()
        try:
            origem_rel = v.relative_to(WORKSPACE.resolve()).as_posix()
        except ValueError:
            raise HTTPException(400, "O vídeo de origem está fora da pasta de trabalho.")
        ini_c, fim_c = a, b; transc = f"saida/{f['slug']}/{Path(f['arquivo']).name}"; baixado = None
    else:
        if not f.get("url"):
            raise HTTPException(400, "Fonte sem link para baixar o trecho.")
        pasta = CLIPES_DIR / f"acervo-{f['plataforma']}-{f['id'].split(':')[-1]}-{int(a)}s"
        try:
            arq, desloc = await _a.to_thread(acv.baixar_trecho, f["url"], a, b, pasta)
        except acv.ErroAcervo as e:
            raise HTTPException(502, f"Não consegui baixar o trecho: {e}")
        origem_rel = arq.relative_to(WORKSPACE).as_posix(); ini_c, fim_c = round(desloc, 2), round(desloc + (b - a), 2); transc = None; baixado = origem_rel
    corte = {"id": "a01", "inicio": ini_c, "fim": fim_c, "duracao": round(fim_c - ini_c, 2), "titulo": titulo, "gancho": gancho or titulo, "destaque": "", "tema": q or titulo,
             "motivo": f"trecho achado na busca por fala" + (f' ("{q}")' if q else "") + f" em \"{f['titulo'][:60]}\"" + (f", instante {int(a)} s do original" if f["origem"] == "gsi" else ""), "tipo": "resposta", "nota": 0, "pessoas": ""}
    slug_c = acv.slug_corte(f, a, titulo)
    desc = [clp.pedido_editar(origem_rel, transc, corte, tipo_origem), "", "Fluxo: `fluxos/reels-padrao.md` a partir do passo 3 (depois do `extrair_trecho`).", "Estilo de legenda: `padrao`.",
            *( [f"O arquivo é só a janela do original ({f['titulo'][:60]}, {link}) com 5 s de margem antes e depois: ajuste início e fim pela fala completa, sem cortar no meio da frase."] if f["origem"] == "gsi" and (link := acv.link_instante(f, a)) else [] ),
            f"Entregue os arquivos em `saida/{slug_c}/`; legenda do post, hashtags, título, gancho e pendências na mensagem final (seções `## `). Não altere `entrada/` nem `clipes/`.", "Responda em PT-BR, curto, citando os JSONs das ferramentas."]
    conv = await _criar_issue(f"Corte do acervo: {titulo}", desc, slug_c, {"acervo": {"fonte": f["id"], "inicio": a, "fim": b, "q": q, "arquivo": baixado or origem_rel}, "origem": "acervo", "fluxo": "reels-padrao"})
    return {"conversa": conv, "arquivo": baixado or origem_rel, "corte": corte}


# --- Biblioteca de ganchos com desempenho (01/11/2026): peças do app, experimentos e conteúdos próprios medidos pelo GSI (só leitura).
@app.get("/api/gs/ganchos")
def ganchos_listar(origem: str = "tudo", medidos: str = "", q: str = "", minimo: str = "0", tipo: str = ""):
    try:
        mn = float(str(minimo).replace(",", ".") or 0)
    except ValueError:
        mn = 0.0
    itens = gch.listar(SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE), origem=origem, so_medidos=medidos.lower() in ("1", "sim", "true"), q=q.strip(), minimo=mn)
    tipos = gch.por_tipo(itens)  # resumo por tipo sobre os filtros atuais, antes de filtrar o tipo (fase 2, 03/11/2026)
    if tipo:
        itens = [i for i in itens if i["tipo"] == tipo]
    return {"itens": [{**i, "pedido": gch.texto_pedido(i)} for i in itens[:400]], "resumo": gch.resumo(itens), "tipos": tipos,
            "nota": "Razão = views ÷ mediana do formato no último snapshot do GSI (não é tempo real; Instagram pela coleta antiga até a Meta entrar). YouTube: o gancho é o título; Instagram: a primeira linha da legenda; peças do app: a etiqueta gancho."}


@app.get("/api/gs/operacao")
async def operacao():
    """Painel Operação: placa de vídeo, disco, CPU/RAM, processos da voz, Paperclip (agentes, em andamento, fila, aguardando), Claude Code. Só leitura."""
    pc, pedidos = None, None
    try:
        h = await _pc("GET", "/api/health"); ag = await _pc("GET", f"/api/companies/{CFG['company_id']}/agents")
        nomes = {v["chave"]: k for k, v in MODELOS.items()}
        pc = {"status": h.get("status"), "versao": h.get("version"),
              "agentes": [{"nome": a.get("name"), "status": a.get("status"), "modelo": (a.get("adapterConfig") or {}).get("model"), "id_app": next((nomes[c] for c in nomes if CFG.get(c) == a.get("id")), None)} for a in ag]}
        issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
        u = arq.uso(issues or [])
        andamento = [{"id": i["id"], "codigo": i.get("identifier"), "titulo": (i.get("title") or "")[:70], "desde": i.get("startedAt")} for i in issues if i.get("status") == "in_progress"]
        pedidos = {"em_andamento": andamento, "na_fila": u["na_fila"], "aguardando_voce": u["aguardando_voce"], "hoje": u["periodos"]["hoje"]}
    except Exception as e:  # noqa
        pc = {"status": "offline", "erro": str(e)[:120]}
    # nvidia-smi/PowerShell/--version são síncronos: em thread para não travar o event loop do gateway (11/11/2026)
    return await asyncio.to_thread(opr.resumo, WORKSPACE, pc, pedidos)


@app.get("/api/gs/push/chave")
def push_chave():
    """Chave pública VAPID para o navegador se inscrever (gerada na primeira chamada)."""
    return {"chave": pushn.chave_publica(), "inscritos": len(pushn.listar())}


@app.post("/api/gs/push/inscrever")
async def push_inscrever(request: Request):
    d = await request.json()
    try:
        return pushn.inscrever(d.get("inscricao") or d, aparelho=d.get("aparelho", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/push/sair")
async def push_sair(request: Request):
    d = await request.json()
    return pushn.remover(d.get("endpoint", ""))


@app.post("/api/gs/push/teste")
def push_teste():
    """Manda uma notificação de teste a todos os aparelhos inscritos."""
    return pushn.enviar("Editor GS", "Notificações ligadas neste aparelho.", "/", "teste")


@app.on_event("startup")
async def _iniciar_reserva():
    import asyncio
    if EXECUTOR is not None:
        try:
            atz.ao_iniciar(EXECUTOR)  # tira a PAUSA que a atualização automática pôs antes de reiniciar
        except Exception as e:  # noqa: BLE001
            log.warning("atualização (ao iniciar): %s", e)
        EXECUTOR.iniciar()
    if atz.ligado(CFG):
        asyncio.get_event_loop().create_task(_laco_atualizacao())
    if CFG.get("reserva_automatica", True):
        asyncio.get_event_loop().create_task(_laco_reserva())
    asyncio.get_event_loop().create_task(_laco_push())
    if CFG.get("automacoes_laco", True):
        asyncio.get_event_loop().create_task(_laco_automacoes())


async def _laco_atualizacao():
    """Atualização automática do plugin (13/11/2026): primeira olhada 3 min depois de subir, depois a cada `atualizacao_intervalo_min` (30)."""
    import asyncio
    await asyncio.sleep(180)
    while True:
        try:
            r = await asyncio.to_thread(atz.checar, EXECUTOR, CFG)
            if r.get("aplicando"):
                log.info("atualização automática: %s → %s", r["aplicando"].get("de"), r["aplicando"].get("para"))
        except Exception as e:  # noqa: BLE001
            log.warning("atualização automática: %s", e)
        await asyncio.sleep(max(10, int(CFG.get("atualizacao_intervalo_min", 30))) * 60)


@app.get("/api/gs/atualizacao")
def atualizacao_estado():
    return {**atz.estado(), "modo_plugin": atz.modo_plugin(), "ligado": atz.ligado(CFG), "versao": atz.versao_local()}


@app.post("/api/gs/atualizacao/agora")
async def atualizacao_agora():
    """Clique "Procurar atualização": confere já e aplica se houver e a fila estiver livre."""
    if not atz.modo_plugin():
        raise HTTPException(400, "Esta instalação não é pelo plugin: atualize pelo git.")
    return await asyncio.to_thread(atz.checar, EXECUTOR, CFG)


@app.post("/api/gs/reserva")
async def reserva_agora():
    """Roda a reserva automática já (o laço roda a cada minuto)."""
    return {"trocas": await reservar_travados(), "recuperadas": await recuperar_mensagens_finais()}


@app.get("/api/gs/estado")
async def estado():
    try:
        h = await _pc("GET", "/api/health"); ag = await _pc("GET", f"/api/companies/{CFG['company_id']}/agents")
        a = next((x for x in ag if x["id"] == CFG["agent_id"]), {})
        f = next((x for x in ag if x["id"] == CFG.get("agent_fable_id")), None)
        return {"paperclip": h.get("status"), "versao": h.get("version"), "notion_escrita": NOTION_ESCRITA, "licenca": _licenca_situacao(), "editor": {"nome": a.get("name"), "status": a.get("status"), "modelo": (a.get("adapterConfig") or {}).get("model")},
                "fable": ({"nome": f.get("name"), "status": f.get("status"), "modelo": (f.get("adapterConfig") or {}).get("model")} if f else None),
                "modelos": [{"id": k, "rotulo": v["rotulo"], "disponivel": bool(CFG.get(v["chave"]))} for k, v in MODELOS.items()]}
    except Exception as e:
        return JSONResponse({"paperclip": "offline", "erro": str(e)}, status_code=503)


@app.get("/api/gs/fluxos")
def fluxos():
    out = []
    for p in sorted((RAIZ / "fluxos").glob("*.md")):
        if p.name.startswith("_"):  # 13/11/2026: referência que o agente lê (ex.: _acabamento-referencia.md), não fluxo de pedido
            continue
        linhas = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        out.append({"nome": p.stem, "titulo": linhas[0].lstrip("# ").replace("Fluxo: ", "") if linhas else p.stem, "descricao": linhas[1] if len(linhas) > 1 else "", "conteudo": p.read_text(encoding="utf-8")})
    return out


AJUDA = ["COMPARTILHAR-CELULAR.md", "AGENTES.md", "PUBLICAR.md", "YOUTUBE-APP.md", "CANVA-CONNECT.md", "MATERIAIS-DRIVE.md", "MATERIAIS-GRATUITOS.md", "INSTAGRAM-COOKIES.md", "META-APP.md"]  # guias de docs/ mostrados na página Ajuda do app


@app.get("/api/gs/ajuda")
def ajuda():
    out = []
    for nome in AJUDA:
        p = RAIZ / "docs" / nome
        if p.exists():
            linhas = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            out.append({"nome": p.stem, "titulo": linhas[0].lstrip("# ") if linhas else p.stem, "conteudo": p.read_text(encoding="utf-8")})
    return out


FLUXOS_DIR = RAIZ / "fluxos"
ESTILOS_DIR = RAIZ / "estilos"
FLUXOS_FIXOS = {"reels-padrao", "referencia-analise", "minha-versao", "cortes-longos", "carrossel", "depoimentos-semanais", "respostas-comentarios", "analise-resultados", "roteiro", "traduzir-legenda", "video-locucao", "dublagem", "apostila", "gravo-eu-mesmo", "pesquisa-skills", "reproduzir-skill", "dissecar-skill"}


@app.post("/api/gs/fluxos")
def fluxo_criar(nome: str = Form(...), descricao: str = Form(""), passos: str = Form(...)):
    """Cria um fluxo (pedido pronto) em fluxos/<slug>.md a partir do app. Fluxos fixos do sistema não são sobrescritos."""
    slug = refs._slug(nome, 40)
    if not slug or slug in FLUXOS_FIXOS:
        raise HTTPException(400, "Escolha outro nome para o fluxo.")
    p = FLUXOS_DIR / f"{slug}.md"
    if p.exists():
        raise HTTPException(409, f"Já existe um fluxo chamado {slug}; apague ou use outro nome.")
    corpo = f"# Fluxo: {nome.strip()}\n\n{descricao.strip() or 'Pedido pronto criado pelo app.'}\n\nPassos para o Editor:\n{passos.strip()}\n"
    p.write_text(corpo, encoding="utf-8")
    return {"nome": slug, "titulo": nome.strip(), "descricao": descricao.strip(), "conteudo": corpo}


@app.delete("/api/gs/fluxos/{nome}")
def fluxo_apagar(nome: str):
    if nome in FLUXOS_FIXOS or not re.match(r"^[a-z0-9\-]+$", nome):
        raise HTTPException(400, "Esse fluxo é fixo do sistema.")
    p = FLUXOS_DIR / f"{nome}.md"
    if not p.exists():
        raise HTTPException(404, "Fluxo não encontrado.")
    p.unlink(); return {"ok": True}


@app.post("/api/gs/estilos")
def estilo_criar(nome: str = Form(...), base: str = Form("padrao"), cor_destaque: str = Form(""), tamanho_9x16: int = Form(0), maiusculas: str = Form(""), posicao: str = Form(""), palavras_por_linha_max: int = Form(0), zoom_por_frase: str = Form(""), clarao_transicao: str = Form(""), tela_final_cta: str = Form("")):
    """Cria um estilo de legenda em estilos/<slug>.json copiando um estilo base e trocando o que foi informado (cor de destaque, tamanho, maiúsculas, posição, zoom, clarão, tela final)."""
    slug = refs._slug(nome, 30)
    if not slug or slug in ("padrao",):
        raise HTTPException(400, "Escolha outro nome para o estilo.")
    pb = ESTILOS_DIR / f"{refs._slug(base, 30)}.json"
    if not pb.exists():
        raise HTTPException(404, "Estilo base não encontrado.")
    d = json.loads(pb.read_text(encoding="utf-8")); d["nome"] = slug; d["casa"] = False  # copiar um estilo da casa não herda a proteção
    leg, mon = d.setdefault("legenda", {}), d.setdefault("montagem", {})
    if cor_destaque:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", cor_destaque.strip()):
            raise HTTPException(400, "cor_destaque deve ser #RRGGBB.")
        leg["cor_destaque"] = cor_destaque.strip().upper()
    if tamanho_9x16:
        leg["tamanho_9x16"] = max(36, min(120, int(tamanho_9x16))); leg["tamanho_16x9"] = int(leg["tamanho_9x16"] * 0.75)
    if maiusculas:
        leg["maiusculas"] = maiusculas.lower() in ("1", "true", "sim")
    if posicao in ("baixa", "media", "alta"):
        leg["posicao"] = posicao
    if palavras_por_linha_max:
        leg["palavras_por_linha_max"] = max(2, min(8, int(palavras_por_linha_max)))
    for campo, valor in (("zoom_por_frase", zoom_por_frase), ("clarao_transicao", clarao_transicao), ("tela_final_cta", tela_final_cta)):
        if valor:
            mon[campo] = valor.lower() in ("1", "true", "sim")
    p = ESTILOS_DIR / f"{slug}.json"
    if p.exists():
        raise HTTPException(409, f"Já existe o estilo {slug}.")
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


@app.delete("/api/gs/estilos/{nome}")
def estilo_apagar(nome: str):
    if nome in ("padrao", "elementos") or not re.match(r"^[a-z0-9\-]+$", nome):
        raise HTTPException(400, "O estilo padrão não pode ser apagado.")
    p = ESTILOS_DIR / f"{nome}.json"
    if not p.exists():
        raise HTTPException(404, "Estilo não encontrado.")
    if json.loads(p.read_text(encoding="utf-8")).get("casa"):
        raise HTTPException(400, "Estilo da casa não se apaga (o agente e os fluxos usam). Monte um seu a partir dele.")
    p.unlink(); return {"ok": True}


@app.get("/api/gs/busca")
async def busca(q: str):
    """Busca nas conversas: título e código da issue, pedido, relatório e post.md da entrega. Devolve até 30 resultados com trecho."""
    termo = (q or "").strip().lower()
    if len(termo) < 2:
        return []
    def norm(t):
        t = unicodedata.normalize("NFKD", t or "").lower(); return "".join(c for c in t if not unicodedata.combining(c))
    termo_n = norm(termo)
    issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
    idx = _indice(); out = []; cache = txt.cache_ler(TEXTOS_CACHE)
    for it in issues if isinstance(issues, list) else issues.get("issues", []):
        c = _conversa(it, idx); textos = [("título", c["titulo"] or ""), ("pedido", re.sub(r"<!--.*?-->", "", it.get("description") or ""))]
        textos += [(s["titulo"].lower(), s["conteudo"]) for s in cache.get(c["id"], {}).get("secoes", [])]
        if c["slug"]:
            for nome in ("relatorio.md", "post.md", "roteiro.md"):
                p = SAIDA / c["slug"] / nome
                if p.exists():
                    textos.append((nome, p.read_text(encoding="utf-8", errors="ignore")[:20000]))
        for onde, t in textos:
            tn = norm(t); i = tn.find(termo_n)
            if i >= 0 or termo_n == (c["codigo"] or "").lower():
                ini = max(0, i - 60); trecho = t[ini:ini + 160].replace("\n", " ")
                out.append({**c, "onde": onde, "trecho": trecho}); break
        if len(out) >= 30:
            break
    return out


@app.get("/api/gs/estilos")
def estilos():
    return eb.estilos()


# Estilo do criativo (fase D, 07/11/2026): energia + chaves + "Salvar como meu padrão" + memórias visíveis (servico/estilo_criativo.py)
@app.get("/api/gs/estilo-criativo")
def estilo_criativo():
    ecr.garantir_espelho(); d = ecr.ler()
    return {**d, "opcoes": ecr.opcoes(), "texto_padrao": ecr.texto_instrucoes(d["padrao"])}


@app.post("/api/gs/estilo-criativo/padrao")
async def estilo_criativo_padrao(request: Request):
    return ecr.salvar_padrao(await request.json())


@app.post("/api/gs/estilo-criativo/texto")
async def estilo_criativo_texto(request: Request):
    """Prévia do parágrafo que vai no pedido (o painel mostra antes de enviar)."""
    return {"texto": ecr.texto_instrucoes(await request.json())}


@app.post("/api/gs/estilo-criativo/memorias")
def estilo_criativo_lembrar(texto: str = Form(""), origem: str = Form("Raphael")):
    try:
        return ecr.lembrar(texto, origem)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/gs/estilo-criativo/memorias/{mid}")
def estilo_criativo_esquecer(mid: str):
    if not ecr.esquecer(mid):
        raise HTTPException(404, "Memória não encontrada.")
    return {"ok": True}


@app.get("/api/gs/estilos/biblioteca")
def estilos_biblioteca():
    """Página Estilos (03/11/2026): estilos completos, modelos de legenda, animações, transições, elementos e formatos, cada um com o estado da prévia."""
    return eb.biblioteca()


@app.post("/api/gs/estilos/previas")
def estilos_previas(itens: str = Form("todas")):
    """Enfileira prévias (feitas pelos motores da entrega, uma por vez). itens = "todas" ou "tipo:id,tipo:id"."""
    lst = eb.todos_itens() if itens.strip() == "todas" else [tuple(x.split(":", 1)) for x in itens.split(",") if ":" in x]
    return {"enfileiradas": eb.pedir_previas(lst)}


@app.get("/api/gs/estilos/previa/{nome}")
def estilos_previa(nome: str):
    if not re.match(r"^[a-z]+-[a-z0-9\-]+-[0-9a-f]{10}\.(mp4|jpg)$", nome):
        raise HTTPException(400, "nome inválido")
    p = eb.PREVIAS / nome
    if not p.exists():
        raise HTTPException(404, "prévia não encontrada")
    return FileResponse(p, media_type="video/mp4" if nome.endswith(".mp4") else "image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


@app.post("/api/gs/estilos/montar")
async def estilos_montar(dados: dict):
    """Monta um estilo a partir da biblioteca (modelo de legenda + elementos + transição + formato + temas) e já pede a prévia dele."""
    try:
        d = eb.montar_estilo(dados, refs._slug)
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))
    eb.pedir_previas([("estilo", d["nome"])])
    return d


@app.get("/api/gs/conversas")
async def conversas():
    issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues"); idx = _indice()
    out = [_conversa(i, idx) for i in issues if i.get("status") != "cancelled" and i.get("identifier") not in CFG.get("ocultar_issues", [])]
    return sorted(out, key=lambda c: c["atualizado"] or "", reverse=True)


async def _salvar_uploads(pasta: Path, arquivos):
    """Grava os uploads em `pasta` (nomes saneados) e devolve os nomes salvos."""
    salvos = []
    for a in arquivos:
        nome = re.sub(r"[^\w.\-]+", "_", a.filename or "arquivo")
        destino = pasta / nome
        with destino.open("wb") as f:
            while True:
                bloco = await a.read(8 * 1024 * 1024)
                if not bloco:
                    break
                f.write(bloco)
        salvos.append(nome)
    return salvos


def _recebido(token: str):
    """Lê o material compartilhado que ainda espera o pedido. None se o token não existe."""
    if not TOKEN_RE.match(token or ""):
        return None
    pasta = RECEBIDOS / token
    meta = pasta / "recebido.json"
    if not meta.exists():
        return None
    d = json.loads(meta.read_text(encoding="utf-8"))
    arquivos = [{"nome": p.name, "tipo": _tipo(p), "tamanho_mb": round(p.stat().st_size / 1e6, 1)} for p in sorted(pasta.iterdir()) if p.is_file() and p.name != "recebido.json"]
    return {"token": token, "texto": d.get("texto", ""), "quando": d.get("quando"), "arquivos": arquivos}


def _mover_recebido(token: str, destino: Path):
    """Move os arquivos recebidos para a pasta do pedido e apaga a pasta temporária. Devolve os nomes."""
    pasta = RECEBIDOS / token
    nomes = []
    for p in sorted(pasta.iterdir()):
        if p.is_file() and p.name != "recebido.json":
            shutil.move(str(p), str(destino / p.name)); nomes.append(p.name)
    shutil.rmtree(pasta, ignore_errors=True)
    return nomes


async def _receber(texto: str, arquivos):
    """Guarda o que chegou pelo compartilhamento do celular e devolve o token para o app montar o pedido."""
    if not arquivos and not texto.strip():
        raise HTTPException(400, "Nada para receber: compartilhe um vídeo, áudio, imagem ou texto.")
    RECEBIDOS.mkdir(parents=True, exist_ok=True)
    token = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_urlsafe(4)}"
    pasta = RECEBIDOS / token; pasta.mkdir()
    await _salvar_uploads(pasta, arquivos)
    (pasta / "recebido.json").write_text(json.dumps({"texto": texto.strip(), "quando": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
    return _recebido(token)


@app.post("/compartilhar")
async def compartilhar(title: str = Form(""), text: str = Form(""), url: str = Form(""), arquivos: list[UploadFile] = File(default=[])):
    """Alvo do share_target do PWA (Android/Chrome): recebe o material e abre o Novo pedido com ele anexado."""
    texto = "\n".join(t for t in (title, text, url) if t and t.strip())
    rec = await _receber(texto, arquivos)
    return RedirectResponse(url=f"/novo?recebido={rec['token']}", status_code=303)


@app.post("/api/gs/recebidos")
async def receber(texto: str = Form(""), text: str = Form(""), arquivos: list[UploadFile] = File(default=[])):
    """Mesma coisa em JSON, para o Atalho do iPhone: devolve token e a URL do app para abrir."""
    rec = await _receber(texto or text, arquivos)
    return {**rec, "url": f"/novo?recebido={rec['token']}"}


@app.get("/api/gs/recebidos/{token}")
def recebido(token: str):
    rec = _recebido(token)
    if not rec:
        raise HTTPException(404, "Material não encontrado (já virou pedido ou o link venceu).")
    return rec


def _refs():
    return refs.Referencias(REFERENCIAS)


@app.get("/api/gs/referencias")
def referencias_listar():
    return _refs().listar()


@app.post("/api/gs/referencias")
async def referencias_criar(tarefas: BackgroundTasks, texto: str = Form(""), url: str = Form(""), arquivos: list[UploadFile] = File(default=[]), recebido: str = Form("")):
    """Guarda um link ou vídeo como referência. Link: baixa em segundo plano com yt-dlp (status `baixando` → `pronto`/`erro`)."""
    tmp = RECEBIDOS / f"_ref-{secrets.token_urlsafe(4)}"; tmp.mkdir(parents=True, exist_ok=True)
    salvos = [str(tmp / n) for n in await _salvar_uploads(tmp, arquivos)]
    if recebido:
        rec = _recebido(recebido)
        if not rec:
            raise HTTPException(404, "Material recebido não encontrado.")
        salvos += [str(tmp / n) for n in _mover_recebido(recebido, tmp)]
        texto = texto or rec.get("texto", "")
    try:
        d = _refs().criar(texto=texto, url=url, arquivos_salvos=salvos)
    except refs.ErroReferencia as e:
        shutil.rmtree(tmp, ignore_errors=True); raise HTTPException(400, str(e))
    shutil.rmtree(tmp, ignore_errors=True)
    if d["status"] == "baixando":
        tarefas.add_task(_refs().baixar, d["id"])
    return d


@app.get("/api/gs/referencias/concorrentes/destaques")
def concorrentes_destaques(dias: int = 120, minimo: float = 1.6):
    """Vídeos dos canais acompanhados que renderam acima da mediana do próprio canal (YouTube, gs.db só leitura)."""
    if not GSI_DB.exists():
        return {"dias": dias, "minimo": minimo, "itens": [], "canais": [], "nota": "gs.db não encontrado"}
    try:
        return rds.destaques_concorrentes(GSI_DB, dias=max(7, min(365, dias)), minimo=max(1.0, minimo))
    except Exception as e:
        return {"dias": dias, "minimo": minimo, "itens": [], "canais": [], "erro": str(e)[:200]}


@app.get("/api/gs/referencias/concorrentes")
def referencias_concorrentes():
    """Fontes acompanhadas pelo GSI (concorrentes, parceiros e referências), só leitura do gs.db."""
    if not GSI_DB.exists():
        return []
    con = sqlite3.connect(f"file:{GSI_DB}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    try:
        linhas = con.execute("select source_id, platform, handle, display_name, kind, category, notes, status, active, added_at from sources order by platform, handle").fetchall()
        yt = {r[0]: (r[1], r[2]) for r in con.execute("select source_id, count(*), max(published_at) from yt_videos group by 1")}
        ig = {r[0]: (r[1], r[2]) for r in con.execute("select source_id, count(*), max(posted_at) from ig_posts group by 1")}
    finally:
        con.close()
    out = []
    for r in linhas:
        n, ultimo = yt.get(r["source_id"]) or ig.get(r["source_id"]) or (0, None)
        url = f"https://www.youtube.com/@{r['handle']}" if r["platform"] == "youtube" and r["handle"] and not str(r["handle"]).startswith("UC") else f"https://www.instagram.com/{r['handle']}/" if r["platform"] == "instagram" and r["handle"] else None
        out.append({"id": r["source_id"], "plataforma": r["platform"], "handle": r["handle"], "nome": r["display_name"], "tipo": r["kind"], "categoria": r["category"], "notas": r["notes"],
                    "ativo": bool(r["active"]), "itens": n, "ultimo": ultimo, "url": url})
    return out


def _perfil_escrever():
    """Perfil do Thiago completo (padrões dos posts + "o que rende") em referencias/_perfil-thiago/, que o Editor lê antes de roteiro, gancho e edição."""
    d = prf.calcular(GSI_DB)
    r = prf.rende(GSI_DB, gch.por_tipo(gch.listar(SAIDA, GSI_DB, txt.cache_ler(TEXTOS_CACHE))), ad.estado().get("melhor_horario") or ad.melhor_horario(GSI_DB, ad.config("melhor_horario", aut.registro())))
    if not d.get("erro"):
        pasta = REFERENCIAS / "_perfil-thiago"; pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "perfil.md").write_text(prf.markdown(d) + prf.rende_markdown(r), encoding="utf-8")
        (pasta / "perfil.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        (pasta / "rende.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        d["arquivo"] = str(pasta / "perfil.md")
    return d, r


@app.get("/api/gs/referencias/perfil")
def referencias_perfil(gravar: bool = False):
    """Padrões do perfil do Thiago (Instagram e YouTube) a partir do gs.db, só leitura. gravar=1 também escreve referencias/_perfil-thiago/perfil.md para o Editor."""
    if gravar:
        d, _ = _perfil_escrever(); return d
    return prf.calcular(GSI_DB)


@app.get("/api/gs/perfil/rende")
def perfil_rende(atualizar: bool = False):
    """Perfil vivo (03/11/2026): o que rende para o Thiago (duração, formato, gancho, horário). Atualiza sozinho uma vez por dia; atualizar=1 refaz agora."""
    arq = REFERENCIAS / "_perfil-thiago" / "rende.json"
    if atualizar or not arq.exists():
        _, r = _perfil_escrever(); return r
    return json.loads(arq.read_text(encoding="utf-8"))

@app.get("/api/gs/notion/pagina/{pid}/texto")
def notion_pagina_texto(pid: str):
    """Texto de um cartão do Notion (blocos de primeiro nível + campo Roteiro do pulso), só leitura, para montar um pedido."""
    if not re.match(r"^[0-9a-f]{32}$", pid):
        raise HTTPException(400, "id inválido")
    tok, cfg = _notion_token()
    if not tok:
        raise HTTPException(503, "NOTION_TOKEN não encontrado no .env do GSI")
    hdr = {"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"]}
    try:
        pg = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.notion.com/v1/pages/{pid}", headers=hdr), timeout=30))
        props = pg.get("properties", {}); roteiro_pulso = _notion_val(props, "Roteiro do pulso") or ""; descricao = _notion_val(props, "Descrição") or ""
        linhas, cursor = [], None
        while True:
            u = f"https://api.notion.com/v1/blocks/{pid}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=30))
            for b in r.get("results", []):
                t = b.get("type"); x = b.get(t) or {}; rich = x.get("rich_text") or []
                txt = "".join(s.get("plain_text", "") for s in rich)
                if not txt:
                    continue
                pref = {"heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "bulleted_list_item": "- ", "numbered_list_item": "1. ", "to_do": "[ ] ", "quote": "> ", "callout": "> "}.get(t, "")
                linhas.append(pref + txt)
            if not r.get("has_more"):
                break
            cursor = r.get("next_cursor")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Notion: {e}")
    return {"id": pid, "titulo": _notion_val(props, "Name"), "formato": _notion_val(props, "Formato") or [], "descricao": descricao, "roteiro_pulso": roteiro_pulso, "corpo": "\n".join(linhas)[:12000], "url": pg.get("url")}


@app.get("/api/gs/referencias/{rid}")
def referencias_ler(rid: str):
    try:
        return _refs().ler(rid)
    except refs.ErroReferencia as e:
        raise HTTPException(404, str(e))


@app.post("/api/gs/referencias/{rid}/baixar")
def referencias_rebaixar(rid: str, tarefas: BackgroundTasks):
    try:
        d = _refs().atualizar(rid, status="baixando")
    except refs.ErroReferencia as e:
        raise HTTPException(404, str(e))
    tarefas.add_task(_refs().baixar, rid); return d


@app.post("/api/gs/referencias/{rid}/nota")
def referencias_nota(rid: str, nota: str = Form(""), titulo: str = Form("")):
    try:
        return _refs().atualizar(rid, nota=nota.strip() if nota else None, titulo=titulo.strip() if titulo else None)
    except refs.ErroReferencia as e:
        raise HTTPException(404, str(e))


@app.delete("/api/gs/referencias/{rid}")
def referencias_apagar(rid: str):
    try:
        return _refs().apagar(rid)
    except refs.ErroReferencia as e:
        raise HTTPException(404, str(e))


@app.post("/api/gs/referencias/{rid}/analisar")
async def referencias_analisar(rid: str):
    """Cria um pedido para o Editor analisar a referência (fluxo referencia-analise), sem produzir vídeo."""
    try:
        ref = _refs().ler(rid)
    except refs.ErroReferencia as e:
        raise HTTPException(404, str(e))
    pedido = refs.pedido_analise(ref)
    slug = _slug("analise " + (ref.get("titulo") or rid))
    desc = [pedido, "", "Fluxo: `fluxos/referencia-analise.md` (siga os passos dele).", "", f"Entregue a análise em `referencias/{rid}/analise.md` e repita as seções na mensagem final; nada vai para `saida/`. Não altere `entrada/`.",
            "Responda em PT-BR, curto, citando os JSONs das ferramentas.", "", f"<!-- gs-slug: {slug} -->"]
    issue = await _pc("POST", f"/api/companies/{CFG['company_id']}/issues", json={
        "title": f"Analisar referência: {(ref.get('titulo') or rid)[:60]}", "description": "\n".join(desc), "status": "todo", "priority": "medium",
        "assigneeAgentId": _agente_do_modelo("padrao"), "projectId": CFG["project_id"]})
    idx = _indice(); idx[issue["id"]] = {"slug": slug, "codigo": issue.get("identifier"), "criado": time.time(), "referencia": rid}; _salvar_indice(idx)
    _refs().anotar_pedido(rid, issue, "analise")
    return _conversa(issue, idx)


async def _criar_issue(titulo: str, desc_linhas: list[str], slug: str, extra: dict | None = None):
    desc_linhas = desc_linhas + ["", f"<!-- gs-slug: {slug} -->"]
    issue = await _pc("POST", f"/api/companies/{CFG['company_id']}/issues", json={
        "title": titulo[:110], "description": "\n".join(desc_linhas), "status": "todo", "priority": "medium",
        "assigneeAgentId": _agente_do_modelo("padrao"), "projectId": CFG["project_id"]})
    idx = _indice(); idx[issue["id"]] = {"slug": slug, "codigo": issue.get("identifier"), "criado": time.time(), **({"por": acs.QUEM.get()} if acs.QUEM.get() else {}), **(extra or {})}; _salvar_indice(idx)
    return _conversa(issue, idx)


@app.post("/api/gs/clipes")
async def clipes_criar(tarefas: BackgroundTasks, nota: str = Form(""), url: str = Form(""), tipo_origem: str = Form("live"), n: int = Form(10),
                       arquivos: list[UploadFile] = File(default=[]), recebido: str = Form(""), referencia: str = Form(""),
                       modo: str = Form("propor"), n_reels: int = Form(3), pecas: str = Form("reels,carrossel,stories,youtube"), estilo: str = Form("")):
    """Clipador: manda um vídeo longo (arquivo, link ou referência já baixada) para o Editor propor cortes (fase PROPOR).
    modo=kit (03/11/2026): kit de derivação, o Editor já entrega N Reels editados, carrossel, Stories e YouTube num pedido só."""
    tipo_origem = tipo_origem if tipo_origem in clp.TIPOS else "outro"
    nota = nota.strip(); url = url.strip()
    if not url and not arquivos and not recebido and not referencia:
        m = refs.URL_RE.search(nota)
        if m:
            url = m.group(0); nota = (nota[:m.start()] + nota[m.end():]).strip()
    kit = modo == "kit"
    slug = _slug(("kit " if kit else "clipes ") + (nota or (arquivos[0].filename if arquivos else url or referencia or "video")))
    pasta_in = ENTRADA / slug; pasta_in.mkdir(parents=True, exist_ok=True)
    origem_rel = None
    nomes = await _salvar_uploads(pasta_in, arquivos)
    if recebido:
        if not _recebido(recebido):
            raise HTTPException(404, "Material recebido não encontrado.")
        nomes += _mover_recebido(recebido, pasta_in)
    video = next((x for x in nomes if x.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".m4a", ".mp3", ".wav"))), None)
    if video:
        origem_rel = f"entrada/{slug}/{video}"
    elif referencia:
        try:
            ref = refs.Referencias(REFERENCIAS).ler(referencia)
        except refs.ErroReferencia as e:
            raise HTTPException(404, str(e))
        if not ref.get("video"):
            raise HTTPException(400, "Essa referência ainda não tem vídeo baixado.")
        origem_rel = f"referencias/{ref['id']}/{ref['video']}"
    elif url:
        # baixa como referência (reaproveita o yt-dlp) e aponta para ela
        d = refs.Referencias(REFERENCIAS).criar(texto=nota or "vídeo longo para cortes", url=url, por="clipador")
        origem_rel = f"referencias/{d['id']}/referencia.mp4"
        tarefas.add_task(refs.Referencias(REFERENCIAS).baixar, d["id"])
    else:
        shutil.rmtree(pasta_in, ignore_errors=True)
        raise HTTPException(400, "Anexe o vídeo longo, cole um link ou escolha uma referência.")
    if not any(pasta_in.iterdir()):
        pasta_in.rmdir()
    espera = " (pode estar baixando; se não existir, espere até 3 min e tente de novo)." if url and not video and not referencia else "."
    if kit:
        lista = [x.strip() for x in pecas.split(",") if x.strip() in ("reels", "carrossel", "stories", "youtube")] or ["reels"]
        desc = [clp.pedido_kit(origem_rel, tipo_origem, nota, n_reels, lista), "", f"Vídeo de origem: `{origem_rel}`" + espera, "Fluxo: `fluxos/kit-derivacao.md`.",
                f"Estilo de legenda: `{estilo or 'padrao'}`.", "", f"Entregue tudo em `saida/{slug}/`. Não altere `entrada/`.", "Responda em PT-BR, curto, citando os JSONs das ferramentas."]
        return await _criar_issue(f"Kit: {nota[:60] or origem_rel.rsplit('/', 1)[-1]}", desc, slug, {"clipador": {"origem": origem_rel, "tipo_origem": tipo_origem}, "kit": {"n_reels": n_reels, "pecas": lista}})
    pedido = clp.pedido_propor(origem_rel, tipo_origem, nota, n)
    desc = [pedido, "", f"Vídeo de origem: `{origem_rel}`" + espera,
            "Fluxo: `fluxos/cortes-longos.md` (fase PROPOR).", "", f"Entregue `cortes.json` em `saida/{slug}/`; resumo e pendências na mensagem final (seções `## `). Não altere `entrada/`.", "Responda em PT-BR, curto, citando os JSONs das ferramentas."]
    return await _criar_issue(f"Clipador: {nota[:60] or origem_rel.rsplit('/', 1)[-1]}", desc, slug, {"clipador": {"origem": origem_rel, "tipo_origem": tipo_origem}})


@app.get("/api/gs/conversas/{cid}/cortes")
def clipes_cortes(cid: str):
    """Cortes propostos pelo Editor nesta conversa (cortes.json) e o estado de edição de cada um."""
    try:
        slug, pasta = _pasta_saida(cid)
    except HTTPException:  # sem entrega ainda: 200 com lista vazia, não erro na UI (11/11/2026)
        return {"slug": _indice().get(cid, {}).get("slug"), "cortes": [], "pronto": False}
    d = clp.ler_cortes(pasta)
    if not d:
        return {"slug": slug, "cortes": [], "pronto": False}
    est = clp.ler_estado(pasta)
    for c in d["cortes"]:
        c["editado"] = est["editados"].get(c["id"]) or ({"issue_id": cid, "codigo": "kit", "slug": slug, "quando": ""} if c.get("kit") else None)  # trecho já editado dentro do kit
    meta = _indice().get(cid, {}).get("clipador", {})
    return {"slug": slug, "pronto": True, "origem": d.get("origem") or meta.get("origem"), "tipo_origem": d.get("tipo_origem") or meta.get("tipo_origem"), "duracao_s": d.get("duracao_s"), "cortes": d["cortes"]}


@app.post("/api/gs/conversas/{cid}/cortes/editar")
async def clipes_editar(cid: str, ids: str = Form(...)):
    """Cria um pedido de edição (reels-padrao) para cada corte escolhido. Só por clique humano."""
    slug, pasta = _pasta_saida(cid)
    d = clp.ler_cortes(pasta)
    if not d:
        raise HTTPException(400, "Ainda não há cortes.json nesta conversa.")
    meta = _indice().get(cid, {}).get("clipador", {})
    origem = d.get("origem") or meta.get("origem")
    if not origem:
        raise HTTPException(400, "cortes.json sem origem.")
    origem_rel = origem if not origem.startswith("/") else origem
    transc = next((f"saida/{slug}/{p.name}" for p in pasta.glob("*.json") if "palavras" in p.name or "transcricao" in p.name), None)
    escolhidos = [x.strip() for x in ids.split(",") if x.strip()]
    est = clp.ler_estado(pasta); criados = []
    for c in d["cortes"]:
        if c["id"] not in escolhidos or c["id"] in est["editados"]:
            continue
        slug_c = clp.slug_corte(slug, c)
        desc = [clp.pedido_editar(origem_rel, transc, c, d.get("tipo_origem") or meta.get("tipo_origem", "")), "", "Fluxo: `fluxos/reels-padrao.md` a partir do passo 3 (depois do `extrair_trecho`).", "Estilo de legenda: `padrao`.",
                f"Entregue os arquivos em `saida/{slug_c}/`; legenda do post, hashtags, título, gancho e pendências na mensagem final (seções `## `). Não altere `entrada/`.", "Responda em PT-BR, curto, citando os JSONs das ferramentas."]
        conv = await _criar_issue(f"Corte {c['id']}: {c.get('titulo') or c.get('gancho') or slug_c}", desc, slug_c, {"corte_de": cid, "corte_id": c["id"]})
        est["editados"][c["id"]] = {"issue_id": conv["id"], "codigo": conv["codigo"], "slug": slug_c, "quando": datetime.now().isoformat(timespec="seconds")}
        criados.append(conv)
    clp.gravar_estado(pasta, est)
    return {"criados": criados, "editados": est["editados"]}


@app.post("/api/gs/conversas")
async def nova_conversa(pedido: str = Form(""), fluxo: str = Form(""), estilo: str = Form("padrao"), arquivos: list[UploadFile] = File(default=[]), recebido: str = Form(""), referencia: str = Form(""), notion_page: str = Form(""), origem: str = Form("app"), pasta: str = Form(""), modelo: str = Form(""), campanha: str = Form(""), drive: str = Form(""), estilo_criativo: str = Form(""), pedido_usuario: str = Form("")):
    # chamada interna (automações, Redes, campanhas) pode omitir campos: chega o Form padrão, não texto
    pasta, modelo, campanha, notion_page, recebido, referencia, drive, estilo_criativo, pedido_usuario = (x if isinstance(x, str) else "" for x in (pasta, modelo, campanha, notion_page, recebido, referencia, drive, estilo_criativo, pedido_usuario))
    pedido_usuario = pedido_usuario.strip()  # o que o usuário digitou (o app acrescenta ficha de marca, voz, campanha…): é o que a conversa mostra
    try:
        sel_drive = dra.selecao(drive)
    except dra.ErroDrive as e:
        raise HTTPException(400, str(e))
    origem = origem if isinstance(origem, str) else "app"
    pedido = pedido.strip()
    await _sincronizar_instrucoes()
    escolhido = (modelo if isinstance(modelo, str) else "").strip().lower()  # chamadas internas passam o default Form
    modelo = escolhido if escolhido and escolhido != "padrao" else (_modelo_pedido_no_texto(pedido) or (_modelo_padrao_do_fluxo(fluxo) if not escolhido else "padrao"))  # chip > texto > fluxo > padrão
    agente = _agente_do_modelo(modelo)
    pasta_proj = _pasta_nome(pasta) or PASTAS_POR_ORIGEM.get(origem, "")  # pasta (projeto) do pedido; `pasta` abaixo é a pasta de entrada
    if pasta_proj:
        pasta_proj = _garantir_pasta(pasta_proj)
    ref = None
    if referencia:
        try:
            ref = refs.Referencias(REFERENCIAS).ler(referencia)
        except refs.ErroReferencia as e:
            raise HTTPException(404, str(e))
        if not pedido:
            pedido = refs.pedido_minha_versao(ref)
    rec = _recebido(recebido) if recebido else None
    if not pedido and not arquivos and not rec and not sel_drive:
        raise HTTPException(400, "Escreva o pedido ou anexe um arquivo.")
    primeiro = arquivos[0].filename if arquivos else (rec["arquivos"][0]["nome"] if rec and rec["arquivos"] else (sel_drive[0]["caminho"].rsplit("/", 1)[-1] if sel_drive else None))
    slug = _slug(pedido or primeiro or "pedido")
    pasta = ENTRADA / slug; pasta.mkdir(parents=True, exist_ok=True)
    salvos = [f"entrada/{slug}/{n}" for n in await _salvar_uploads(pasta, arquivos)]
    if rec:
        for nome in _mover_recebido(recebido, pasta):
            salvos.append(f"entrada/{slug}/{nome}")
    nomes_drive = dra.nomes_destino(sel_drive, pasta) if sel_drive else []
    salvos += [f"entrada/{slug}/{n}" for n in nomes_drive]
    base_titulo = pedido_usuario or _pedido_do_usuario(pedido)
    titulo = _titulo_curto(base_titulo) if base_titulo else f"Editar {salvos[0].split('/')[-1]}"
    desc = [pedido or "Edite o material anexado.", ""]
    if salvos:
        desc += ["Arquivos enviados:"] + [f"- `{s}`" for s in salvos] + [""]
    if ref:
        desc += [f"Referência: `referencias/{ref['id']}/` ({ref.get('titulo') or ref.get('url')}; vídeo `{ref.get('video') or 'ainda baixando'}`).", ""]
    if fluxo:
        desc += [f"Fluxo: `fluxos/{fluxo}.md` (siga os passos dele).", ""]
    if estilo_criativo.strip():  # painel Estilo do criativo (fase D): energia e chaves viram instrução; memórias ficam em preferencias/memorias.md
        try:
            desc += [ecr.texto_instrucoes(json.loads(estilo_criativo)), ""]
        except Exception:  # noqa: BLE001
            pass
    desc += [_linha_estilo(estilo), f"Entregue os arquivos em `saida/{slug}/`; os textos (resumo, legenda do post, hashtags, título, gancho, pendências) vão na mensagem final em seções `## `, não em .md. Não altere `entrada/`.",
             "Responda em PT-BR, curto, citando os JSONs das ferramentas.", "", f"<!-- gs-slug: {slug} -->"]
    issue = await _pc("POST", f"/api/companies/{CFG['company_id']}/issues", json={
        "title": titulo, "description": "\n".join(desc), "status": "backlog" if sel_drive else "todo", "priority": "medium",  # do Drive: espera o download para entrar na fila
        "assigneeAgentId": agente, "projectId": CFG["project_id"]})
    idx = _indice(); idx[issue["id"]] = {"slug": slug, "codigo": issue.get("identifier"), "criado": time.time(), **({"notion_page": re.sub(r"[^0-9a-f]", "", notion_page)} if notion_page else {}), "origem": origem, **({"pasta": pasta_proj} if pasta_proj else {}), "fluxo": fluxo or None, "estilo": estilo, "modelo": modelo, **({"pedido_usuario": pedido_usuario[:4000]} if pedido_usuario else {})}; _salvar_indice(idx)
    if ref:
        refs.Referencias(REFERENCIAS).anotar_pedido(ref["id"], issue, "minha-versao" if fluxo == "minha-versao" else "pedido")
    if campanha.strip():  # pedido aberto "para a campanha": a peça já nasce com a etiqueta
        try:
            pcs.gravar(SAIDA / slug, {"campanha": campanha.strip()[:60]}, por="pedido")
        except Exception as e:  # noqa
            log.warning("etiqueta de campanha: %s", e)
    if sel_drive:
        _drive_iniciar(issue["id"], sel_drive, pasta, nomes_drive, depois={"tipo": "pedido"}); idx = _indice()
    return _conversa(issue, idx)


@app.get("/api/gs/conversas/{cid}")
async def conversa(cid: str):
    issue = await _pc("GET", f"/api/issues/{cid}"); idx = _indice(); c = _conversa(issue, idx)
    coments = await _pc("GET", f"/api/issues/{cid}/comments")
    itens = coments if isinstance(coments, list) else coments.get("comments", coments.get("items", []))
    msgs = [{"id": m.get("id"), "autor": _autor_comentario(m), "texto": m.get("body") or "", "quando": m.get("createdAt")}
            for m in sorted(itens, key=lambda m: m.get("createdAt", ""))]
    completo = re.sub(r"<!--.*?-->", "", issue.get("description") or "", flags=re.S).strip()
    usuario = (idx.get(cid) or {}).get("pedido_usuario") or _pedido_do_usuario(completo)
    anexos = [a.rsplit("/", 1)[-1] for a in re.findall(r"^- `(entrada/[^`]+)`", completo, re.M)]
    ref_m = re.search(r"^Referência: `referencias/[^`]*` \(([^;\n]+)", completo, re.M)
    pedido = {"autor": "voce", "texto": usuario or ("Edite o material anexado." if anexos else completo), "quando": issue.get("createdAt"), "id": "pedido",
              "detalhes": completo if completo != usuario else None, "anexos": anexos, "fluxo": (idx.get(cid) or {}).get("fluxo"), "referencia": ref_m.group(1).strip() if ref_m else None}
    ag = await _pc("GET", f"/api/companies/{CFG['company_id']}/agents"); a = next((x for x in ag if x["id"] == CFG["agent_id"]), {})
    entregas = _entregas(c["slug"])
    rel = next((e for e in entregas if e["nome"] == "relatorio.md"), None)
    relatorio = (SAIDA / rel["caminho"]).read_text(encoding="utf-8") if rel else None
    ent = txt.entrega_de_mensagens(msgs); textos = ent["secoes"] if ent else []
    pst = next((e for e in entregas if e["nome"] == "post.md"), None)  # entregas antigas ainda têm post.md; as novas trazem as seções na mensagem
    post = _post((SAIDA / pst["caminho"]).read_text(encoding="utf-8")) if pst else txt.post_de(textos)
    _textos_cache_atualizar(issue, c, ent)
    inter = []
    try:
        lst = await _pc("GET", f"/api/issues/{cid}/interactions")
        itens = lst if isinstance(lst, list) else lst.get("interactions", lst.get("items", []))
        for it in itens:
            if it.get("status") in ("pending", "open", "waiting", None) and not it.get("resolvedAt"):
                pl = it.get("payload") or {}
                inter.append({"id": it.get("id"), "tipo": it.get("kind"), "titulo": it.get("title"), "resumo": it.get("summary"), "pergunta": pl.get("prompt"),
                              "opcoes": pl.get("options") or pl.get("choices") or [], "status": it.get("status")})
    except HTTPException:
        pass
    progresso = None
    try:  # tempo trabalhado de fato (soma das rodadas), "o Editor trabalhou por N min"
        runs = await _pc("GET", f"/api/issues/{cid}/runs")
        runs = runs if isinstance(runs, list) else runs.get("runs", runs.get("items", []))
        trabalho = arq.trabalho(runs)
        ativa = next((r for r in runs if r.get("status") in ("running", "queued", "in_progress") and r.get("logRef")), None)
        if ativa and (RUN_LOGS / ativa["logRef"]).is_file():  # 11/11/2026: etapa, % e tempo restante da rodada em andamento
            progresso = await asyncio.to_thread(prg.calcular, RUN_LOGS / ativa["logRef"], RUN_LOGS)
    except Exception:  # noqa: BLE001
        trabalho = trabalho if "trabalho" in locals() else None
    cc = next((e for e in entregas if e["nome"] == "capcut.json"), None)
    capcut = json.loads((SAIDA / cc["caminho"]).read_text(encoding="utf-8")) if cc else None
    return {**c, "editor_status": a.get("status"), "mensagens": [pedido] + msgs, "entregas": entregas, "relatorio": relatorio, "post": post, "post_origem": "arquivo" if pst else ("mensagem" if post else None), "textos": textos, "interacoes": inter, "capcut": capcut,
            "economia": arq.economia_pedido(SAIDA, c["slug"], issue), "trabalho": trabalho, "progresso": progresso,
            "peca": (pcs.etiquetas(SAIDA / c["slug"], textos, {**c, **({k: idx[cid].get(k) for k in ("corte_de", "referencia")} if cid in idx else {})}) if c.get("slug") and (SAIDA / c["slug"]).is_dir() else None)}


@app.get("/api/gs/conversas/{cid}/continuar")
async def continuar_conversa(cid: str):
    """"Continuar numa conversa nova" (fase D): conversa longa vira um pedido novo já preenchido com o resumo do que foi feito, os arquivos
    entregues (o Editor lê de saida/ e não refaz) e a mesma pasta, fluxo e estilo. Não cria nada: o app abre o Novo pedido com isso."""
    d = await conversa(cid)
    resumo = ""
    for m in reversed(d.get("mensagens") or []):
        t = m.get("texto") or ""
        if m.get("autor") == "editor" and "## Resumo" in t:
            resumo = t.split("## Resumo", 1)[1].split("\n## ", 1)[0].strip(); break
    idx = _indice().get(cid) or {}
    arquivos = [e["caminho"] for e in (d.get("entregas") or []) if not e["nome"].startswith(("_", "."))][:12]
    pedido_original = ((d.get("mensagens") or [{}])[0].get("texto") or "").split("\n\nArquivos enviados:", 1)[0].strip()[:600]
    linhas = [f"Continuação de {d.get('codigo') or 'uma conversa'} (\"{d.get('titulo')}\").", "", f"Pedido original: {pedido_original}"]
    if resumo:
        linhas += ["", "O que já foi feito:", resumo[:1500]]
    if arquivos:
        linhas += ["", "Arquivos já entregues (estão em saida/; use-os, não refaça o que está bom):"] + [f"- `saida/{a}`" for a in arquivos]
    linhas += ["", "Agora quero: "]
    return {"pedido": "\n".join(linhas), "pasta": d.get("pasta") or "", "fluxo": idx.get("fluxo") or "", "estilo": idx.get("estilo") or "padrao", "origem": d.get("codigo")}


@app.post("/api/gs/conversas/{cid}/mensagens")
async def mensagem(cid: str, texto: str = Form(""), modelo: str = Form(""), arquivos: list[UploadFile] = File(default=[]), drive: str = Form("")):
    """Mensagem na conversa, com anexos opcionais (vídeo, áudio, imagem, PDF) gravados em `entrada/<slug>/` e listados na mensagem (ex.: o take do modo
    "Gravo eu mesmo", ou "use este arquivo na cena 3"). Reabre a issue para o mesmo agente; `modelo` (ou "usa o Fable" / "volta para o Opus" no texto) troca o agente."""
    texto = (texto or "").strip()
    try:
        sel_drive = dra.selecao(drive if isinstance(drive, str) else "")
    except dra.ErroDrive as e:
        raise HTTPException(400, str(e))
    if not texto and not arquivos and not sel_drive:
        raise HTTPException(400, "Escreva a mensagem ou anexe um arquivo.")
    issue = await _pc("GET", f"/api/issues/{cid}")
    await _sincronizar_instrucoes()
    pedido = (modelo or "").strip().lower() or _modelo_pedido_no_texto(texto)
    agente = _agente_do_modelo(pedido) if pedido else (issue.get("assigneeAgentId") or CFG["agent_id"])
    trocou = pedido and agente != issue.get("assigneeAgentId")
    corpo = texto
    if arquivos:
        slug = (_indice().get(cid) or {}).get("slug") or _slug(issue.get("title") or cid)
        pasta = ENTRADA / slug; pasta.mkdir(parents=True, exist_ok=True)
        salvos = [f"entrada/{slug}/{n}" for n in await _salvar_uploads(pasta, arquivos)]
        corpo = (corpo + "\n\n" if corpo else "") + "Arquivos anexados agora: " + ", ".join(f"`{x}`" for x in salvos) + ". Use-os neste pedido (são a entrada nova desta mensagem)."
        _indice_atualizar(cid, slug=slug)
    if trocou:
        corpo += f"\n\n(Pedido do Raphael: continuar com o modelo {MODELOS[pedido]['rotulo']}. Leia a conversa inteira e os arquivos já entregues em saida/ antes de refazer; não repita o que já está bom.)"
    if sel_drive:  # do Drive: a mensagem só vai depois do download, para o agente não começar sem o arquivo
        slug = (_indice().get(cid) or {}).get("slug") or _slug(issue.get("title") or cid)
        pasta = ENTRADA / slug; pasta.mkdir(parents=True, exist_ok=True); _indice_atualizar(cid, slug=slug)
        nomes = dra.nomes_destino(sel_drive, pasta)
        _drive_iniciar(cid, sel_drive, pasta, nomes, depois={"tipo": "mensagem", "corpo": corpo, "agente": agente, "reabrir": bool(issue.get("status") in ("done", "in_review", "backlog", "blocked") or trocou)})
        return {"ok": True, "modelo": _modelo_do_agente(agente), "trocou": bool(trocou), "drive": len(nomes)}
    await _pc("POST", f"/api/issues/{cid}/comments", json={"body": corpo})
    if issue.get("status") in ("done", "in_review", "backlog", "blocked") or trocou:  # blocked: o Paperclip desistiu após tentativas falhas; a mensagem reabre
        await _pc("PATCH", f"/api/issues/{cid}", json={"status": "todo", "assigneeAgentId": agente})
    return {"ok": True, "modelo": _modelo_do_agente(agente), "trocou": bool(trocou)}


def _respostas_pergunta(inter: dict, texto: str):
    """Perguntas do agente (`ask_user_questions`): o Paperclip quer uma resposta por pergunta com `questionId`, `optionIds` e `otherText`.
    O app manda um texto só: vai como texto livre (opção `freeText`, se houver) em todas as perguntas; sem opção de texto livre, escolhe a opção cujo
    rótulo apareça no texto, senão a primeira."""
    respostas = []
    for q in ((inter.get("payload") or {}).get("questions") or []):
        ops = q.get("options") or []
        livre = next((o for o in ops if o.get("freeText")), None)
        if livre:
            respostas.append({"questionId": q["id"], "optionIds": [livre["id"]], "otherText": texto})
            continue
        t = (texto or "").lower()
        escolhida = next((o for o in ops if (o.get("label") or "").lower() and (o.get("label") or "").lower() in t), None) or (ops[0] if ops else None)
        respostas.append({"questionId": q["id"], "optionIds": [escolhida["id"]] if escolhida else [], "otherText": None if escolhida else texto})
    return respostas


@app.post("/api/gs/conversas/{cid}/interacoes/{iid}/{acao}")
async def decidir(cid: str, iid: str, acao: str, comentario: str = Form("")):
    if acao not in ("aceitar", "recusar", "responder"):
        raise HTTPException(400, "acao deve ser aceitar, recusar ou responder")
    rota = {"aceitar": "accept", "recusar": "reject", "responder": "respond"}[acao]
    body = {"comment": comentario} if comentario else {}
    if acao == "recusar" and comentario:
        body["reason"] = comentario  # confirmações exigem motivo da recusa
    if acao == "responder":
        body = {"response": comentario}
        try:
            lst = await _pc("GET", f"/api/issues/{cid}/interactions")
            inter = next((x for x in (lst if isinstance(lst, list) else lst.get("interactions", [])) if x.get("id") == iid), None)
        except HTTPException:
            inter = None
        if inter and inter.get("kind") == "ask_user_questions":
            body = {"answers": _respostas_pergunta(inter, comentario)}
    await _pc("POST", f"/api/issues/{cid}/interactions/{iid}/{rota}", json=body)
    return {"ok": True}


@app.get("/api/gs/materiais")
def materiais_estado():
    """Espelho dos materiais do Drive (logo, fotos, takes): estado, índice e pendências."""
    est = mat.estado(MATERIAIS)
    idx = MATERIAIS / "indice.json"
    est["itens"] = json.loads(idx.read_text(encoding="utf-8")).get("itens", []) if idx.exists() else []
    return est


@app.post("/api/gs/materiais/sincronizar")
def materiais_sincronizar():
    """rclone sync do Drive para workspace/materiais/ + índice para o Editor + logo oficial em estilos/logo.png. Só por clique."""
    try:
        return mat.sincronizar(MATERIAIS, ESTILOS_DIR)
    except mat.ErroMateriais as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/materiais/buscar")
def materiais_buscar(link: str = Form(...)):
    """Baixa um arquivo ou pasta do Drive pelo link para materiais/_links/<id>/ (para cartões do Notion com link de material)."""
    try:
        m = mat.ID_RE.search(link)
        if not m:
            raise HTTPException(400, "Link do Drive sem ID.")
        return mat.buscar_por_link(link, MATERIAIS / "_links" / m.group(1))
    except mat.ErroMateriais as e:
        raise HTTPException(400, str(e))


def _canva_redirect(request: Request):
    base = os.environ.get("EDITOR_GS_URL_PUBLICA", "").strip() or str(request.base_url).rstrip("/")
    return base + "/api/gs/canva/callback"


@app.get("/api/gs/canva/estado")
def canva_estado(request: Request):
    return cv.estado(_canva_redirect(request))


@app.get("/api/gs/canva/conectar")
def canva_conectar(request: Request):
    """Começa o OAuth do Canva (uma vez): redireciona para a tela de autorização."""
    try:
        return _Redir(cv.url_autorizacao(_canva_redirect(request)), status_code=302)
    except cv.ErroCanva as e:
        raise HTTPException(400, str(e))


@app.get("/api/gs/canva/callback")
def canva_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code:
        raise HTTPException(400, f"Canva recusou: {error or 'sem código'}")
    try:
        cv.trocar_codigo(code, state, _canva_redirect(request))
    except cv.ErroCanva as e:
        raise HTTPException(400, str(e))
    return _Redir("/estilos?canva=conectado", status_code=302)


@app.post("/api/gs/conversas/{cid}/canva")
def canva_importar(cid: str, arquivo: str = Form("carrossel.pptx"), titulo: str = Form("")):
    """Importa o editável da entrega no Canva e devolve o link de edição (válido 30 dias; pode importar de novo)."""
    slug, pasta = _pasta_saida(cid)
    if "/" in arquivo or not arquivo.lower().endswith((".pptx", ".pdf")):
        raise HTTPException(400, "Escolha o carrossel.pptx ou carrossel.pdf da entrega.")
    try:
        res = cv.importar(pasta / arquivo, titulo.strip() or f"GS {slug[:40]}")
    except cv.ErroCanva as e:
        raise HTTPException(400, str(e))
    lista = json.loads((pasta / "canva.json").read_text(encoding="utf-8")) if (pasta / "canva.json").exists() else []
    lista.append(res); (pasta / "canva.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


@app.get("/api/gs/conversas/{cid}/canva")
def canva_lista(cid: str):
    try:
        slug, pasta = _pasta_saida(cid)
    except HTTPException:  # sem entrega ainda: lista vazia em vez de 404 (11/11/2026)
        return []
    return json.loads((pasta / "canva.json").read_text(encoding="utf-8")) if (pasta / "canva.json").exists() else []


def _notion_patch(pid: str, propriedades: dict):
    tok, cfg = _notion_token()
    if not tok:
        raise HTTPException(503, "NOTION_TOKEN não encontrado no .env do GSI")
    req = urllib.request.Request(f"https://api.notion.com/v1/pages/{pid}", method="PATCH", data=json.dumps({"properties": propriedades}).encode(),
                                 headers={"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"], "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"Notion {e.code}: {e.read()[:200].decode(errors='ignore')}")
    except Exception as e:
        raise HTTPException(502, f"Notion: {e}")


@app.post("/api/gs/conversas/{cid}/aprovar")
async def aprovar(cid: str, comentario: str = Form("Ficou bom.")):
    """Aprovação humana da entrega: comenta na issue, marca done e, se o pedido veio de um cartão do Notion, passa o cartão para Prontos
    e anota os links da entrega no campo "Roteiro do pulso" (escrita no Notion só por este clique do Raphael)."""
    issue = await _pc("GET", f"/api/issues/{cid}")
    await _pc("POST", f"/api/issues/{cid}/comments", json={"body": f"APROVADO pelo Raphael no app. {comentario.strip()}"})
    if issue.get("status") not in ("done", "cancelled"):
        await _pc("PATCH", f"/api/issues/{cid}", json={"status": "done"})
    meta = _indice().get(cid, {}); slug = meta.get("slug"); pid = meta.get("notion_page")
    res = {"ok": True, "issue": cid, "notion": None}
    if slug and (SAIDA / slug).is_dir():
        aprv.registrar(SAIDA / slug, comentario=comentario)
    if pid and slug and not NOTION_ESCRITA:
        res["notion"] = "desligado: o Editor GS não escreve no Notion (decisão do Raphael, 31/10/2026); quem ajusta o cartão é o Raphael ou o pulso"
    elif pid and slug:
        base = os.environ.get("EDITOR_GS_URL_PUBLICA", "").strip() or URL_PADRAO
        ent = [e for e in _entregas(slug) if e["principal"]]
        links = "\n".join(f"- {e['nome']}: {base}{e['url']}" for e in ent)
        canva = SAIDA / slug / "canva.json"
        if canva.exists():
            try:
                for l in json.loads(canva.read_text(encoding="utf-8"))[-1:]:
                    links += f"\n- Canva (editável): {l.get('edit_url')}"
            except Exception:
                pass
        texto = f"[Editor GS {meta.get('codigo','')} · aprovado em {datetime.now():%d/%m/%Y %H:%M}]\n{links}"
        props = {"Status": {"status": {"name": "Prontos"}}, "Roteiro do pulso": {"rich_text": [{"text": {"content": texto[:1900]}}]}}
        try:
            _notion_patch(pid, props); res["notion"] = "Prontos"
        except HTTPException as e:
            # sem permissão de Status: tenta só o texto
            try:
                _notion_patch(pid, {"Roteiro do pulso": {"rich_text": [{"text": {"content": texto[:1900]}}]}}); res["notion"] = f"links anotados; Status não mudou ({e.detail})"
            except HTTPException as e2:
                res["notion"] = f"falhou: {e2.detail}"
    return res


@app.get("/api/gs/publicar/estado")
def publicar_estado(forcar: bool = False):
    """O que está pronto para publicar/guardar: contas da Publora e destino no Drive. Sem credencial, só pendências.
    Contas e remotes do rclone com cache de 5 min (servico/publicar.py); ?forcar=1 relê (11/11/2026)."""
    est = {"publora": {"configurado": False, "contas": [], "pendencias": []}, "drive": pub.drive_estado(forcar), "youtube": yt.estado("")}
    try:
        est["publora"]["contas"] = pub.contas_cacheadas(forcar); est["publora"]["configurado"] = True
    except pub.ErroPublicacao as e:
        est["publora"]["pendencias"].append(str(e))
    except Exception as e:
        est["publora"]["pendencias"].append(f"Publora inacessível: {e}")
    return est


def _projeto_dir(cid: str, nome: str) -> Path:
    _, pasta = _pasta_saida(cid)
    d = (pasta / "_projeto" / nome).resolve()
    if d.parent != (pasta / "_projeto").resolve() or not (d / "projeto.json").exists():
        raise HTTPException(404, "Projeto editável não encontrado (entregas montadas antes de 12/11/2026 não têm).")
    return d


@app.get("/api/gs/conversas/{cid}/projetos")
def projetos_editaveis(cid: str):
    """Editor manual (12/11/2026): projetos editáveis desta conversa (um por vídeo montado pelo motor)."""
    _, pasta = _pasta_saida(cid)
    return {"projetos": edm.projetos(pasta)}


@app.get("/api/gs/conversas/{cid}/projetos/{nome}")
def projeto_editavel(cid: str, nome: str):
    d = _projeto_dir(cid, nome); slug, _ = _pasta_saida(cid)
    sfx = sorted(f.name for f in (RAIZ / "remotion" / "public" / "sfx").glob("*.wav"))
    return {**edm.ler(d), "midia_base": f"/editor-midia/{cid}/{nome}", "sfx_catalogo": sfx, "conversa": cid, "arquivos_base": f"/arquivos/{slug}"}


@app.post("/api/gs/conversas/{cid}/projetos/{nome}/renderizar")
async def projeto_renderizar(cid: str, nome: str, request: Request):
    """Recebe as props editadas (+ correções de legenda) e refaz o vídeo em segundo plano; o original não é tocado."""
    d = _projeto_dir(cid, nome); corpo = await request.json()
    if not isinstance(corpo.get("props"), dict):
        raise HTTPException(400, "Faltam as props.")
    try:
        return edm.renderizar(d, corpo["props"], corpo.get("correcoes") or None, por=acs.QUEM.get() or "Raphael", acabamento=corpo.get("acabamento") or None,
                              edl=corpo.get("edl") or None, legenda_estilo=corpo.get("legenda_estilo") or None)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/conversas/{cid}/projetos/{nome}/previa_legenda")
async def projeto_previa_legenda(cid: str, nome: str, request: Request):
    """Editor manual fase 2 (12/11/2026): legenda no tempo da EDL editada e no estilo escolhido, para a prévia (linhas do motor ASS ou a prop da cinética)."""
    d = _projeto_dir(cid, nome); corpo = await request.json()
    try:
        return edm.previa_legenda(d, corpo.get("edl") or None, corpo.get("estilo") or None, corpo.get("correcoes") or None)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/conversas/{cid}/projetos/{nome}/capcut")
async def projeto_capcut(cid: str, nome: str, request: Request):
    """CapCut fiel (12/11/2026): manda o projeto para o CapCut desta máquina (cortes com zoom e transições do CapCut, grafismos e legenda transparentes, efeitos e trilha)."""
    d = _projeto_dir(cid, nome)
    try:
        corpo = await request.json()
    except Exception:  # noqa: BLE001
        corpo = {}
    try:
        return edm.exportar_capcut(d, legenda=(corpo or {}).get("legenda") or "nativa")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/editor-midia/{cid}/{nome}/{caminho:path}")
def projeto_midia(cid: str, nome: str, caminho: str):
    """staticFile() do Remotion no editor manual: render/* vem do projeto; fontes/* e sfx/* da pasta public do motor; bruto/* = o bruto da EDL (fase 2)."""
    if caminho.startswith("bruto/"):
        b = edm.caminho_bruto(_projeto_dir(cid, nome))
        if not b or not b.is_file():
            raise HTTPException(404, "Bruto não encontrado.")
        return FileResponse(b)
    raiz = (_projeto_dir(cid, nome) / "midia") if caminho.startswith("render/") else (RAIZ / "remotion" / "public")
    alvo = (raiz / caminho).resolve()
    if raiz.resolve() not in alvo.parents or not alvo.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(alvo)


def _pasta_saida(cid: str):
    slug = _indice().get(cid, {}).get("slug")
    pasta = SAIDA / slug if slug else None
    if not pasta or not pasta.exists():
        raise HTTPException(404, "Esta conversa ainda não tem entrega.")
    return slug, pasta


# --- Checkpoints e "Desfazer" (10/11/2026): foto de saida/<slug>/ antes de cada rodada do agente; voltar é por clique humano ----------
def _checkpoint_antes_da_rodada(issue: dict, run: dict, numero: int):
    """Gancho do executor local: antes de disparar a rodada, tira o checkpoint da pasta de entrega da conversa (se ela já existe)."""
    slug = _conversa(issue, _indice()).get("slug")
    if slug and (SAIDA / slug).is_dir():
        r = ckp.tirar(SAIDA / slug, rodada=numero)
        if r:
            log.info("checkpoint %s de %s antes da rodada %s (%s)", r["n"], slug, numero, r["resumo"])


if EXECUTOR is not None:
    EXECUTOR.antes_da_rodada = _checkpoint_antes_da_rodada
    EXECUTOR.ao_limite_de_uso = _trocar_por_limite


@app.get("/api/gs/conversas/{cid}/checkpoints")
def checkpoints_listar(cid: str):
    """Checkpoints da entrega desta conversa (mais novo primeiro): n, quando, rodada, resumo. Sem entrega: lista vazia."""
    slug = _indice().get(cid, {}).get("slug")
    pasta = SAIDA / slug if slug else None
    return {"slug": slug, "itens": ckp.listar(pasta) if pasta and pasta.is_dir() else []}


@app.post("/api/gs/conversas/{cid}/desfazer")
async def desfazer(cid: str, request: Request):
    """↶ Desfazer: volta a pasta de entrega ao estado do checkpoint `n` (body JSON {"n": 3}; sem n, o último). O estado atual vira um
    checkpoint novo antes (desfazer é desfazível). Não roda com rodada em andamento (409). Registra uma mensagem de sistema na conversa."""
    try:
        body = await request.json() if (await request.body()) else {}
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "JSON inválido")
    n = (body or {}).get("n")
    issue = await _pc("GET", f"/api/issues/{cid}")
    if issue.get("activeRun"):
        raise HTTPException(409, "O Editor está trabalhando nesta conversa: pare a rodada (■ Parar) antes de desfazer.")
    slug, pasta = _pasta_saida(cid)
    try:
        r = ckp.restaurar(pasta, n)
    except (ValueError, KeyError) as e:
        raise HTTPException(404, str(e).strip("'\""))
    hora = (r.get("quando") or "")[11:16]
    texto = (f"↶ Desfeito: voltou ao estado antes da rodada {r['rodada']} ({hora})." if r.get("rodada") else f"↶ Desfeito: voltou ao checkpoint {r['n']} ({hora}).") \
        + f" {len(r['restaurados'])} arquivo(s) restaurado(s), {len(r['apagados'])} apagado(s). O estado anterior ficou guardado como checkpoint {r['checkpoint_novo']['n']}."
    try:
        await _pc("POST", f"/api/issues/{cid}/comments", json={"body": texto})
    except HTTPException as e:
        log.warning("desfazer %s: mensagem na conversa falhou (%s)", cid, e.detail)
    return {**r, "slug": slug, "mensagem": texto}


@app.post("/api/gs/conversas/{cid}/publicar")
def publicar_conversa(cid: str, arquivo: str = Form("final_9x16.mp4"), legenda: str = Form(""), plataformas: str = Form(""), quando: str = Form(""), titulo: str = Form(""), capa: str = Form("")):
    """Manda o vídeo da entrega para a Publora como rascunho (sem `quando`) ou agendado (ISO 8601 UTC). `capa` = imagem da entrega usada como capa do Reels. Só por clique humano."""
    slug, pasta = _pasta_saida(cid)
    if "/" in arquivo or arquivo.startswith(".") or "/" in capa or capa.startswith("."):
        raise HTTPException(400, "Nome de arquivo inválido.")
    contas = [x.strip() for x in plataformas.split(",") if x.strip()]
    try:
        res = pub.Publora().publicar(pasta / arquivo, legenda.strip(), contas, quando.strip() or None, titulo.strip() or None, capa=(pasta / capa) if capa else None)
    except pub.ErroPublicacao as e:
        raise HTTPException(400, str(e))
    pub.registrar(pasta, {"tipo": "publora", "arquivo": arquivo, "plataformas": contas, "legenda": legenda.strip(), **({"capa_arquivo": capa} if capa else {}), **res})
    return res


def _yt_redirect(request: Request):
    base = os.environ.get("EDITOR_GS_URL_PUBLICA", "").strip().rstrip("/")
    return (base or str(request.base_url).rstrip("/")) + "/api/gs/youtube/callback"


@app.get("/api/gs/youtube/estado")
def youtube_estado(request: Request):
    return yt.estado(_yt_redirect(request))


@app.get("/api/gs/youtube/conectar")
def youtube_conectar(request: Request):
    """Começa o OAuth do Google (uma vez): redireciona para a tela de consentimento."""
    try:
        return _Redir(yt.url_autorizacao(_yt_redirect(request)), status_code=302)
    except yt.ErroYouTube as e:
        raise HTTPException(400, str(e))


@app.get("/api/gs/youtube/callback")
def youtube_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code:
        raise HTTPException(400, f"Google recusou: {error or 'sem código'}")
    try:
        yt.trocar_codigo(code, state, _yt_redirect(request))
    except yt.ErroYouTube as e:
        raise HTTPException(400, str(e))
    return _Redir("/estilos?youtube=conectado", status_code=302)


@app.post("/api/gs/conversas/{cid}/youtube")
def youtube_publicar(cid: str, arquivo: str = Form("final_16x9.mp4"), titulo: str = Form(""), descricao: str = Form(""), tags: str = Form(""), privacidade: str = Form("private"),
                     quando: str = Form(""), capa: str = Form("")):
    """Sobe o vídeo da entrega direto no canal conectado (app próprio, sem Publora). Padrão: privado; `quando` (ISO UTC) agenda a publicação. Só por clique humano."""
    slug, pasta = _pasta_saida(cid)
    if "/" in arquivo or arquivo.startswith(".") or "/" in capa or capa.startswith("."):
        raise HTTPException(400, "Nome de arquivo inválido.")
    try:
        res = yt.publicar(pasta / arquivo, titulo.strip(), descricao.strip(), [t.strip().lstrip("#") for t in re.split(r"[,\n]", tags) if t.strip()], privacidade.strip() or "private",
                          quando.strip() or None, capa=(pasta / capa) if capa else None)
    except yt.ErroYouTube as e:
        raise HTTPException(400, str(e))
    pub.registrar(pasta, {"tipo": "youtube", "arquivo": arquivo, "descricao": descricao.strip()[:500], **res})
    return res


@app.get("/api/gs/conversas/{cid}/publicacoes")
def publicacoes(cid: str, atualizar: bool = False):
    """Histórico do que foi mandado para a Publora e para o Drive nesta entrega; `atualizar=1` consulta o status atual na Publora."""
    slug, pasta = _pasta_saida(cid)
    lista = pub.registros(pasta)
    if atualizar:
        try:
            p = pub.Publora()
            for it in lista:
                if it.get("tipo") == "publora" and it.get("postGroupId"):
                    try:
                        it.update(p.estado(it["postGroupId"]))
                    except pub.ErroPublicacao as e:
                        it["erro_status"] = str(e)
        except pub.ErroPublicacao:
            pass
        for it in lista:
            if it.get("tipo") == "youtube" and it.get("video_id"):
                try:
                    it.update(yt.estado_video(it["video_id"]))
                except yt.ErroYouTube as e:
                    it["erro_status"] = str(e)
    return lista


@app.post("/api/gs/conversas/{cid}/drive")
def drive_conversa(cid: str, arquivos: str = Form("final_9x16.mp4,final_16x9.mp4,capa.png,post.md")):
    """Copia arquivos da entrega para DRIVE_DESTINO/<slug>/ pelo rclone."""
    slug, pasta = _pasta_saida(cid)
    nomes = [x.strip() for x in arquivos.split(",") if x.strip() and "/" not in x and not x.startswith(".")]
    if "post.md" in nomes and not (pasta / "post.md").exists():  # entregas novas: a legenda está na mensagem, vai como post.txt
        nomes.remove("post.md"); ps = txt.post_de(txt.cache_ler(TEXTOS_CACHE).get(cid, {}).get("secoes", []))
        if ps:
            (pasta / "post.txt").write_text("\n\n".join(f"{txt.ROTULOS.get(k, k)}\n{v}" for k, v in ps.items()) + "\n", encoding="utf-8"); nomes.append("post.txt")
    try:
        res = pub.salvar_drive(pasta, slug, nomes)
    except pub.ErroPublicacao as e:
        raise HTTPException(400, str(e))
    pub.registrar(pasta, {"tipo": "drive", **res})
    return res


@app.post("/api/gs/capcut/abrir")
def abrir_capcut():
    """Abre o CapCut no Windows (só funciona no próprio notebook)."""
    import subprocess
    exe = "C:\\Users\\rapha\\AppData\\Local\\CapCut\\Apps\\CapCut.exe"
    try:
        subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{exe}'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"não abriu o CapCut: {e}")


@app.post("/api/gs/conversas/{cid}/parar")
async def parar(cid: str):
    """Botão ■ Parar (02/11/2026): interrompe a execução atual do Editor nesta conversa (cancela o heartbeat run ativo no Paperclip) e deixa o pedido
    em pausa (status blocked) para não voltar à fila sozinho. O que já foi gerado em saida/ fica. "Retomar" devolve o pedido à fila."""
    issue = await _pc("GET", f"/api/issues/{cid}")
    run = issue.get("activeRun"); run_id = run.get("id") if isinstance(run, dict) else (run or None)
    cancelada = False
    if run_id:
        try:
            await _pc("POST", f"/api/heartbeat-runs/{run_id}/cancel", json={}); cancelada = True
        except HTTPException as e:
            log.warning("parar %s: cancel do run %s falhou (%s)", cid, run_id, e.detail)
    if issue.get("status") not in ("done", "cancelled"):
        await _pc("PATCH", f"/api/issues/{cid}", json={"status": "blocked", "comment": "⏸ Edição pausada pelo app (botão Parar). Clique em Retomar para continuar de onde parou."})
    return {"ok": True, "run_cancelada": cancelada, "status": "blocked" if issue.get("status") not in ("done", "cancelled") else issue.get("status")}


@app.post("/api/gs/conversas/{cid}/retomar")
async def retomar(cid: str):
    """▶ Retomar: devolve o pedido pausado à fila do Editor (status todo). O Editor relê o pedido, os comentários e o que já existe em saida/."""
    await _pc("PATCH", f"/api/issues/{cid}", json={"status": "todo", "comment": "▶ Retomar: continue de onde parou; o que já está em saida/ pode ser reaproveitado."})
    return {"ok": True, "status": "todo"}


@app.post("/api/gs/conversas/{cid}/cancelar")
async def cancelar(cid: str):
    await _pc("PATCH", f"/api/issues/{cid}", json={"status": "cancelled", "comment": "Pedido cancelado pelo app."})
    return {"ok": True}


NOTION_CACHE = {"t": 0.0, "dados": []}
MOLDES = {"reels modelo", "carrossel modelo"}


def _notion_token():
    env = GSI_RAIZ / ".env"
    if not env.exists():
        return None, None
    kv = dict(l.strip().split("=", 1) for l in env.read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))
    tok = (kv.get("NOTION_TOKEN") or "").strip().strip('"')
    try:
        ver = json.loads((GSI_RAIZ / "integracoes" / "config_pulso_conteudo.json").read_text(encoding="utf-8"))["notion"]["versao_api"]
        ds = json.loads((GSI_RAIZ / "integracoes" / "config_pulso_conteudo.json").read_text(encoding="utf-8"))["notion"]["data_sources"]["INSTA"]
    except Exception:
        return None, None
    return (tok or None), {"versao": ver, "ds": ds}


def _notion_val(p, name):
    v = p.get(name)
    if not v:
        return None
    t = v["type"]; x = v.get(t)
    if t in ("select", "status"):
        return x and x["name"]
    if t == "multi_select":
        return [o["name"] for o in x]
    if t in ("checkbox", "url"):
        return x
    if t == "title":
        return "".join(s["plain_text"] for s in x)
    if t == "rich_text":
        return "".join(s["plain_text"] for s in x)
    if t == "date":
        return (x or {}).get("start")
    return None


def _notion_com_material():
    """Cartões da base INSTA do Notion que já têm material para editar (leitura; o Notion continua HUMAN_ONLY para escrita)."""
    if time.time() - NOTION_CACHE["t"] < 300 and NOTION_CACHE["dados"]:
        return NOTION_CACHE["dados"]
    tok, cfg = _notion_token()
    if not tok:
        raise HTTPException(503, "NOTION_TOKEN não encontrado no .env do GSI")
    out, cursor = [], None
    while True:
        body = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        req = urllib.request.Request(f"https://api.notion.com/v1/data_sources/{cfg['ds']}/query", method="POST", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"], "Content-Type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            raise HTTPException(502, f"Notion: {e}")
        for pg in r.get("results", []):
            p = pg["properties"]; titulo = _notion_val(p, "Name") or ""
            st = _notion_val(p, "Status"); fila = _notion_val(p, "Fila") or []; mat = _notion_val(p, "Material"); pr = _notion_val(p, "Prioridade")
            if titulo.strip().lower() in MOLDES or st in ("Postados", "Prontos", "🔁 Recorrente"):
                continue
            tem = ("Edição" in fila) or (mat or "").startswith("✅") or st == "Arte/Edição" or bool(_notion_val(p, "Video Editado"))
            if not tem:
                continue
            motivo = []
            if "Edição" in fila: motivo.append("Fila: Edição (vídeo existente)")
            if (mat or "").startswith("✅"): motivo.append("Material pronto")
            if st == "Arte/Edição": motivo.append("Status: Arte/Edição")
            if _notion_val(p, "Video Editado"): motivo.append("Vídeo editado marcado")
            out.append({"id": pg["id"].replace("-", ""), "titulo": titulo, "status": st, "fila": fila, "material": mat, "prioridade": pr, "formato": _notion_val(p, "Formato") or [],
                        "url": _notion_val(p, "URL"), "roteiro": bool(_notion_val(p, "Roteiro")), "motivo": motivo, "atualizado": pg.get("last_edited_time"),
                        "notion_url": pg.get("url"), "origem": "notion"})
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
    ordem = {"Maxima": 0, "Media": 1, None: 2, "Minima": 3}
    out.sort(key=lambda c: (0 if c["status"] == "Arte/Edição" else 1, ordem.get(c["prioridade"], 2), c["atualizado"] or ""), reverse=False)
    NOTION_CACHE.update({"t": time.time(), "dados": out})
    return out


def _notion_carrosseis():
    """Cartões do Notion com Formato Carrosel que ainda não foram postados (leitura)."""
    tok, cfg = _notion_token()
    if not tok:
        raise HTTPException(503, "NOTION_TOKEN não encontrado no .env do GSI")
    out, cursor = [], None
    while True:
        body = {"page_size": 100, "filter": {"property": "Formato", "multi_select": {"contains": "Carrosel"}}, **({"start_cursor": cursor} if cursor else {})}
        req = urllib.request.Request(f"https://api.notion.com/v1/data_sources/{cfg['ds']}/query", method="POST", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"], "Content-Type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            raise HTTPException(502, f"Notion: {e}")
        for pg in r.get("results", []):
            p = pg["properties"]; titulo = _notion_val(p, "Name") or ""; st = _notion_val(p, "Status")
            if titulo.strip().lower() in MOLDES or st in ("Postados", "Prontos", "🔁 Recorrente"):
                continue
            out.append({"id": pg["id"].replace("-", ""), "titulo": titulo, "status": st, "fila": _notion_val(p, "Fila") or [], "material": _notion_val(p, "Material"), "prioridade": _notion_val(p, "Prioridade"), "formato": _notion_val(p, "Formato") or [],
                        "url": _notion_val(p, "URL"), "roteiro": bool(_notion_val(p, "Roteiro")), "motivo": ["Formato: Carrosel"] + (["Roteiro marcado"] if _notion_val(p, "Roteiro") else []), "atualizado": pg.get("last_edited_time"), "notion_url": pg.get("url"), "origem": "notion"})
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
    ordem = {"Maxima": 0, "Media": 1, None: 2, "Minima": 3}
    out.sort(key=lambda c: (0 if c["status"] in ("Arte/Edição", "Aprovado") else 1, ordem.get(c["prioridade"], 2), c["atualizado"] or ""))
    return out


@app.get("/api/gs/ideias")
def ideias(status: str = "approved,proposed", limite: int = 60):
    if status == "carrosseis":
        return _notion_carrosseis()
    """Ideias do GSI (somente leitura do gs.db) ou, com status=com_material, cartões do Notion com material pronto. Nada é escrito."""
    if status == "com_material":
        return _notion_com_material()
    if not GSI_DB.exists():
        return JSONResponse({"erro": f"banco do GSI não encontrado: {GSI_DB}", "ideias": []}, status_code=503)
    st = [x.strip() for x in status.split(",") if x.strip()]
    q = f"select canonical_id, title, description, status, editorial_zone, primary_family, format_candidate, audience_candidate, novelty, saturation, reinforcement_count, updated_at from ideas where status in ({','.join('?'*len(st))}) and (duplicate_of is null) order by case status when 'approved' then 0 else 1 end, reinforcement_count desc, updated_at desc limit ?"
    con = sqlite3.connect(f"file:{GSI_DB}?mode=ro", uri=True)
    try:
        rows = con.execute(q, [*st, limite]).fetchall()
    finally:
        con.close()
    cols = ["id", "titulo", "descricao", "status", "zona", "familia", "formato", "publico", "novidade", "saturacao", "reforcos", "atualizado"]
    return [dict(zip(cols, r)) for r in rows]


def _estado_uso(pasta: Path):
    """O que já foi feito com a entrega, pelo publicacoes.json: postado/agendado (Publora, YouTube), guardado no Drive, ou ainda não usado (filtros da Biblioteca)."""
    regs = pub.registros(pasta) if pasta.exists() else []
    n = {"publora": 0, "youtube": 0, "drive": 0}
    for r in regs:
        t = r.get("tipo")
        if t in n:
            n[t] += 1
    rotulo = "postado ou agendado" if (n["publora"] or n["youtube"]) else ("no Drive" if n["drive"] else "ainda não usado")
    return {**n, "rotulo": rotulo, "ultimo": regs[-1].get("quando") if regs else None}


@app.get("/api/gs/biblioteca")
def biblioteca():
    pastas = []
    idx = _indice(); por_slug = {v.get("slug"): {"id": k, "pasta": v.get("pasta")} for k, v in idx.items() if v.get("slug")}
    for d in sorted((p for p in SAIDA.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
        ps = por_slug.get(d.name) or {}
        pastas.append({"slug": d.name, "itens": _entregas(d.name), "uso": _estado_uso(d), "conversa": ps.get("id"), "pasta": ps.get("pasta"), "teste": _eh_teste(ps.get("pasta"), d.name)})
    return pastas


# --- Redes: calendário, comentários e resultados (só leitura; pedidos ao Editor viram conversas) ----
NOTION_CAL_CACHE = {"t": 0.0, "chave": None, "dados": []}
MES_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _notion_calendario(ini: str, fim: str):
    """Cartões do Notion Mídias (INSTA) com Data de publicação no intervalo. Leitura; cache de 5 min."""
    if NOTION_CAL_CACHE["chave"] == (ini, fim) and time.time() - NOTION_CAL_CACHE["t"] < 300:
        return NOTION_CAL_CACHE["dados"]
    tok, cfg = _notion_token()
    if not tok:
        return []
    out, cursor = [], None
    while True:
        body = {"page_size": 100, "filter": {"and": [{"property": "Data de publicação", "date": {"on_or_after": ini}}, {"property": "Data de publicação", "date": {"on_or_before": fim}}]}, **({"start_cursor": cursor} if cursor else {})}
        req = urllib.request.Request(f"https://api.notion.com/v1/data_sources/{cfg['ds']}/query", method="POST", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"], "Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=30))
        for pg in r.get("results", []):
            p = pg["properties"]; titulo = _notion_val(p, "Name") or ""; st = _notion_val(p, "Status")
            if titulo.strip().lower() in MOLDES:
                continue
            out.append({"dia": _notion_val(p, "Data de publicação"), "titulo": titulo, "status": st, "formato": _notion_val(p, "Formato") or [], "fila": _notion_val(p, "Fila") or [],
                        "material": _notion_val(p, "Material"), "notion_url": pg.get("url"), "recorrente": st == "🔁 Recorrente", "postado": st == "Postados"})
        if not r.get("has_more"):
            break
        cursor = r.get("next_cursor")
    NOTION_CAL_CACHE.update({"t": time.time(), "chave": (ini, fim), "dados": out})
    return out


@app.get("/api/gs/redes/calendario")
def redes_calendario(antes: int = 14, depois: int = 28):
    """Calendário: agendados/rascunhos da Publora, postados (gs.db) e planejados no Notion Mídias."""
    hoje = date.today(); ini = (hoje - timedelta(days=antes)).isoformat(); fim = (hoje + timedelta(days=depois)).isoformat()
    notion, aviso = [], None
    try:
        notion = _notion_calendario(ini, fim)
    except Exception as e:
        aviso = f"Notion indisponível: {e}"
    r = rds.calendario(GSI_DB, SAIDA, notion, antes, depois); r["aviso"] = aviso
    return r


@app.get("/api/gs/redes/comentarios")
def redes_comentarios(dias: int = 30, todos: bool = False):
    """Comentários de leitores nos conteúdos próprios (gs.db), autor pseudonimizado; por padrão só os sem resposta."""
    return rds.comentarios(GSI_DB, dias, todos)


@app.post("/api/gs/redes/comentarios/rascunhar")
async def redes_rascunhar(ids: str = Form(""), dias: int = Form(30)):
    """Cria um pedido para o Editor rascunhar respostas (fluxo respostas-comentarios). Nada é respondido na rede."""
    sel = {x.strip() for x in ids.split(",") if x.strip()}
    todos = rds.comentarios(GSI_DB, dias, todos=True, limite=100000)["itens"]
    itens = [i for i in todos if i["id"] in sel] if sel else [i for i in todos if not i["respondido"]][:20]
    if not itens:
        raise HTTPException(400, "Nenhum comentário escolhido.")
    return await nova_conversa(pedido=rds.pedido_respostas(itens), fluxo="respostas-comentarios", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="redes")


@app.get("/api/gs/redes/resultados")
def redes_resultados(dias: int = 30):
    """Desempenho dos conteúdos próprios no período (último snapshot do GSI) e comparação com o período anterior."""
    if dias not in (7, 30, 90):
        raise HTTPException(400, "dias deve ser 7, 30 ou 90")
    return rds.resultados(GSI_DB, dias)


@app.post("/api/gs/redes/resultados/analisar")
async def redes_analisar(dias: int = Form(30)):
    """Pede ao Editor a leitura dos resultados (fluxo analise-resultados), com os números no pedido."""
    res = rds.resultados(GSI_DB, dias)
    if not res.get("itens"):
        raise HTTPException(400, "Sem conteúdo medido nesse período.")
    return await nova_conversa(pedido=rds.pedido_analise(res), fluxo="analise-resultados", estilo="padrao", arquivos=[], recebido="", referencia="", notion_page="", origem="redes")


@app.get("/api/gs/redes/relatorio-mes")
def redes_relatorio(mes: str = ""):
    """Relatório do mês em Markdown (números do GSI, sem modelo de linguagem), gravado em workspace/relatorios/."""
    mes = mes or date.today().strftime("%Y-%m")
    if not MES_RE.match(mes):
        raise HTTPException(400, "mes deve ser AAAA-MM")
    return rds.relatorio_mes(GSI_DB, mes, WORKSPACE / "relatorios")


@app.get("/api/gs/redes/relatorio-mes/arquivo")
def redes_relatorio_arquivo(mes: str):
    if not MES_RE.match(mes or ""):
        raise HTTPException(400, "mes deve ser AAAA-MM")
    p = WORKSPACE / "relatorios" / f"relatorio-{mes}.md"
    if not p.exists():
        raise HTTPException(404, "Gere o relatório primeiro.")
    return FileResponse(p, media_type="text/markdown", filename=p.name)


# --- Arquivos: armazenamento, limpeza de trabalho, uso e uploads avulsos ---------------------------

@app.get("/api/gs/armazenamento")
def armazenamento(dias: int = 30):
    return arq.armazenamento(WORKSPACE, dias)


@app.post("/api/gs/armazenamento/limpar")
def armazenamento_limpar(dias: int = Form(30)):
    """Apaga `_trabalho/` e `trabalho/` de entregas paradas há mais de `dias` (padrão 30, mínimo 7). Entregas, `_anteriores/` e entrada/ ficam."""
    if dias < 7:
        raise HTTPException(400, "Mínimo de 7 dias.")
    return arq.limpar(SAIDA, dias)


@app.get("/api/gs/uso")
async def uso():
    issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
    nomes = {}
    try:
        for a_ in await _pc("GET", f"/api/companies/{CFG['company_id']}/agents"):
            nomes[a_.get("id")] = a_.get("name")
    except Exception:  # noqa
        pass
    u = arq.uso(issues or [], agentes=nomes); u["economia"] = arq.economia(SAIDA, issues or [], _indice())
    return u


def _avulsos_dir():
    return ENTRADA / "_biblioteca"


@app.post("/api/gs/biblioteca/upload")
async def biblioteca_upload(arquivos: list[UploadFile] = File(...)):
    """Upload avulso para a biblioteca (entrada/_biblioteca/); o Editor usa pelo caminho quando o pedido citar."""
    d = _avulsos_dir(); d.mkdir(parents=True, exist_ok=True)
    nomes = await _salvar_uploads(d, arquivos)
    return {"salvos": [f"entrada/_biblioteca/{n}" for n in nomes]}


@app.get("/api/gs/biblioteca/avulsos")
def biblioteca_avulsos():
    d = _avulsos_dir()
    if not d.exists():
        return []
    return [{"nome": p.name, "caminho": f"entrada/_biblioteca/{p.name}", "tipo": _tipo(p), "tamanho_mb": round(p.stat().st_size / 1e6, 1), "modificado": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}
            for p in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True) if p.is_file()]


@app.delete("/api/gs/biblioteca/avulsos/{nome}")
def biblioteca_avulso_apagar(nome: str):
    if "/" in nome or nome.startswith("."):
        raise HTTPException(400, "Nome inválido.")
    p = _avulsos_dir() / nome
    if not p.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    p.unlink(); return {"ok": True}


# --- Laboratório (13/11/2026): recursos novos para o Raphael testar; "deu problema" vira anotação para a próxima rodada ---------------

@app.get("/api/gs/laboratorio")
def laboratorio_listar():
    return nov.listar()


@app.post("/api/gs/laboratorio/{nid}/avaliar")
def laboratorio_avaliar(nid: str, estado: str = Form(...), nota: str = Form("")):
    try:
        r = nov.avaliar(nid, estado, nota, acs.QUEM.get() or "Raphael")
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if estado == "com_problema":
        try:
            ant.criar(_anotacoes_dir(), f"[Laboratório] {r['titulo']}: {r['nota']}", [], "laboratorio")
        except ValueError:
            pass
    return r


# --- Anotações do celular e atalho com link secreto ------------------------------------------------

def _anotacoes_dir():
    return WORKSPACE / "anotacoes"


def _atalho_arq():
    return WORKSPACE / "atalho.json"


async def _anotacao_nova(texto: str, arquivos, origem: str):
    d = _anotacoes_dir(); tmpd = d / f"_tmp-{secrets.token_hex(3)}"; nomes = []
    if arquivos:
        tmpd.mkdir(parents=True, exist_ok=True); nomes = await _salvar_uploads(tmpd, arquivos)
    try:
        nota = ant.criar(d, texto, nomes, origem)
    except ValueError as e:
        shutil.rmtree(tmpd, ignore_errors=True); raise HTTPException(400, str(e))
    if nomes:
        tmpd.rename(d / nota["id"])
    return nota


@app.get("/api/gs/anotacoes")
def anotacoes_listar():
    """Anotações rápidas (texto, link, arquivo) vindas do celular ou do app. Só viram pedido com clique."""
    return ant.listar(_anotacoes_dir())


@app.post("/api/gs/anotacoes")
async def anotacoes_criar(texto: str = Form(""), arquivos: list[UploadFile] = File(default=[]), origem: str = Form("app")):
    return await _anotacao_nova(texto, arquivos, origem)


@app.delete("/api/gs/anotacoes/{nid}")
def anotacoes_apagar(nid: str):
    try:
        ant.apagar(_anotacoes_dir(), nid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "Anotação não encontrada.")
    return {"ok": True}


@app.post("/api/gs/anotacoes/{nid}/pedido")
def anotacoes_pedido(nid: str):
    """Leva a anotação (texto + arquivos) para o Novo pedido, pelo mesmo caminho do material recebido do celular. A anotação vai para "Em produção" (não some)."""
    d = _anotacoes_dir(); nota = next((n for n in ant.listar(d) if n["id"] == nid), None)
    if not nota:
        raise HTTPException(404, "Anotação não encontrada.")
    if nota.get("status", "a_fazer") != "a_fazer":
        raise HTTPException(409, "Essa anotação já virou pedido. Volte para \"A fazer\" para pedir de novo.")
    RECEBIDOS.mkdir(parents=True, exist_ok=True)
    token = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_urlsafe(4)}"; pasta = RECEBIDOS / token; pasta.mkdir()
    for nome in nota.get("arquivos", []):
        src = d / nid / nome
        if src.is_file():
            shutil.copy2(src, pasta / nome)
    (pasta / "recebido.json").write_text(json.dumps({"texto": nota.get("texto", ""), "quando": datetime.now().isoformat(timespec="seconds"), "anotacao": nid}, ensure_ascii=False), encoding="utf-8")
    ant.mudar_status(d, nid, "em_producao", pedido=f"/novo?recebido={token}")
    return {"token": token, "url": f"/novo?recebido={token}"}


@app.post("/api/gs/anotacoes/{nid}/status")
def anotacoes_status(nid: str, status: str = Form(...)):
    """Move a anotação entre A fazer, Em produção e Feita (ciclo próprio das ideias do celular; nada vai ao Notion)."""
    try:
        return ant.mudar_status(_anotacoes_dir(), nid, status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "Anotação não encontrada.")


def _atalho_dados(t: str):
    base = os.environ.get("EDITOR_GS_URL_PUBLICA", "").rstrip("/")
    return {"token": t, "base": base, "app": base or URL_PADRAO, "url": f"{base}/api/webhooks/compartilhar/{t}"}


@app.get("/api/gs/atalho")
def atalho():
    """Link secreto do celular (Atalho do iPhone / HTTP Shortcuts). Gerado uma vez; 'novo' troca o token.
    O GET devolve o link mascarado (só os 4 últimos); o inteiro sai só pelo POST /copiar, no clique de "Copiar" (11/11/2026)."""
    d = _atalho_dados(ant.token_atalho(_atalho_arq())); t = d.pop("token"); d.pop("url")
    return {**d, "final": t[-4:], "url_mascarada": f"{d['base']}/api/webhooks/compartilhar/••••{t[-4:]}", "campos": {"acao": "pedido | anotacao", "texto": "texto ou link (opcional)", "arquivos": "arquivo(s), opcional"}}


@app.post("/api/gs/atalho/copiar")
def atalho_copiar():
    return _atalho_dados(ant.token_atalho(_atalho_arq()))


@app.post("/api/gs/atalho/novo")
def atalho_novo():
    return _atalho_dados(ant.token_atalho(_atalho_arq(), novo=True))


@app.get("/api/webhooks/compartilhar/{token}")
def webhook_compartilhar_get(token: str):
    """O link do atalho aberto num navegador (GET) não é o app: manda para a Ajuda, que mostra o endereço certo e o QR."""
    if not ant.token_valido(_atalho_arq(), token):
        raise HTTPException(403, "Link do atalho inválido ou trocado. Gere um novo em Ajuda → Atalho do celular.")
    return RedirectResponse("/ajuda?de=atalho", status_code=302)


@app.post("/api/webhooks/compartilhar/{token}")
async def webhook_compartilhar(token: str, acao: str = Form("pedido"), texto: str = Form(""), text: str = Form(""), title: str = Form(""), url: str = Form(""), arquivos: list[UploadFile] = File(default=[])):
    """Alvo do atalho do celular. `acao=pedido` guarda o material e devolve a URL do Novo pedido; `acao=anotacao` só anota (texto, link, arquivo)."""
    if not ant.token_valido(_atalho_arq(), token):
        raise HTTPException(403, "Link do atalho inválido ou trocado. Gere um novo em Ajuda → Atalho do celular.")
    t = "\n".join(x for x in (title, texto or text, url) if x and x.strip())
    if acao == "anotacao":
        nota = await _anotacao_nova(t, arquivos, "celular")
        return {**nota, "acao": "anotacao", "mensagem": "Anotado. Aparece em Ideias → Anotações do celular."}
    rec = await _receber(t, arquivos)
    return {**rec, "acao": "pedido", "url": f"/novo?recebido={rec['token']}", "mensagem": "Material recebido. Abra o app para escrever o pedido."}


# ---- Textos (entregas em texto: ficam na mensagem final do Editor, não em .md) ----
def _msgs_de(coments):
    itens = coments if isinstance(coments, list) else coments.get("comments", coments.get("items", []))
    return [{"id": m.get("id"), "autor": "editor" if m.get("authorAgentId") else "voce", "texto": m.get("body") or "", "quando": m.get("createdAt")}
            for m in sorted(itens, key=lambda m: m.get("createdAt", ""))]


def _textos_cache_atualizar(issue, c, ent):
    d = txt.cache_ler(TEXTOS_CACHE); novo = txt.cache_item(c, issue.get("updatedAt"), ent)
    if d.get(c["id"]) != novo:
        d[c["id"]] = novo; txt.cache_gravar(TEXTOS_CACHE, d)


async def _textos_todos():
    """Cache das entregas em texto de todas as conversas; só busca comentários das que mudaram desde a última leitura."""
    issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues")
    issues = issues if isinstance(issues, list) else issues.get("issues", [])
    idx = _indice(); d = txt.cache_ler(TEXTOS_CACHE); mudou = False; vivos = set()
    for it in issues:
        if it.get("identifier") in CFG.get("ocultar_issues", []):
            continue
        c = _conversa(it, idx); vivos.add(c["id"]); ant_ = d.get(c["id"])
        if ant_ and ant_.get("atualizado") == it.get("updatedAt"):
            if ant_.get("pasta") != c.get("pasta") or ant_.get("status") != c.get("status"):
                ant_["pasta"] = c.get("pasta"); ant_["status"] = c.get("status"); mudou = True
            continue
        try:
            msgs = _msgs_de(await _pc("GET", f"/api/issues/{c['id']}/comments"))
        except HTTPException:
            continue
        d[c["id"]] = txt.cache_item(c, it.get("updatedAt"), txt.entrega_de_mensagens(msgs)); mudou = True
    for k in [k for k in d if k not in vivos]:
        d.pop(k); mudou = True
    if mudou:
        txt.cache_gravar(TEXTOS_CACHE, d)
    return list(d.values())


@app.get("/api/gs/textos")
async def textos_lista(q: str = "", tipo: str = "", pasta: str = ""):
    """Roteiros, legendas, análises, respostas e transcrições entregues nas conversas (seções `## ` da mensagem final do Editor)."""
    itens = txt.filtrar(await _textos_todos(), q, tipo, pasta)
    salvos = {(g.get("codigo"), g.get("chave")) for g in txt.guardados(TEXTOS_DIR)} if TEXTOS_DIR.exists() else set()
    for it in itens:
        it["guardadas"] = [s["chave"] for s in it["secoes"] if (it.get("codigo"), s["chave"]) in salvos] + (["tudo"] if (it.get("codigo"), "tudo") in salvos else [])
    return {"itens": itens, "tipos": [{"chave": k, "rotulo": txt.ROTULOS[k]} for k in txt.TIPOS_TEXTO]}


@app.post("/api/gs/conversas/{cid}/textos/guardar")
async def textos_guardar(cid: str, chave: str = Form(""), titulo: str = Form(""), mensagem: str = Form(""), secao: str = Form("")):
    """Guarda uma seção da entrega em texto como referência: .md em referencias/_textos/ (o Editor lê o INDICE.md). Só por pedido, pelo app.
    Sem `mensagem`: seção `chave` da entrega mais recente. Com `mensagem` (id do comentário): seção dessa mensagem antiga, por `chave` ou pelo título `secao`."""
    if mensagem:
        issue = await _pc("GET", f"/api/issues/{cid}"); c = _conversa(issue, _indice())
        coments = await _pc("GET", f"/api/issues/{cid}/comments")
        itens = coments if isinstance(coments, list) else coments.get("comments", coments.get("items", []))
        m = next((x for x in itens if str(x.get("id")) == mensagem and x.get("authorAgentId")), None)
        if not m:
            raise HTTPException(404, "Mensagem do Editor não encontrada nesta conversa.")
        secs = txt.secoes_de(m.get("body") or "")
        if not chave and secao:
            chave = next((x["chave"] for x in secs if txt._norm(x["titulo"]) == txt._norm(secao)), "")
        if not secs or not chave:
            raise HTTPException(404, "Essa mensagem não tem a seção pedida.")
        item = txt.cache_item(c, issue.get("updatedAt"), {"id": m.get("id"), "quando": m.get("createdAt"), "secoes": secs})
        try:
            return txt.guardar(TEXTOS_DIR, item, chave, titulo)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not chave:
        raise HTTPException(400, "Informe a chave da seção.")
    item = txt.cache_ler(TEXTOS_CACHE).get(cid)
    if not item or not item.get("secoes"):
        await conversa(cid)  # atualiza o cache a partir da conversa
        item = txt.cache_ler(TEXTOS_CACHE).get(cid)
    if not item or not item.get("secoes"):
        raise HTTPException(404, "Esta conversa não tem entrega em texto (seções ## na mensagem do Editor).")
    try:
        return txt.guardar(TEXTOS_DIR, item, chave, titulo)
    except ValueError as e:
        raise HTTPException(400, str(e))


def _notion_get(pid: str):
    tok, cfg = _notion_token()
    if not tok:
        raise HTTPException(503, "NOTION_TOKEN não encontrado no .env do GSI")
    req = urllib.request.Request(f"https://api.notion.com/v1/pages/{pid}", headers={"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"]})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"Notion {e.code}: {e.read()[:200].decode(errors='ignore')}")
    except Exception as e:
        raise HTTPException(502, f"Notion: {e}")


def _notion_cartoes(q: str, limite: int = 20):
    """Cartões da base INSTA pelo título (leitura) para o Raphael escolher o destino de um texto."""
    tok, cfg = _notion_token()
    if not tok:
        raise HTTPException(503, "NOTION_TOKEN não encontrado no .env do GSI")
    body = {"page_size": min(100, max(1, limite)), **({"filter": {"property": "Name", "title": {"contains": q.strip()}}} if q.strip() else {}),
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}]}
    req = urllib.request.Request(f"https://api.notion.com/v1/data_sources/{cfg['ds']}/query", method="POST", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + tok, "Notion-Version": cfg["versao"], "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        raise HTTPException(502, f"Notion: {e}")
    out = []
    for pg in r.get("results", []):
        pr = pg.get("properties", {}); titulo = _notion_val(pr, "Name") or ""
        if titulo.strip().lower() in MOLDES:
            continue
        out.append({"id": pg["id"].replace("-", ""), "titulo": titulo, "status": _notion_val(pr, "Status"), "formato": _notion_val(pr, "Formato") or [], "url": pg.get("url")})
    return out[:limite]


def _rich_text(texto: str):
    """Texto longo em itens de até 1900 caracteres (limite do Notion é 2000 por item)."""
    t = texto or ""; partes = [t[i:i + 1900] for i in range(0, len(t), 1900)] or [""]
    return [{"type": "text", "text": {"content": x}} for x in partes[:100]]


async def _secoes_da_conversa(cid: str, chave: str, mensagem: str, secao: str):
    """(item, seções escolhidas) da entrega mais recente (chave) ou de uma mensagem antiga (mensagem + chave|secao). Mesma regra do guardar."""
    if mensagem:
        issue = await _pc("GET", f"/api/issues/{cid}"); c = _conversa(issue, _indice())
        coments = await _pc("GET", f"/api/issues/{cid}/comments")
        itens = coments if isinstance(coments, list) else coments.get("comments", coments.get("items", []))
        m = next((x for x in itens if str(x.get("id")) == mensagem and x.get("authorAgentId")), None)
        if not m:
            raise HTTPException(404, "Mensagem do Editor não encontrada nesta conversa.")
        secs = txt.secoes_de(m.get("body") or "")
        if not chave and secao:
            chave = next((x["chave"] for x in secs if txt._norm(x["titulo"]) == txt._norm(secao)), "")
        item = txt.cache_item(c, issue.get("updatedAt"), {"id": m.get("id"), "quando": m.get("createdAt"), "secoes": secs})
    else:
        item = txt.cache_ler(TEXTOS_CACHE).get(cid)
        if not item or not item.get("secoes"):
            await conversa(cid); item = txt.cache_ler(TEXTOS_CACHE).get(cid)
        if not item or not item.get("secoes"):
            raise HTTPException(404, "Esta conversa não tem entrega em texto (seções ## na mensagem do Editor).")
        secs = item["secoes"]
        if not chave and secao:
            chave = next((x["chave"] for x in secs if txt._norm(x["titulo"]) == txt._norm(secao)), "")
    if not chave:
        raise HTTPException(400, "Informe a chave ou o título da seção.")
    esc = [x for x in secs if x["chave"] == chave] if chave != "tudo" else [x for x in secs if x["chave"].split("-")[0] in txt.TIPOS_TEXTO] or secs
    if not esc:
        raise HTTPException(404, "Essa mensagem não tem a seção pedida.")
    return item, esc


@app.get("/api/gs/notion/cartoes")
def notion_cartoes(q: str = ""):
    return _notion_cartoes(q)


@app.post("/api/gs/conversas/{cid}/textos/notion")
async def textos_notion(cid: str, chave: str = Form(""), mensagem: str = Form(""), secao: str = Form(""), pagina: str = Form(""), modo: str = Form("acrescentar")):
    """Envia uma seção da entrega para o campo "Roteiro do pulso" de um cartão EXISTENTE do Notion (base INSTA). Só por clique do Raphael no app
    (NOTION_WRITE_MODE = HUMAN_ONLY), nunca cria página nem bloco (o workspace está sem blocos livres). `modo` acrescentar (padrão) ou substituir."""
    if not NOTION_ESCRITA:
        raise HTTPException(409, "O Editor GS não escreve no Notion (decisão do Raphael, 31/10/2026). Copie o texto e cole no cartão, ou deixe o pulso cuidar.")
    item, esc = await _secoes_da_conversa(cid, chave, mensagem, secao)
    pid = re.sub(r"[^0-9a-f]", "", (pagina or "").lower()) or (_indice().get(cid, {}).get("notion_page") or "")
    if not pid:
        raise HTTPException(400, "Escolha o cartão do Notion de destino (este pedido não veio de um cartão).")
    if modo not in ("acrescentar", "substituir"):
        raise HTTPException(400, "modo deve ser acrescentar ou substituir.")
    pg = _notion_get(pid); props = pg.get("properties", {})
    if "Roteiro do pulso" not in props:
        raise HTTPException(400, "Esse cartão não tem o campo \"Roteiro do pulso\" (é da base INSTA?).")
    atual = _notion_val(props, "Roteiro do pulso") or ""
    rot = txt.ROTULOS.get(esc[0]["chave"].split("-")[0], esc[0]["titulo"]) if len(esc) == 1 else "Textos da entrega"
    corpo = "\n\n".join((f"{x['titulo']}\n{x['conteudo']}" if len(esc) > 1 else x["conteudo"]) for x in esc)
    bloco = f"[Editor GS {item.get('codigo') or ''} · {rot} · {datetime.now():%d/%m/%Y %H:%M}]\n{corpo}".strip()
    novo = bloco if (modo == "substituir" or not atual.strip()) else f"{atual.rstrip()}\n\n{bloco}"
    _notion_patch(pid, {"Roteiro do pulso": {"rich_text": _rich_text(novo)}})
    return {"ok": True, "pagina": pid, "url": pg.get("url"), "titulo": _notion_val(props, "Name"), "campo": "Roteiro do pulso", "modo": modo, "chars": len(novo), "secoes": [x["chave"] for x in esc]}


@app.get("/api/gs/textos/guardados")
def textos_guardados():
    return txt.guardados(TEXTOS_DIR) if TEXTOS_DIR.exists() else []


@app.delete("/api/gs/textos/guardados/{nome}")
def textos_apagar(nome: str):
    try:
        txt.apagar(TEXTOS_DIR, nome)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Não encontrado.")
    return {"ok": True}


@app.get("/api/gs/qr")
def qr(texto: str = ""):
    """QR code em SVG (segno, sem rede) para abrir o app no celular."""
    import segno
    t = (texto or "").strip()[:500] or URL_PADRAO
    svg = segno.make(t, error="m").svg_inline(scale=6, dark="#000921", light="#ffffff", border=2)
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


TAILSCALE_EXE = Path("/mnt/c/Program Files/Tailscale/tailscale.exe")  # o Tailscale roda no Windows; o WSL só consulta


@app.get("/api/gs/celular")
def celular():
    """Estado do Tailscale visto do notebook: o app está sendo servido (tailscale serve) e quais aparelhos da conta estão conectados.
    Só leitura; sem o executável do Windows devolve disponivel=false."""
    import subprocess
    if not TAILSCALE_EXE.exists():
        return {"disponivel": False, "aparelhos": [], "serve": None, "erro": "tailscale.exe não encontrado"}
    try:
        st = json.loads(subprocess.run([str(TAILSCALE_EXE), "status", "--json"], capture_output=True, text=True, timeout=8).stdout or "{}")
        sv = subprocess.run([str(TAILSCALE_EXE), "serve", "status"], capture_output=True, text=True, timeout=8).stdout or ""
    except Exception as e:
        return {"disponivel": False, "aparelhos": [], "serve": None, "erro": str(e)[:120]}
    aparelhos = []
    for p in list((st.get("Peer") or {}).values()) + ([st["Self"]] if st.get("Self") else []):
        aparelhos.append({"nome": p.get("HostName"), "online": bool(p.get("Online")), "visto": p.get("LastSeen"), "os": (p.get("OS") or "").lower()})
    m = re.search(r"(https://\S+)", sv)
    return {"disponivel": True, "aparelhos": aparelhos, "serve": m.group(1) if m and "3200" in sv else None}


@app.get("/api/gs/licenca")
def licenca_ver():
    return _licenca_situacao()


@app.post("/api/gs/licenca")
def licenca_ativar(chave: str = Form(...)):
    r = lic.ativar(cam.ESTADO, chave, revogadas=(CFG.get("licenca") or {}).get("revogadas"))
    if not r["ok"]:
        raise HTTPException(400, f"Chave recusada: {r['motivo']}")
    return _licenca_situacao()


@app.middleware("http")
async def _exigir_licenca(request: Request, call_next):
    """Modo plugin sem chave válida: a API do app responde 402 com o motivo (o app mostra; /estado continua para a tela explicar)."""
    if LICENCA_EXIGIDA and request.url.path.startswith("/api/gs/") and not request.url.path.startswith(LICENCA_LIVRE):
        st = _licenca_situacao()
        if not st["ok"]:
            return JSONResponse({"detail": f"Editor GS sem chave válida: {st['motivo']}"}, status_code=402)
    return await call_next(request)


@app.get("/api/gs/versao")
def versao():
    """Build do app em app/dist/versao.json (o PWA compara com o seu e oferece Atualizar) e hora em que o gateway subiu."""
    try:
        return {**json.loads((DIST / "versao.json").read_text(encoding="utf-8")), "gateway_desde": INICIO}
    except Exception:
        return {"build": None, "gateway_desde": INICIO}


@app.middleware("http")
async def _porta_de_entrada(request: Request, call_next):
    """Acesso de fora da máquina (Tailscale/Funnel) exige a chave (cookie gs_acesso); localhost passa direto. Ver servico/acesso.py."""
    quem = ""
    if acs.ativo() and not acs.local(request.headers.get("host", "")):
        quem = acs.quem_da_chave(request.cookies.get(acs.COOKIE))
        if not quem:
            caminho = request.url.path
            if acs.exige_chave(caminho):
                return JSONResponse({"erro": "Sem acesso. Abra o link de entrada que o Raphael mandou."}, status_code=401)
            if request.method == "GET" and "text/html" in request.headers.get("accept", "") and not acs.livre(caminho):
                return RedirectResponse("/entrar", status_code=302)  # navegação (não é arquivo do app) vai para a entrada
    tok = acs.QUEM.set(quem)
    try:
        return await call_next(request)
    finally:
        acs.QUEM.reset(tok)


@app.get("/entrar")
def entrar(request: Request, chave: str = ""):
    """Link de entrada: /entrar?chave=... grava o cookie (1 ano) e abre o app; sem chave mostra o campo; chave errada avisa."""
    if not chave:
        return HTMLResponse(acs.pagina())
    quem = acs.quem_da_chave(chave)
    if not quem:
        log.warning("entrar: chave inválida de %s", request.client.host if request.client else "?")
        return HTMLResponse(acs.pagina("Chave não reconhecida. Confira com o Raphael."), status_code=403)
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"
    r = RedirectResponse("/", status_code=302)
    r.set_cookie(acs.COOKIE, chave.strip(), max_age=acs.DIAS_COOKIE * 86400, httponly=True, secure=https, samesite="lax", path="/")
    log.info("entrar: %s entrou", quem)
    return r


@app.get("/entrar/sair")
def entrar_sair():
    r = RedirectResponse("/entrar", status_code=302); r.delete_cookie(acs.COOKIE, path="/"); return r


@app.get("/api/gs/quem")
def quem_entrou():
    """Quem está usando (pela chave) e se o acesso por chave está ligado. Localhost devolve quem vazio."""
    return {"quem": acs.QUEM.get(), "acesso_por_chave": acs.ativo()}


@app.middleware("http")
async def _sem_cache_do_app(request: Request, call_next):
    """index.html, service worker e manifesto nunca ficam presos no cache do navegador do celular (os assets com hash podem)."""
    resp = await call_next(request)
    if request.method == "GET" and (request.url.path in ("/", "/index.html", "/sw.js", "/registerSW.js", "/manifest.webmanifest", "/versao.json")
                                    or resp.headers.get("content-type", "").startswith("text/html")):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


# ---- Anexos do Google Drive (06/11/2026): navegar e escolher; só leitura no Drive ----
DRIVE_TAREFAS: dict = {}


@app.get("/api/gs/drive/raizes")
async def drive_raizes():
    return {"raizes": [{"id": r["id"], "rotulo": r["rotulo"]} for r in await asyncio.to_thread(dra.raizes, pub.RCLONE)]}


@app.get("/api/gs/drive/listar")
async def drive_listar(raiz: str = "0", caminho: str = ""):
    try:
        return await asyncio.to_thread(dra.listar, pub.RCLONE, raiz, caminho)
    except dra.ErroDrive as e:
        raise HTTPException(400, str(e))
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "O Drive demorou para responder. Tente de novo.")


def _drive_iniciar(cid: str, sel: list, pasta: Path, nomes: list, depois: dict):
    """Marca o download no índice e roda em segundo plano; quando termina, libera o pedido (backlog → todo) ou posta a mensagem."""
    _indice_atualizar(cid, drive={"estado": "baixando", "nomes": nomes, "quando": datetime.now().isoformat(timespec="seconds")})
    DRIVE_TAREFAS[cid] = asyncio.create_task(_drive_baixar(cid, sel, pasta, nomes, depois))


async def _drive_baixar(cid: str, sel: list, pasta: Path, nomes: list, depois: dict):
    try:
        for it, n in zip(sel, nomes):
            await asyncio.to_thread(dra.baixar, pub.RCLONE, it, pasta / n)
        rel = [f"entrada/{pasta.name}/{n}" for n in nomes]
        if depois.get("tipo") == "mensagem":
            corpo = depois.get("corpo") or ""
            corpo = (corpo + "\n\n" if corpo else "") + "Arquivos anexados agora (do Google Drive): " + ", ".join(f"`{x}`" for x in rel) + ". Use-os neste pedido (são a entrada nova desta mensagem)."
            await _pc("POST", f"/api/issues/{cid}/comments", json={"body": corpo})
            if depois.get("reabrir"):
                await _pc("PATCH", f"/api/issues/{cid}", json={"status": "todo", "assigneeAgentId": depois.get("agente")})
        else:
            await _pc("PATCH", f"/api/issues/{cid}", json={"status": "todo"})
        _indice_atualizar(cid, drive={"estado": "pronto", "nomes": nomes, "quando": datetime.now().isoformat(timespec="seconds")})
    except Exception as e:  # noqa: BLE001
        msg = str(e) if isinstance(e, dra.ErroDrive) else f"{type(e).__name__}: {e}"
        log.warning("drive %s: %s", cid, msg)
        _indice_atualizar(cid, drive={"estado": "erro", "nomes": nomes, "erro": msg[:300], "quando": datetime.now().isoformat(timespec="seconds")})
        try:
            await _pc("POST", f"/api/issues/{cid}/comments", json={"body": f"⚠ Não consegui baixar do Google Drive: {msg[:300]}. Anexe de novo pelo 📎."})
        except Exception:  # noqa: BLE001
            pass
    finally:
        DRIVE_TAREFAS.pop(cid, None)


# ---- Menu ⋯ da conversa (06/11/2026, como no Máquina): mover para pasta, marcar como concluída, excluir (vai para a Lixeira) ----
async def _cancelar_run(issue: dict) -> bool:
    run = issue.get("activeRun"); run_id = run.get("id") if isinstance(run, dict) else (run or None)
    if not run_id:
        return False
    try:
        await _pc("POST", f"/api/heartbeat-runs/{run_id}/cancel", json={}); return True
    except HTTPException as e:
        log.warning("cancel do run %s falhou (%s)", run_id, e.detail); return False


def _cid_ok(cid: str):
    if not re.match(r"^[0-9a-zA-Z\-]{2,64}$", cid or ""):
        raise HTTPException(400, "id inválido")


@app.post("/api/gs/conversas/{cid}/concluir")
async def concluir(cid: str):
    """Marca como concluída sem aprovar a entrega (não registra aprovação nem mexe no Notion). Para o agente se estiver editando."""
    _cid_ok(cid); issue = await _pc("GET", f"/api/issues/{cid}")
    if issue.get("status") == "cancelled":
        raise HTTPException(409, "Conversa na Lixeira: restaure antes.")
    parado = await _cancelar_run(issue)
    if issue.get("status") != "done":
        await _pc("PATCH", f"/api/issues/{cid}", json={"status": "done", "comment": "✔ Marcado como concluído no app."})
    _indice_atualizar(cid, concluida_em=datetime.now().isoformat(timespec="seconds"))
    return {"ok": True, "status": "done", "run_cancelada": parado}


@app.post("/api/gs/conversas/{cid}/excluir")
async def excluir(cid: str):
    """Excluir conversa: some da lista e vai para a Lixeira (issue cancelada no Paperclip). Arquivos em entrada/ e saida/ ficam; Restaurar traz de volta."""
    _cid_ok(cid); issue = await _pc("GET", f"/api/issues/{cid}")
    if issue.get("status") == "cancelled" and (_indice().get(cid) or {}).get("excluida"):
        return {"ok": True, "status": "cancelled"}
    parado = await _cancelar_run(issue)
    _indice_atualizar(cid, excluida=datetime.now().isoformat(timespec="seconds"), status_antes=issue.get("status"))
    if issue.get("status") != "cancelled":
        await _pc("PATCH", f"/api/issues/{cid}", json={"status": "cancelled", "comment": "🗑 Conversa excluída no app (está na Lixeira; os arquivos continuam)."})
    return {"ok": True, "status": "cancelled", "run_cancelada": parado}


@app.post("/api/gs/conversas/{cid}/restaurar")
async def restaurar(cid: str):
    """Tira da Lixeira. Volta ao status de antes se era concluída/entregue/pausada; se estava na fila ou editando, volta pausada (▶ Retomar continua)."""
    _cid_ok(cid); idx = _indice(); meta = idx.get(cid) or {}
    antes = meta.get("status_antes")
    novo = antes if antes in ("done", "in_review", "blocked") else "blocked"
    await _pc("PATCH", f"/api/issues/{cid}", json={"status": novo, "comment": "♻ Conversa restaurada da Lixeira no app."})
    meta.pop("excluida", None); meta.pop("status_antes", None); idx[cid] = meta; _salvar_indice(idx)
    return {"ok": True, "status": novo}


@app.get("/api/gs/lixeira")
async def lixeira():
    issues = await _pc("GET", f"/api/companies/{CFG['company_id']}/issues"); idx = _indice()
    out = [_conversa(i, idx) for i in issues if i.get("status") == "cancelled" and i.get("identifier") not in CFG.get("ocultar_issues", [])]
    return sorted(out, key=lambda c: (c.get("excluida") or c["atualizado"] or ""), reverse=True)


# ---- Pastas (projetos) ----
@app.get("/api/gs/pastas")
def pastas():
    """Pastas existentes com o número de pedidos em cada uma (pelo índice) e quantos pedidos estão sem pasta."""
    idx = _indice(); cont = {}
    for m in idx.values():
        if m.get("pasta"):
            cont[m["pasta"]] = cont.get(m["pasta"], 0) + 1
    lista = _pastas(); nomes = {p["nome"] for p in lista}
    out = [{"nome": p["nome"], "criada": p.get("criada"), "n": cont.get(p["nome"], 0)} for p in lista]
    out += [{"nome": n, "criada": None, "n": c} for n, c in cont.items() if n not in nomes]
    out.sort(key=lambda p: (-p["n"], p["nome"].lower()))
    return {"pastas": out, "sem_pasta": sum(1 for m in idx.values() if not m.get("pasta"))}


@app.post("/api/gs/pastas")
def nova_pasta(nome: str = Form("")):
    n = _pasta_nome(nome)
    if not n:
        raise HTTPException(400, "Dê um nome à pasta.")
    if any(p["nome"].lower() == n.lower() for p in _pastas()):
        raise HTTPException(409, "Já existe uma pasta com esse nome.")
    return {"nome": _garantir_pasta(n)}


@app.post("/api/gs/pastas/{nome}/renomear")
def renomear_pasta(nome: str, novo: str = Form("")):
    n = _pasta_nome(novo)
    if not n:
        raise HTTPException(400, "Dê um nome à pasta.")
    lista = _pastas(); alvo = next((p for p in lista if p["nome"] == nome), None)
    if not alvo:
        raise HTTPException(404, "Pasta não encontrada.")
    if n.lower() != nome.lower() and any(p["nome"].lower() == n.lower() for p in lista):
        raise HTTPException(409, "Já existe uma pasta com esse nome.")
    alvo["nome"] = n; _salvar_pastas(lista)
    idx = _indice(); k = 0
    for m in idx.values():
        if m.get("pasta") == nome:
            m["pasta"] = n; k += 1
    _salvar_indice(idx)
    return {"nome": n, "movidas": k}


@app.delete("/api/gs/pastas/{nome}")
def apagar_pasta(nome: str):
    """Apaga só a pasta: os pedidos dela ficam sem pasta (nada é apagado no Paperclip nem em saida/)."""
    lista = _pastas()
    if not any(p["nome"] == nome for p in lista):
        raise HTTPException(404, "Pasta não encontrada.")
    _salvar_pastas([p for p in lista if p["nome"] != nome])
    idx = _indice(); k = 0
    for m in idx.values():
        if m.get("pasta") == nome:
            m.pop("pasta", None); k += 1
    _salvar_indice(idx)
    return {"apagada": nome, "liberadas": k}


@app.post("/api/gs/conversas/{cid}/pasta")
def mover_para_pasta(cid: str, pasta: str = Form("")):
    """Põe o pedido numa pasta (cria se não existir) ou tira dela com pasta vazia."""
    if not re.match(r"^[0-9a-zA-Z\-]{2,64}$", cid):
        raise HTTPException(400, "id inválido")
    idx = _indice(); meta = idx.setdefault(cid, {}); n = _pasta_nome(pasta)
    if n:
        meta["pasta"] = _garantir_pasta(n)
    else:
        meta.pop("pasta", None)
    _salvar_indice(idx)
    return {"id": cid, "pasta": meta.get("pasta")}


# ---- Fichas de marca ----
MARCA_DIR = WORKSPACE / "marca"


@app.get("/api/gs/marca")
def marca(gravar: bool = False):
    """Fichas de marca (manual, tom de voz, produtos e ofertas) lidas do GSI, só leitura. gravar=1 também escreve a cópia em workspace/marca/ para o Editor."""
    return mrc.gravar(GSI_RAIZ, GSI_DB, MARCA_DIR) if gravar else mrc.ficha(GSI_RAIZ, GSI_DB)


# Voz clonada (página Voz): ouvir referências e amostras no app, decidir referência/aprovação/uso padrão e gerar amostra nova (servico/voz.py).
VOZ_DIR = WORKSPACE / "voz"


@app.get("/api/gs/voz")
def voz_listar():
    vozes = vz.listar(VOZ_DIR)
    return {"disponivel": any(v["disponivel"] for v in vozes) if vozes else vz.disponivel(), "motores": vz.motores(), "vozes": vozes, "geracao": vz.estado(), "texto_padrao": vz.TEXTO_PADRAO}


# leve, para a tela Início (só precisa saber se a voz existe e se é padrão): sem medir áudio (11/11/2026)
@app.get("/api/gs/voz/resumo")
def voz_resumo():
    vozes = vz.resumo(VOZ_DIR)
    return {"disponivel": any(v["disponivel"] for v in vozes) if vozes else vz.disponivel(), "vozes": vozes}


@app.get("/api/gs/voz/geracao")
def voz_geracao():
    return vz.estado()


@app.post("/api/gs/voz/{nome}/decisao")
def voz_decidir(nome: str, referencia: str = Form(""), exagero: str = Form(""), cfg: str = Form(""), temperatura: str = Form(""), aprovada: str = Form(""), padrao_locucao: str = Form(""), nota: str = Form(None),
                motor: str = Form(""), qwen_temperatura: str = Form(""), qwen_top_p: str = Form(""), qwen_repeticao: str = Form("")):
    """Decisão humana sobre a voz clonada: motor (qwen | chatterbox), referência padrão, exagero/cfg (Chatterbox), parâmetros do Qwen, aprovada (sim/nao), uso por padrão na locução (sim/nao), nota. Só grava o que foi enviado."""
    def b(v):
        return None if v == "" else v.lower() in ("1", "true", "sim")
    def f(v):
        return None if v == "" else float(v)
    try:
        q = {"temperatura": f(qwen_temperatura), "top_p": f(qwen_top_p), "repeticao": f(qwen_repeticao)}
        q = {k: v for k, v in q.items() if v is not None} or None
        return vz.decidir(nome, referencia=referencia or None, exagero=f(exagero), cfg=f(cfg), temperatura=f(temperatura), aprovada=b(aprovada), padrao_locucao=b(padrao_locucao), nota=nota, voz_dir=VOZ_DIR,
                          motor=(motor or None), qwen=q)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/gs/voz/{nome}/amostra")
def voz_amostra(nome: str, texto: str = Form(""), referencia: str = Form(""), exagero: str = Form(""), cfg: str = Form(""), motor: str = Form(""), ref_text: str = Form(""), semente: str = Form(""),
                qwen_temperatura: str = Form(""), qwen_top_p: str = Form(""), qwen_repeticao: str = Form(""), idioma: str = Form("pt")):
    """Gera uma amostra nova com a referência escolhida no motor pedido (ou o do voz.json). Qwen: ~2 min de carga + ~11 s por segundo de fala; Chatterbox: ~40 s + ~3 s/s. Uma por vez."""
    try:
        q = {k: float(v) for k, v in (("temperatura", qwen_temperatura), ("top_p", qwen_top_p), ("repeticao", qwen_repeticao)) if v}
        return vz.gerar_amostra(nome, texto or vz.TEXTO_PADRAO, referencia=referencia or None, exagero=float(exagero) if exagero else None, cfg=float(cfg) if cfg else None, voz_dir=VOZ_DIR,
                                motor=(motor or None), ref_text=(ref_text or None), semente=(int(semente) if semente.strip() else None), qwen=(q or None), idioma=(idioma or "pt")[:2])
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.delete("/api/gs/voz/{nome}/amostras/{arquivo}")
def voz_apagar_amostra(nome: str, arquivo: str):
    try:
        return vz.apagar_amostra(nome, arquivo, voz_dir=VOZ_DIR)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


try:  # cópia para o Editor refeita a cada subida do gateway (falha silenciosa: o GSI pode não estar montado)
    mrc.gravar(GSI_RAIZ, GSI_DB, MARCA_DIR)
except Exception:
    pass


if SAIDA.exists():
    app.mount("/arquivos", StaticFiles(directory=str(SAIDA)), name="arquivos")
if EXECUTOR is not None:
    app.include_router(exl.rotas(EXECUTOR))  # /api/health, /api/issues/..., /api/heartbeat-runs/...: o agente usa por curl (PAPERCLIP_API_URL = este gateway)
REFERENCIAS.mkdir(parents=True, exist_ok=True)
app.mount("/referencias", StaticFiles(directory=str(REFERENCIAS)), name="referencias")
VOZ_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/voz-arquivos", StaticFiles(directory=str(VOZ_DIR)), name="voz")  # áudios da voz clonada (a rota /voz é a página do app)
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="app")


@app.exception_handler(404)
async def _spa_fallback(request, exc):
    """Rota do app (/novo, /c/<id>, /ideias…) aberta direto, sem service worker: devolve o index.html do PWA.
    Caminhos de API, de arquivos ou com extensão continuam 404."""
    caminho = request.url.path
    if request.method == "GET" and DIST.exists() and not caminho.startswith(("/api/", "/arquivos/", "/editor-midia/")) and "." not in caminho.rsplit("/", 1)[-1]:
        return FileResponse(DIST / "index.html", media_type="text/html")
    return JSONResponse({"detail": getattr(exc, "detail", "Não encontrado")}, status_code=404)
