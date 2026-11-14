"""Estilo do criativo (fase D, 07/11/2026): painel da conversa no jeito do Máquina (docs/maquina/ANALISE-2026-11-06.md, item 12).
Energia do vídeo (calmo · dinâmico · bem dinâmico) + chaves (corte inteligente, zoom, clarão, sem pausa, grafismos, legenda, tela final, barra, efeitos)
viram um parágrafo de instruções no pedido ou numa mensagem da conversa; "Salvar como meu padrão" guarda a escolha e ela vem marcada nos pedidos novos.
Memórias ("Também no seu padrão"): preferências que o Raphael escreveu ou que o Editor aprendeu nas conversas (ferramenta MCP lembrar_preferencia),
visíveis e removíveis. O gateway espelha as memórias em workspace/preferencias/memorias.md, que o AGENTS.md manda ler antes de editar."""
import json, os, secrets, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _ws() -> Path:
    from servico import caminhos as _cam
    return _cam.WORKSPACE


def arq() -> Path:
    return _ws() / "preferencias" / "estilo.json"


ENERGIAS = {
    # 13/11/2026: grafismo virou teto com motivo (era "a cada 3–6 s", lido como cota) e o bem dinâmico perdeu "sem respiro entre frases" (comia sílaba):
    # o ritmo vem de tirar pausa e take ruim, não de apertar a borda da fala.
    "calmo": {"rotulo": "Calmo", "texto": "energia CALMA: cortes que respiram (propor_cortes modo normal, min_pausa_s=0.4), zoom só nas trocas de frase (ritmo_zoom_s=0), "
              "sem efeitos sonoros, gráfico só com motivo forte na fala (no máximo um a cada 6 s), montar_remotion energia=\"calmo\""},
    "dinamico": {"rotulo": "Dinâmico", "texto": "energia DINÂMICA (padrão): propor_cortes modo dinamico, ritmo do estilo, pausa máxima 0,30 s, gráfico só com motivo na fala "
                 "(no máximo um no peito a cada 4 s), montar_remotion energia=\"dinamico\""},
    "bem_dinamico": {"rotulo": "Bem dinâmico", "texto": "energia BEM DINÂMICA: pausas curtas (propor_cortes modo bem_dinamico) sem comer o fim das palavras, troca de "
                     "enquadramento a cada 3 s (ritmo_zoom_s=3), gráfico só com motivo na fala (no máximo um a cada 3 s), efeitos sonoros ligados, gancho palavra por palavra, "
                     "montar_remotion energia=\"bem_dinamico\""},
}
# chave → (rótulo no painel, padrão, instrução quando ligada, instrução quando desligada)
CHAVES = {
    "corte_inteligente": ("Corte inteligente", True, "corte inteligente: tire tempo morto, repetições de take e frases abandonadas (fique com o melhor take)",
                          "corte só de silêncio: não tire repetições nem takes"),
    "zoom_ritmo": ("Zoom no ritmo da fala", True, "enquadramento variando e câmera viva (transicoes=\"auto\")", "sem zoom (zoom=False): só as transições, enquadramento fixo"),
    "clarao": ("Flash na troca de cena", True, "flash só nas viradas grandes (a gramática de corte escolhe)", "sem flash (clarao=False)"),
    "sem_pausa": ("Sem pausa entre cenas", False, "sem pausa entre cenas: fala emendada, nenhuma pausa acima de 0,25 s", ""),
    "grafismos": ("Grafismos na tela", True, "grafismos semânticos guiados pela fala (planejar_grafismos → grafismos=)", "sem grafismos nem palavras-chave na tela"),
    "efeitos": ("Efeitos sonoros", True, "efeitos sonoros discretos (sfx=True)", "sem efeitos sonoros (sfx=False)"),
    "barra": ("Barra de progresso", True, "barra de progresso", "sem barra de progresso"),
    "tela_final": ("Tela final com CTA", True, "tela final com CTA de seguir", "sem tela final (tela_final=False)"),
}
LEGENDAS = {"baixa": "Rodapé", "centro": "Centro"}
PADRAO = {"energia": "dinamico", "chaves": {k: v[1] for k, v in CHAVES.items()}, "legenda": "baixa"}


def ler() -> dict:
    try:
        d = json.loads(arq().read_text(encoding="utf-8"))
    except Exception:  # noqa
        d = {}
    return {"padrao": normalizar(d.get("padrao") or {}), "memorias": d.get("memorias") or [], "atualizado": d.get("atualizado")}


def _gravar(d: dict):
    a = arq(); a.parent.mkdir(parents=True, exist_ok=True)
    d["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = a.with_suffix(".tmp"); tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); tmp.replace(a)
    _espelhar(d)


def normalizar(cfg: dict) -> dict:
    """Completa e limpa uma escolha do painel (valores desconhecidos caem no padrão)."""
    cfg = cfg if isinstance(cfg, dict) else {}
    energia = cfg.get("energia") if cfg.get("energia") in ENERGIAS else PADRAO["energia"]
    ch = cfg.get("chaves") if isinstance(cfg.get("chaves"), dict) else {}
    chaves = {k: bool(ch.get(k, v[1])) for k, v in CHAVES.items()}
    legenda = cfg.get("legenda") if cfg.get("legenda") in LEGENDAS else PADRAO["legenda"]
    return {"energia": energia, "chaves": chaves, "legenda": legenda}


def salvar_padrao(cfg: dict) -> dict:
    d = ler(); d["padrao"] = normalizar(cfg); _gravar(d); return d


def lembrar(texto: str, origem: str = "Raphael") -> dict:
    """Acrescenta uma memória; texto igual (sem caixa/espaço) não duplica."""
    t = " ".join(str(texto or "").split())[:240]
    if len(t) < 4:
        raise ValueError("Escreva a preferência (pelo menos 4 letras).")
    d = ler()
    if any(m["texto"].lower() == t.lower() for m in d["memorias"]):
        return next(m for m in d["memorias"] if m["texto"].lower() == t.lower())
    m = {"id": secrets.token_hex(4), "texto": t, "origem": str(origem or "Raphael")[:40], "criado": time.strftime("%Y-%m-%dT%H:%M:%S")}
    d["memorias"].append(m); d["memorias"] = d["memorias"][-60:]; _gravar(d); return m


def esquecer(mid: str) -> bool:
    d = ler(); antes = len(d["memorias"]); d["memorias"] = [m for m in d["memorias"] if m["id"] != mid]
    if len(d["memorias"]) == antes:
        return False
    _gravar(d); return True


def _espelhar(d: dict):
    """workspace/preferencias/memorias.md: o que o Editor lê antes de editar (AGENTS.md)."""
    linhas = ["# Preferências do Raphael (memórias do Estilo do criativo)", "",
              "Geradas pelo app (painel Estilo do criativo). Valem em toda edição, salvo pedido contrário na conversa. Não edite à mão: use `lembrar_preferencia`.", ""]
    linhas += [f"- {m['texto']} _(origem: {m['origem']}, {m['criado'][:10]})_" for m in d.get("memorias") or []] or ["- (nenhuma ainda)"]
    p = normalizar(d.get("padrao") or {})
    linhas += ["", "## Padrão salvo do painel", "", texto_instrucoes(p, cabecalho=False)]
    a = arq().parent / "memorias.md"; a.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def texto_instrucoes(cfg: dict, cabecalho: bool = True) -> str:
    """Parágrafo que vai no pedido (ou na mensagem 'refaça com este estilo')."""
    c = normalizar(cfg)
    partes = [ENERGIAS[c["energia"]]["texto"]]
    for k, (rot, _pad, lig, desl) in CHAVES.items():
        t = lig if c["chaves"][k] else desl
        if t:
            partes.append(t)
    partes.append(f"legenda {'no centro (posicao centro)' if c['legenda'] == 'centro' else 'no rodapé (posicao baixa)'}")
    corpo = "; ".join(partes) + "."
    return f"Estilo do criativo (painel): {corpo}" if cabecalho else corpo


def opcoes() -> dict:
    return {"energias": [{"id": k, "rotulo": v["rotulo"]} for k, v in ENERGIAS.items()],
            "chaves": [{"id": k, "rotulo": v[0], "padrao": v[1]} for k, v in CHAVES.items()],
            "legendas": [{"id": k, "rotulo": v} for k, v in LEGENDAS.items()]}


def garantir_espelho():
    if not (arq().parent / "memorias.md").exists():
        a = arq(); a.parent.mkdir(parents=True, exist_ok=True); _espelhar(ler())
