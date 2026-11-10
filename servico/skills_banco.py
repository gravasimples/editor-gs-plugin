"""Banco de skills de edição (10/11/2026): catálogo do que existe fora (skills do Claude Code, plugins, repositórios, presets, estilos de
criadores que vendem ou publicam) e que pode ampliar o que o Editor sabe fazer, mais o canal "Ensinar o Editor" (regras, conhecimento e
referências do Raphael) e a pesquisa recorrente de mercado.

Pastas (dentro de workspace/, que é a pasta de trabalho do agente):
- skills_banco/catalogo.json: um item por achado, com estado (achado → avaliar → aprovado/instalado/reproduzido | descartado); decisão é humana.
- skills_banco/achados/*.json: o agente da pesquisa escreve listas aqui; o gateway junta no catálogo ao ler (dedupe por url) e move para _importados/.
- skills_banco/rodadas.json: histórico das rodadas de pesquisa (quem pediu, pedido aberto, quando).
- .claude/skills/<slug>/SKILL.md: skills instaladas (o Claude Code carrega as skills de projeto a partir do cwd do agente).
- conhecimento/<slug>.md + INDICE.md: textos que o Raphael deu para o Editor estudar (o AGENTS.md manda ler o índice).
Nada aqui publica, nem muda estilo padrão sozinho: skill instalada ou reproduzida só vale por padrão depois de "aprovado" pelo Raphael."""
import json, os, re, secrets, shutil, subprocess, tempfile, unicodedata
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TIPOS = {"skill-claude": "skill do Claude Code (SKILL.md)", "plugin": "plugin do Claude Code (marketplace)", "repo": "repositório (GitHub etc.)", "estilo": "estilo ou preset de edição de um criador",
         "ferramenta": "ferramenta ou serviço de apoio", "criador": "criador/empresa que vende ou ensina edição", "curso": "curso, aula ou tutorial", "outro": "outro"}
ESTADOS = ("achado", "avaliar", "aprovado", "instalado", "reproduzido", "descartado")
TRANSICOES = {"achado": ("avaliar", "aprovado", "descartado"), "avaliar": ("aprovado", "descartado", "achado"), "aprovado": ("instalado", "reproduzido", "descartado", "avaliar"),
              "instalado": ("aprovado", "descartado"), "reproduzido": ("aprovado", "descartado"), "descartado": ("achado",)}


def _ws() -> Path:
    return Path(os.environ.get("EDITOR_GS_WORKSPACE", RAIZ / "workspace"))


def _dir() -> Path:
    d = _ws() / "skills_banco"; d.mkdir(parents=True, exist_ok=True); return d


def _skills_dir() -> Path:
    d = _ws() / ".claude" / "skills"; d.mkdir(parents=True, exist_ok=True); return d


def _conhecimento_dir() -> Path:
    d = _ws() / "conhecimento"; d.mkdir(parents=True, exist_ok=True); return d


def _slug(t, n=48):
    t = unicodedata.normalize("NFKD", str(t or "").lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n].strip("-") or "item"


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _ler(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return padrao


def _gravar(p: Path, dados):
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"); tmp.replace(p)


def _url_chave(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    u = re.sub(r"^https?://(www\.)?", "", u); u = re.sub(r"[?#].*$", "", u)
    return u


# ----------------------------------------------------------------------------------------------------------------- catálogo
def _normalizar(it: dict, por: str, fonte: str) -> dict | None:
    url = str(it.get("url") or "").strip()
    nome = " ".join(str(it.get("nome") or it.get("titulo") or "").split())[:120]
    if not url and not nome:
        return None
    tipo = it.get("tipo") if it.get("tipo") in TIPOS else "outro"
    base = _slug(nome or _url_chave(url).split("/")[-1])
    lista = [str(x).strip() for x in (it.get("o_que_aproveitar") or [])] if isinstance(it.get("o_que_aproveitar"), list) else [s.strip() for s in str(it.get("o_que_aproveitar") or "").split(";") if s.strip()]
    return {"id": base, "nome": nome or base, "tipo": tipo, "url": url, "autor": str(it.get("autor") or "")[:80], "licenca": str(it.get("licenca") or "")[:60], "preco": str(it.get("preco") or "")[:60],
            "resumo": str(it.get("resumo") or "")[:600], "o_que_aproveitar": lista[:8], "como_reproduzir": str(it.get("como_reproduzir") or "")[:800],
            "evidencia": str(it.get("evidencia") or "")[:300], "estado": "achado", "achado_em": _agora(), "achado_por": por, "fonte": fonte, "notas": [],
            "tags": [str(t).strip().lower() for t in (it.get("tags") or [])][:8]}


def registrar(itens: list, por: str = "Raphael", fonte: str = "manual") -> dict:
    """Junta itens ao catálogo. Dedupe por url (ou por id quando não há url); o que já existe não perde a decisão humana. Devolve {novos, ja_tinha}."""
    cat = _ler(_dir() / "catalogo.json", {"itens": []})
    por_url = {_url_chave(c["url"]): c for c in cat["itens"] if c.get("url")}; por_id = {c["id"]: c for c in cat["itens"]}
    novos, ja = [], []
    for it in itens or []:
        n = _normalizar(it if isinstance(it, dict) else {"url": str(it)}, por, fonte)
        if not n:
            continue
        chave = _url_chave(n["url"]) if n["url"] else None
        if chave and chave in por_url:
            ex = por_url[chave]
            for k in ("resumo", "o_que_aproveitar", "como_reproduzir", "evidencia", "licenca", "preco", "autor"):
                if not ex.get(k) and n.get(k):
                    ex[k] = n[k]
            ja.append(ex["id"]); continue
        if n["id"] in por_id:
            if not chave:
                ja.append(n["id"]); continue
            k = 2
            while f"{n['id']}-{k}" in por_id:
                k += 1
            n["id"] = f"{n['id']}-{k}"
        cat["itens"].append(n); por_id[n["id"]] = n
        if chave:
            por_url[chave] = n
        novos.append(n["id"])
    _gravar(_dir() / "catalogo.json", cat)
    return {"novos": novos, "ja_tinha": ja}


def importar_achados() -> dict:
    """Lê skills_banco/achados/*.json (escritos pelo agente da pesquisa), junta no catálogo e move para _importados/."""
    pasta = _dir() / "achados"; pasta.mkdir(exist_ok=True); feitos = []; novos = 0
    for a in sorted(pasta.glob("*.json")):
        d = _ler(a, None)
        itens = d.get("itens") if isinstance(d, dict) else d
        if isinstance(itens, list):
            r = registrar(itens, por=(d.get("por") if isinstance(d, dict) else None) or "Editor (pesquisa)", fonte=f"pesquisa {a.stem}")
            novos += len(r["novos"]); feitos.append(a.name)
        dest = pasta / "_importados"; dest.mkdir(exist_ok=True); a.replace(dest / a.name)
    return {"arquivos": feitos, "novos": novos}


def catalogo(estado: str = "", tipo: str = "", q: str = "") -> list:
    importar_achados()
    itens = _ler(_dir() / "catalogo.json", {"itens": []})["itens"]
    if estado:
        itens = [i for i in itens if i.get("estado") == estado]
    if tipo:
        itens = [i for i in itens if i.get("tipo") == tipo]
    if q:
        ql = q.lower(); itens = [i for i in itens if ql in json.dumps(i, ensure_ascii=False).lower()]
    ordem = {e: n for n, e in enumerate(("avaliar", "achado", "aprovado", "instalado", "reproduzido", "descartado"))}
    return sorted(itens, key=lambda i: (ordem.get(i.get("estado"), 9), i.get("achado_em") or ""), reverse=False)


def item(id_: str) -> dict:
    it = next((i for i in _ler(_dir() / "catalogo.json", {"itens": []})["itens"] if i["id"] == id_), None)
    if not it:
        raise KeyError(f"item não encontrado: {id_}")
    return it


def _atualizar(id_: str, fn) -> dict:
    cat = _ler(_dir() / "catalogo.json", {"itens": []})
    it = next((i for i in cat["itens"] if i["id"] == id_), None)
    if not it:
        raise KeyError(f"item não encontrado: {id_}")
    fn(it); _gravar(_dir() / "catalogo.json", cat); return it


def decidir(id_: str, estado: str, por: str, nota: str = "") -> dict:
    """Decisão humana sobre um item. Só transições previstas; 'instalado' e 'reproduzido' são marcados pelas ações, não à mão."""
    if estado not in ESTADOS:
        raise ValueError(f"estado deve ser um de: {', '.join(ESTADOS)}")
    if not str(por or "").strip():
        raise ValueError("decisão é humana: informe quem decidiu")

    def f(it):
        if estado not in TRANSICOES.get(it["estado"], ()) and estado != it["estado"]:
            raise ValueError(f"de '{it['estado']}' não dá para ir a '{estado}' (possíveis: {', '.join(TRANSICOES.get(it['estado'], ()))})")
        it["estado"] = estado; it["decidido_por"] = por; it["decidido_em"] = _agora()
        if nota.strip():
            it["notas"].append({"quando": _agora(), "por": por, "texto": nota.strip()[:500]})
    return _atualizar(id_, f)


def anotar(id_: str, texto: str, por: str) -> dict:
    if len(str(texto or "").strip()) < 2:
        raise ValueError("nota vazia")
    return _atualizar(id_, lambda it: it["notas"].append({"quando": _agora(), "por": por, "texto": texto.strip()[:500]}))


def editar(id_: str, campos: dict) -> dict:
    permitidos = {"nome", "tipo", "url", "autor", "licenca", "preco", "resumo", "como_reproduzir", "evidencia"}

    def f(it):
        for k, v in campos.items():
            if k in permitidos and v is not None:
                it[k] = (v if k != "tipo" or v in TIPOS else it["tipo"])
        if "o_que_aproveitar" in campos and isinstance(campos["o_que_aproveitar"], str):
            it["o_que_aproveitar"] = [s.strip() for s in campos["o_que_aproveitar"].split(";") if s.strip()][:8]
    return _atualizar(id_, f)


# ----------------------------------------------------------------------------------------------------------------- instalar skill
_GH = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+)(?:/(?:tree|blob)/([^/]+)/(.+))?/?$")


def _skill_valida(pasta: Path) -> str:
    s = pasta / "SKILL.md"
    if not s.is_file():
        raise ValueError("SKILL.md não encontrado nessa pasta (uma skill do Claude Code é uma pasta com SKILL.md).")
    txt = s.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^---\s*\n(.*?)\n---", txt, re.S)
    nome = ""
    if m:
        mm = re.search(r"^name:\s*(.+)$", m.group(1), re.M); nome = mm.group(1).strip().strip("'\"") if mm else ""
    if not nome and not txt.strip():
        raise ValueError("SKILL.md vazio.")
    for p in pasta.rglob("*"):
        if p.suffix.lower() in (".exe", ".dll", ".so", ".dylib", ".bin"):
            raise ValueError(f"a skill traz binário ({p.name}); não instalo binário sem revisão.")
    return nome


def instalar(id_: str, por: str = "Raphael", _baixar_=None) -> dict:
    """Instala uma skill do Claude Code em workspace/.claude/skills/<slug>/ a partir da URL do item (GitHub: repositório inteiro quando a raiz tem
    SKILL.md, ou a subpasta apontada por /tree/<ramo>/<caminho>). Só tipos skill-claude e plugin; a skill passa a ser carregada pelo agente
    nas próximas rodadas, mas só vira regra quando o Raphael aprovar o uso no pedido ou no estilo."""
    it = item(id_)
    if it["tipo"] not in ("skill-claude", "plugin"):
        raise ValueError("só instalo itens do tipo skill-claude ou plugin; para os outros use 'Reproduzir no Editor'.")
    m = _GH.match(it["url"].strip())
    if not m:
        raise ValueError("a URL precisa ser de um repositório ou pasta do GitHub (https://github.com/dono/repo[/tree/ramo/pasta]).")
    dono, repo, ramo, sub = m.group(1), m.group(2).removesuffix(".git"), m.group(3), m.group(4)
    destino = _skills_dir() / _slug(it["id"])
    with tempfile.TemporaryDirectory(prefix="skill-") as tmp:
        clone = Path(tmp) / "repo"
        if _baixar_:
            _baixar_(dono, repo, ramo, clone)
        else:
            cmd = ["git", "clone", "--depth", "1", "--quiet"] + (["--branch", ramo] if ramo else []) + [f"https://github.com/{dono}/{repo}.git", str(clone)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
            if r.returncode != 0:
                raise ValueError("git clone falhou: " + (r.stderr or r.stdout).strip()[-300:])
        origem = clone / sub if sub else clone
        if sub and origem.is_file():
            origem = origem.parent
        if not origem.is_dir():
            raise ValueError(f"pasta {sub!r} não existe no repositório.")
        if not (origem / "SKILL.md").is_file():  # repositório com várias skills: pega a primeira pasta com SKILL.md (e avisa)
            cands = sorted(p.parent for p in origem.rglob("SKILL.md") if ".git" not in p.parts)
            if len(cands) != 1:
                raise ValueError("o repositório tem " + (f"{len(cands)} skills; aponte a URL para a pasta de uma (tree/<ramo>/<pasta>)." if cands else "nenhum SKILL.md."))
            origem = cands[0]
        nome = _skill_valida(origem)
        shutil.rmtree(destino, ignore_errors=True)
        shutil.copytree(origem, destino, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", "*.pyc"))
    tam = sum(p.stat().st_size for p in destino.rglob("*") if p.is_file())
    inst = {"pasta": destino.relative_to(_ws()).as_posix(), "skill": nome or destino.name, "quando": _agora(), "por": por, "bytes": tam, "origem": it["url"]}
    _atualizar(id_, lambda x: (x.update(estado="instalado", instalacao=inst, decidido_por=por, decidido_em=_agora()), x["notas"].append({"quando": _agora(), "por": por, "texto": f"instalada em {inst['pasta']}"})))
    return inst


def desinstalar(id_: str, por: str = "Raphael") -> dict:
    it = item(id_)
    pasta = _ws() / (it.get("instalacao") or {}).get("pasta", "")
    if it.get("instalacao") and pasta.is_dir() and pasta.parent == _skills_dir():
        shutil.rmtree(pasta, ignore_errors=True)
    _atualizar(id_, lambda x: (x.update(estado="aprovado", decidido_por=por, decidido_em=_agora()), x.pop("instalacao", None), x["notas"].append({"quando": _agora(), "por": por, "texto": "desinstalada"})))
    return {"ok": True}


def instaladas() -> list:
    out = []
    for p in sorted(_skills_dir().iterdir()) if _skills_dir().exists() else []:
        if p.is_dir() and (p / "SKILL.md").is_file():
            txt = (p / "SKILL.md").read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^description:\s*(.+)$", txt, re.M)
            out.append({"pasta": p.name, "descricao": (m.group(1).strip().strip("'\"") if m else "")[:200], "arquivos": sum(1 for _ in p.rglob("*") if _.is_file())})
    return out


# ----------------------------------------------------------------------------------------------------------------- ensinar o Editor
def ensinar(tipo: str, titulo: str, texto: str, por: str = "Raphael", fonte: str = "") -> dict:
    """tipo 'regra': vira memória (preferencias/memorias.md, via estilo_criativo.lembrar). tipo 'conhecimento': arquivo em conhecimento/<slug>.md
    e linha no INDICE.md, que o AGENTS.md manda o Editor ler. 'referencia' (link de vídeo) não é daqui: vai para a página Referências."""
    texto = (texto or "").strip()
    if tipo == "regra":
        from servico import estilo_criativo as ecr
        m = ecr.lembrar(texto, origem=f"{por} (Banco de skills)")
        return {"tipo": "regra", "memoria": m}
    if tipo != "conhecimento":
        raise ValueError("tipo deve ser regra ou conhecimento (vídeo ou link de referência: página Referências).")
    if len(texto) < 20:
        raise ValueError("conhecimento muito curto (mínimo 20 caracteres); regra curta vai como 'regra'.")
    titulo = " ".join((titulo or texto[:60]).split())[:100]
    slug = f"{datetime.now():%Y-%m-%d}-{_slug(titulo, 40)}"; p = _conhecimento_dir() / f"{slug}.md"
    k = 2
    while p.exists():
        p = _conhecimento_dir() / f"{slug}-{k}.md"; k += 1
    p.write_text(f"# {titulo}\n\nDado por: {por} · {_agora()[:16].replace('T', ' ')}" + (f" · fonte: {fonte.strip()}" if fonte.strip() else "") + "\n\n" + texto + "\n", encoding="utf-8")
    _reindexar()
    return {"tipo": "conhecimento", "arquivo": p.relative_to(_ws()).as_posix(), "titulo": titulo}


def _reindexar():
    d = _conhecimento_dir(); linhas = ["# Conhecimento dado pelo Raphael ao Editor", "",
                                       "Textos para estudar antes de editar quando o pedido tocar no assunto (leia só os que se aplicam). Não são claims da marca; não copiar frases de terceiros.", ""]
    for p in sorted(d.glob("*.md")):
        if p.name == "INDICE.md":
            continue
        t = p.read_text(encoding="utf-8", errors="replace").splitlines()
        titulo = t[0].lstrip("# ").strip() if t else p.stem
        linhas.append(f"- `{p.name}`: {titulo}")
    if len(linhas) == 4:
        linhas.append("- (nada ainda)")
    (d / "INDICE.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def conhecimento() -> list:
    d = _conhecimento_dir(); out = []
    for p in sorted(d.glob("*.md"), reverse=True):
        if p.name == "INDICE.md":
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        out.append({"arquivo": p.name, "titulo": (t.splitlines() or [p.stem])[0].lstrip("# ").strip(), "tamanho": len(t), "quando": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")})
    return out


def conhecimento_apagar(arquivo: str) -> bool:
    p = _conhecimento_dir() / Path(arquivo).name
    if p.is_file() and p.name != "INDICE.md":
        p.unlink(); _reindexar(); return True
    return False


# ----------------------------------------------------------------------------------------------------------------- pesquisa recorrente
def rodadas() -> list:
    return _ler(_dir() / "rodadas.json", [])


def rodada_gravar(rod: dict):
    rs = rodadas(); rs = [r for r in rs if r.get("id") != rod["id"]] + [rod]; _gravar(_dir() / "rodadas.json", rs[-100:]); return rod


def pesquisa_devida(agora: datetime = None, dias: int = 7) -> tuple[bool, str]:
    agora = agora or datetime.now(); rs = rodadas()
    if not rs:
        return True, "nenhuma rodada ainda"
    ult = rs[-1]
    try:
        q = datetime.fromisoformat(ult["quando"])
    except Exception:  # noqa: BLE001
        return True, "última rodada sem data"
    if agora - q >= timedelta(days=dias):
        return True, f"última em {ult['quando'][:10]}"
    return False, f"última em {ult['quando'][:10]}; próxima em {(q + timedelta(days=dias)).date().isoformat()}"


def pedido_pesquisa(foco: str = "") -> str:
    """Texto do pedido para o agente (fluxo pesquisa-skills): o que já temos, para não repetir, e onde escrever os achados."""
    cat = catalogo(); urls = [i["url"] for i in cat if i.get("url")]
    desc = [i["id"] for i in cat if i.get("estado") == "descartado"]
    nome = f"achados-{datetime.now():%Y%m%d-%H%M}.json"
    partes = ["Rodada de pesquisa do Banco de skills de edição (fluxo pesquisa-skills).",
              f"Escreva os achados em `skills_banco/achados/{nome}` (JSON: {{\"por\": \"Editor (pesquisa)\", \"itens\": [...]}}; campos por item: nome, tipo, url, autor, licenca, preco, resumo, o_que_aproveitar (lista), como_reproduzir, evidencia, tags).",
              f"Já conhecemos {len(urls)} itens; não repita estas URLs: " + (", ".join(urls[-60:]) if urls else "(nenhuma ainda)") + ".",
              (f"Descartados pelo Raphael (não traga de novo nem parecidos): {', '.join(desc[-30:])}." if desc else ""),
              (f"Foco pedido pelo Raphael nesta rodada: {foco.strip()}" if foco.strip() else "")]
    return "\n".join(p for p in partes if p)


def pedido_reproduzir(it: dict, modo: str = "reproduzir") -> str:
    """Pedido para o agente estudar um item e traduzi-lo para o vocabulário do Editor (estilo JSON, fluxo, grafismos, transições)."""
    cab = [f"{'Avaliar' if modo == 'avaliar' else 'Reproduzir no Editor'} o item `{it['id']}` do Banco de skills (fluxo reproduzir-skill, modo {modo}).",
           f"Nome: {it['nome']} · tipo: {it['tipo']} ({TIPOS.get(it['tipo'], '')}) · URL: {it['url'] or '(sem)'} · autor: {it.get('autor') or '?'} · licença: {it.get('licenca') or '?'} · preço: {it.get('preco') or '?'}",
           f"Resumo: {it.get('resumo') or '(sem)'}", f"O que aproveitar: {'; '.join(it.get('o_que_aproveitar') or []) or '(sem)'}", f"Como reproduzir (hipótese): {it.get('como_reproduzir') or '(sem)'}",
           f"Evidência de que funciona: {it.get('evidencia') or '(sem)'}"]
    if it.get("notas"):
        cab.append("Notas do Raphael: " + " | ".join(n["texto"] for n in it["notas"][-5:]))
    if modo == "avaliar":
        cab.append("Só avalie: nada de instalar, criar estilo ou fluxo. Entregue a avaliação nas seções do fluxo.")
    return "\n".join(cab)


def estado() -> dict:
    cat = catalogo(); dev, motivo = pesquisa_devida()
    por_estado = {}
    for i in cat:
        por_estado[i["estado"]] = por_estado.get(i["estado"], 0) + 1
    rs = rodadas()
    return {"n": len(cat), "por_estado": por_estado, "rodadas": rs[-10:], "pesquisa_devida": dev, "pesquisa_motivo": motivo, "instaladas": instaladas(), "conhecimento": conhecimento(),
            "tipos": TIPOS, "estados": list(ESTADOS)}
