"""Revisor de marca na entrega (item 3 da ordem de 31/10/2026): regras duras do manual da Grava Simples aplicadas aos textos da entrega
(legenda, roteiro, título, gancho, hashtags, texto para gravar) antes de o Raphael aprovar. Só aponta; não corrige nem bloqueia.
Regras em servico/marca_regras.json (editável; padrão abaixo): claims proibidos (número de alunos), preço/oferta/escassez, travessão,
promessa de resultado, excesso de hashtags/emoji, legenda longa demais, título todo em caixa alta."""
import json, re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
REGRAS = _cam.estado("marca_regras.json")
PADRAO = {
    "alta": [
        {"id": "alunos", "regex": r"\b\d[\d\.\s]*\s*mil\s+alunos\b|\+?\s*20\s*mil\s+alunos|\balunos\s+formados\b", "msg": "Número de alunos é PENDING_VALIDATION: não citar."},
        {"id": "preco", "regex": r"R\$\s?\d|\b\d+\s*x\s*(de\s*)?R\$|\bparcel(a|e)|\bdesconto\b|\bcupom\b", "msg": "Preço, parcela, desconto ou cupom: oferta não é claim orgânico autorizado."},
        {"id": "escassez", "regex": r"\b(últimas?|ultimas?)\s+vagas?\b|\bsó\s+hoje\b|\bcorre\s+que\b|\bvagas?\s+limitad|\bencerra\s+(hoje|amanhã)\b|\btempo\s+limitado\b", "msg": "Falsa escassez: o manual proíbe."},
        {"id": "garantia", "regex": r"\bgarant(o|ia|ido|imos)\b.*\b(resultado|faturar|vender|ganhar)|\bresultado\s+garantido\b|\b100%\s+(garantido|certo)", "msg": "Promessa de resultado: não transformar promessa criativa em garantia."},
    ],
    "media": [
        {"id": "travessao", "regex": r"—|\s–\s", "msg": "Travessão: a voz do Thiago não usa; trocar por ponto, vírgula ou dois-pontos."},
        {"id": "vitalicio_oferta", "regex": r"\bacesso\s+vital[ií]cio\b|\bvital[ií]cio\s+por\b", "msg": "Acesso vitalício como oferta: não é claim vigente validado."},
        {"id": "faturamento", "regex": r"\bfatur(ei|ou|amento)\b|\bmilh(ão|ões)\s+(de\s+)?reais\b|\b[0-9]+\s*k\s+por\s+m[eê]s\b", "msg": "Faturamento: não usar em conteúdo."},
        {"id": "bordao", "regex": r"(ó,?\s*olha\s+só.*){2,}|(a\s+real\s+é\s+que.*){2,}", "msg": "Bordão repetido: o manual pede expressões naturais, sem forçar."},
    ],
    "baixa": [
        {"id": "hashtags", "max": 10, "msg": "Mais de 10 hashtags."},
        {"id": "legenda_longa", "max_chars": 2200, "msg": "Legenda acima de 2.200 caracteres (limite do Instagram)."},
        {"id": "emoji", "max": 5, "msg": "Muitos emojis decorativos: o manual pede legenda limpa."},
        {"id": "caixa_alta", "msg": "Título ou gancho inteiro em caixa alta: só botão, selo ou uma palavra de destaque."},
        {"id": "jargao", "regex": r"\bbitrate\b|\bencoder\b|\bNVENC\b|\bx264\b|\bkeyframe\b|\bdownscale\b", "msg": "Termo técnico sem o benefício antes: conferir se explica para iniciante."},
    ],
}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\U0001F1E6-\U0001F1FF]")


def regras(arq: Path = None):
    p = arq or REGRAS
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {k: d.get(k, PADRAO[k]) for k in PADRAO}
    except Exception:  # noqa
        return PADRAO


def _trecho(texto, m, n=70):
    i = max(0, m.start() - 30); j = min(len(texto), m.end() + 40)
    return ("…" if i else "") + texto[i:j].replace("\n", " ") + ("…" if j < len(texto) else "")


def revisar(textos: dict, arq: Path = None):
    """textos = {"descricao": ..., "roteiro": ..., "titulo": ..., "gancho": ..., "hashtags": ..., "gravar": ..., "srt": ...}. Devolve {"avisos": [...], "resumo": {"alta": n, "media": n, "baixa": n}, "ok": bool}."""
    R = regras(arq); avisos = []
    campos = {k: (v or "") for k, v in (textos or {}).items() if isinstance(v, str)}
    for grav in ("alta", "media"):
        for r in R[grav]:
            rx = re.compile(r["regex"], re.I | re.S)
            for campo, t in campos.items():
                for m in rx.finditer(t):
                    avisos.append({"gravidade": grav, "regra": r["id"], "campo": campo, "trecho": _trecho(t, m), "msg": r["msg"]})
                    break
    for r in R["baixa"]:
        if r["id"] == "hashtags":
            t = campos.get("hashtags") or campos.get("descricao") or ""
            n = len(re.findall(r"#\w+", t))
            if n > r.get("max", 10):
                avisos.append({"gravidade": "baixa", "regra": "hashtags", "campo": "hashtags", "trecho": f"{n} hashtags", "msg": r["msg"]})
        elif r["id"] == "legenda_longa":
            t = campos.get("descricao") or ""
            if len(t) > r.get("max_chars", 2200):
                avisos.append({"gravidade": "baixa", "regra": "legenda_longa", "campo": "descricao", "trecho": f"{len(t)} caracteres", "msg": r["msg"]})
        elif r["id"] == "emoji":
            t = campos.get("descricao") or ""
            n = len(EMOJI.findall(t))
            if n > r.get("max", 5):
                avisos.append({"gravidade": "baixa", "regra": "emoji", "campo": "descricao", "trecho": f"{n} emojis", "msg": r["msg"]})
        elif r["id"] == "caixa_alta":
            for campo in ("titulo", "gancho"):
                t = (campos.get(campo) or "").strip()
                letras = [ch for ch in t if ch.isalpha()]
                if len(letras) >= 12 and all(ch.isupper() for ch in letras):
                    avisos.append({"gravidade": "baixa", "regra": "caixa_alta", "campo": campo, "trecho": t[:60], "msg": r["msg"]})
        elif r.get("regex"):
            rx = re.compile(r["regex"], re.I)
            for campo, t in campos.items():
                m = rx.search(t)
                if m:
                    avisos.append({"gravidade": "baixa", "regra": r["id"], "campo": campo, "trecho": _trecho(t, m), "msg": r["msg"]}); break
    ordem = {"alta": 0, "media": 1, "baixa": 2}; avisos.sort(key=lambda a: ordem[a["gravidade"]])
    resumo = {g: sum(1 for a in avisos if a["gravidade"] == g) for g in ("alta", "media", "baixa")}
    return {"avisos": avisos, "resumo": resumo, "ok": resumo["alta"] == 0 and resumo["media"] == 0, "nota": "Revisor de marca: regras duras do manual, sem modelo de linguagem. Aponta, não corrige; a decisão é do Raphael."}
