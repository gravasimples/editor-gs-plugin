"""Demos das skills instaladas (12/11/2026): para cada skill de `.claude/skills/`, três edições de amostra com os mesmos brutos
(Reels do Insta do GS, ADS no estilo dos que rodam e aula com edição básica), para ver lado a lado o que cada skill entrega.

- workspace/skills_banco/demos.json: {skill: {formato: {issue_id, codigo, slug, criado}}}; o gateway completa status e vídeo final.
- Brutos em workspace/entrada/_demos-skills/ (copiados do Drive/acervo; os mesmos para todas as skills, para comparar).
Demo é pedido de teste: entra no fim da fila como qualquer outro, nunca na frente de pedido do Raphael."""
import json
from datetime import datetime
from pathlib import Path

PASTA_BRUTOS = "entrada/_demos-skills"
FORMATOS = {
    "reels": {"rotulo": "Reels do Insta", "bruto": "reels-bruto-obvio02.mp4", "saida": "9:16",
              "objetivo": "Reels de 30 a 60 s no padrão dos Reels que o @thiago.obsstudio posta: gancho forte nos 3 primeiros segundos, cortes secos sem pausa, "
                          "legenda animada palavra por palavra, animações e grafismos na palavra dita, trilha baixa sob a voz e efeitos sonoros discretos. "
                          "O bruto é da série \"O óbvio\": o Thiago falando para a câmera; áudio do microfone já sincronizado."},
    "ads": {"rotulo": "Anúncio (ADS)", "bruto": "ads-bruto-multistream.mp4", "saida": "9:16",
            "objetivo": "Anúncio para Meta Ads de 30 a 50 s no estilo dos ADS que rodam na conta: gancho visual até 3 s, escolher o melhor take de cada fala "
                        "(o bruto tem 6 min com vários takes seguidos sobre multistream; áudio do microfone já sincronizado), ritmo rápido, escrita na tela com os benefícios, legenda dinâmica e um CTA final claro. "
                        "Sem preço, oferta ou escassez inventados (use só o que o Thiago falar no take)."},
    "aula": {"rotulo": "Aula (edição básica)", "bruto": "aula-bruto.mp4", "saida": "16:9",
             "objetivo": "Edição básica de aula do curso: começa direto no professor e termina na última fala, cortes secos tirando erros, retomadas e pausas longas "
                         "(pausas curtas até ~1,5 s ficam), zoom suave alternado e zoom na área da tela quando ele mostra algo. Sem legenda, sem música, sem vinheta."},
}


def _arq(ws: Path) -> Path:
    d = ws / "skills_banco"; d.mkdir(parents=True, exist_ok=True); return d / "demos.json"


def ler(ws: Path) -> dict:
    try:
        return json.loads(_arq(ws).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def registrar(ws: Path, skill: str, formato: str, conversa: dict):
    d = ler(ws); d.setdefault(skill, {})[formato] = {"issue_id": conversa["id"], "codigo": conversa.get("codigo"), "slug": conversa.get("slug"),
                                                     "criado": datetime.now().isoformat(timespec="seconds")}
    _arq(ws).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def brutos_faltando(ws: Path) -> list:
    return [f["bruto"] for f in FORMATOS.values() if not (ws / PASTA_BRUTOS / f["bruto"]).exists()]


def pedido(skill: str, nome: str, formato: str) -> str:
    f = FORMATOS[formato]
    return "\n".join([
        f"Demo da skill instalada `{skill}` ({nome}), formato **{f['rotulo']}** ({f['saida']}).",
        "",
        f"Objetivo: mostrar visualmente a capacidade e o estilo desta skill. Edite o bruto `{PASTA_BRUTOS}/{f['bruto']}` USANDO A SKILL: leia `skills_biblioteca/{skill}/SKILL.md` (ou `.claude/skills/{skill}/SKILL.md` se ela estiver ativa) "
        "e siga o método, as ferramentas e os presets dela (rode o setup dela se for a primeira vez). Não use o nosso fluxo padrão nem o motor `montar_remotion` "
        "no lugar da skill; se um passo da skill não funcionar no Windows, contorne com o mínimo e registre o que não deu.",
        "",
        f"Peça: {f['objetivo']}",
        "Marca: manual da Grava Simples (marinho #000921, laranja #F79615, branco; voz do Thiago). Onde a skill tiver preset próprio de cor/fonte, adapte para a marca.",
        "Sem perguntas: decida sozinho (é uma demo), não espere aprovação de plano.",
        "",
        "Entrega: um vídeo `final_*.mp4` na pasta de saída e, na mensagem final, as seções `## O que a skill fez`, `## Pontos fortes`, `## Limites encontrados` "
        "e `## Tempo e custo` (minutos de render e etapas).",
    ])


def estado(ws: Path, instaladas: list, entregas_fn, status: dict) -> list:
    """instaladas: [{'id','nome',...}]; entregas_fn(slug) → lista de entregas; status: {issue_id: status}."""
    d = ler(ws); out = []
    for s in instaladas:
        sid = s.get("pasta") or s["id"]; fs = {}
        for k, f in FORMATOS.items():
            r = (d.get(sid) or {}).get(k)
            if not r:
                fs[k] = None; continue
            ents = entregas_fn(r.get("slug")) if r.get("slug") else []
            vids = [e for e in ents if e["tipo"] == "video" and e["nome"].startswith("final")] or [e for e in ents if e["tipo"] == "video"]
            fs[k] = {**r, "status": status.get(r["issue_id"]), "video": vids[-1]["url"] if vids else None}
        out.append({"skill": sid, "nome": s.get("nome") or sid, "url": s.get("url"), "formatos": fs})
    return out
