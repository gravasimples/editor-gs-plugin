"""Entregas em texto (roteiro, legenda do post, análise, transcrição, resumo) ficam na MENSAGEM final do Editor na conversa,
em seções `## `, não em .md na pasta. Este módulo separa essas seções, mantém um cache por conversa (servico/textos.json)
para a página Textos e a busca, e guarda como referência (.md em referencias/_textos/) só o que o Raphael pedir."""
import json, re, unicodedata
from datetime import datetime
from pathlib import Path

ROTULOS = {"resumo": "Resumo", "roteiro": "Roteiro", "descricao": "Legenda do post", "hashtags": "Hashtags", "titulo": "Título (YouTube)",
           "gancho": "Gancho", "analise": "Análise", "respostas": "Respostas", "transcricao": "Transcrição", "pendencias": "Pendências",
           "arquivos": "Arquivos", "gravar": "Para gravar", "tela": "O que mostrar na tela", "cta": "CTA", "cortes": "Cortes", "plano": "Plano", "mensagem": "Mensagem", "takes": "Takes que melhorariam"}
# o que vale como "texto para ler" na página Textos (o resto fica só na conversa)
TIPOS_TEXTO = ["roteiro", "descricao", "analise", "respostas", "transcricao", "resumo"]
NOME_ARQ = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9\-]{1,80}\.md$")


def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower()); return "".join(c for c in t if not unicodedata.combining(c)).strip()


def chave_de(titulo):
    n = _norm(titulo)
    if "resumo" in n or "o que foi feito" in n or "o que fiz" in n: return "resumo"
    if "roteiro" in n: return "roteiro"
    if "hashtag" in n: return "hashtags"
    if "titulo" in n: return "titulo"
    if "gancho" in n: return "gancho"
    if "descri" in n or "legenda do post" in n or n in ("legenda", "copy", "texto do post"): return "descricao"
    if "analise" in n: return "analise"
    if "resposta" in n: return "respostas"
    if "transcri" in n: return "transcricao"
    if "pendencia" in n or "conferir" in n or "duvida" in n: return "pendencias"
    if "arquivo" in n or "baixar" in n or "entregue" in n: return "arquivos"
    if "take" in n: return "takes"
    if "gravar" in n: return "gravar"
    if "tela" in n: return "tela"
    if n.startswith("cta") or "chamada" in n: return "cta"
    if "corte" in n: return "cortes"
    if "plano" in n: return "plano"
    s = re.sub(r"[^a-z0-9]+", "-", n).strip("-")[:30]
    return s or "secao"


def secoes_de(texto):
    """Separa um Markdown por `## `. O texto antes do primeiro título vira a seção `mensagem` (se não estiver vazio).
    Devolve [{chave, titulo, conteudo}] na ordem; títulos repetidos ganham sufixo na chave."""
    if not texto or not re.search(r"(?m)^##\s+\S", texto):
        return []
    out, atual, buf = [], None, []
    def fechar():
        if atual is None:
            t = "\n".join(buf).strip()
            if t: out.append({"chave": "mensagem", "titulo": "Mensagem", "conteudo": t})
        else:
            out.append({"chave": chave_de(atual), "titulo": atual.strip(), "conteudo": "\n".join(buf).strip()})
    for linha in texto.splitlines():
        m = re.match(r"^##\s+(.+?)\s*#*\s*$", linha)
        if m and not linha.startswith("###"):
            fechar(); atual, buf = m.group(1), []
        else:
            buf.append(linha)
    fechar()
    vistos = {}
    for s in out:
        k = s["chave"]; vistos[k] = vistos.get(k, 0) + 1
        if vistos[k] > 1: s["chave"] = f"{k}-{vistos[k]}"
    return [s for s in out if s["conteudo"]]


def post_de(secoes):
    """O que o Publicar precisa (descrição, hashtags, título, gancho) a partir das seções da mensagem."""
    d = {s["chave"]: s["conteudo"] for s in secoes if s["chave"] in ("descricao", "hashtags", "titulo", "gancho")}
    return d or None


def entrega_de_mensagens(msgs):
    """A última mensagem do Editor que tem seções `## ` é a entrega em texto. None se não houver."""
    for m in reversed(msgs or []):
        if m.get("autor") != "editor":
            continue
        sec = secoes_de(m.get("texto") or "")
        if sec:
            return {"id": m.get("id"), "quando": m.get("quando"), "secoes": sec}
    return None


# ---- cache por conversa (servico/textos.json) ----
def cache_ler(arquivo: Path):
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    except Exception:
        return {}


def cache_gravar(arquivo: Path, d):
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def cache_item(conversa, issue_atualizado, entrega):
    """Entrada do cache para uma conversa: metadados + seções da entrega em texto (lista vazia quando não há)."""
    return {"id": conversa["id"], "codigo": conversa.get("codigo"), "titulo": conversa.get("titulo"), "slug": conversa.get("slug"), "pasta": conversa.get("pasta"),
            "status": conversa.get("status"), "atualizado": issue_atualizado, "quando": (entrega or {}).get("quando") or conversa.get("atualizado"),
            "secoes": (entrega or {}).get("secoes") or []}


def filtrar(itens, q="", tipo="", pasta=""):
    """Filtra os itens do cache (só os que têm seção de texto) por busca, tipo de seção e pasta."""
    qn = _norm(q); out = []
    for it in itens:
        sec = [s for s in it.get("secoes", []) if s["chave"].split("-")[0] in TIPOS_TEXTO]
        if not sec:
            continue
        if pasta and (it.get("pasta") or "") != pasta:
            continue
        if tipo:
            sec = [s for s in sec if s["chave"].split("-")[0] == tipo]
            if not sec: continue
        if qn and qn not in _norm(" ".join([it.get("titulo") or "", it.get("codigo") or ""] + [s["conteudo"] for s in sec])):
            continue
        out.append({**it, "secoes": sec})
    out.sort(key=lambda x: x.get("quando") or "", reverse=True)
    return out


# ---- guardar como referência (.md só quando o Raphael pedir) ----
def _slug(t):
    return re.sub(r"[^a-z0-9]+", "-", _norm(t)).strip("-")[:60] or "texto"


def guardar(destino: Path, item, chave, titulo="", por="Raphael"):
    """Grava referencias/_textos/<data>-<codigo>-<chave>.md com a seção escolhida (ou todas as de texto, chave='tudo') e refaz o INDICE.md."""
    destino.mkdir(parents=True, exist_ok=True)
    secs = item.get("secoes", [])
    if chave == "tudo":
        esc = [s for s in secs if s["chave"].split("-")[0] in TIPOS_TEXTO] or secs
    else:
        esc = [s for s in secs if s["chave"] == chave]
    if not esc:
        raise ValueError(f"seção '{chave}' não existe nesta conversa")
    hoje = datetime.now()
    quando = (item.get("quando") or "")[:10] or hoje.strftime("%Y-%m-%d")
    codigo = (item.get("codigo") or item.get("id") or "x").lower()
    nome = f"{quando}-{_slug(codigo)}-{_slug(chave)}.md"
    rotulo = titulo.strip() or (ROTULOS.get(chave.split("-")[0], esc[0]["titulo"]) if chave != "tudo" else "Textos da entrega")
    corpo = [f"# {item.get('titulo') or codigo} — {rotulo}", "",
             f"Origem: Editor GS {item.get('codigo') or ''}, entregue em {quando}. Guardado como referência por {por} em {hoje:%d/%m/%Y %H:%M}.",
             f"Tipo: {chave}. Pasta: {item.get('pasta') or 'sem pasta'}. Use como exemplo de voz e estrutura; não é claim nem número validado.", ""]
    for s in esc:
        if len(esc) > 1: corpo += [f"## {s['titulo']}", ""]
        corpo += [s["conteudo"], ""]
    (destino / nome).write_text("\n".join(corpo).rstrip() + "\n", encoding="utf-8")
    indice(destino)
    return {"nome": nome, "arquivo": str(destino / nome), "chave": chave, "codigo": item.get("codigo")}


def guardados(destino: Path):
    out = []
    for p in sorted(destino.glob("*.md"), reverse=True):
        if p.name == "INDICE.md" or not NOME_ARQ.match(p.name):
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        linhas = txt.splitlines()
        tit = linhas[0].lstrip("# ").strip() if linhas else p.stem
        m = re.search(r"Origem: Editor GS\s*([A-Z]+-\d+)", txt); t = re.search(r"Tipo:\s*([a-z0-9\-]+)", txt)
        out.append({"nome": p.name, "titulo": tit, "codigo": m.group(1) if m else None, "chave": t.group(1) if t else None,
                    "quando": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"), "conteudo": txt})
    return out


def apagar(destino: Path, nome):
    if not NOME_ARQ.match(nome or ""):
        raise ValueError("nome inválido")
    p = destino / nome
    if not p.exists():
        raise FileNotFoundError(nome)
    p.unlink(); indice(destino)


def indice(destino: Path):
    """INDICE.md para o Editor: um item por texto guardado (título, origem, tipo)."""
    itens = guardados(destino)
    linhas = ["# Textos guardados como referência", "", "Roteiros, legendas e análises que o Raphael aprovou e quis guardar. Servem de exemplo de voz, estrutura e tamanho.",
              "Não copie frases inteiras; não são claims nem números validados.", ""]
    for it in itens:
        linhas.append(f"- `{it['nome']}` — {it['titulo']}" + (f" (origem {it['codigo']})" if it["codigo"] else ""))
    if not itens:
        linhas.append("(nenhum ainda)")
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "INDICE.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return len(itens)
