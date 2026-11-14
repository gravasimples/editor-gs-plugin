"""Banco de skills de edição (10/11/2026): catálogo do que existe fora (skills do Claude Code, plugins, repositórios, presets, estilos de
criadores que vendem ou publicam) e que pode ampliar o que o Editor sabe fazer, mais o canal "Ensinar o Editor" (regras, conhecimento e
referências do Raphael) e a pesquisa recorrente de mercado.

Pastas (dentro de workspace/, que é a pasta de trabalho do agente):
- skills_banco/catalogo.json: um item por achado, com estado (achado → avaliar → aprovado/instalado/reproduzido | descartado); decisão é humana.
- skills_banco/achados/*.json: o agente da pesquisa escreve listas aqui; o gateway junta no catálogo ao ler (dedupe por url) e move para _importados/.
- skills_banco/rodadas.json: histórico das rodadas de pesquisa (quem pediu, pedido aberto, quando).
- skills_biblioteca/<slug>/SKILL.md: skills instaladas em quarentena (13/11/2026). O agente não carrega; lê por caminho só quando o pedido citar.
- .claude/skills/<slug>/SKILL.md: skills ativas (o Claude Code carrega a descrição de todas em todo pedido, a partir do cwd do agente). Só por "Ativar".
- skills_banco/raiox/<pasta>.json: raio-x sem modelo (custo, rede, telemetria, publicação, licença, peso, sistema, idioma).
- skills_banco/dissecacoes/<id>.json: peças de uma skill em 4 caixas (regra, ativo, código, descartar), escritas pelo fluxo dissecar-skill;
  a decisão por peça (aproveitar/descartar) é do Raphael e o que ele aproveita entra na fila de absorção (skills_banco/absorver.json).
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
    # 11/11/2026: cai no workspace de caminhos.py (~/EditorGS/workspace na instalação), não no do repositório; o gateway lia uma pasta vazia.
    v = os.environ.get("EDITOR_GS_WORKSPACE")
    if v:
        return Path(v)
    from servico import caminhos as _cam
    return _cam.WORKSPACE


def _dir() -> Path:
    d = _ws() / "skills_banco"; d.mkdir(parents=True, exist_ok=True); return d


def _skills_dir() -> Path:
    d = _ws() / ".claude" / "skills"; d.mkdir(parents=True, exist_ok=True); return d


def _biblioteca_dir() -> Path:
    d = _ws() / "skills_biblioteca"; d.mkdir(parents=True, exist_ok=True); return d


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
    importar_achados(); importar_dissecacoes()
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


_PULAR = (".git", "node_modules", "__pycache__", ".venv", "venv")
_MAX_ARQ = 25 * 1024 * 1024  # arquivo acima disso (modelo, vídeo de exemplo) não vem junto; a skill continua valendo como conhecimento


def _descobrir_skills(origem: Path) -> list[Path]:
    """Pastas com SKILL.md que valem para o Claude Code (13/11/2026). Antes o instalador recusava repositório com mais de uma skill, e todas as
    aprovadas eram assim (2BFT tem 14, ChatCut 135 cópias para vários agentes). Ordem: SKILL.md na raiz → plugin do marketplace (pasta `source`
    de cada plugin) → skills/ → .claude/skills/ → qualquer SKILL.md fora de pastas de outros agentes."""
    if (origem / "SKILL.md").is_file():
        return [origem]
    def achar(base: Path) -> list[Path]:
        return sorted({p.parent for p in base.rglob("SKILL.md") if not any(x in p.parts for x in _PULAR)}) if base.is_dir() else []
    mk = origem / ".claude-plugin" / "marketplace.json"
    if mk.is_file():
        try:
            fontes = [origem / str(p.get("source", "./")).strip() for p in json.loads(mk.read_text(encoding="utf-8")).get("plugins", []) if isinstance(p.get("source", "./"), str)]
        except (ValueError, AttributeError):
            fontes = []
        achados = [s for f in fontes if f.resolve() != origem.resolve() for s in achar(f / "skills")]
        if achados:
            return achados
    for base in (origem / "skills", origem / ".claude" / "skills"):
        if achar(base):
            return achar(base)
    return achar(origem)


def _copiar_skill(origem: Path, destino: Path) -> list[str]:
    pulados = []
    def ignorar(d, nomes):
        fora = set(shutil.ignore_patterns(*_PULAR, "*.pyc")(d, nomes))
        for n in nomes:
            p = Path(d) / n
            if n not in fora and p.is_file() and p.stat().st_size > _MAX_ARQ:
                fora.add(n); pulados.append(f"{p.relative_to(origem).as_posix()} ({p.stat().st_size // 1048576} MB)")
        return fora
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(origem, destino, ignore=ignorar)
    return pulados


def instalar(id_: str, por: str = "Raphael", _baixar_=None) -> dict:
    """Instala as skills do Claude Code de um item em workspace/.claude/skills/ a partir da URL (GitHub: repositório inteiro ou a subpasta de
    /tree/<ramo>/<caminho>). Repositório com uma skill vira <slug>/; com várias, cada uma vira <slug>--<pasta>/ (pacote). Pula skill com binário
    e arquivo acima de 25 MB (avisa). Tipos skill-claude, plugin e repo que traga SKILL.md; a skill passa a ser carregada pelo agente nas próximas
    rodadas, mas só vira regra quando o Raphael aprovar o uso no pedido ou no estilo."""
    it = item(id_)
    if it["tipo"] not in ("skill-claude", "plugin", "repo"):
        raise ValueError("só instalo skill, plugin ou repositório com SKILL.md; para os outros use 'Reproduzir no Editor'.")
    m = _GH.match(it["url"].strip())
    if not m:
        raise ValueError("a URL precisa ser de um repositório ou pasta do GitHub (https://github.com/dono/repo[/tree/ramo/pasta]).")
    dono, repo, ramo, sub = m.group(1), m.group(2).removesuffix(".git"), m.group(3), m.group(4)
    base = _slug(it["id"])
    with tempfile.TemporaryDirectory(prefix="sk-") as tmp:
        clone = Path(tmp) / "r"
        if _baixar_:
            _baixar_(dono, repo, ramo, clone)
        else:
            # core.longpaths: no Windows o clone em %TEMP% estourava 260 caracteres em repositórios fundos ("Filename too long").
            cmd = ["git", "-c", "core.longpaths=true", "clone", "--depth", "1", "--quiet"] + (["--branch", ramo] if ramo else []) + [f"https://github.com/{dono}/{repo}.git", str(clone)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
            if r.returncode != 0:
                raise ValueError("git clone falhou: " + (r.stderr or r.stdout).strip()[-300:])
        origem = clone / sub if sub else clone
        if sub and origem.is_file():
            origem = origem.parent
        if not origem.is_dir():
            raise ValueError(f"pasta {sub!r} não existe no repositório.")
        cands = _descobrir_skills(origem)
        if not cands:
            raise ValueError("nenhum SKILL.md no repositório: use 'Reproduzir no Editor' para extrair a técnica.")
        skills, recusadas, pulados, validas = [], [], [], []
        for c in cands:
            try:
                validas.append((c, _skill_valida(c)))
            except ValueError as e:
                recusadas.append(f"{c.name}: {e}")
        if validas:  # reinstalação limpa o pacote anterior (ativo ou em quarentena), só quando a nova tem o que instalar
            for raiz in (_skills_dir(), _biblioteca_dir()):
                for p in [*raiz.glob(base + "--*"), raiz / base]:
                    if p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
        for c, nome in validas:
            # 13/11/2026: instala em quarentena. Em .claude/skills/ a descrição entrava em todo pedido (40 skills, ~16 KB) e puxava o agente para serviço pago.
            destino = _biblioteca_dir() / (base if len(cands) == 1 else f"{base}--{_slug(c.name, 40)}")
            pulados += [f"{c.name}/{x}" for x in _copiar_skill(c, destino)]
            skills.append({"pasta": destino.relative_to(_ws()).as_posix(), "skill": nome or c.name})
        if not skills:
            raise ValueError("nenhuma skill pôde ser instalada: " + "; ".join(recusadas)[:400])
    tam = sum(p.stat().st_size for s in skills for p in (_ws() / s["pasta"]).rglob("*") if p.is_file())
    inst = {"pasta": skills[0]["pasta"], "skill": skills[0]["skill"], "skills": skills, "recusadas": recusadas, "pulados": pulados[:20],
            "quando": _agora(), "por": por, "bytes": tam, "origem": it["url"]}
    nota = f"instalada{'s' if len(skills) > 1 else ''} {len(skills)} skill{'s' if len(skills) > 1 else ''} em quarentena (skills_biblioteca/{base}{'--*' if len(skills) > 1 else ''})"
    for s in skills:
        try:
            raio_x(Path(s["pasta"]).name)
        except Exception:  # noqa: BLE001
            pass
    if recusadas:
        nota += f"; {len(recusadas)} recusada(s) (binário)"
    if pulados:
        nota += f"; {len(pulados)} arquivo(s) grande(s) não copiado(s)"
    _atualizar(id_, lambda x: (x.update(estado="instalado", instalacao=inst, decidido_por=por, decidido_em=_agora()), x["notas"].append({"quando": _agora(), "por": por, "texto": nota})))
    return inst


def desinstalar(id_: str, por: str = "Raphael") -> dict:
    it = item(id_)
    inst = it.get("instalacao") or {}
    for s in inst.get("skills") or ([{"pasta": inst["pasta"]}] if inst.get("pasta") else []):
        for raiz in (_skills_dir(), _biblioteca_dir()):
            pasta = raiz / Path(s["pasta"]).name
            if pasta.is_dir() and pasta.parent == raiz:
                shutil.rmtree(pasta, ignore_errors=True)
    _atualizar(id_, lambda x: (x.update(estado="aprovado", decidido_por=por, decidido_em=_agora()), x.pop("instalacao", None), x["notas"].append({"quando": _agora(), "por": por, "texto": "desinstalada"})))
    return {"ok": True}


def _descricao(p: Path) -> str:
    """Descrição do frontmatter (também a de bloco `description: |`), que é o que o Claude Code põe no contexto de todo pedido quando a skill está ativa."""
    txt = (p / "SKILL.md").read_text(encoding="utf-8", errors="replace") if (p / "SKILL.md").is_file() else ""
    m = re.search(r"^---\s*\n(.*?)\n---", txt, re.S); fm = m.group(1) if m else ""
    mm = re.search(r"^description:\s*(.*?)(?=^\S[\w-]*:|\Z)", fm, re.M | re.S)
    if not mm:
        return ""
    v = mm.group(1).strip()
    if v[:1] in "|>":
        v = v[1:]
    return " ".join(v.split()).strip("'\"")


def _listar(raiz: Path, ativa: bool) -> list:
    out = []
    for p in sorted(raiz.iterdir()) if raiz.exists() else []:
        if p.is_dir() and (p / "SKILL.md").is_file():
            d = _descricao(p); rx = _ler(_dir() / "raiox" / f"{p.name}.json", None)
            out.append({"pasta": p.name, "ativa": ativa, "descricao": d[:200], "tokens": max(1, len(d) // 4) if d else 0, "arquivos": sum(1 for _ in p.rglob("*") if _.is_file()), "raiox": rx})
    return out


def instaladas() -> list:
    """Ativas (carregadas pelo agente) primeiro, depois as da biblioteca (quarentena)."""
    return _listar(_skills_dir(), True) + _listar(_biblioteca_dir(), False)


def _mover(pasta: str, de: Path, para: Path) -> Path:
    nome = Path(pasta).name
    if not nome or nome in (".", ".."):
        raise ValueError("pasta inválida")
    o, d = de / nome, para / nome
    if not (o.is_dir() and o.parent == de):
        raise KeyError(f"skill não encontrada: {nome}")
    if d.exists():
        raise ValueError(f"já existe {d.relative_to(_ws()).as_posix()}")
    o.replace(d)
    _corrigir_pasta_no_catalogo(nome, d)
    return d


def _corrigir_pasta_no_catalogo(nome: str, nova: Path):
    cat = _ler(_dir() / "catalogo.json", {"itens": []}); rel = nova.relative_to(_ws()).as_posix(); mudou = False
    for it in cat["itens"]:
        inst = it.get("instalacao") or {}
        for s in [inst, *(inst.get("skills") or [])]:
            if s.get("pasta") and Path(s["pasta"]).name == nome:
                s["pasta"] = rel; mudou = True
    if mudou:
        _gravar(_dir() / "catalogo.json", cat)


def ativar(pasta: str, por: str) -> dict:
    """Decisão humana: a skill passa a ser carregada pelo agente em todo pedido (custa a descrição dela em tokens a cada rodada)."""
    if not str(por or "").strip():
        raise ValueError("ativar é decisão humana: informe quem decidiu")
    d = _mover(pasta, _biblioteca_dir(), _skills_dir())
    rx = _ler(_dir() / "raiox" / f"{d.name}.json", {}) or {}
    return {"pasta": d.name, "ativa": True, "tokens": max(1, len(_descricao(d)) // 4), "alertas": rx.get("alertas") or []}


def desativar(pasta: str, por: str = "Raphael") -> dict:
    d = _mover(pasta, _skills_dir(), _biblioteca_dir())
    return {"pasta": d.name, "ativa": False}


def quarentena_tudo(por: str = "Raphael", manter: tuple = ("gs-",)) -> dict:
    """Move todas as skills ativas para a biblioteca, menos as nossas (prefixo gs-). Migração de 13/11/2026; não apaga nada."""
    movidas = []
    for p in sorted(_skills_dir().iterdir()):
        if p.is_dir() and not p.name.startswith(manter):
            try:
                _mover(p.name, _skills_dir(), _biblioteca_dir()); movidas.append(p.name)
            except (KeyError, ValueError):
                pass
    return {"movidas": movidas}


_PESADAS = (".venv", "venv", "node_modules", "__pycache__", ".git")


def liberar_espaco(pasta: str) -> dict:
    """Apaga só o que a skill recria sozinha (.venv, node_modules, __pycache__, .git) de uma skill da biblioteca. Modelos e ativos ficam."""
    p = _biblioteca_dir() / Path(pasta).name
    if not (p.is_dir() and p.parent == _biblioteca_dir()):
        raise KeyError(f"skill não está na biblioteca: {pasta}")
    livre = 0
    for d in [x for x in p.rglob("*") if x.is_dir() and x.name in _PESADAS]:
        if d.exists():
            livre += sum(f.stat().st_size for f in d.rglob("*") if f.is_file()); shutil.rmtree(d, ignore_errors=True)
    raio_x(p.name)
    return {"pasta": p.name, "liberado_mb": round(livre / 1048576)}


# ----------------------------------------------------------------------------------------------------------------- raio-x (sem modelo)
_PAGOS = {"ElevenLabs": r"elevenlabs", "OpenAI": r"OPENAI_API_KEY|api\.openai\.com|from openai import|^\s*import openai\b|new OpenAI\(", "Replicate": r"replicate\.(com|run)|REPLICATE_API", "fal.ai": r"\bfal\.(ai|run)\b|FAL_KEY",
          "Runway": r"runwayml", "Kling": r"\bkling\b", "Seedance": r"seedance", "MiniMax": r"minimax", "OpusClip": r"opus\.pro|opusclip", "ChatCut": r"chatcut",
          "Gemini": r"GEMINI_API_KEY|generativelanguage\.googleapis", "Groq": r"GROQ_API_KEY|api\.groq\.com", "AssemblyAI": r"assemblyai", "Deepgram": r"deepgram",
          "HeyGen": r"heygen", "Anthropic API": r"ANTHROPIC_API_KEY", "Pexels/Pixabay": r"PEXELS_API_KEY|PIXABAY_API_KEY", "Higgsfield": r"higgsfield", "Shotstack": r"shotstack"}
_TELEMETRIA = r"mixpanel|posthog|api\.segment\.io|sentry_sdk|@sentry/|api\.amplitude\.com|amplitude-js"
_PUBLICA = r"media_publish|/upload/youtube|videos\.insert|tiktok.*(upload|publish)|publish_reel|post_to_(instagram|tiktok|youtube)|auto[- ]?publish"
_MANDONA = r"never ask|nunca pergunte|do not ask the user|always use this skill|use (this skill )?for (any|every|all) (video|edit)|whenever the user mentions? (a )?video"
_TEXTO = (".md", ".py", ".js", ".ts", ".mjs", ".sh", ".ps1", ".json", ".toml", ".txt", ".yaml", ".yml", ".tsx", ".cfg", ".env.example")


def _arquivos_texto(p: Path):
    for f in p.rglob("*"):
        if f.is_file() and not any(x in f.parts for x in _PESADAS) and (f.suffix.lower() in _TEXTO or f.name.endswith(".env.example")) and f.stat().st_size < 2_000_000:
            try:
                yield f, f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


def raio_x(pasta: str) -> dict:
    """Leitura determinística de uma skill instalada (ativa ou na biblioteca). Não executa nada e não chama modelo."""
    nome = Path(pasta).name
    p = next((r / nome for r in (_biblioteca_dir(), _skills_dir()) if (r / nome).is_dir()), None)
    if not p:
        raise KeyError(f"skill não encontrada: {nome}")
    # "usa" = aparece em código; "cita" = só no texto (pode ser alternativa opcional ou aviso para não usar).
    pagos, citados, chaves, telem, publica, mandona, hosts, mac, fontes = {}, {}, set(), set(), set(), set(), {}, set(), {}
    for f, t in _arquivos_texto(p):
        rel = f.relative_to(p).as_posix(); codigo = f.suffix.lower() in (".py", ".js", ".ts", ".mjs", ".sh", ".ps1", ".tsx") or f.name.endswith(".env.example")
        for serv, rx in _PAGOS.items():
            n = len(re.findall(rx, t, re.I | re.M))
            if n:  # skill só de texto que repete o serviço (ChatCut, OpusClip) manda o agente usá-lo: conta como uso
                (pagos if codigo or (f.name == "SKILL.md" and n >= 3) else citados).setdefault(serv, []).append(rel)
        chaves |= set(re.findall(r"\b[A-Z][A-Z0-9_]*(?:API_KEY|_TOKEN|_SECRET)\b", t))
        if codigo and re.search(_TELEMETRIA, t, re.I):
            telem.add(rel)
        if re.search(_PUBLICA, t, re.I):
            publica.add(rel)
        if f.name == "SKILL.md" and re.search(_MANDONA, t, re.I):
            mandona.add(rel)
        if f.suffix.lower() in (".py", ".js", ".ts", ".mjs", ".sh", ".ps1"):
            for h in re.findall(r"https?://([a-z0-9.-]+\.[a-z]{2,})", t, re.I):
                if not re.search(r"github\.com|githubusercontent|pypi|npmjs|localhost|127\.0\.0\.1|example\.(com|org)|w3\.org|schema", h, re.I):
                    hosts[h.lower()] = hosts.get(h.lower(), 0) + 1
            if re.search(r"\bosascript\b|/Applications/|\bbrew install\b|\bpbcopy\b", t):
                mac.add(rel)
    for f in p.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2"):
            fontes[f.parent.name] = 1
    peso, pesado = 0, {}
    for f in p.rglob("*"):
        if f.is_file():
            s = f.stat().st_size; peso += s
            top = f.relative_to(p).parts[0] if len(f.relative_to(p).parts) > 1 else "(raiz)"
            pesado[top] = pesado.get(top, 0) + s
    lic = next((f for f in p.iterdir() if f.is_file() and re.match(r"licen[cs]e|copying", f.name, re.I)), None)
    lic_txt = lic.read_text(encoding="utf-8", errors="replace")[:400] if lic else ""
    licenca = next((n for n, rx in (("MIT", r"\bMIT License\b|Permission is hereby granted"), ("Apache-2.0", r"Apache License"), ("AGPL", r"Affero"), ("GPL", r"GNU General Public"), ("BSD", r"\bBSD\b")) if re.search(rx, lic_txt)), "sem arquivo de licença" if not lic else "outra")
    if not lic:  # pacote: o arquivo de licença fica na raiz do repositório, não na pasta de cada skill; vale a do catálogo
        dono = next((i for i in _ler(_dir() / "catalogo.json", {"itens": []})["itens"]
                     if any(Path(s.get("pasta") or "").name == nome for s in [(i.get("instalacao") or {}), *((i.get("instalacao") or {}).get("skills") or [])])), None)
        if dono and dono.get("licenca"):
            licenca = re.sub(r"\s*\(.*$", "", dono["licenca"]).strip() + " (catálogo)"
    modelos_en = sorted({f.name for f in p.rglob("*") if re.search(r"\.en\b|-en\b|_en\b", f.name) and re.search(r"whisper|tts|asr", f.as_posix(), re.I)})
    desc = _descricao(p)
    alertas = []
    if pagos:
        alertas.append({"tipo": "custo", "texto": "usa serviço pago: " + ", ".join(sorted(pagos))})
    if telem:
        alertas.append({"tipo": "telemetria", "texto": f"telemetria em {len(telem)} arquivo(s)"})
    if publica:
        alertas.append({"tipo": "publica", "texto": "tem caminho de publicação automática"})
    if mandona:
        alertas.append({"tipo": "mandona", "texto": "a instrução tenta tomar todo pedido ou tirar as perguntas"})
    if not re.match(r"(MIT|Apache|BSD)", licenca):
        alertas.append({"tipo": "licenca", "texto": f"licença: {licenca} (só ideia, sem copiar código)"})
    if mac:
        alertas.append({"tipo": "sistema", "texto": "partes só de macOS"})
    if modelos_en:
        alertas.append({"tipo": "idioma", "texto": "modelo de fala só em inglês: " + ", ".join(modelos_en[:3])})
    if peso > 200 * 1048576:
        alertas.append({"tipo": "peso", "texto": f"{peso // 1048576} MB em disco"})
    r = {"pasta": nome, "quando": _agora(), "licenca": licenca, "peso_mb": round(peso / 1048576, 1), "peso_por_pasta": {k: round(v / 1048576, 1) for k, v in sorted(pesado.items(), key=lambda x: -x[1])[:6]},
         "recriavel_mb": round(sum(v for k, v in pesado.items() if k in _PESADAS) / 1048576, 1), "pagos": {k: sorted(set(v))[:4] for k, v in pagos.items()}, "citados": {k: sorted(set(v))[:3] for k, v in citados.items() if k not in pagos}, "chaves": sorted(chaves)[:12],
         "telemetria": sorted(telem)[:4], "publica": sorted(publica)[:4], "mandona": sorted(mandona), "hosts": dict(sorted(hosts.items(), key=lambda x: -x[1])[:8]), "so_mac": sorted(mac)[:4],
         "modelos_en": modelos_en[:4], "fontes": sorted(fontes)[:12], "tokens_se_ativa": max(1, len(desc) // 4) if desc else 0, "alertas": alertas,
         "sugestao": "descartar" if (pagos and not re.search(r"free|grátis|offline|local|no api key", desc, re.I)) or publica or telem or mandona else "dissecar"}  # ativar nunca é sugestão automática
    d = _dir() / "raiox"; d.mkdir(exist_ok=True); _gravar(d / f"{nome}.json", r)
    return r


def raio_x_todas() -> list:
    return [raio_x(s["pasta"]) for s in instaladas()]


# ----------------------------------------------------------------------------------------------------------------- dissecar e absorver
CAIXAS = {"regra": "regra ou número (vira conhecimento ou parâmetro do motor)", "ativo": "ativo (som, fonte, modelo, efeito, preset)",
          "codigo": "código reaproveitável (só licença MIT/Apache, com crédito)", "descartar": "descartar (custo, telemetria, publicação, estética de outros, já temos)"}
DESTINOS = ("motor", "revisor", "estilo", "grafismos", "som", "conhecimento", "fluxo", "app", "nenhum")


def _dissec_arq(id_: str) -> Path:
    d = _dir() / "dissecacoes"; d.mkdir(exist_ok=True); return d / f"{_slug(id_, 60)}.json"


def dissecacao(id_: str) -> dict | None:
    return _ler(_dissec_arq(id_), None)


def gravar_dissecacao(id_: str, pecas: list, por: str, resumo: str = "") -> dict:
    """Grava (ou substitui) as peças de um item. Peça: {caixa, titulo, detalhe, fonte, destino, custo?}. Decisões já tomadas por título continuam."""
    item(id_)
    antigas = {p["titulo"]: p for p in (dissecacao(id_) or {}).get("pecas", [])}
    out = []
    for n, p in enumerate(pecas or []):
        if not isinstance(p, dict) or not str(p.get("titulo") or "").strip():
            continue
        cx = p.get("caixa") if p.get("caixa") in CAIXAS else "regra"
        tit = " ".join(str(p["titulo"]).split())[:140]
        nova = {"n": len(out) + 1, "caixa": cx, "titulo": tit, "detalhe": str(p.get("detalhe") or "")[:900], "fonte": str(p.get("fonte") or "")[:200],
                "destino": p.get("destino") if p.get("destino") in DESTINOS else ("nenhum" if cx == "descartar" else "conhecimento"), "custo": str(p.get("custo") or "")[:120],
                "decisao": (antigas.get(tit) or {}).get("decisao") or ("descartar" if cx == "descartar" else ""), "decidido_por": (antigas.get(tit) or {}).get("decidido_por") or ""}
        out.append(nova)
    d = {"id": id_, "quando": _agora(), "por": por, "resumo": str(resumo or "")[:800], "pecas": out}
    _gravar(_dissec_arq(id_), d)
    _atualizar(id_, lambda x: x["notas"].append({"quando": _agora(), "por": por, "texto": f"dissecada: {len(out)} peça(s)"}))
    return d


def importar_dissecacoes() -> list:
    """O agente do fluxo dissecar-skill escreve skills_banco/dissecacoes/_entrada/<id>.json; aqui vira a dissecação oficial do item."""
    ent = _dir() / "dissecacoes" / "_entrada"; ent.mkdir(parents=True, exist_ok=True); feitos = []
    for a in sorted(ent.glob("*.json")):
        d = _ler(a, None)
        try:
            if isinstance(d, dict) and d.get("id"):
                gravar_dissecacao(d["id"], d.get("pecas") or [], por=d.get("por") or "Editor (dissecar)", resumo=d.get("resumo") or ""); feitos.append(d["id"])
        except KeyError:
            pass
        dest = ent / "_importados"; dest.mkdir(exist_ok=True); a.replace(dest / a.name)
    return feitos


def decidir_peca(id_: str, n: int, decisao: str, por: str) -> dict:
    """aproveitar → entra na fila de absorção; descartar e depois só marcam. Decisão humana."""
    if decisao not in ("aproveitar", "descartar", "depois", ""):
        raise ValueError("decisão deve ser aproveitar, descartar ou depois")
    if not str(por or "").strip():
        raise ValueError("decisão é humana: informe quem decidiu")
    d = dissecacao(id_)
    if not d:
        raise KeyError(f"item sem dissecação: {id_}")
    p = next((x for x in d["pecas"] if x["n"] == int(n)), None)
    if not p:
        raise KeyError(f"peça {n} não existe")
    p.update(decisao=decisao, decidido_por=por, decidido_em=_agora()); _gravar(_dissec_arq(id_), d)
    fila = _ler(_dir() / "absorver.json", [])
    chave = f"{id_}#{p['titulo']}"
    fila = [f for f in fila if f.get("chave") != chave]
    if decisao == "aproveitar":
        it = item(id_)
        fila.append({"chave": chave, "item": id_, "nome": it["nome"], "licenca": it.get("licenca") or "", "url": it.get("url") or "", **{k: p[k] for k in ("caixa", "titulo", "detalhe", "fonte", "destino")},
                     "estado": "na_fila", "por": por, "quando": _agora()})
    _gravar(_dir() / "absorver.json", fila)
    return p


def absorver() -> list:
    return _ler(_dir() / "absorver.json", [])


def absorvido(chave: str, estado: str, por: str, nota: str = "") -> dict:
    """Marca uma peça da fila: na_fila → feito (entrou no motor/estilo/conhecimento) ou cancelado."""
    if estado not in ("na_fila", "feito", "cancelado"):
        raise ValueError("estado deve ser na_fila, feito ou cancelado")
    fila = absorver(); f = next((x for x in fila if x["chave"] == chave), None)
    if not f:
        raise KeyError("peça não está na fila")
    f.update(estado=estado, marcado_por=por, marcado_em=_agora(), **({"nota": nota.strip()[:300]} if nota.strip() else {})); _gravar(_dir() / "absorver.json", fila)
    return f


def peca_para_conhecimento(id_: str, n: int, por: str) -> dict:
    """Atalho: peça da caixa 'regra' vira texto em conhecimento/ (o Editor lê quando o pedido tocar no assunto) e sai da fila como feita."""
    d = dissecacao(id_) or {}; p = next((x for x in d.get("pecas", []) if x["n"] == int(n)), None)
    if not p:
        raise KeyError(f"peça {n} não existe")
    it = item(id_)
    texto = f"{p['titulo']}\n\n{p['detalhe']}\n\nOrigem: {it['nome']} ({it.get('url') or 'sem link'}; licença {it.get('licenca') or '?'}) · {p.get('fonte') or ''}. Técnica estudada; não copiar texto nem código de terceiros."
    r = ensinar("conhecimento", f"{p['titulo']} ({it['nome']})", texto, por=por, fonte=it.get("url") or "")
    if p.get("decisao") != "aproveitar":
        decidir_peca(id_, n, "aproveitar", por)
    absorvido(f"{id_}#{p['titulo']}", "feito", por, nota=f"virou conhecimento: {r['arquivo']}")
    return r


def pedido_dissecar(it: dict) -> str:
    inst = it.get("instalacao") or {}
    pastas = [s["pasta"] for s in (inst.get("skills") or ([{"pasta": inst["pasta"]}] if inst.get("pasta") else []))]
    rx = [(_ler(_dir() / "raiox" / f"{Path(x).name}.json", None) or {}) for x in pastas]
    ja = sorted({f["titulo"] for f in absorver() if f.get("estado") in ("na_fila", "feito")})
    linhas = [f"Dissecar o item `{it['id']}` do Banco de skills (fluxo dissecar-skill).",
              f"Nome: {it['nome']} · URL: {it.get('url') or '(sem)'} · licença: {it.get('licenca') or '?'}",
              ("Pastas instaladas (leia daqui; NÃO estão carregadas como skill): " + ", ".join(f"`{x}`" for x in pastas)) if pastas else "Não instalada: leia pela URL (README e SKILL.md).",
              "Raio-x automático: " + " | ".join(f"{Path(p).name}: {', '.join(a['texto'] for a in (r.get('alertas') or []) if a.get('texto')) or 'sem alerta'}" for p, r in zip(pastas, rx)) if pastas else "",
              f"Escreva o resultado em `skills_banco/dissecacoes/_entrada/{_slug(it['id'], 60)}.json` no formato do fluxo.",
              ("Já aproveitado de outras skills (não repita; cite só se esta fizer melhor): " + "; ".join(ja[-40:])) if ja else ""]
    if it.get("notas"):
        linhas.append("Notas do Raphael: " + " | ".join(n["texto"] for n in it["notas"][-5:]))
    return "\n".join(x for x in linhas if x)


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
    inst = instaladas(); fila = absorver()
    return {"n": len(cat), "por_estado": por_estado, "rodadas": rs[-10:], "pesquisa_devida": dev, "pesquisa_motivo": motivo, "instaladas": inst, "conhecimento": conhecimento(),
            "tipos": TIPOS, "estados": list(ESTADOS), "tokens_ativas": sum(s["tokens"] for s in inst if s["ativa"]), "caixas": CAIXAS, "destinos": list(DESTINOS),
            "dissecados": sorted(p.stem for p in (_dir() / "dissecacoes").glob("*.json")) if (_dir() / "dissecacoes").exists() else [],
            "absorver": sorted(fila, key=lambda f: (f.get("estado") != "na_fila", f.get("quando") or ""))}
