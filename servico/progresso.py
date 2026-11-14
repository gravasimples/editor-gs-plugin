"""Progresso ao vivo do pedido (11/11/2026): etapa atual, porcentagem e tempo restante estimado, lidos do registro da rodada.
O executor grava cada rodada em run-logs/<run>.ndjson (stream-json do `claude -p`). As ferramentas que o agente chama dizem a etapa
(transcrever → Transcrevendo, aplicar_cortes → Cortes, montar_remotion → Montando o vídeo...). A estimativa vem das rodadas já
concluídas: quanto tempo cada etapa costuma levar (mediana). Sem histórico suficiente, mostra só etapa e tempo decorrido.
Só leitura; nada aqui muda o pedido."""
import json, re, statistics, time
from datetime import datetime, timezone
from pathlib import Path

ETAPAS = [
    ("preparo", "Preparando o material"),
    ("transcricao", "Transcrevendo"),
    ("plano", "Planejando a edição"),
    ("cortes", "Cortes"),
    ("tela", "Legenda e grafismos"),
    ("render", "Montando o vídeo"),
    ("revisao", "Revisão final"),
    ("entrega", "Entregando"),
]
ORDEM = {e: i for i, (e, _) in enumerate(ETAPAS)}

# ferramenta do MCP (sem o prefixo) → etapa; o que não está aqui não muda a etapa
FERRAMENTAS = {
    "info": "preparo", "extrair_trecho": "preparo", "baixar_video": "preparo", "buscar_material": "preparo", "extrair_quadros": "preparo",
    "transcrever": "transcricao",
    "propor_cortes": "plano", "ajustar_edl": "plano", "consultar_repertorio": "plano", "ver_ficha_repertorio": "plano", "detectar_gestos": "plano",
    "aplicar_cortes": "cortes", "cortar_e_legendar": "cortes", "encurtar_pausas": "cortes",
    "gerar_legenda": "tela", "planejar_grafismos": "tela", "validar_grafismos": "tela", "palavras_chave": "tela",
    "montar_remotion": "render", "montar": "render", "montar_pip": "render", "montar_dividido": "render", "montar_antes_depois": "render",
    "montar_react": "render", "montar_locucao": "render", "animar_carrossel": "render", "gerar_carrossel": "render", "narrar": "render", "dublar": "render",
    "gerar_capa": "render", "exportar_capcut": "render", "revisar_video": "revisao",  # capa e CapCut saem junto com o render "folha_contato": "revisao", "comparar_versoes": "revisao",
    "comparar_com_repertorio": "revisao", "revisar_marca": "revisao", "finalizar_audio": "revisao",
}
# o agente às vezes chama os motores por script no terminal: o comando diz a etapa
_BASH = [(re.compile(r"montar_remotion|remotion render|montar_pip|montar_dividido"), "render"), (re.compile(r"aplicar_cortes|cortar_e_legendar"), "cortes"),
         (re.compile(r"gerar_legenda|grafismos"), "tela"), (re.compile(r"transcrever|whisper"), "transcricao"), (re.compile(r"folha_contato|revisar_video"), "revisao")]
_COMENTARIO = re.compile(r"/api/issues/[^/\s]+/comments")
_EXECUTA = re.compile(r"python(\.exe)?\s|npx\s|remotion render|ffmpeg")
MIN_RODADAS = 5  # abaixo disso a estimativa é a inicial
LIMITE_NORMAL_S = 45 * 60  # rodada mais longa que isso teve trava ou espera: fica fora do histórico
# estimativa inicial (s) enquanto há menos de MIN_RODADAS rodadas de edição no histórico: Reel de fala de 30–60 s medido em 07–11/11
PADRAO_S = {"_inicio": 40, "preparo": 60, "transcricao": 90, "plano": 150, "cortes": 90, "tela": 150, "render": 360, "revisao": 150, "entrega": 40}


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _etapa_do_uso(nome: str, entrada: dict):
    nome = nome.rsplit("__", 1)[-1]
    if nome in FERRAMENTAS:
        return FERRAMENTAS[nome]
    if nome == "Bash":
        cmd = str((entrada or {}).get("command", ""))
        if _COMENTARIO.search(cmd):  # mensagem na conversa: o plano cita "legenda", "capcut"... e não é etapa feita
            return "entrega" if "## Resumo" in cmd else None
        if not _EXECUTA.search(cmd):  # grep/sed/cat no código que cita montar_remotion não é etapa
            return None
        for rx, et in _BASH:
            if rx.search(cmd):
                return et
    return None


def marcos(log_path: Path):
    """Lê a rodada: início, fim (se terminou) e o primeiro instante de cada etapa. Etapa só avança (o agente volta a transcrever
    para conferir, mas a barra não anda para trás)."""
    inicio = fim = None; chegou = {}; atual = None
    try:
        linhas = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for l in linhas:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        ts = _dt(o.get("ts"))
        if ts and inicio is None:
            inicio = ts
        ch = o.get("chunk")
        if not ch:
            continue
        if '"tool_use"' not in ch and '"result"' not in ch:  # cada chunk é um objeto do stream-json
            continue
        try:
            d = json.loads(ch)
        except ValueError:
            continue
        if d.get("type") == "result":
            fim = ts; continue
        if d.get("type") != "assistant":
            continue
        for c in (d.get("message") or {}).get("content") or []:
            if c.get("type") != "tool_use":
                continue
            et = _etapa_do_uso(c.get("name", ""), c.get("input"))
            if et and (atual is None or ORDEM[et] > ORDEM[atual]):
                atual = et; chegou.setdefault(et, ts)
    if inicio is None:
        return None
    return {"inicio": inicio, "fim": fim, "chegou": chegou, "atual": atual}


_HIST = {"quando": 0.0, "pasta": None, "dados": None}


def historico(pasta: Path, n=40):
    """Mediana da duração de cada etapa nas últimas `n` rodadas concluídas que chegaram ao render (rodadas de edição). Cache de 10 min."""
    if _HIST["dados"] is not None and _HIST["pasta"] == str(pasta) and time.time() - _HIST["quando"] < 600:
        return _HIST["dados"]
    durs = {e: [] for e, _ in ETAPAS}; totais = []
    arqs = sorted(Path(pasta).glob("*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)[: n * 2]
    usadas = 0
    for a in arqs:
        m = marcos(a)
        if not m or not m["fim"] or "render" not in m["chegou"]:
            continue
        if (m["fim"] - m["inicio"]).total_seconds() > LIMITE_NORMAL_S:  # rodada com trava (GRA-66: 3 h) não ensina o tempo normal
            continue
        pontos = sorted(m["chegou"].items(), key=lambda kv: ORDEM[kv[0]])
        if not pontos:
            continue
        totais.append((m["fim"] - m["inicio"]).total_seconds())
        durs.setdefault("_inicio", []).append((pontos[0][1] - m["inicio"]).total_seconds())
        for (e, t), prox in zip(pontos, pontos[1:] + [(None, m["fim"])]):
            durs[e].append(max(0.0, (prox[1] - t).total_seconds()))
        usadas += 1
        if usadas >= n:
            break
    dados = {"rodadas": usadas, "total_s": statistics.median(totais) if totais else None,
             "etapa_s": {e: statistics.median(v) for e, v in durs.items() if v}}
    _HIST.update(quando=time.time(), pasta=str(pasta), dados=dados)
    return dados


def calcular(log_path: Path, pasta_hist: Path, agora=None):
    """Progresso da rodada em andamento: lista de etapas (feita/atual/futura), porcentagem (0–99 enquanto roda) e minutos restantes
    estimados (histórico ou estimativa inicial). A estimativa nunca é mostrada como promessa: o app escreve "cerca de"."""
    m = marcos(log_path)
    if not m:
        return None
    agora = agora or datetime.now(timezone.utc)
    h = historico(pasta_hist)
    # duração prevista de cada etapa: mediana do histórico com 3+ rodadas; antes disso, a estimativa inicial (PADRAO_S)
    med = (h.get("etapa_s") or {}) if h.get("rodadas", 0) >= MIN_RODADAS else {}
    atual = m["atual"]
    i_atual = ORDEM[atual] if atual else -1
    decorrido = (agora - m["inicio"]).total_seconds()
    prev = {e: med.get(e, PADRAO_S[e]) for e, _ in ETAPAS}
    prev_inicio = med.get("_inicio", PADRAO_S["_inicio"])
    feitas = prev_inicio + sum(prev[e] for e, _ in ETAPAS[: max(0, i_atual)])
    na_etapa = (agora - m["chegou"][atual]).total_seconds() if atual else decorrido
    dur_atual = prev[atual] if atual else prev_inicio
    total_prev = prev_inicio + sum(prev.values())
    andou = feitas + min(na_etapa, dur_atual * 0.95)
    pct = int(max(1, min(99, round(100 * andou / total_prev)))) if total_prev else None
    restante = max(dur_atual - na_etapa, dur_atual * 0.1) + sum(prev[e] for e, _ in ETAPAS[i_atual + 1:])
    etapas = [{"id": e, "nome": nome, "estado": "feita" if ORDEM[e] < i_atual else ("atual" if ORDEM[e] == i_atual else "futura")} for e, nome in ETAPAS]
    lenta = bool(atual and na_etapa > max(3 * dur_atual, 600))  # muito acima do normal: o app avisa em vez de prometer
    return {"etapas": etapas, "atual": atual, "atual_nome": dict(ETAPAS).get(atual, "Lendo o pedido"), "pct": pct,
            "decorrido_s": int(decorrido), "na_etapa_s": int(na_etapa), "restante_s": None if lenta else int(restante),
            "lenta": lenta, "estimativa": "historico" if med else "inicial", "base_rodadas": h.get("rodadas", 0), "terminou": bool(m["fim"])}
