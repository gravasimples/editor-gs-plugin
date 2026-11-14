"""Fichas de marca para o app e para o Editor: manual da marca e tom de voz (contexto/ do GSI, só leitura)
e produtos/ofertas do gs.db (só leitura). Nada aqui valida claim: preço, oferta e número de alunos continuam
sujeitos ao estado registrado no GSI (observed, pending_validation…) e à aprovação humana."""
import json, re, sqlite3
from datetime import datetime
from pathlib import Path

ARQUIVOS = {"manual": "contexto/manual-marca-grava-simples.md", "voz": "contexto/tom-de-voz.md", "produtos_md": "contexto/produtos.md"}
AVISO_PRODUTOS = ("Preço, oferta, número de alunos e promessa comercial NÃO são claims autorizados: aparecem aqui com o estado em que o GSI os "
                  "registrou e a data em que foram vistos. Não cite preço nem oferta numa entrega sem pedido explícito e aprovação humana. "
                  "Produto ou oferta marcados como pendentes de validação não entram em conteúdo.")


def _secoes(md: str):
    """Divide um Markdown em seções pelo título de nível 2. O que vem antes do primeiro `## ` vira a seção 'Introdução'."""
    secoes, titulo, corpo = [], None, []
    for linha in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", linha)
        if m:
            if titulo is not None or any(l.strip() for l in corpo):
                secoes.append({"titulo": titulo or "Introdução", "conteudo": "\n".join(corpo).strip()})
            titulo, corpo = m.group(1), []
        elif not linha.startswith("# "):
            corpo.append(linha)
    if titulo is not None or any(l.strip() for l in corpo):
        secoes.append({"titulo": titulo or "Introdução", "conteudo": "\n".join(corpo).strip()})
    return [s for s in secoes if s["conteudo"]]


def _ler(raiz_gsi: Path, chave: str):
    p = raiz_gsi / ARQUIVOS[chave]
    if not p.exists():
        return {"arquivo": str(p), "existe": False, "atualizado": None, "secoes": [], "texto": ""}
    txt = p.read_text(encoding="utf-8")
    return {"arquivo": str(p), "existe": True, "atualizado": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes"), "secoes": _secoes(txt), "texto": txt}


def _json(v, padrao):
    try:
        return json.loads(v) if v else padrao
    except Exception:
        return padrao


def produtos(db: Path):
    """Produtos e ofertas do gs.db, só leitura, com estado e pendências. Sem PII: as tabelas são catálogo público."""
    if not db.exists():
        return {"erro": f"banco do GSI não encontrado: {db}", "itens": []}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
    try:
        prods = con.execute("SELECT * FROM products ORDER BY CASE category WHEN 'course' THEN 0 WHEN 'bundle' THEN 1 WHEN 'service' THEN 2 ELSE 3 END, name").fetchall()
        ofertas = con.execute("SELECT * FROM offers ORDER BY observed_on DESC").fetchall()
    finally:
        con.close()
    por_produto = {}
    for o in ofertas:
        por_produto.setdefault(o["product_slug"], []).append({
            "id": o["offer_id"], "nome": o["name"], "preco": o["price"], "moeda": o["currency"] or "BRL", "parcelas": o["installments"], "valor_parcela": o["installment_value"],
            "acesso": o["access_period"], "url": o["sales_url"], "visto_em": o["observed_on"], "status": o["status"], "confianca": o["confidence"], "notas": o["notes"]})
    itens = []
    for p in prods:
        itens.append({"slug": p["product_slug"], "nome": p["name"], "apelidos": _json(p["aliases_json"], []), "categoria": p["category"], "componentes": _json(p["components_json"], []),
                      "publico": p["audience"], "problema": p["problem"], "promessa": p["promise"], "entregaveis": _json(p["deliverables_json"], []),
                      "status": p["status"], "confianca": p["confidence"], "fonte": p["source"], "pendencias": _json(p["pending_fields_json"], []), "notas": p["notes"],
                      "ofertas": por_produto.get(p["product_slug"], [])})
    return {"itens": itens, "n_ofertas": len(ofertas), "aviso": AVISO_PRODUTOS}


def ficha(raiz_gsi: Path, db: Path):
    return {"manual": _ler(raiz_gsi, "manual"), "voz": _ler(raiz_gsi, "voz"), "produtos_md": _ler(raiz_gsi, "produtos_md"), "produtos": produtos(db),
            "gerado_em": datetime.now().isoformat(timespec="seconds")}


def _preco(o):
    if o["preco"] is None:
        return "preço não registrado"
    base = f"R$ {o['preco']:.2f}".replace(".", ",")
    if o["parcelas"] and o["valor_parcela"]:
        base += f" ou {o['parcelas']}× R$ {o['valor_parcela']:.2f}".replace(".", ",")
    return base


def produtos_markdown(d):
    """produtos.md para o Editor: ficha curta por produto com estado explícito; ofertas listadas com data e status."""
    L = ["# Produtos da Grava Simples — ficha para o Editor", "", f"Gerado em {datetime.now():%d/%m/%Y %H:%M} a partir do gs.db do GSI (só leitura).", "", f"> {AVISO_PRODUTOS}", ""]
    rot = {"observed": "observado", "validated": "validado", "hypothesis": "hipótese", "pending_validation": "PENDENTE DE VALIDAÇÃO", "outdated": "desatualizado"}
    cat = {"course": "curso", "bundle": "combo", "service": "serviço", "community": "comunidade", "digital_asset": "ativo digital", "checklist": "checklist", "program": "programa", "upgrade": "upgrade", "unknown": "?"}
    for p in d.get("itens", []):
        L.append(f"## {p['nome']} (`{p['slug']}`) — {cat.get(p['categoria'], p['categoria'] or '?')}, estado: {rot.get(p['status'], p['status'])}")
        if p["apelidos"]:
            L.append(f"- Também chamado: {', '.join(p['apelidos'])}")
        if p["publico"]:
            L.append(f"- Público: {p['publico']}")
        if p["problema"]:
            L.append(f"- Problema que resolve: {p['problema']}")
        if p["promessa"]:
            L.append(f"- Promessa (texto da página, não claim seu): {p['promessa']}")
        if p["entregaveis"]:
            L.append(f"- Entregáveis: {', '.join(p['entregaveis'])}")
        if p["componentes"]:
            L.append(f"- Inclui: {', '.join(p['componentes'])}")
        for o in p["ofertas"]:
            L.append(f"- Oferta `{o['id']}`: {_preco(o)}{' · ' + o['acesso'] if o['acesso'] else ''} · visto em {o['visto_em']} · estado {rot.get(o['status'], o['status'])}{' · ' + o['url'] if o['url'] else ''}")
        if p["pendencias"]:
            L.append(f"- Pendências (não afirmar): {'; '.join(p['pendencias'])}")
        L.append("")
    return "\n".join(L)


def gravar(raiz_gsi: Path, db: Path, destino: Path):
    """Escreve a cópia para o Editor em `destino/` (manual.md, voz.md, produtos.md) e devolve a ficha."""
    d = ficha(raiz_gsi, db)
    destino.mkdir(parents=True, exist_ok=True)
    cab = f"<!-- Cópia só leitura gerada pelo gateway do Editor GS em {datetime.now():%d/%m/%Y %H:%M}. A fonte é o GSI; não edite aqui. -->\n\n"
    for chave, nome in (("manual", "manual.md"), ("voz", "voz.md")):
        if d[chave]["existe"]:
            (destino / nome).write_text(cab + d[chave]["texto"], encoding="utf-8")
    if not d["produtos"].get("erro"):
        (destino / "produtos.md").write_text(produtos_markdown(d["produtos"]), encoding="utf-8")
    d["arquivos"] = sorted(p.name for p in destino.glob("*.md"))
    d["destino"] = str(destino)
    return d
