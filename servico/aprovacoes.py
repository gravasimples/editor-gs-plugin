"""Central de aprovação (item 3 da ordem de 31/10/2026): tudo que espera o Raphael numa fila só, dentro do app: entregas em revisão
(issues in_review ou done sem aprovação registrada) e decisões pendentes do Editor (interactions). Cada item traz prévia, textos,
etiquetas, avisos do revisor de marca e as ações já existentes (aprovar, pedir ajuste com o segundo do vídeo, aceitar/recusar).
Sem link externo: decisão do Raphael de 31/10 (tudo fica no app). As partes puras ficam aqui; a leitura do Paperclip fica no gateway."""
import json, re
from datetime import datetime
from pathlib import Path


def aprovada(pasta: Path):
    """Aprovação registrada localmente em saida/<slug>/aprovacao.json (o comentário "APROVADO" na issue continua sendo a fonte no Paperclip)."""
    p = pasta / "aprovacao.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return None


def registrar(pasta: Path, por="Raphael", comentario="", tipo="aprovada"):
    """tipo: aprovada (botão Aprovar) ou vista (tirou da fila sem aprovar nem reprovar)."""
    pasta.mkdir(parents=True, exist_ok=True)
    d = {"por": por, "quando": datetime.now().isoformat(timespec="seconds"), "comentario": (comentario or "")[:500], "tipo": tipo}
    (pasta / "aprovacao.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def item_entrega(conv, entregas, textos, peca, revisao, mensagem_final=None):
    """Monta o cartão da fila para uma entrega: prévia (vídeo principal ou primeira imagem), textos curtos, etiquetas, avisos."""
    video = next((e for e in entregas if e.get("principal") and e.get("tipo") == "video"), None) or next((e for e in entregas if e.get("tipo") == "video"), None)
    capa = next((e for e in entregas if e.get("nome") == "capa.png"), None)
    imagens = [e for e in entregas if e.get("tipo") == "imagem" and e.get("nome") != "capa.png"][:8]
    t = {s.get("chave"): s.get("conteudo") for s in (textos or [])}
    return {"tipo": "entrega", "id": conv.get("id"), "codigo": conv.get("codigo"), "titulo": conv.get("titulo"), "slug": conv.get("slug"), "status": conv.get("status"), "atualizado": conv.get("atualizado"), "pasta": conv.get("pasta"),
            "video": video, "capa": capa, "imagens": imagens, "n_arquivos": len(entregas),
            "textos": {k: (t.get(k) or "")[:600] for k in ("gancho", "descricao", "titulo", "resumo", "pendencias") if t.get(k)},
            "etiquetas": (peca or {}).get("etiquetas") or {}, "revisao": revisao, "mensagem_final": (mensagem_final or "")[:400]}


def item_decisao(conv, it):
    return {"tipo": "decisao", "id": conv.get("id"), "codigo": conv.get("codigo"), "titulo": conv.get("titulo"), "slug": conv.get("slug"), "status": conv.get("status"), "atualizado": conv.get("atualizado"),
            "interacao": {"id": it.get("id"), "tipo": it.get("kind"), "titulo": it.get("title"), "resumo": it.get("summary"), "pergunta": ((it.get("payload") or {}).get("prompt")), "opcoes": ((it.get("payload") or {}).get("options") or (it.get("payload") or {}).get("choices") or [])}}


def pedido_ajuste(texto, segundo=None, arquivo=None):
    """Texto do pedido de ajuste com o instante do vídeo marcado, para o Editor saber onde mexer sem adivinhar."""
    texto = (texto or "").strip()
    if segundo is not None:
        s = int(float(segundo)); mm, ss = divmod(s, 60)
        return f"Ajuste no vídeo{(' ' + arquivo) if arquivo else ''}, aos {mm}:{ss:02d} ({s} s): {texto}"
    return texto
