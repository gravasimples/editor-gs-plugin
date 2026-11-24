"""Campanhas e lançamentos (03/11/2026): agrupa as peças de uma campanha (Black, Níver, lançamento de aula…) com período, objetivo,
mensagem-chave e meta de peças, e soma os números do GSI no fim. A ligação peça → campanha é a etiqueta "campanha" da ficha da peça
(servico/pecas.py); criar a campanha também cria a etiqueta. Pedido aberto "para a campanha" já nasce com a etiqueta.
Peças orgânicas continuam sem preço, oferta ou falsa escassez (o revisor de marca segura). Só leitura no gs.db."""
import json, re, statistics, unicodedata
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
ARQ = _cam.estado("campanhas.json")
CAMPOS = ("nome", "inicio", "fim", "objetivo", "mensagem", "meta_pecas", "redes", "notas")


def _id(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "campanha"


def listar_bruto(arq: Path = None):
    try:
        return json.loads((arq or ARQ).read_text(encoding="utf-8"))
    except Exception:  # noqa
        return []


def _gravar(lista, arq: Path = None):
    (arq or ARQ).write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")


def _data(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:  # noqa
        return None


def salvar(dados: dict, arq: Path = None, por="Raphael"):
    """Cria ou atualiza (mesmo id) uma campanha. Nome obrigatório; fim não pode vir antes do início."""
    nome = (dados.get("nome") or "").strip()[:60]
    if not nome:
        raise ValueError("A campanha precisa de um nome.")
    ini, fim = _data(dados.get("inicio")), _data(dados.get("fim"))
    if dados.get("inicio") and not ini or dados.get("fim") and not fim:
        raise ValueError("Datas no formato AAAA-MM-DD.")
    if ini and fim and fim < ini:
        raise ValueError("O fim vem antes do início.")
    lista = listar_bruto(arq); cid = dados.get("id") or _id(nome)
    atual = next((c for c in lista if c["id"] == cid), None)
    if atual is None and any(c["id"] == cid for c in lista):
        raise ValueError("Já existe uma campanha com esse nome.")
    meta = dados.get("meta_pecas")
    item = {**(atual or {"id": cid, "criada": datetime.now().isoformat(timespec="minutes")}),
            "nome": nome, "inicio": ini.isoformat() if ini else None, "fim": fim.isoformat() if fim else None,
            "objetivo": (dados.get("objetivo") or "").strip()[:300], "mensagem": (dados.get("mensagem") or "").strip()[:300],
            "meta_pecas": int(meta) if str(meta or "").strip().isdigit() else None,
            "redes": [r for r in (dados.get("redes") if isinstance(dados.get("redes"), list) else str(dados.get("redes") or "").split(",")) if r.strip()],
            "notas": (dados.get("notas") or "").strip()[:1000], "atualizada": datetime.now().isoformat(timespec="minutes"), "por": por}
    item["redes"] = [r.strip() for r in item["redes"]]
    lista = [c for c in lista if c["id"] != cid] + [item]
    _gravar(lista, arq)
    return item


def apagar(cid: str, arq: Path = None):
    """Apaga só o registro da campanha; as peças mantêm a etiqueta."""
    lista = listar_bruto(arq); nova = [c for c in lista if c["id"] != cid]
    if len(nova) == len(lista):
        raise KeyError(cid)
    _gravar(nova, arq)


def situacao(c: dict, hoje: date = None):
    hoje = hoje or date.today(); ini, fim = _data(c.get("inicio")), _data(c.get("fim"))
    if ini and hoje < ini:
        return "planejada"
    if fim and hoje > fim:
        return "encerrada"
    return "no ar" if ini else "sem data"


def _mesma(a, b):
    return (a or "").strip().lower() == (b or "").strip().lower()


def resumo(c: dict, linhas: list, hoje: date = None):
    """Números da campanha a partir das linhas da tabela Peças (pecas.listar): peças, publicadas, views, mediana da razão, melhor peça,
    por formato, progresso da meta e sugestões (peças publicadas no período sem campanha)."""
    pecas = [l for l in linhas if _mesma(l["etiquetas"].get("campanha"), c["nome"])]
    pub = [l for l in pecas if l["estado"] == "postado ou agendado"]
    medidas = [l for l in pecas if l.get("views") is not None]
    razoes = [l["vs_mediana"] for l in medidas if l.get("vs_mediana") is not None]
    melhor = max(medidas, key=lambda l: (l.get("vs_mediana") or 0, l.get("views") or 0), default=None)
    formatos = {}
    for l in pecas:
        f = l["etiquetas"].get("formato") or "outro"; formatos[f] = formatos.get(f, 0) + 1
    ini, fim = _data(c.get("inicio")), _data(c.get("fim"))
    def no_periodo(l):
        d = _data(l.get("publicado_em"))
        return bool(d and ini and d >= ini and (not fim or d <= fim))
    sugestoes = [{"slug": l["slug"], "titulo": l["titulo"], "publicado_em": l.get("publicado_em")} for l in linhas
                 if no_periodo(l) and not l["etiquetas"].get("campanha") or (no_periodo(l) and _mesma(l["etiquetas"].get("campanha"), "Orgânico"))][:20]
    return {**c, "situacao": situacao(c, hoje), "n_pecas": len(pecas), "n_publicadas": len(pub), "n_medidas": len(medidas),
            "views": sum(l["views"] or 0 for l in medidas) if medidas else None, "razao_mediana": round(statistics.median(razoes), 2) if razoes else None,
            "melhor": {"slug": melhor["slug"], "titulo": melhor["titulo"], "views": melhor["views"], "vs_mediana": melhor.get("vs_mediana")} if melhor else None,
            "formatos": formatos, "progresso": round(len(pecas) / c["meta_pecas"], 2) if c.get("meta_pecas") else None,
            "pecas": [{"slug": l["slug"], "titulo": l["titulo"], "codigo": l.get("codigo"), "conversa": l.get("conversa"), "formato": l["etiquetas"].get("formato"), "estado": l["estado"],
                       "publicado_em": l.get("publicado_em"), "views": l.get("views"), "vs_mediana": l.get("vs_mediana")} for l in pecas],
            "sugestoes": sugestoes}


def texto_pedido(c: dict):
    """Linha que vai no pedido aberto "para a campanha", para o Editor saber o contexto."""
    partes = [f"Peça da campanha \"{c['nome']}\""]
    if c.get("objetivo"):
        partes.append(f"objetivo: {c['objetivo']}")
    if c.get("mensagem"):
        partes.append(f"mensagem-chave: {c['mensagem']}")
    if c.get("inicio") or c.get("fim"):
        partes.append(f"período {c.get('inicio') or '?'} a {c.get('fim') or '?'}")
    return "; ".join(partes) + ". Peça orgânica: sem preço, oferta, número de alunos ou falsa escassez."


def pedido_analise(r: dict):
    """Pedido de análise da campanha para o Editor (fluxo analise-resultados), com a tabela das peças."""
    L = [f"Análise da campanha \"{r['nome']}\" ({r.get('inicio') or '?'} a {r.get('fim') or '?'}; {r['situacao']}). Objetivo: {r.get('objetivo') or 'não informado'}.",
         f"Peças: {r['n_pecas']} (meta {r.get('meta_pecas') or '—'}), publicadas {r['n_publicadas']}, medidas {r['n_medidas']}, views somadas {r['views'] or '—'}, mediana da razão {r['razao_mediana'] or '—'}×.", "",
         "| Peça | Formato | Estado | Publicada | Views | Razão |", "|---|---|---|---|---|---|"]
    L += [f"| {p['titulo']} | {p['formato'] or '-'} | {p['estado']} | {(p['publicado_em'] or '-')[:10]} | {p['views'] if p['views'] is not None else '-'} | {p['vs_mediana'] if p['vs_mediana'] is not None else '-'} |" for p in r["pecas"]]
    L += ["", "Diga o que funcionou na campanha, o que não funcionou e 3 sugestões para a próxima, sem inventar número. Razão = views ÷ mediana do formato (1,0 = na média)."]
    return "\n".join(L)
