"""Ficha única da peça (item 1 da ordem aprovada pelo Raphael em 31/10/2026): cada entrega do Editor GS (saida/<slug>/) ganha etiquetas
(campanha, pilar, gancho, formato, CTA, voz, origem, redes) guardadas em saida/<slug>/peca.json, parte inferida dos arquivos e textos
e parte escolhida pelo humano; a ficha junta pedido, textos da entrega, arquivos, publicações e as métricas do GSI quando a peça
publicada casa com um vídeo do YouTube ou post do Instagram (por id do YouTube ou permalink da Publora). Base da aba Métricas e Automações.
Só leitura no gs.db; nada aqui publica."""
import json, re, sqlite3
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
ETIQUETAS_CFG = _cam.estado("etiquetas.json")
FORMATOS = ["reel", "story", "carrossel", "youtube", "short", "imagem", "apostila", "outro"]
VOZES = ["thiago", "clonada", "sintetica", "sem"]
ORIGENS = ["pedido", "ideia", "notion", "pulso", "automacao", "clipador", "referencia"]
REDES = ["instagram", "youtube", "tiktok", "facebook"]
PADRAO_CFG = {"campanhas": ["Orgânico", "Black", "Vitalício", "Lançamento"],
              "pilares": ["OBS passo a passo", "Áudio e vídeo", "Aulas e lives", "Bastidor", "Depoimentos", "Oferta"],
              "ctas": ["seguir", "salvar", "compartilhar", "comentar palavra-chave", "link na bio", "nenhum"]}


def config(cfg: Path = None):
    p = cfg or ETIQUETAS_CFG
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        d = {}
    out = dict(PADRAO_CFG); out.update({k: v for k, v in d.items() if isinstance(v, list)})
    return out


def config_adicionar(campo, valor, cfg: Path = None):
    """Acrescenta um valor à lista (campanhas, pilares, ctas) e grava."""
    if campo not in PADRAO_CFG:
        raise ValueError("campo deve ser campanhas, pilares ou ctas")
    valor = (valor or "").strip()[:60]
    if not valor:
        raise ValueError("valor vazio")
    p = cfg or ETIQUETAS_CFG
    d = config(p)
    if valor not in d[campo]:
        d[campo].append(valor)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def _json(p: Path, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return padrao if padrao is not None else {}


def inferir(pasta: Path, secoes=None, conversa=None):
    """Etiquetas automáticas a partir do que já existe na pasta da entrega, nos textos e na conversa. Nunca sobrescreve escolha humana."""
    auto = {}
    nomes = {p.name for p in pasta.iterdir()} if pasta.exists() else set()
    if any(n.startswith("carrossel") for n in nomes) or any(re.match(r"slide-\d+\.png", n) for n in nomes):
        auto["formato"] = "carrossel"
    elif any(n.startswith("apostila") and n.endswith(".pdf") for n in nomes):
        auto["formato"] = "apostila"
    elif "final_9x16.mp4" in nomes:
        auto["formato"] = "reel"
    elif "final_16x9.mp4" in nomes:
        auto["formato"] = "youtube"
    elif any(n.endswith(".mp4") for n in nomes):
        auto["formato"] = "outro"
    elif any(n.endswith(".png") for n in nomes):
        auto["formato"] = "imagem"
    # voz: palavras.json das entregas
    for p in list(pasta.glob("*palavras*.json")) + list(pasta.glob("*.palavras.json")) if pasta.exists() else []:
        d = _json(p)
        o = d.get("origem")
        if o == "tts-clonada":
            auto["voz"] = "clonada"; break
        if o in ("tts", "dublagem"):
            auto["voz"] = "sintetica"; break
        if o == "transcricao" or d.get("palavras"):
            auto["voz"] = "thiago"
    if "voz" not in auto and auto.get("formato") in ("carrossel", "apostila", "imagem"):
        auto["voz"] = "sem"
    for s in secoes or []:
        if s.get("chave") == "gancho" and s.get("conteudo"):
            linha = next((re.sub(r"\*+|__|`", "", l).strip(" -*0123456789.)\"“”") for l in s["conteudo"].splitlines() if l.strip()), "")  # sem Markdown
            if linha:
                auto["gancho"] = linha[:140]
            break
    c = conversa or {}
    if c.get("notion_page"):
        auto["origem"] = "notion"
    elif c.get("corte_de") or "corte-" in (c.get("slug") or ""):
        auto["origem"] = "clipador"
    elif (c.get("pasta") or "") == "Pulso do GSI" or (c.get("origem") == "pulso"):
        auto["origem"] = "pulso"
    elif (c.get("pasta") or "") == "Automações" or (c.get("origem") == "automacao"):
        auto["origem"] = "automacao"
    elif c.get("referencia"):
        auto["origem"] = "referencia"
    return auto


def ler(pasta: Path):
    return _json(pasta / "peca.json", {})


def etiquetas(pasta: Path, secoes=None, conversa=None):
    """Etiquetas efetivas: humanas por cima das inferidas. Devolve {"etiquetas", "auto", "humanas", "atualizado", "por"}."""
    d = ler(pasta)
    auto = inferir(pasta, secoes, conversa)
    hum = dict(d.get("etiquetas") or {})
    ef = dict(auto); ef.update({k: v for k, v in hum.items() if v not in (None, "", [])})
    return {"etiquetas": ef, "auto": auto, "humanas": hum, "atualizado": d.get("atualizado"), "por": d.get("por")}


def gravar(pasta: Path, campos: dict, por="Raphael"):
    """Grava as etiquetas humanas (só os campos enviados; valor vazio apaga o campo). Valida listas fechadas."""
    pasta.mkdir(parents=True, exist_ok=True)
    d = ler(pasta); hum = dict(d.get("etiquetas") or {})
    for k, v in campos.items():
        if k not in ("campanha", "pilar", "gancho", "formato", "cta", "voz", "origem", "redes", "nota"):
            continue
        if v in (None, "", []):
            hum.pop(k, None); continue
        if k == "formato" and v not in FORMATOS:
            raise ValueError(f"formato deve ser um de {', '.join(FORMATOS)}")
        if k == "voz" and v not in VOZES:
            raise ValueError(f"voz deve ser um de {', '.join(VOZES)}")
        if k == "origem" and v not in ORIGENS:
            raise ValueError(f"origem deve ser um de {', '.join(ORIGENS)}")
        if k == "redes":
            v = [x for x in (v if isinstance(v, list) else str(v).split(",")) if x.strip() in REDES]
            v = [x.strip() for x in v]
        if isinstance(v, str):
            v = v.strip()[:200]
        hum[k] = v
    d.update(etiquetas=hum, atualizado=datetime.now().isoformat(timespec="seconds"), por=por)
    (pasta / "peca.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def publicacoes(pasta: Path):
    return _json(pasta / "publicacoes.json", [])


# --- Licença por ativo (10/11/2026, ideia 8 da pesquisa de referências) -------------------------------------------------------
LICENCAS = ["proprio", "cc0", "pexels", "pixabay", "cc-by", "nc", "desconhecida"]
_EXT_ATIVO = r"(?:mp4|mov|webm|mkv|mp3|wav|m4a|ogg|flac|aac|png|jpe?g|webp)"
_RE_BANCO = re.compile(r"banco/([\w\-]+)/([\w\-]+)\." + _EXT_ATIVO, re.I)
_RE_TRILHA = re.compile(r"trilhas?/([\w\-. ]+?\.(?:mp3|wav|m4a|ogg|flac|aac))", re.I)
_TEXTOS_ATIVOS = {".json", ".md", ".txt", ".srt"}
_LIMITE_TEXTO = 2 * 1024 * 1024


def licenca_normalizar(texto):
    """Texto livre de licença (do `.licenca.json` do banco ou da tabela de trilhas) → uma das LICENCAS."""
    t = (texto or "").strip().lower()
    if not t:
        return "desconhecida"
    if "material da empresa" in t or "própri" in t or "propri" in t or "comprad" in t or "grava simples" in t:
        return "proprio"
    if re.search(r"\bnc\b|n[aã]o.comercial|non.?commercial", t):
        return "nc"
    if "cc0" in t or "cc 0" in t or "domínio público" in t or "dominio publico" in t or "public domain" in t:
        return "cc0"
    if "pexels" in t:
        return "pexels"
    if "pixabay" in t:
        return "pixabay"
    if re.search(r"cc.?by|creative commons|atribui|attribution|cr[eé]dito", t):
        return "cc-by"
    return "desconhecida"


def _tabela_trilhas(trilhas: Path):
    """Tabela `| Arquivo | Origem | Licença | Observação |` do trilhas/README.md → {arquivo: {origem, licenca, observacao}}."""
    out = {}
    readme = Path(trilhas) / "README.md" if trilhas else None
    if not readme or not readme.is_file():
        return out
    for linha in readme.read_text(encoding="utf-8").splitlines():
        if not linha.strip().startswith("|"):
            continue
        cels = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(cels) < 3 or cels[0].lower() in ("arquivo", "") or set(cels[0]) <= {"-", " ", ":"} or cels[0].startswith("("):
            continue
        out[cels[0].strip("`")] = {"origem": cels[1], "licenca": cels[2], "observacao": cels[3] if len(cels) > 3 else ""}
    return out


def _referencias(pasta: Path, secoes=None):
    """Caminhos de banco e trilhas citados nos textos da entrega (json/md/txt/srt da pasta, inclusive _trabalho) e nas seções da mensagem final."""
    textos = []
    if pasta.is_dir():
        for p in pasta.rglob("*"):
            if p.is_file() and p.suffix.lower() in _TEXTOS_ATIVOS and p.name != "peca.json" and "_checkpoints" not in p.parts and p.stat().st_size <= _LIMITE_TEXTO:  # peca.json guarda a própria lista: não se cita
                try:
                    textos.append(p.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
    textos += [s.get("conteudo") or "" for s in (secoes or [])]
    banco, trilhas = {}, {}
    for t in textos:
        for m in _RE_BANCO.finditer(t):
            banco[(m.group(1).lower(), m.group(2))] = m.group(0)
        for m in _RE_TRILHA.finditer(t):
            trilhas[m.group(1).strip()] = m.group(1).strip()
    return banco, trilhas, "\n".join(textos)


def ativos(pasta: Path, secoes=None, banco: Path = None, trilhas: Path = None):
    """Ativos de terceiros usados na peça, com licença: material do banco (workspace/banco/<fonte>/<id>.licenca.json, que o motor grava ao
    baixar) e trilhas (tabela do trilhas/README.md). Só o que a entrega cita; sem material registrado, []. Também lê `ativos.json`
    da pasta, se o agente deixar um. Devolve ({ativos}, {alertas})."""
    banco = Path(banco) if banco else _cam.WORKSPACE / "banco"
    trilhas = Path(trilhas) if trilhas else _cam.TRILHAS
    out, vistos = [], set()

    def add(a):
        if a["arquivo"] in vistos:
            return
        vistos.add(a["arquivo"]); out.append(a)

    for a in _json(pasta / "ativos.json", []) if pasta.is_dir() else []:
        if isinstance(a, dict) and a.get("arquivo"):
            add({"arquivo": str(a["arquivo"]), "origem": a.get("origem") or "", "licenca": a["licenca"] if a.get("licenca") in LICENCAS else licenca_normalizar(a.get("licenca")),
                 "atribuicao": a.get("atribuicao") or None, "url": a.get("url") or None})
    ref_banco, ref_trilhas, texto_todo = _referencias(pasta, secoes)
    tabela = _tabela_trilhas(trilhas)
    for nome in tabela:  # o motor devolve só o nome da trilha (`"trilha": "calma-piano.mp3"`); o agente cita assim no Resumo
        if nome and nome in texto_todo:
            ref_trilhas.setdefault(nome, nome)
    for (fonte, ident), caminho in sorted(ref_banco.items()):
        lic = _json(banco / fonte / f"{ident}.licenca.json", None)
        if lic:
            add({"arquivo": caminho, "origem": lic.get("origem") or fonte, "licenca": licenca_normalizar(lic.get("licenca")), "atribuicao": lic.get("atribuicao") or None, "url": lic.get("url") or None, "autor": lic.get("autor")})
        else:
            add({"arquivo": caminho, "origem": fonte, "licenca": "desconhecida", "atribuicao": None, "url": None})
    for nome in sorted(ref_trilhas):
        t = tabela.get(nome) or tabela.get(Path(nome).name)
        if t:
            add({"arquivo": f"trilhas/{nome}", "origem": t["origem"], "licenca": licenca_normalizar(t["licenca"]), "atribuicao": (t.get("observacao") or None), "url": None})
        else:
            add({"arquivo": f"trilhas/{nome}", "origem": "trilhas/ (sem linha na tabela do README)", "licenca": "desconhecida", "atribuicao": None, "url": None})
    return out, alertas_de(out)


def alertas_de(lista):
    """Regras: cc-by sem atribuição e nc avisam; licença desconhecida também (não dá para publicar sem saber)."""
    al = []
    for a in lista:
        nome = Path(a["arquivo"]).name
        tipo = "Trilha" if a["arquivo"].startswith("trilhas/") or Path(nome).suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac") else "Vídeo" if Path(nome).suffix.lower() in (".mp4", ".mov", ".webm", ".mkv") else "Imagem"
        if a["licenca"] == "cc-by" and not a.get("atribuicao"):
            al.append({"arquivo": a["arquivo"], "tipo": "cc-by-sem-credito", "msg": f"{tipo} {nome} é CC-BY sem crédito na legenda"})
        elif a["licenca"] == "nc":
            al.append({"arquivo": a["arquivo"], "tipo": "nc", "msg": f"{tipo} {nome} é só para uso não comercial"})
        elif a["licenca"] == "desconhecida":
            al.append({"arquivo": a["arquivo"], "tipo": "desconhecida", "msg": f"{tipo} {nome} sem licença registrada"})
    return al


def ativos_atualizar(pasta: Path, secoes=None, banco: Path = None, trilhas: Path = None):
    """Calcula ativos e alertas e grava em peca.json quando mudaram (sem mexer nas etiquetas). Devolve (ativos, alertas)."""
    lista, al = ativos(pasta, secoes, banco, trilhas)
    if pasta.is_dir():
        d = ler(pasta)
        if d.get("ativos") != lista or d.get("alertas") != al:
            d["ativos"] = lista; d["alertas"] = al
            (pasta / "peca.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return lista, al


def _ids_publicados(pubs):
    """Ids externos a partir dos registros: YouTube (id do vídeo) e Instagram (shortcode pelo permalink)."""
    out = []
    for r in pubs:
        t = r.get("tipo")
        if t == "youtube":
            vid = r.get("id") or r.get("video_id") or (r.get("video") or {}).get("id")
            if vid:
                out.append(("youtube", str(vid)))
        for p in r.get("posts") or []:
            link = p.get("permalink") or ""
            m = re.search(r"instagram\.com/(?:p|reel|reels)/([\w\-]+)", link)
            if m:
                out.append(("instagram", m.group(1)))
            m = re.search(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/))([\w\-]+)", link)
            if m:
                out.append(("youtube", m.group(1)))
    return out


def metricas(db: Path, ids):
    """Último snapshot current do GSI para cada id publicado + razão sobre a mediana do formato. Vazio sem banco ou sem casamento."""
    if not ids or not Path(db).exists():
        return []
    con = sqlite3.connect(str(db)); con.row_factory = sqlite3.Row
    out = []
    for plat, item in ids:
        r = con.execute("""select platform, item_id, views, likes, comments, engagement_rate, format, theme, ratio_vs_format_median, median_views_format, computed_at, age_days
                           from performance_snapshots where platform=? and item_id=? and horizon='current' order by computed_at desc limit 1""", (plat, item)).fetchone()
        if r:
            out.append({k: r[k] for k in r.keys()})
        else:
            out.append({"platform": plat, "item_id": item, "views": None, "aviso": "ainda sem snapshot no GSI"})
    con.close()
    return out


def ficha(slug, saida: Path, db: Path, cache_textos=None, entregas=None, conversa=None):
    """Tudo da peça num lugar: etiquetas, textos da entrega (cache), arquivos, publicações, métricas."""
    pasta = saida / slug
    item = next((v for v in (cache_textos or {}).values() if v.get("slug") == slug), None)
    secoes = (item or {}).get("secoes") or []
    conv = dict(conversa or {})
    if item:
        conv.setdefault("id", item.get("id")); conv.setdefault("codigo", item.get("codigo")); conv.setdefault("titulo", item.get("titulo")); conv.setdefault("pasta", item.get("pasta")); conv.setdefault("slug", slug)
    et = etiquetas(pasta, secoes, conv)
    pubs = publicacoes(pasta)
    ids = _ids_publicados(pubs)
    textos = {s["chave"]: s["conteudo"] for s in secoes if s.get("chave") in ("roteiro", "descricao", "hashtags", "titulo", "gancho", "resumo", "pendencias", "gravar")}
    lista_ativos, alertas = ativos_atualizar(pasta, secoes)
    return {"slug": slug, "conversa": {k: conv.get(k) for k in ("id", "codigo", "titulo", "pasta", "status", "notion_page")}, **et, "textos": textos, "ativos": lista_ativos, "alertas": alertas,
            "arquivos": entregas or [], "publicacoes": pubs, "ids_publicados": [{"plataforma": p, "id": i} for p, i in ids], "metricas": metricas(db, ids),
            "experimento": _json(pasta / "experimento.json", None),  # Reel reciclado: "mesma peça, outro gancho" (original, gancho antigo e novo)
            "estado": "postado ou agendado" if any(r.get("tipo") in ("publora", "youtube") for r in pubs) else ("no Drive" if any(r.get("tipo") == "drive" for r in pubs) else "ainda não usado")}


def listar(saida: Path, db: Path, cache_textos=None, filtros=None):
    """Uma linha por entrega: etiquetas efetivas, estado, conversa, última métrica (views, razão). Para a tabela Peças."""
    filtros = filtros or {}
    por_slug = {v.get("slug"): v for v in (cache_textos or {}).values() if v.get("slug")}
    out = []
    for d in sorted((p for p in saida.iterdir() if p.is_dir() and not p.name.startswith("_")), key=lambda p: p.stat().st_mtime, reverse=True) if saida.exists() else []:
        item = por_slug.get(d.name) or {}
        secoes = item.get("secoes") or []
        conv = {"id": item.get("id"), "codigo": item.get("codigo"), "titulo": item.get("titulo"), "pasta": item.get("pasta"), "slug": d.name}
        et = etiquetas(d, secoes, conv)["etiquetas"]
        pubs = publicacoes(d); ids = _ids_publicados(pubs); mets = metricas(db, ids)
        melhor = next((m for m in mets if m.get("views") is not None), None)
        linha = {"slug": d.name, "titulo": item.get("titulo") or d.name, "conversa": item.get("id"), "codigo": item.get("codigo"), "pasta": item.get("pasta"), "modificado": datetime.fromtimestamp(d.stat().st_mtime).isoformat(timespec="minutes"),
                 "etiquetas": et, "estado": "postado ou agendado" if any(r.get("tipo") in ("publora", "youtube") for r in pubs) else ("no Drive" if any(r.get("tipo") == "drive" for r in pubs) else "ainda não usado"),
                 "publicado_em": next((r.get("quando") for r in pubs if r.get("tipo") in ("publora", "youtube")), None),
                 "views": (melhor or {}).get("views"), "vs_mediana": (melhor or {}).get("ratio_vs_format_median"), "plataforma": (melhor or {}).get("platform"), "medido_em": (melhor or {}).get("computed_at"),
                 "alertas": len(ler(d).get("alertas") or [])}  # só o que já está gravado em peca.json (a ficha recalcula); a lista não varre arquivos
        ok = True
        for k in ("campanha", "pilar", "formato", "voz", "origem"):
            if filtros.get(k) and et.get(k) != filtros[k]:
                ok = False
        if filtros.get("estado") and linha["estado"] != filtros["estado"]:
            ok = False
        if filtros.get("q"):
            q = filtros["q"].lower()
            if q not in f"{linha['titulo']} {d.name} {et.get('gancho','')} {et.get('campanha','')} {et.get('pilar','')}".lower():
                ok = False
        if ok:
            out.append(linha)
    return out


def resumo(linhas):
    """Contagens para os filtros da tabela: por campanha, pilar, formato, estado; quantas sem etiqueta."""
    def conta(k):
        c = {}
        for l in linhas:
            v = l["etiquetas"].get(k) or "(sem)"
            c[v] = c.get(v, 0) + 1
        return c
    return {"total": len(linhas), "campanhas": conta("campanha"), "pilares": conta("pilar"), "formatos": conta("formato"), "estados": {e: sum(1 for l in linhas if l["estado"] == e) for e in ("postado ou agendado", "no Drive", "ainda não usado")},
            "sem_etiqueta": sum(1 for l in linhas if not l["etiquetas"].get("campanha") or not l["etiquetas"].get("pilar")), "com_metrica": sum(1 for l in linhas if l["views"] is not None)}
