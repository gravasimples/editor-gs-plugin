"""Arquivos e uso: tamanho das pastas do workspace, limpeza de arquivos de trabalho antigos (só `_trabalho/` e `trabalho/` dentro de
`saida/<slug>/`; versões em `_anteriores/`, entradas e entregas nunca são apagadas) e medidor de uso do Editor a partir das issues do Paperclip."""
import shutil, time
from datetime import datetime, timezone
from pathlib import Path

PASTAS_TRABALHO = ("_trabalho", "trabalho")


def _mb(n):
    return round(n / 1e6, 1)


def tamanho(p: Path):
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def candidatos_limpeza(saida: Path, dias=30, agora=None):
    """Pastas de trabalho (`_trabalho/`, `trabalho/`) de entregas sem alteração há mais de `dias`."""
    agora = agora or time.time(); limite = agora - dias * 86400; out = []
    if not saida.exists():
        return out
    for pasta in sorted(p for p in saida.iterdir() if p.is_dir()):
        for nome in PASTAS_TRABALHO:
            t = pasta / nome
            if t.is_dir():
                ultimo = max([f.stat().st_mtime for f in t.rglob("*") if f.is_file()] or [t.stat().st_mtime])
                if ultimo < limite:
                    out.append({"slug": pasta.name, "pasta": nome, "mb": _mb(tamanho(t)), "ultimo_uso": datetime.fromtimestamp(ultimo).isoformat(timespec="seconds")})
    return out


def armazenamento(workspace: Path, dias=30):
    saida = workspace / "saida"
    trabalho = sum(tamanho(p / n) for p in saida.iterdir() for n in PASTAS_TRABALHO) if saida.exists() else 0
    anteriores = sum(tamanho(p / "_anteriores") for p in saida.iterdir()) if saida.exists() else 0
    pastas = {n: _mb(tamanho(workspace / n)) for n in ("entrada", "saida", "referencias", "materiais", "clipes", "relatorios")}
    cand = candidatos_limpeza(saida, dias)
    uso = shutil.disk_usage(workspace if workspace.exists() else Path.home())
    return {"pastas_mb": pastas, "total_mb": round(sum(pastas.values()), 1), "trabalho_mb": _mb(trabalho), "anteriores_mb": _mb(anteriores),
            "limpeza": {"dias": dias, "candidatos": cand, "mb": round(sum(c["mb"] for c in cand), 1)},
            "disco": {"livre_gb": round(uso.free / 1e9, 1), "total_gb": round(uso.total / 1e9, 1)}}


def limpar(saida: Path, dias=30):
    """Apaga as pastas de trabalho antigas. Devolve o que saiu. Nunca toca entrada/, entregas ou `_anteriores/`."""
    feitos = []
    for c in candidatos_limpeza(saida, dias):
        alvo = saida / c["slug"] / c["pasta"]
        if alvo.is_dir() and alvo.name in PASTAS_TRABALHO and alvo.parent.parent == saida:
            shutil.rmtree(alvo, ignore_errors=True); feitos.append(c)
    return {"apagados": feitos, "mb": round(sum(c["mb"] for c in feitos), 1)}


def uso(issues, agora=None, agentes=None):
    """Pedidos por período e duração média, a partir das issues do Paperclip (sem custo em dinheiro: a assinatura cobre).
    `agentes` = {id: nome} → acrescenta `por_agente` (30 dias): pedidos, concluídos, em andamento e duração média de cada agente (Opus, Fable, Codex, Gemini)."""
    agora = agora or datetime.now(timezone.utc)
    por_agente = {}
    def dt(s):
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception:
            return None
    janelas = {"hoje": 1, "7_dias": 7, "30_dias": 30}; out = {k: {"criados": 0, "concluidos": 0} for k in janelas}
    duracoes = []; em_andamento = 0; na_fila = 0; aguardando = 0
    for i in issues:
        if i.get("status") == "cancelled":
            continue
        c, done = dt(i.get("createdAt")), dt(i.get("completedAt"))
        for k, d in janelas.items():
            if c and (agora - c).total_seconds() <= d * 86400:
                out[k]["criados"] += 1
            if done and (agora - done).total_seconds() <= d * 86400:
                out[k]["concluidos"] += 1
        s, st = dt(i.get("startedAt")), i.get("status")
        if st in ("in_progress",) or i.get("activeRun"):
            em_andamento += 1
        elif st in ("todo", "backlog"):
            na_fila += 1
        elif st == "in_review":
            aguardando += 1
        if s and done and done >= s and (agora - done).total_seconds() <= 30 * 86400:
            duracoes.append((done - s).total_seconds() / 60)
        if agentes is not None:
            aid = i.get("assigneeAgentId"); nome = agentes.get(aid) or (aid[:8] if aid else "sem agente")
            pa = por_agente.setdefault(nome, {"pedidos_30d": 0, "concluidos_30d": 0, "em_andamento": 0, "_dur": []})
            if c and (agora - c).total_seconds() <= 30 * 86400:
                pa["pedidos_30d"] += 1
            if done and (agora - done).total_seconds() <= 30 * 86400:
                pa["concluidos_30d"] += 1
                if s and done >= s:
                    pa["_dur"].append((done - s).total_seconds() / 60)
            if st == "in_progress" or i.get("activeRun"):
                pa["em_andamento"] += 1
    for pa in por_agente.values():
        d_ = pa.pop("_dur"); pa["duracao_media_min"] = round(sum(d_) / len(d_), 1) if d_ else None
    return {"periodos": out, **({"por_agente": por_agente} if agentes is not None else {}), "em_andamento": em_andamento, "na_fila": na_fila, "aguardando_voce": aguardando,
            "duracao_media_min": round(sum(duracoes) / len(duracoes), 1) if duracoes else None, "n_medidos": len(duracoes),
            "nota": "O Editor roda pela assinatura Claude (janela de 5 h e semanal); o Paperclip não expõe o consumo da janela, só os pedidos."}


# --- tempo economizado (estimativa simples: duração do vídeo × fator por fluxo + tempo fixo) ---------------------------
# Minutos que uma pessoa levaria para fazer à mão o que o Editor entregou. É estimativa declarada, não medição.
FATORES = {  # fluxo: (minutos fixos, minutos por minuto de vídeo final, minutos por slide/página)
    "reels-padrao": (20, 8, 0), "minha-versao": (30, 8, 0), "cortes-longos": (25, 8, 0), "referencia-analise": (20, 0, 0),
    "video-locucao": (25, 6, 0), "dublagem": (30, 10, 0), "traduzir-legenda": (20, 5, 0),
    "carrossel": (30, 0, 12), "depoimentos-semanais": (30, 0, 10), "apostila": (15, 0, 15),
    "roteiro": (25, 0, 0), "gravo-eu-mesmo": (30, 8, 0), "respostas-comentarios": (15, 0, 0), "analise-resultados": (30, 0, 0), "clipes": (40, 0, 0), "kit-derivacao": (90, 8, 4), "": (20, 8, 0)}
_CACHE_ECONOMIA = {}


def _fluxo_de(issue):
    import re
    m = re.search(r"Fluxo:\s*`fluxos/([\w\-]+)\.md`", issue.get("description") or "")
    if m:
        return m.group(1)
    d = (issue.get("description") or "").lower()
    return "clipes" if "clipador" in d or "clipes" in d else ""


def _duracao_s(p: Path):
    import json, subprocess
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)], capture_output=True, text=True, timeout=30)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def _paginas_pdf(p: Path):
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(p)).pages)
    except Exception:
        return 0


def economia_pedido(saida: Path, slug, issue):
    """Estimativa de minutos economizados numa entrega concluída: fluxo + o que está em saida/<slug>/ (vídeo final, slides, PDF)."""
    if not slug or issue.get("status") not in ("done", "in_review"):
        return None
    pasta = saida / slug
    if not pasta.is_dir():
        return None
    fluxo = _fluxo_de(issue); fixo, por_min, por_item = FATORES.get(fluxo, FATORES[""])
    chave = (slug, fluxo, max((f.stat().st_mtime for f in pasta.iterdir() if f.is_file()), default=0))
    if chave in _CACHE_ECONOMIA:
        return _CACHE_ECONOMIA[chave]
    videos = [f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == ".mp4" and f.name.startswith("final")]
    dur = max((_duracao_s(f) for f in videos), default=0.0)
    itens = 0
    if por_item:
        pngs = [f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == ".png" and f.name != "capa.png"]
        pdfs = [f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() == ".pdf" and not f.name.startswith("carrossel")]
        itens = len(pngs) if pngs else sum(_paginas_pdf(f) for f in pdfs)
    minutos = fixo + por_min * (dur / 60) + por_item * itens
    out = {"minutos": int(round(minutos)), "fluxo": fluxo or "pedido", "video_s": round(dur, 1) if dur else None, "itens": itens or None, "base": "estimativa"}
    _CACHE_ECONOMIA[chave] = out
    return out


def economia(saida: Path, issues, indice, agora=None):
    """Soma do tempo economizado por período (hoje, 7 e 30 dias, total) sobre as entregas concluídas."""
    agora = agora or datetime.now(timezone.utc)
    def dt(s):
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception:
            return None
    janelas = {"hoje": 1, "7_dias": 7, "30_dias": 30}; tot = {k: 0 for k in janelas}; total = 0; n = 0; por_fluxo = {}
    for i in issues:
        slug = (indice.get(i.get("id")) or {}).get("slug")
        e = economia_pedido(saida, slug, i)
        if not e:
            continue
        total += e["minutos"]; n += 1; por_fluxo[e["fluxo"]] = por_fluxo.get(e["fluxo"], 0) + e["minutos"]
        done = dt(i.get("completedAt")) or dt(i.get("updatedAt"))
        for k, d in janelas.items():
            if done and (agora - done).total_seconds() <= d * 86400:
                tot[k] += e["minutos"]
    return {"periodos_min": tot, "total_min": total, "n_entregas": n, "por_fluxo": por_fluxo,
            "nota": "Estimativa: tempo fixo por fluxo + minutos por minuto de vídeo (ou por slide/página). Não é medição; serve para acompanhar a tendência."}



def trabalho(runs, agora=None):
    """Tempo em que o Editor trabalhou de fato no pedido (03/11/2026): soma das rodadas do Paperclip (início → fim; rodada em andamento conta até agora).
    Fila e espera por resposta não contam. Igual ao "o editor trabalhou por N min" do Máquina."""
    agora = agora or datetime.now(timezone.utc)
    def dt(x):
        try:
            return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        except Exception:
            return None
    total = 0.0; n = 0; ativa = False
    for r in runs or []:
        ini = dt(r.get("startedAt"))
        if not ini:
            continue
        fim = dt(r.get("finishedAt"))
        if not fim and r.get("status") in ("running", "queued", "in_progress", None):
            fim = agora; ativa = True
        if fim and fim > ini:
            total += (fim - ini).total_seconds(); n += 1
    return {"segundos": int(total), "minutos": round(total / 60, 1), "rodadas": n, "em_andamento": ativa} if n else None
