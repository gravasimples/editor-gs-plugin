"""Biblioteca de edição (16/11/2026, pedido do Raphael): receitas de estilo profissional (prompt + parâmetros nossos) que viajam com o código.
`biblioteca-edicao/` fica no repositório e vai para o GitHub e para o plugin público: quem instala o Editor GS recebe o repertório inteiro.
- `estilos/<id>.json`: receita curada ou destilada de referências (o que liga, ritmo, grafismos, estrutura, prompt pronto).
- `padroes/formatos.json` e `padroes/efeitos.json`: medidas agregadas das referências estudadas, sem título, link, autor nem quadro.
- `INDICE.md`: lista legível (agente e GitHub).
Cresce assim: referência nova → repertório (ficha local, privada) → `destilar()` atualiza os padrões → o agente propõe receita (fluxo
`destilar-estilos`) → decisão humana em Estilos › Receitas → `aprovar` grava no repositório (máquina de desenvolvimento) ou na biblioteca local.
Referência é estudo: a receita descreve técnica e ritmo com as nossas palavras; nunca texto, imagem, áudio, nome ou link da referência."""
import json, os, re, unicodedata
from datetime import datetime
from pathlib import Path
from .util import ErroFerramenta, ler_json, salvar_json
from . import repertorio as rep
from .grafismos import TIPOS as TIPOS_GRAFISMO, VISUAIS
from .transicoes import TIPOS as TIPOS_TRANSICAO

RAIZ = Path(__file__).resolve().parents[3]
OFICIAL = RAIZ / "biblioteca-edicao"
ENERGIAS = ("calmo", "dinamico", "bem_dinamico")
TEMAS = ("tutorial", "dica", "lista", "opiniao", "historia", "bastidor", "depoimento", "entrevista", "anuncio", "gancho", "novidade", "antes-depois",
         "youtube", "aula", "energia", "tela", "cliente")
OBRIGATORIOS = ("id", "nome", "resumo", "formatos", "temas", "energia", "base_estilo", "estrutura", "regras", "evitar", "prompt")
# o que não pode sair numa receita pública: link, perfil, nome de quem fez a referência, frase copiada entre aspas
PROIBIDO = [(re.compile(r"https?://|www\.", re.I), "link"),
            (re.compile(r"\b[a-z0-9-]+\.(?:com|net|org|io|ly|me|tv|gg|app|link|site|br)\b", re.I), "link"),
            (re.compile(r"(?<![\w.])@[A-Za-z0-9_.]{3,}"), "@perfil"),
            (re.compile(r"m[aá]quina de criativos|\bm[aá]quina\b", re.I), "nome de referência"),
            # aspas com duas palavras ou mais já é frase de alguém (16/11: o limite antigo de 4 palavras deixava passar bordão curto)
            (re.compile(r"[\"“”‘’][^\"“”‘’]{0,80}\s[^\"“”‘’]{0,80}[\"“”‘’]|(?<!\w)'[^'\n]{0,80}\s[^'\n]{0,80}'(?!\w)"), "frase entre aspas (texto copiado?)")]


def _local():
    return rep.WORKSPACE / "biblioteca-local"


def _pastas(origem):
    return {"oficial": OFICIAL / "estilos", "local": _local() / "estilos", "proposta": _local() / "propostas"}[origem]


def _slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:48]


def _textos(c):
    """Todos os textos da receita (o que a varredura de privacidade lê): qualquer string em qualquer chave, inclusive `alvos`, `montagem`
    e chaves extras (16/11: antes só nome/resumo/prompt/listas, e um link em `alvos` ou numa chave nova passava). `fonte` é carimbo nosso."""
    out = []

    def anda(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                anda(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                anda(x)
    anda({k: v for k, v in c.items() if k != "fonte" and not k.startswith("_")})
    return out


def _termos_locais():
    """Nomes que só esta máquina conhece e não podem sair numa receita: título das fichas (3 palavras ou mais), trechos entre aspas e @perfis
    citados na abertura/fechamento delas (nome de série, bordão, perfil) e `biblioteca-local/proibidos.txt` (um termo por linha: pessoa, marca,
    lugar). Volta em forma de slug com espaço; a lista fica fora do repositório."""
    termos = set()
    try:
        for f in rep.listar()["fichas"]:
            t = _slug(f.get("titulo") or "").replace("-", " ")
            if len(t.split()) >= 3:
                termos.add(t)
            try:
                d = rep.ficha(f["id"])
            except Exception:
                continue
            for campo in (d.get("abertura"), d.get("fechamento"), d.get("fonte")):
                for q in re.findall(r"[\"“”‘']([^\"“”‘’']{3,80})[\"“”’']", campo or ""):
                    s = _slug(q).replace("-", " ")
                    if len(s.split()) >= 2:
                        termos.add(s)
                for h in re.findall(r"@([A-Za-z0-9_.]{3,})", campo or ""):
                    termos.add(_slug(h).replace("-", " "))
    except Exception:
        pass
    p = _local() / "proibidos.txt"
    if p.exists():
        termos |= {_slug(l).replace("-", " ") for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    return {t for t in termos if t}


def validar(c):
    """Erros que impedem salvar (lista vazia = ok). Confere vocabulário contra os parâmetros reais do motor e a varredura de privacidade."""
    erros = [f"falta `{k}`" for k in OBRIGATORIOS if not c.get(k)]
    if erros:
        return erros
    if c["id"] != _slug(c["id"]):
        erros.append(f"`id` deve ser só minúsculas, números e hífen (ex.: {_slug(c['id'])})")
    erros += [f"formato desconhecido: {f} (use {', '.join(rep.FORMATOS)})" for f in c["formatos"] if f not in rep.FORMATOS]
    erros += [f"tema desconhecido: {t}" for t in c["temas"] if t not in TEMAS]
    if c["energia"] not in ENERGIAS:
        erros.append(f"energia deve ser {', '.join(ENERGIAS)}")
    if not (RAIZ / "estilos" / f"{c['base_estilo']}.json").exists():
        erros.append(f"base_estilo `{c['base_estilo']}` não existe em estilos/")
    if c.get("legenda") and not (RAIZ / "estilos" / "legendas" / f"{c['legenda']}.json").exists():
        erros.append(f"legenda `{c['legenda']}` não existe em estilos/legendas/")
    g = c.get("grafismos") or {}
    erros += [f"grafismo desconhecido: {t}" for t in g.get("tipos") or [] if t not in TIPOS_GRAFISMO]
    vis = {v for vs in VISUAIS.values() for v in vs}
    erros += [f"visual desconhecido: {v} (use {', '.join(sorted(vis))})" for v in g.get("visual") or [] if v not in vis]
    if g.get("a_cada_s") is not None and not (2 <= float(g["a_cada_s"]) <= 300):
        erros.append("grafismos.a_cada_s fora de 2–300 s")
    erros += [f"transição desconhecida: {t}" for t in (c.get("transicoes") or {}) if t not in TIPOS_TRANSICAO]
    chaves = _chaves_montagem()
    erros += [f"chave de montagem desconhecida: {k}" for k in (c.get("montagem") or {}) if k not in chaves]
    if len(c["prompt"]) > 1400:
        erros.append("prompt passa de 1400 caracteres")
    termos = _termos_locais()
    for txt in _textos(c) + [c["id"].replace("-", " ")]:
        for rx, nome in PROIBIDO:
            if rx.search(txt or ""):
                erros.append(f"{nome} em: {txt[:70]}…")
        s = f" {_slug(txt or '').replace('-', ' ')} "
        for t in termos:
            if f" {t} " in s:
                erros.append(f"nome de referência ({t}) em: {txt[:70]}…")
    erros = list(dict.fromkeys(erros))
    return erros


def _chaves_montagem():
    """Chaves que algum estilo de estilos/ usa no bloco `montagem` (as que o motor entende)."""
    out = set()
    for p in (RAIZ / "estilos").glob("*.json"):
        try:
            out |= set((ler_json(p).get("montagem") or {}).keys())
        except Exception:
            pass
    return out | {"broll_modo"}


def _ler_pasta(origem):
    p = _pastas(origem)
    return [{**ler_json(f), "_origem": origem} for f in sorted(p.glob("*.json"))] if p.is_dir() else []


def _todas():
    """Oficial + local; a local com o mesmo id vence (ajuste feito nesta máquina)."""
    por_id = {c["id"]: c for c in _ler_pasta("oficial")}
    por_id.update({c["id"]: c for c in _ler_pasta("local")})
    return sorted(por_id.values(), key=lambda c: (c.get("ordem", 99), c["nome"]))


def _resumo(c):
    return {k: c.get(k) for k in ("id", "nome", "resumo", "formatos", "temas", "energia", "base_estilo", "legenda")} | {
        "origem": c["_origem"], "grafismos": (c.get("grafismos") or {}).get("tipos", []), "versao": c.get("versao", 1), "atualizado": (c.get("fonte") or {}).get("atualizado")}


def listar(formato="", tema="", energia="", busca=""):
    q = _slug(busca).replace("-", " ") if busca else ""
    out = []
    for c in _todas():
        if formato and formato not in c["formatos"] or tema and tema not in c["temas"] or energia and c["energia"] != energia:
            continue
        if q and not all(w in _slug(" ".join(_textos(c))).replace("-", " ") for w in q.split()):
            continue
        out.append(_resumo(c))
    return {"n": len(out), "receitas": out, "formatos": rep.FORMATOS, "temas": TEMAS, "energias": ENERGIAS,
            "propostas": len(list(_pastas("proposta").glob("*.json"))) if _pastas("proposta").is_dir() else 0}


def _padroes():
    p = OFICIAL / "padroes" / "formatos.json"
    return ler_json(p) if p.exists() else {}


def instrucao(c):
    """O parágrafo que entra no pedido: como aplicar a receita com as ferramentas (o agente lê isto no lugar de interpretar adjetivos)."""
    g = c.get("grafismos") or {}
    partes = [f"Receita de edição `{c['id']}` ({c['nome']}): {c['resumo']}",
              f"Base: estilo `{c['base_estilo']}`, energia {c['energia']}" + (f", legenda `{c['legenda']}`" if c.get("legenda") else "") + "."]
    if g.get("tipos"):
        partes.append(f"Grafismos (só com motivo na fala): {', '.join(g['tipos'])}" + (f", no máximo um a cada {g['a_cada_s']} s" if g.get("a_cada_s") else "")
                      + (f"; acabamento `visual` permitido: {', '.join(g['visual'])}" if g.get("visual") else "") + ".")
    elif g.get("a_cada_s") is None:
        partes.append("Sem grafismos.")
    if c.get("transicoes"):
        partes.append("Transições: `montar_remotion(receita_transicoes='" + json.dumps(c["transicoes"]) + "')` (pesos; a energia ainda ajusta).")
    if c.get("montagem"):
        partes.append("Por cima do bloco `montagem` do estilo base: " + ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in c["montagem"].items()) + ".")
    if c.get("alvos"):
        partes.append("Alvos: " + ", ".join(f"{k} {v}" for k, v in c["alvos"].items()) + ".")
    partes.append("Estrutura: " + " | ".join(c["estrutura"]))
    partes.append("Regras: " + " ".join(f"- {r}" for r in c["regras"]))
    partes.append("Evitar: " + "; ".join(c["evitar"]) + ".")
    return "\n".join(partes)


def ver(id_):
    c = next((x for x in _todas() if x["id"] == id_), None)
    if not c:
        p = _pastas("proposta") / f"{id_}.json"
        if not p.exists():
            raise ErroFerramenta(f"Receita '{id_}' não existe (veja biblioteca_edicao).")
        c = {**ler_json(p), "_origem": "proposta"}
    pad = _padroes()
    medidos = {f: pad[f] for f in c["formatos"] if f in pad}
    extra = {"proposta": c["_proposta"]} if c.get("_proposta") else {}
    return {**{k: v for k, v in c.items() if not k.startswith("_")}, **extra, "origem": c["_origem"], "instrucao": instrucao(c), "medido_nas_referencias": medidos}


def _carimbo(c, tipo, n_refs=0):
    hoje = datetime.now().strftime("%Y-%m-%d")
    f = dict(c.get("fonte") or {})
    f.update({"tipo": f.get("tipo") or tipo, "atualizado": hoje, "referencias": max(n_refs, f.get("referencias", 0))})
    return {**c, "fonte": f}


def propor(c, referencias=None, por="agente"):
    """Guarda uma receita como proposta (esperando decisão humana). `referencias` = ids das fichas do repertório que a sustentam; ficam só aqui."""
    if isinstance(c, str):
        try:
            c = json.loads(c)
        except json.JSONDecodeError as e:
            raise ErroFerramenta(f"receita não é JSON válido: {e}")
    c = {k: v for k, v in c.items() if not k.startswith("_")}
    c["id"] = _slug(c.get("id") or c.get("nome") or "")
    erros = validar(c)
    if erros:
        raise ErroFerramenta("Receita recusada: " + "; ".join(erros))
    refs = [r for r in (referencias or []) if isinstance(r, str)]
    existe = any(x["id"] == c["id"] for x in _todas())
    salvar_json(_pastas("proposta") / f"{c['id']}.json", {**_carimbo(c, "destilado", len(refs)), "_proposta": {
        "por": por, "em": datetime.now().isoformat(timespec="seconds"), "referencias": refs, "substitui": existe}})
    return {"ok": True, "id": c["id"], "substitui": existe, "aviso": "Fica em Estilos › Receitas › Propostas até o Raphael aprovar ou recusar."}


def propostas():
    p = _pastas("proposta")
    return [{**{k: v for k, v in ler_json(f).items() if k != "_proposta"}, "proposta": ler_json(f).get("_proposta", {})} for f in sorted(p.glob("*.json"))] if p.is_dir() else []


def _repo_de_desenvolvimento():
    return (RAIZ / ".git").exists() and os.environ.get("EDITOR_GS_BIBLIOTECA_LOCAL") != "1"


def aprovar(id_, por="Raphael"):
    """Proposta → biblioteca. Na máquina de desenvolvimento (repositório com .git) vai para `biblioteca-edicao/estilos/` e sai no próximo commit e
    publicação para todos; numa instalação de usuário fica na biblioteca local (só dele)."""
    p = _pastas("proposta") / f"{id_}.json"
    if not p.exists():
        raise ErroFerramenta(f"Proposta '{id_}' não existe.")
    d = ler_json(p); meta = d.pop("_proposta", {})
    erros = validar(d)
    if erros:
        raise ErroFerramenta("Proposta não passa mais na validação: " + "; ".join(erros))
    destino = "oficial" if _repo_de_desenvolvimento() else "local"
    anterior = _pastas(destino) / f"{id_}.json"
    d["versao"] = (ler_json(anterior).get("versao", 1) + 1) if anterior.exists() else d.get("versao", 1)
    d["fonte"] = {**d.get("fonte", {}), "aprovado_por": por, "referencias": len(meta.get("referencias") or []) or d.get("fonte", {}).get("referencias", 0)}
    salvar_json(anterior, d); p.unlink()
    _registrar_cobertas(meta.get("referencias") or [])
    if destino == "oficial":
        gerar_indice()
    return {"ok": True, "id": id_, "destino": destino, "versao": d["versao"],
            "proximo": "commit + publicar_plugin para chegar a todos" if destino == "oficial" else "fica só nesta instalação"}


def recusar(id_, motivo=""):
    p = _pastas("proposta") / f"{id_}.json"
    if not p.exists():
        raise ErroFerramenta(f"Proposta '{id_}' não existe.")
    d = ler_json(p); refs = (d.get("_proposta") or {}).get("referencias") or []
    hist = _local() / "recusadas.jsonl"; hist.parent.mkdir(parents=True, exist_ok=True)
    with hist.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"id": id_, "nome": d.get("nome"), "motivo": motivo, "em": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
    p.unlink(); _registrar_cobertas(refs)  # recusada também conta como estudada: não volta a pedir a mesma
    return {"ok": True, "id": id_}


# --- evolução: o que o repertório tem de novo --------------------------------------------------------------
def _estado_p():
    return _local() / "estado.json"


def _registrar_cobertas(ids):
    e = ler_json(_estado_p()) if _estado_p().exists() else {}
    e["cobertas"] = sorted(set(e.get("cobertas", [])) | set(ids)); salvar_json(_estado_p(), e)


def pendentes():
    """Fichas decupadas do repertório que ainda não sustentaram nenhuma receita (aprovada, recusada ou em proposta)."""
    e = ler_json(_estado_p()) if _estado_p().exists() else {}
    cobertas = set(e.get("cobertas", [])) | {r for pr in propostas() for r in pr["proposta"].get("referencias", [])}
    fichas = [f for f in rep.listar()["fichas"] if f["decupada"]]
    novas = [f for f in fichas if f["id"] not in cobertas]
    return {"decupadas": len(fichas), "novas": len(novas), "ids": [f["id"] for f in novas], "por_formato": {k: sum(1 for f in novas if f["formato"] == k) for k in rep.FORMATOS if any(f["formato"] == k for f in novas)},
            "ultima_destilacao": e.get("destilado_em")}


_LIMPA = re.compile(r"[\"“”'‘’][^\"“”'‘’]*[\"“”'‘’]")


def destilar():
    """Sem modelo: medianas e padrões agregados por formato e o catálogo de efeitos, sem título, link, autor nem quadro, em
    `biblioteca-edicao/padroes/` (repositório de desenvolvimento) ou na biblioteca local (instalação de usuário)."""
    formatos = {}
    for f in rep.FORMATOS:
        c = rep.consultar(f, n=0, pacote=False)
        if c.get("n"):
            formatos[f] = {"descricao": rep.FORMATOS[f], "referencias": c["n"], "decupadas": c.get("decupadas", 0),
                           "alvos": {k: v for k, v in (c.get("alvos") or {}).items() if v is not None}, "padroes": c.get("padroes") or {}}
    efeitos = None
    try:
        from . import efeitos_ref
        cat = efeitos_ref.catalogo()
        efeitos = {"videos": cat["videos"], "efeitos": cat["efeitos"],
                   "temos": [{k: g[k] for k in ("recurso", "descricao", "videos", "usos", "igual", "parcial")} for g in cat["temos"]],
                   "lacunas": [{"familia": g["familia"], "efeito": _LIMPA.sub("", g["nome"]).strip(), "videos": g["videos"], "impacto": g["impacto"], "dificuldade": g["dificuldade"]}
                               for g in cat["faltam"]]}
    except ErroFerramenta:
        pass
    base = (OFICIAL if _repo_de_desenvolvimento() else _local()) / "padroes"
    hoje = datetime.now().strftime("%Y-%m-%d")
    salvar_json(base / "formatos.json", {"atualizado": hoje, **formatos})
    if efeitos:
        salvar_json(base / "efeitos.json", {"atualizado": hoje, **efeitos})
    e = ler_json(_estado_p()) if _estado_p().exists() else {}
    e["destilado_em"] = datetime.now().isoformat(timespec="seconds"); salvar_json(_estado_p(), e)
    if base.parent == OFICIAL:
        gerar_indice()
    return {"ok": True, "onde": str(base), "formatos": {k: v["referencias"] for k, v in formatos.items()}, "efeitos": bool(efeitos), "pendentes": pendentes()}


def gerar_indice():
    cs = _ler_pasta("oficial")
    pad = _padroes()
    linhas = ["# Biblioteca de edição do Editor GS", "",
              "Receitas de estilo profissional que o agente aplica pelo nome (`ver_estilo_edicao`). Cada uma traduz técnica estudada em referências",
              "para os parâmetros do motor; nenhuma carrega texto, imagem, áudio, nome ou link de quem fez a referência.",
              f"Gerado em {datetime.now().strftime('%d/%m/%Y')}: {len(cs)} receitas; padrões medidos em {sum(v.get('referencias', 0) for k, v in pad.items() if isinstance(v, dict))} referências.", "",
              "| Receita | Formatos | Temas | Energia | Base |", "|---|---|---|---|---|"]
    for c in sorted(cs, key=lambda c: (c.get("ordem", 99), c["nome"])):
        linhas.append(f"| **{c['nome']}** (`{c['id']}`) — {c['resumo']} | {', '.join(c['formatos'])} | {', '.join(c['temas'])} | {c['energia']} | `{c['base_estilo']}` |")
    linhas += ["", "Como cresce: ver `README.md`."]
    (OFICIAL / "INDICE.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return {"ok": True, "receitas": len(cs)}
