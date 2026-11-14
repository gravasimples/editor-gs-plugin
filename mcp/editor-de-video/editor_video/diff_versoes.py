"""Diff "o que mudou" entre duas versões (10/11/2026): EDL (trechos tirados/devolvidos), plano de grafismos (itens que entraram, saíram ou
mudaram de lugar) e estilo (chaves alteradas). Devolve JSON estruturado + `resumo` em frases curtas para o cartão da conversa. Sem ffmpeg."""
import json
from pathlib import Path
from .util import ler_json, ErroFerramenta

MOTIVO_NOME = {"pausa": "a pausa", "refação (frase repetida)": "a refação", "vício de linguagem isolado": "o vício de linguagem",
               "recomeço (tomada abandonada)": "o recomeço"}


def mmss(s):
    """0:12 ou 0:12,4 (décimo só quando não é inteiro)."""
    s = max(0.0, float(s)); m = int(s // 60); r = s - m * 60
    txt = f"{m}:{r:04.1f}".replace(".", ",")
    return txt[:-2] if txt.endswith(",0") else txt


def _carregar(obj):
    """Caminho de arquivo, JSON em texto, dict ou lista → objeto."""
    if obj is None:
        return None
    if isinstance(obj, (dict, list)):
        return obj
    t = str(obj).strip()
    if t.startswith(("{", "[")):
        return json.loads(t)
    return ler_json(Path(t))


def _par(a, b, nome):
    if (a is None) != (b is None):
        raise ErroFerramenta(f"{nome}: informe os dois lados (a e b) ou nenhum")
    return a is not None


# --- EDL --------------------------------------------------------------------------------------------------------

def _intervalos(edl):
    return sorted((float(m["inicio"]), float(m["fim"])) for m in edl.get("manter", []) if float(m["fim"]) > float(m["inicio"]))


def _diferenca(xs, ys):
    """Partes de xs que não estão em ys (intervalos ordenados, no tempo do bruto)."""
    out = []
    for a, z in xs:
        cursor = a
        for p, q in ys:
            if q <= cursor or p >= z:
                continue
            if p > cursor:
                out.append((cursor, min(p, z)))
            cursor = max(cursor, q)
            if cursor >= z:
                break
        if cursor < z:
            out.append((cursor, z))
    return [(round(a, 3), round(z, 3)) for a, z in out if z - a >= 0.02]


def _motivo_em(edl, a, z):
    """Motivo registrado na EDL para o trecho (o removido que mais cobre o intervalo)."""
    melhor, cob = None, 0.0
    for r in edl.get("removidos", []):
        c = min(z, float(r["fim"])) - max(a, float(r["inicio"]))
        if c > cob:
            melhor, cob = r, c
    return melhor


def comparar_edl(edl_a, edl_b):
    """A → B: `tirou` = estava em A e saiu em B; `voltou` = não estava em A e entrou em B. Tempos no vídeo bruto."""
    ia, ib = _intervalos(edl_a), _intervalos(edl_b)
    tirou = [{"inicio": a, "fim": z, "duracao_s": round(z - a, 2), "motivo": (_motivo_em(edl_b, a, z) or {}).get("motivo"), "texto": (_motivo_em(edl_b, a, z) or {}).get("texto", "")}
             for a, z in _diferenca(ia, ib)]
    voltou = [{"inicio": a, "fim": z, "duracao_s": round(z - a, 2)} for a, z in _diferenca(ib, ia)]
    dur_a = round(sum(z - a for a, z in ia), 2); dur_b = round(sum(z - a for a, z in ib), 2)
    frases = []
    for t in tirou:
        nome = MOTIVO_NOME.get(t["motivo"] or "", "o trecho")
        fala = f' ("{t["texto"][:40]}")' if t.get("texto") and nome == "o trecho" else ""
        frases.append(f"Tirou {nome} de {mmss(t['inicio'])} a {mmss(t['fim'])}{fala}.")
    for v in voltou:
        frases.append(f"Voltou o trecho de {mmss(v['inicio'])} a {mmss(v['fim'])}.")
    if dur_a != dur_b:
        frases.append(f"Duração: {dur_a:.1f} s → {dur_b:.1f} s.".replace(".", ","))
    return {"tirou": tirou, "voltou": voltou, "duracao_a_s": dur_a, "duracao_b_s": dur_b, "trechos_a": len(ia), "trechos_b": len(ib)}, frases


# --- Grafismos ----------------------------------------------------------------------------------------------------

def _itens_grafismos(plano):
    if isinstance(plano, dict):
        plano = plano.get("itens", [])
    return [dict(g) for g in (plano or []) if isinstance(g, dict) and g.get("tipo")]


def _chave(g):
    """Identidade do item sem o tempo: tipo + textos (o que muda de lugar continua sendo o mesmo item)."""
    sub = tuple(str(it.get("texto") or it.get("logo") or it.get("icone") or it) for it in (g.get("itens") or []))
    return (str(g["tipo"]).lower(), str(g.get("texto", "")), str(g.get("rotulo", "")), str(g.get("troca", "")), sub)


def _onde(g):
    if g.get("inicio") is not None:
        return f"em {mmss(g['inicio'])}"
    if g.get("palavra"):
        return f"na palavra '{g['palavra']}'"
    return "sem instante"


def _nome(g):
    t = g.get("texto") or g.get("rotulo") or ", ".join(str(it.get("texto") or it.get("logo") or it.get("icone") or "") for it in (g.get("itens") or [])[:3])
    return f"{g['tipo']} '{t}'" if t else str(g["tipo"])


def comparar_grafismos(plano_a, plano_b):
    """Itens que entraram, saíram ou mudaram de instante/palavra entre dois planos (arquivo, JSON ou dict)."""
    a, b = _itens_grafismos(plano_a), _itens_grafismos(plano_b)
    ka = {}; kb = {}
    for g in a:
        ka.setdefault(_chave(g), []).append(g)
    for g in b:
        kb.setdefault(_chave(g), []).append(g)
    entrou, saiu, moveu = [], [], []
    for k, gs in kb.items():
        for g in gs[len(ka.get(k, [])):]:
            entrou.append(g)
    for k, gs in ka.items():
        for g in gs[len(kb.get(k, [])):]:
            saiu.append(g)
    for k in ka.keys() & kb.keys():
        for ga, gb in zip(ka[k], kb[k]):
            mudou = {}
            for campo in ("inicio", "fim", "palavra", "posicao", "tela_cheia"):
                if ga.get(campo) != gb.get(campo):
                    mudou[campo] = {"de": ga.get(campo), "para": gb.get(campo)}
            if mudou:
                moveu.append({"item": gb, "mudou": mudou})
    frases = [f"Entrou o gráfico {_nome(g)} {_onde(g)}." for g in entrou] + [f"Saiu o gráfico {_nome(g)} ({_onde(g)})." for g in saiu]
    for m in moveu:
        g = m["item"]; de = m["mudou"]
        if "inicio" in de or "palavra" in de:
            origem = f"de {mmss(de['inicio']['de'])}" if "inicio" in de and de["inicio"]["de"] is not None else (f"da palavra '{de['palavra']['de']}'" if "palavra" in de else "")
            frases.append(f"O gráfico {_nome(g)} mudou {origem} para {_onde(g)[3:] if _onde(g).startswith('em ') else _onde(g)}.".replace("  ", " "))
        else:
            frases.append(f"O gráfico {_nome(g)} mudou {', '.join(de)}.")
    return {"entrou": entrou, "saiu": saiu, "moveu": moveu, "n_a": len(a), "n_b": len(b)}, frases


# --- Estilo -------------------------------------------------------------------------------------------------------

def _achatar(d, prefixo=""):
    out = {}
    for k, v in (d or {}).items():
        nome = f"{prefixo}{k}"
        if isinstance(v, dict):
            out.update(_achatar(v, nome + "."))
        else:
            out[nome] = v
    return out


def comparar_estilo(estilo_a, estilo_b):
    """Chaves (achatadas, ex.: legenda.cor_destaque) que mudaram, entraram ou saíram. `nome` é ignorado."""
    fa, fb = _achatar(estilo_a), _achatar(estilo_b)
    fa.pop("nome", None); fb.pop("nome", None)
    mudou = {k: {"de": fa[k], "para": fb[k]} for k in fa.keys() & fb.keys() if fa[k] != fb[k]}
    entrou = {k: fb[k] for k in fb.keys() - fa.keys()}
    saiu = {k: fa[k] for k in fa.keys() - fb.keys()}
    frases = [f"Estilo: {k} de {v['de']} para {v['para']}." for k, v in sorted(mudou.items())]
    frases += [f"Estilo: {k} = {v} (novo)." for k, v in sorted(entrou.items())]
    frases += [f"Estilo: {k} saiu (era {v})." for k, v in sorted(saiu.items())]
    return {"mudou": mudou, "entrou": entrou, "saiu": saiu}, frases


# --- Tudo junto ---------------------------------------------------------------------------------------------------

def comparar_versoes(edl_a=None, edl_b=None, grafismos_a=None, grafismos_b=None, estilo_a=None, estilo_b=None):
    """Compara os pares informados (cada um pode faltar). Devolve `cortes`, `grafismos`, `estilo` (None quando o par não veio), `mudou` e `resumo`."""
    res = {"cortes": None, "grafismos": None, "estilo": None}; frases = []
    if _par(edl_a, edl_b, "edl"):
        res["cortes"], f = comparar_edl(_carregar(edl_a), _carregar(edl_b)); frases += f
    if _par(grafismos_a, grafismos_b, "grafismos"):
        res["grafismos"], f = comparar_grafismos(_carregar(grafismos_a), _carregar(grafismos_b)); frases += f
    if _par(estilo_a, estilo_b, "estilo"):
        res["estilo"], f = comparar_estilo(_carregar(estilo_a), _carregar(estilo_b)); frases += f
    if all(v is None for v in res.values()):
        raise ErroFerramenta("nada para comparar: passe ao menos um par (edl_a/edl_b, grafismos_a/grafismos_b ou estilo_a/estilo_b)")
    res["mudou"] = bool(frases)
    res["resumo"] = frases or ["Nada mudou."]
    return res
