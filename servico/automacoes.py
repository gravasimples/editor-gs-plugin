"""Registro das automações que tocam o conteúdo da Grava Simples, para a aba Métricas e Automações.
Dois grupos: (1) as do GSI (pulso de conteúdo, radar diário, ponte pulso → Editor GS, pulso principal): só leitura dos arquivos de
configuração e estado do GSI, com a instrução de onde ligar/pausar (o app não escreve no GSI); (2) as do próprio Editor GS
(vigia de push, limpeza de trabalho) e as planejadas na proposta de 31/10 (série de Stories, Reel reciclado, variação do vencedor,
primeiro comentário, pós-mortem, alertas, melhor horário), com chave guardada em servico/automacoes.json: a chave marca o que o
Raphael quer ligado quando a automação existir; nada roda sozinho por causa dela."""
import json, time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
REGISTRO = _cam.estado("automacoes.json")
PLANEJADAS = [
    {"id": "stories_serie", "nome": "Série recorrente de Stories", "descricao": "Gera texto e arte na marca para uma série fixa (bastidor de terça, dúvida da semana) e agenda como rascunho na Publora.", "precisa": "Publora; Meta para publicar direto", "tamanho": "M"},
    {"id": "reel_reciclado", "nome": "Reel reciclado com gancho novo", "descricao": "A cada N dias escolhe um evergreen acima da mediana, troca só o gancho e a legenda, agenda rascunho e registra como experimento.", "precisa": "métricas do GSI; Publora", "tamanho": "M"},
    {"id": "variacao_vencedor", "nome": "Variação do vencedor", "descricao": "Peça que fecha D+7 acima de 1,5× a mediana gera dois pedidos de variação na fila do Editor GS.", "precisa": "pós-mortem D+7 (já existe)", "tamanho": "P"},
    {"id": "primeiro_comentario", "nome": "Primeiro comentário com link", "descricao": "Ao publicar, posta o primeiro comentário com o link sck da peça ou o CTA.", "precisa": "Publora ou Meta", "tamanho": "P"},
    {"id": "posmortem", "nome": "Pós-mortem D+7", "descricao": "Ficha automática por peça publicada: métricas × mediana do formato, veredito e hipótese; vira aprendizado proposto.", "precisa": "nada (já existe o botão manual)", "tamanho": "P"},
    {"id": "alertas", "nome": "Alertas de tração e risco", "descricao": "Push quando uma peça foge da mediana para cima ou para baixo, ou quando comentários negativos acumulam.", "precisa": "snapshot diário do GSI; com a Meta fica mais rápido", "tamanho": "P"},
    {"id": "pasta_vigiada", "nome": "Pasta vigiada do Drive", "descricao": "Gravação nova em 10. Mídias/Materiais para Editar vira pedido sozinha; a subpasta escolhe o tipo (Kit, Cortes, Profissional, Tutorial…).", "precisa": "Drive conectado (rclone, já feito) e a pasta criada", "tamanho": "M"},
    {"id": "melhor_horario", "nome": "Melhor horário por rede", "descricao": "Recalcula toda semana os horários a partir dos dados próprios; as automações agendam neles.", "precisa": "histórico do GSI (mais preciso com a Meta)", "tamanho": "M"},
    {"id": "skills_garimpo", "nome": "Garimpo semanal de skills e ferramentas", "descricao": "Uma vez por semana o Editor pesquisa na internet skills, plugins, repositórios, presets e criadores de edição e registra os achados no Banco de skills; decidir, instalar e reproduzir continuam cliques do Raphael.", "precisa": "nada (web do próprio agente; modelo padrão)", "tamanho": "P"},
]


def _json(p: Path, padrao=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return padrao if padrao is not None else {}


def _mtime(p: Path):
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")
    except Exception:  # noqa
        return None


def _ultimo(pasta: Path, padrao="*.md"):
    try:
        arqs = sorted(pasta.glob(padrao), key=lambda x: x.stat().st_mtime)
        return arqs[-1] if arqs else None
    except Exception:  # noqa
        return None


def do_gsi(gsi: Path):
    """Estado das automações do GSI lido dos arquivos (sem rodar nada)."""
    out = []
    cfg = _json(gsi / "integracoes" / "config_pulso_conteudo.json")
    stop = (gsi / "dados" / "pulsos" / "STOP").exists()
    est = _json(gsi / "dados" / "pulsos" / "estado.json"); fila = _json(gsi / "dados" / "pulsos" / "fila.json")
    ult = _ultimo(gsi / "briefings" / "pulsos", "pulso-*.md")
    out.append({"id": "gsi_pulso_conteudo", "grupo": "GSI", "nome": "Pulso de conteúdo (Notion Mídias)", "ligada": bool(cfg.get("enabled")) and not stop, "estado": "pausada (STOP)" if stop else ("ligada" if cfg.get("enabled") else "desligada"),
                "detalhe": f"modo {cfg.get('modo', '?')} · 7 horários por dia · fila {len(fila) if isinstance(fila, dict) else 0} tarefa(s) · Notion lido {str(est.get('lido_em', ''))[:16].replace('T', ' ')}",
                "ultima": _mtime(ult) if ult else None, "ultimo_arquivo": (f"briefings/pulsos/{ult.name}" if ult else None),
                "onde": "GSI: `python3 integracoes/pulso_conteudo.py status`; pausar criando `dados/pulsos/STOP`; religar apagando o STOP (enabled em config_pulso_conteudo.json)."})
    cfg = _json(gsi / "integracoes" / "config_radar.json"); ult = _ultimo(gsi / "briefings" / "radar", "radar-*.md")
    out.append({"id": "gsi_radar", "grupo": "GSI", "nome": "Radar diário de ideias", "ligada": bool(cfg.get("enabled")), "estado": "ligada" if cfg.get("enabled") else "desligada",
                "detalhe": f"pesquisa às {cfg.get('hora_radar', '?')}h · leitura das caixas às {', '.join(str(h) for h in cfg.get('horas_aprovacoes', []))}h · doc {((cfg.get('doc') or {}).get('url') or '')}",
                "ultima": _mtime(ult) if ult else None, "ultimo_arquivo": (f"briefings/radar/{ult.name}" if ult else None), "onde": "GSI: `python3 integracoes/radar.py status`; enabled em config_radar.json."})
    cfg = _json(gsi / "integracoes" / "config_editor_gs_ponte.json"); est = _json(gsi / "dados" / "pulsos" / "editor_gs_ponte.json")
    env = (est.get("enviados") or {}) if isinstance(est, dict) else {}
    ultimos = sorted((v.get("quando") or "" for v in env.values()), reverse=True)
    out.append({"id": "gsi_ponte", "grupo": "GSI", "nome": "Ponte pulso → Editor GS", "ligada": bool(cfg.get("enabled")), "estado": "ligada" if cfg.get("enabled") else "desligada",
                "detalhe": f"até {cfg.get('max_por_rodada', '?')} pedido por rodada e {cfg.get('max_por_dia', '?')} por dia · {len(env)} cartão(ões) já enviados · critérios: {', '.join((cfg.get('criterios') or {}).keys())}",
                "ultima": (ultimos[0][:16].replace('T', ' ') if ultimos else None), "ultimo_arquivo": "dados/pulsos/editor_gs_ponte.json", "onde": "GSI: `python3 integracoes/editor_gs_ponte.py listar`; enabled em config_editor_gs_ponte.json."})
    ks = (gsi / "integracoes" / "scheduler" / "KILL_SWITCH").exists()
    out.append({"id": "gsi_pulso_principal", "grupo": "GSI", "nome": "Pulso principal (coletas, discovery, 14h)", "ligada": not ks, "estado": "pausado (KILL_SWITCH)" if ks else "ligado",
                "detalhe": "coleta YouTube/Instagram, discovery, snapshots de desempenho; a medição das peças depende dele", "ultima": None, "ultimo_arquivo": None,
                "onde": "GSI: `python3 integracoes/scheduler/scheduler.py status`; rodar à mão `python3 -B integracoes/scheduler/rotinas.py run daily_scripts`; KILL_SWITCH só sai com autorização do Raphael."})
    return out


def do_app(push_inscritos=0, limpeza_dias=30):
    return [{"id": "app_push", "grupo": "Editor GS", "nome": "Vigia de avisos (push)", "ligada": push_inscritos > 0, "estado": f"{push_inscritos} aparelho(s) inscrito(s)" if push_inscritos else "sem aparelho inscrito",
             "detalhe": "a cada 30 s: entrega pronta, decisão pendente, pedido travado", "ultima": None, "ultimo_arquivo": None, "onde": "Ajuda → Avisos no celular"},
            {"id": "app_limpeza", "grupo": "Editor GS", "nome": f"Limpeza de trabalho ({limpeza_dias} dias)", "ligada": False, "estado": "manual", "detalhe": "apaga só _trabalho/ de entregas paradas; botão na Biblioteca", "ultima": None, "ultimo_arquivo": None, "onde": "Biblioteca → Armazenamento"}]


def registro(arq: Path = None):
    return _json(arq or REGISTRO, {})


# --- Automação 1 · Série recorrente de Stories ("Dúvida da semana") — 01/11/2026 ---------------------------------------------
# O app escolhe uma dúvida real da audiência no gs.db do GSI (comentário público classificado como QUESTION, sem autor), abre um
# pedido no Editor GS com o fluxo `stories-serie`, e quando a entrega fica pronta manda o vídeo 9:16 das três telas à Publora
# como RASCUNHO de Story (`videoType: "STORIES"`). Nunca agenda nem publica; nunca escreve no Notion nem no GSI.
import re, sqlite3
from datetime import timedelta

RODADAS = _cam.estado("automacao_rodadas.json")
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
SERIES = {"duvida_semana": {"nome": "Dúvida da semana", "descricao": "três telas: a dúvida de alguém da audiência, a resposta do Thiago e o convite para a próxima dúvida"}}
PADRAO_STORIES = {"serie": "duvida_semana", "dia_semana": 1, "hora": 10, "contas": [], "plataformas": ["youtube", "instagram"], "min_chars": 40, "dias_fonte": 900}
_PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d .()-]{8,}\d|https?://\S+|www\.\S+", re.I)


def stories_config(arq: Path = None):
    r = registro(arq).get("stories_serie") or {}
    return {**PADRAO_STORIES, **{k: v for k, v in (r.get("config") or {}).items() if k in PADRAO_STORIES}}


def stories_configurar(campos: dict, arq: Path = None, por="Raphael"):
    """Dia da semana (0=segunda), hora (0–23), contas da Publora e plataformas-fonte. Não liga nem desliga: a chave é `alternar`."""
    arq = arq or REGISTRO
    reg = registro(arq); ent = reg.get("stories_serie") or {}; cfg = {**PADRAO_STORIES, **(ent.get("config") or {})}
    if "dia_semana" in campos:
        d = int(campos["dia_semana"]); cfg["dia_semana"] = d if 0 <= d <= 6 else cfg["dia_semana"]
    if "hora" in campos:
        h = int(campos["hora"]); cfg["hora"] = h if 0 <= h <= 23 else cfg["hora"]
    if "contas" in campos:
        cfg["contas"] = [x.strip() for x in (campos["contas"] if isinstance(campos["contas"], list) else str(campos["contas"]).split(",")) if x.strip()]
    if "plataformas" in campos:
        cfg["plataformas"] = [x for x in (campos["plataformas"] if isinstance(campos["plataformas"], list) else str(campos["plataformas"]).split(",")) if x in ("youtube", "instagram")] or cfg["plataformas"]
    ent["config"] = cfg; ent["config_por"] = por; ent["config_quando"] = datetime.now().isoformat(timespec="minutes"); reg["stories_serie"] = ent
    arq.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    return cfg


def alternar(id_, ligada: bool, arq: Path = None, por="Raphael"):
    """Chave das automações planejadas/existentes do Editor GS (as do GSI se ligam no GSI). Para a série de Stories, ligada = o laço abre a rodada semanal."""
    if id_ not in {p["id"] for p in PLANEJADAS}:
        raise ValueError("Só as automações planejadas do Editor GS têm chave aqui; as do GSI se ligam no GSI.")
    arq = arq or REGISTRO
    reg = registro(arq); ent = reg.get(id_) or {}; ent.update({"ligada": bool(ligada), "quando": datetime.now().isoformat(timespec="minutes"), "por": por}); reg[id_] = ent
    arq.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    return ent


def rodadas(arq: Path = None):
    d = _json(arq or RODADAS, [])
    return d if isinstance(d, list) else []


def rodada_gravar(rod: dict, arq: Path = None):
    arq = arq or RODADAS
    lst = [r for r in rodadas(arq) if r.get("id") != rod["id"]] + [rod]
    lst.sort(key=lambda r: r.get("quando") or "")
    arq.write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
    return rod


def rodada_estado(rod: dict, estado: str, nota: str = "", arq: Path = None, **extra):
    rod["estado"] = estado; rod.update(extra)
    rod.setdefault("historico", []).append({"quando": datetime.now().isoformat(timespec="seconds"), "estado": estado, **({"nota": nota} if nota else {})})
    return rodada_gravar(rod, arq)


def _limpar_texto(t: str):
    t = _PII.sub("", t or "")
    t = re.sub(r"@[\w.]+", "", t)  # nunca o nome ou @ de quem perguntou
    return re.sub(r"\s+", " ", t).strip()


def stories_fontes_usadas(rods=None):
    return {f"{(r.get('fonte') or {}).get('plataforma')}:{(r.get('fonte') or {}).get('id')}" for r in (rods if rods is not None else rodadas()) if r.get("fonte")}


def stories_fonte(db: Path, usados: set = None, cfg: dict = None):
    """Uma dúvida real: comentário público (YouTube/Instagram) classificado QUESTION no GSI, não do dono do canal, com '?', sem
    dado pessoal, ainda não usado pela série. Ordem: tem tópico > likes > mais recente. Só leitura no gs.db. None se não houver."""
    cfg = cfg or PADRAO_STORIES; usados = usados or set()
    if not Path(db).exists():
        return None
    desde = (datetime.now() - timedelta(days=int(cfg.get("dias_fonte", 900)))).strftime("%Y-%m-%d")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tabelas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        if "comment_classifications" not in tabelas:
            return None
        cands = []
        for plat, tab, chave in (("youtube", "yt_comments", "video_id"), ("instagram", "ig_comments", "shortcode")):
            if plat not in cfg.get("plataformas", []) or tab not in tabelas:
                continue
            q = f"""select c.comment_id, c.text, c.likes, c.posted_at, c.{chave}, cc.topics_json from comment_classifications cc
                    join {tab} c on c.comment_id = cc.comment_id
                    where cc.platform = ? and cc.classification = 'QUESTION' and cc.is_current = 1 and coalesce(c.is_owner, 0) = 0
                      and c.posted_at >= ? and (c.parent_id is null or c.parent_id = '')"""
            for cid, texto, likes, quando, origem, topics in con.execute(q, (plat, desde)):
                if f"{plat}:{cid}" in usados:
                    continue
                limpo = _limpar_texto(texto)
                if len(limpo) < int(cfg.get("min_chars", 40)) or "?" not in limpo or len(limpo) > 600:
                    continue
                try:
                    tops = [t for t in json.loads(topics or "[]") if t]
                except Exception:  # noqa
                    tops = []
                cands.append({"plataforma": plat, "id": cid, "texto": limpo, "topicos": tops, "likes": int(likes or 0), "quando": (quando or "")[:10], "origem": origem, "contexto": _contexto(con, plat, origem, tabelas)})
        cands.sort(key=lambda c: (bool(c["topicos"]), c["likes"], c["quando"]), reverse=True)
        return cands[0] if cands else None
    finally:
        con.close()


def _contexto(con, plat, origem, tabelas):
    """Onde a pergunta foi feita (título do vídeo ou começo da legenda do post), para o Editor entender "ela", "esse", "aí"."""
    try:
        if plat == "youtube" and "yt_videos" in tabelas:
            r = con.execute("select title from yt_videos where video_id = ?", (origem,)).fetchone(); return f"vídeo \"{r[0]}\"" if r and r[0] else None
        if plat == "instagram" and "ig_posts" in tabelas:
            r = con.execute("select caption from ig_posts where shortcode = ?", (origem,)).fetchone(); return ("post \"" + _limpar_texto(r[0])[:120] + "\"") if r and r[0] else None
    except Exception:  # noqa
        return None
    return None


def stories_pedido(fonte: dict, cfg: dict = None):
    serie = SERIES.get((cfg or PADRAO_STORIES).get("serie", "duvida_semana"), SERIES["duvida_semana"])
    tops = ", ".join(fonte.get("topicos") or []) or "sem tópico classificado"
    return "\n".join([
        f"{serie['nome']}: {fonte['texto'][:90]}",  # primeira linha vira título do pedido e slug da pasta (precisa variar entre rodadas)
        "",
        f"Série recorrente de Stories · {serie['nome']} (Automação 1 do Editor GS). Fluxo: `fluxos/stories-serie.md`.",
        "",
        f"Dúvida escolhida pelo app (comentário público no {fonte['plataforma']}, {fonte.get('quando') or 'data não registrada'}, {fonte.get('likes', 0)} curtida(s); autor omitido de propósito; tópicos: {tops}):",
        f"> {fonte['texto']}",
        *( [f"Onde foi perguntado: {fonte['contexto']} (use para entender a que a pessoa se refere; não precisa citar)."] if fonte.get("contexto") else [] ),
        "",
        f"Entregue 3 telas `final_story-01..03.png` (1080×1920) e o vídeo `final_stories_9x16.mp4` com as três telas (5 s cada), mais `## Legenda do post` e `## Hashtags` na mensagem final. {serie['descricao'].capitalize()}.",
        "Não cite nome, @ nem canal de quem perguntou. Sem preço, oferta, número de alunos ou link. O app vai mandar o vídeo à Publora só como rascunho de Story; publicar é decisão do Raphael. Não escreva no Notion.",
        "Modo automático: poste o `## Plano de cenas` (texto das 3 telas) e monte direto, sem pedir aprovação."])


def _semana(dt: datetime):
    iso = dt.isocalendar(); return f"{iso[0]}-W{iso[1]:02d}"


def stories_devida(agora: datetime, reg: dict = None, rods: list = None, cfg: dict = None):
    """(True, motivo) quando a série está ligada, é o dia e já passou da hora, e nenhuma rodada começou nesta semana."""
    reg = reg if reg is not None else registro(); cfg = cfg or stories_config()
    ent = reg.get("stories_serie") or {}
    if not ent.get("ligada"):
        return False, "desligada (chave na aba Automações)"
    if agora.weekday() != int(cfg["dia_semana"]):
        return False, f"hoje não é {DIAS[int(cfg['dia_semana'])]}"
    if agora.hour < int(cfg["hora"]):
        return False, f"antes das {cfg['hora']}h"
    rods = rods if rods is not None else rodadas()
    sem = _semana(agora)
    if any(r.get("automacao") == "stories_serie" and r.get("semana") == sem for r in rods):
        return False, "já houve rodada nesta semana"
    return True, "na hora"


def stories_proxima(agora: datetime, cfg: dict = None, rods: list = None):
    """Próxima data prevista (texto curto) considerando o dia/hora e se a semana atual já foi usada."""
    cfg = cfg or stories_config(); rods = rods if rods is not None else rodadas()
    alvo = agora.replace(hour=int(cfg["hora"]), minute=0, second=0, microsecond=0)
    alvo += timedelta(days=(int(cfg["dia_semana"]) - alvo.weekday()) % 7)
    if alvo <= agora or any(r.get("automacao") == "stories_serie" and r.get("semana") == _semana(alvo) for r in rods):
        alvo += timedelta(days=7)
    return alvo.strftime("%d/%m %Hh") + f" ({DIAS[alvo.weekday()]})"


def rodada_id(agora: datetime, prefixo="stories"):
    import secrets
    return f"{prefixo}-{agora.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"  # sufixo evita colisão de duas rodadas no mesmo segundo (o registro faz upsert por id)


def rodada_nova(fonte: dict, conversa: dict, por: str = "laço", agora: datetime = None, arq: Path = None, automacao: str = "stories_serie", **extra):
    agora = agora or datetime.now()
    rod = {"id": rodada_id(agora, "stories" if automacao == "stories_serie" else "reciclado"), "automacao": automacao, "quando": agora.isoformat(timespec="seconds"), "por": por,
           "fonte": fonte, "issue": conversa.get("id"), "codigo": conversa.get("codigo"), "slug": conversa.get("slug"), "estado": "pedido_aberto", "publora": None, "historico": [], **extra}
    if automacao == "stories_serie":
        rod.update(serie=stories_config().get("serie"), semana=_semana(agora))
    return rodada_estado(rod, "pedido_aberto", f"pedido {conversa.get('codigo') or ''} criado", arq)


def stories_video_de(pasta: Path):
    for padrao in ("final_stories_9x16.mp4", "final_stories*.mp4", "final_9x16.mp4", "final_*.mp4"):
        achados = sorted(Path(pasta).glob(padrao)) if Path(pasta).exists() else []
        if achados:
            return achados[0]
    return None


def stories_legenda_de(secoes: list, fonte: dict = None):
    d = {s["chave"]: s["conteudo"] for s in (secoes or [])}
    leg = (d.get("descricao") or "").strip()
    if not leg and fonte:
        leg = f"Dúvida da semana: {fonte['texto'][:140]}"
    tags = " ".join(re.findall(r"#\w+", d.get("hashtags") or ""))[:120]
    return (leg + ("\n\n" + tags if tags and tags not in leg else "")).strip()[:2000]


def _stories_resumo(rods: list, cfg: dict, reg: dict, agora: datetime = None):
    agora = agora or datetime.now()
    minhas = [r for r in rods if r.get("automacao") == "stories_serie"]
    ult = minhas[-1] if minhas else None
    ligada = bool((reg.get("stories_serie") or {}).get("ligada"))
    est = {"pedido_aberto": "pedido aberto no Editor", "rascunho_publora": "rascunho na Publora", "entregue_sem_publora": "entregue; Publora não configurada", "entregue_sem_video": "entregue sem o vídeo",
           "bloqueado_revisor": "segurada pelo revisor de marca", "sem_fonte": "sem dúvida nova na fonte", "cancelado": "pedido cancelado", "falhou": "falhou"}
    partes = [f"{DIAS[int(cfg['dia_semana'])]} às {cfg['hora']}h", f"próxima {stories_proxima(agora, cfg, rods)}" if ligada else "ligue para agendar", f"{len(minhas)} rodada(s)"]
    if ult:
        partes.append(f"última {ult['quando'][:16].replace('T', ' ')} · {est.get(ult.get('estado'), ult.get('estado'))}" + (f" · {ult.get('codigo')}" if ult.get("codigo") else ""))
    return " · ".join(partes), (ult["quando"][:16].replace("T", " ") if ult else None)


def planejadas(arq: Path = None, rods_arq: Path = None):
    reg = registro(arq)
    out = []
    for p in PLANEJADAS:
        r = reg.get(p["id"]) or {}
        item = {**p, "grupo": "Planejada", "ligada": bool(r.get("ligada")), "estado": "liberada pelo Raphael (ainda em construção)" if r.get("ligada") else "planejada, desligada",
                "detalhe": p["descricao"], "ultima": None, "ultimo_arquivo": None, "onde": "aqui (a chave só registra a decisão; nada roda até a automação existir)", "decidido_em": r.get("quando")}
        if p["id"] == "stories_serie":
            cfg = stories_config(arq); rods = rodadas(rods_arq)
            detalhe, ultima = _stories_resumo(rods, cfg, reg)
            item.update({"grupo": "Editor GS", "estado": "ligada (só rascunho)" if r.get("ligada") else "desligada", "detalhe": f"{p['descricao']} · {detalhe}", "ultima": ultima,
                         "onde": "aqui: chave liga a rodada semanal; \"Rodar agora\" faz uma rodada fora de hora; nunca publica, só rascunho na Publora", "config": cfg, "existe": True})
        if p["id"] == "reel_reciclado":
            cfg = reciclado_config(arq); rods = rodadas(rods_arq)
            detalhe, ultima = _reciclado_resumo(rods, cfg, reg)
            item.update({"grupo": "Editor GS", "estado": "ligada (só rascunho)" if r.get("ligada") else "desligada", "detalhe": f"{p['descricao']} · {detalhe}", "ultima": ultima,
                         "onde": "aqui: chave liga a rodada a cada N dias; \"Rodar agora\" faz uma fora de hora; nunca publica, só rascunho de Reels na Publora; cada rodada vira um experimento (mesma peça, outro gancho)", "config": cfg, "existe": True})
        if p["id"] in ("posmortem", "variacao_vencedor", "alertas", "melhor_horario"):  # construídas em 03/11/2026 (servico/automacoes_dados.py)
            from servico import automacoes_dados as _ad
            est = _ad.estado(); quando = {"posmortem": (est.get("posmortem") or {}).get("quando"), "alertas": est.get("alertas_quando"),
                                          "melhor_horario": (est.get("melhor_horario") or {}).get("calculado_em"),
                                          "variacao_vencedor": max([v.get("quando") or "" for v in (est.get("variacoes") or {}).values()], default=None)}[p["id"]]
            onde = {"posmortem": "aqui: ligada, gera uma vez por dia (8h) as fichas D+7 pendentes; \"Rodar agora\" gera na hora",
                    "variacao_vencedor": "aqui: ligada, abre no máximo 2 pedidos por semana (um por peça acima de 1,5× no D+7); nunca publica",
                    "alertas": "aqui: ligada, confere a cada 10 min o último snapshot do GSI e manda push uma vez por alerta",
                    "melhor_horario": "aqui: ligada, recalcula toda semana; a tabela aparece nesta aba"}[p["id"]]
            item.update({"grupo": "Editor GS", "estado": "ligada" if r.get("ligada") else "desligada", "ultima": quando, "onde": onde, "existe": True})
        if p["id"] == "skills_garimpo":  # construída em 10/11/2026 (servico/skills_banco.py)
            from servico import skills_banco as _sb
            rs = _sb.rodadas(); ult = rs[-1] if rs else None; dev, motivo = _sb.pesquisa_devida()
            item.update({"grupo": "Editor GS", "estado": "ligada" if r.get("ligada") else "desligada", "ultima": (ult["quando"][:16].replace("T", " ") if ult else None), "existe": True,
                         "detalhe": f"{p['descricao']} · {len(rs)} rodada(s) · {motivo}" + (f" · última {ult.get('estado')} {ult.get('codigo') or ''}" if ult else ""),
                         "onde": "aqui: ligada, abre um pedido de pesquisa por semana; \"Pesquisar agora\" na aba Banco de skills faz uma rodada fora de hora"})
        if p["id"] == "pasta_vigiada":  # construída em 03/11/2026 (servico/pasta_vigiada.py)
            from servico import pasta_vigiada as _pv
            est = _pv.estado()
            item.update({"grupo": "Editor GS", "estado": "ligada" if r.get("ligada") else "desligada", "ultima": est.get("lido_em"), "existe": True,
                         "onde": "aqui: ligada, lê a pasta a cada 10 min e abre um pedido por gravação nova; só lê o Drive (nada é movido nem apagado)"})
        out.append(item)
    return out


def listar(gsi: Path, push_inscritos=0, arq: Path = None, rods_arq: Path = None):
    return do_gsi(gsi) + do_app(push_inscritos) + planejadas(arq, rods_arq)


# --- Automação 2 · Reel reciclado com gancho novo — 01/11/2026 -----------------------------------------------------------------
# A cada N dias o app escolhe um evergreen próprio acima da mediana do formato (Reel do Instagram ou Short do YouTube medido pelo GSI,
# ou peça do próprio app já publicada e medida), baixa o original (yt-dlp; peça do app usa o arquivo local), abre um pedido no Editor
# com o fluxo `reel-reciclado` (mesmo corte e áudio; só o gancho na tela, a capa e a legenda mudam) e, quando a entrega fica pronta,
# manda à Publora como RASCUNHO de Reels e grava `saida/<slug>/experimento.json` ("mesma peça, outro gancho"). Nunca publica; nunca
# escreve no Notion nem no GSI. O pós-mortem D+7 da peça nova, comparado com a razão da original, fecha o experimento.
import shutil, subprocess

PADRAO_RECICLADO = {"cada_dias": 7, "hora": 9, "min_razao": 1.5, "min_idade_dias": 45, "min_duracao_s": 12, "max_duracao_s": 90, "plataformas": ["instagram", "youtube"], "contas": [],
                    "voz_clonada": False, "tentativas": 3,
                    "temas": ["obs", "grav", "câmera", "camera", "webcam", "microfone", "áudio", "audio", "live", "aula", "cenário", "cenario", "luz", "ilumin", "preset", "tela", "zoom", "meet", "stream", "vídeo", "video", "tripé", "tripe", "infoprodut"]}
RECICLAGEM_REL = "entrada/_reciclagem"  # origem baixada fica em entrada/_reciclagem/<plataforma>-<id>/origem.mp4 (uma vez por original)


class ErroReciclagem(Exception):
    pass


def reciclado_config(arq: Path = None):
    r = registro(arq).get("reel_reciclado") or {}
    return {**PADRAO_RECICLADO, **{k: v for k, v in (r.get("config") or {}).items() if k in PADRAO_RECICLADO}}


def reciclado_configurar(campos: dict, arq: Path = None, por="Raphael"):
    """cada_dias (1–60), hora (0–23), min_razao (>= 1), min_idade_dias (>= 0), contas da Publora, plataformas-fonte, voz_clonada. Não liga nem desliga: a chave é `alternar`."""
    arq = arq or REGISTRO
    reg = registro(arq); ent = reg.get("reel_reciclado") or {}; cfg = {**PADRAO_RECICLADO, **(ent.get("config") or {})}
    if "cada_dias" in campos:
        d = int(campos["cada_dias"]); cfg["cada_dias"] = d if 1 <= d <= 60 else cfg["cada_dias"]
    if "hora" in campos:
        h = int(campos["hora"]); cfg["hora"] = h if 0 <= h <= 23 else cfg["hora"]
    if "min_razao" in campos:
        r = float(str(campos["min_razao"]).replace(",", ".")); cfg["min_razao"] = r if r >= 1 else cfg["min_razao"]
    if "min_idade_dias" in campos:
        i = int(campos["min_idade_dias"]); cfg["min_idade_dias"] = i if i >= 0 else cfg["min_idade_dias"]
    if "contas" in campos:
        cfg["contas"] = [x.strip() for x in (campos["contas"] if isinstance(campos["contas"], list) else str(campos["contas"]).split(",")) if x.strip()]
    if "plataformas" in campos:
        cfg["plataformas"] = [x for x in (campos["plataformas"] if isinstance(campos["plataformas"], list) else str(campos["plataformas"]).split(",")) if x in ("instagram", "youtube")] or cfg["plataformas"]
    if "voz_clonada" in campos:
        cfg["voz_clonada"] = str(campos["voz_clonada"]).lower() in ("1", "true", "sim")
    ent["config"] = cfg; ent["config_por"] = por; ent["config_quando"] = datetime.now().isoformat(timespec="minutes"); reg["reel_reciclado"] = ent
    arq.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    return cfg


def reciclado_usados(rods=None):
    """Originais já reciclados (ou com download que falhou nesta semana não contam: só os que viraram pedido)."""
    return {f"{(r.get('fonte') or {}).get('plataforma')}:{(r.get('fonte') or {}).get('id')}" for r in (rods if rods is not None else rodadas())
            if r.get("automacao") == "reel_reciclado" and r.get("fonte") and r.get("estado") not in ("sem_fonte",)}


def _tem_tema(texto: str, temas: list):
    t = (texto or "").lower()
    return not temas or any(k in t for k in temas)


def _idade_dias(publicado: str, hoje: datetime):
    try:
        return (hoje.date() - datetime.fromisoformat(str(publicado)[:10]).date()).days
    except Exception:  # noqa
        return None


def reciclado_candidatos(db: Path, saida: Path = None, usados: set = None, cfg: dict = None, hoje: datetime = None, cache_textos: dict = None, limite: int = 12):
    """Evergreens próprios acima da mediana do formato, ordenados: peça do app com arquivo local primeiro, depois razão × mediana.
    Fonte GSI: último snapshot `current` de cada Reel (Instagram) ou Short (YouTube) das contas próprias (sources.kind='own'), com
    razão >= min_razao, idade >= min_idade_dias, duração dentro da faixa, não pago, com tema de gravação na legenda/título e ainda não
    reciclado. Fonte app: saida/<slug>/ com publicacoes.json casado a um id medido e `final_9x16.mp4` local. Só leitura."""
    cfg = cfg or PADRAO_RECICLADO; usados = usados or set(); hoje = hoje or datetime.now()
    out = []
    if saida and Path(saida).exists() and Path(db).exists():
        from servico import pecas as _pcs
        for linha in _pcs.listar(Path(saida), db, cache_textos or {}):
            raz = linha.get("vs_mediana"); plat = linha.get("plataforma")
            if raz is None or raz < float(cfg["min_razao"]) or not (Path(saida) / linha["slug"] / "final_9x16.mp4").exists():
                continue
            idade = _idade_dias(linha.get("publicado_em"), hoje)
            if idade is None or idade < int(cfg["min_idade_dias"]):
                continue
            ids = [i for i in _pcs._ids_publicados(_pcs.publicacoes(Path(saida) / linha["slug"])) if i[0] == plat]
            iid = ids[0][1] if ids else linha["slug"]
            if f"{plat}:{iid}" in usados or plat not in cfg.get("plataformas", []):
                continue
            out.append({"plataforma": plat, "id": iid, "url": None, "titulo": linha.get("titulo") or linha["slug"], "legenda": "", "gancho": (linha.get("etiquetas") or {}).get("gancho"),
                        "publicado": (linha.get("publicado_em") or "")[:10], "idade_dias": idade, "duracao_s": None, "views": linha.get("views"), "razao": round(float(raz), 1), "mediana": None,
                        "origem": "app", "arquivo": f"saida/{linha['slug']}/final_9x16.mp4", "slug_origem": linha["slug"], "codigo_origem": linha.get("codigo")})
    if Path(db).exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); con.row_factory = sqlite3.Row
        try:
            tabelas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
            if "performance_snapshots" in tabelas:
                donos = [r["handle"] for r in con.execute("select handle from sources where kind='own'")] if "sources" in tabelas else []
                q = f"""select s.platform, s.item_id, s.views, s.ratio_vs_format_median, s.median_views_format, s.format from performance_snapshots s join (select platform u_p, item_id u_i, max(computed_at) u_m from performance_snapshots where horizon='current' group by 1, 2) u on u.u_p=s.platform and u.u_i=s.item_id
                        where s.horizon='current' and s.format in ('reel', 'short') and s.ratio_vs_format_median >= ?
                        {('and s.owner in (' + ','.join('?' * len(donos)) + ')') if donos else ''}
                        and s.computed_at = u.u_m  -- 03/11/2026: máximo agrupado (era subconsulta por linha, lenta)"""
                ja = {f"{c['plataforma']}:{c['id']}" for c in out}  # peça do app com o mesmo id tem prioridade (arquivo local)
                for s in con.execute(q, [float(cfg["min_razao"])] + donos):
                    plat, iid = s["platform"], s["item_id"]
                    if plat not in cfg.get("plataformas", []) or f"{plat}:{iid}" in usados or f"{plat}:{iid}" in ja:
                        continue
                    if plat == "instagram" and "ig_posts" in tabelas:
                        p = con.execute("select caption, posted_at, video_duration_s, is_paid, url from ig_posts where shortcode=?", (iid,)).fetchone()
                        if not p or p["is_paid"]:
                            continue
                        legenda = _limpar_texto(p["caption"] or ""); titulo = (legenda.splitlines() or [""])[0][:80] or iid; pub = p["posted_at"]; dur = p["video_duration_s"]; url = p["url"] or f"https://www.instagram.com/reel/{iid}/"
                    elif plat == "youtube" and "yt_videos" in tabelas:
                        v = con.execute("select title, description, published_at, duration_s from yt_videos where video_id=?", (iid,)).fetchone()
                        if not v:
                            continue
                        legenda = _limpar_texto(v["description"] or "")[:300]; titulo = (v["title"] or iid)[:80]; pub = v["published_at"]; dur = v["duration_s"]; url = f"https://www.youtube.com/shorts/{iid}"
                    else:
                        continue
                    idade = _idade_dias(pub, hoje)
                    if idade is None or idade < int(cfg["min_idade_dias"]):
                        continue
                    if dur is not None and not (float(cfg["min_duracao_s"]) <= float(dur) <= float(cfg["max_duracao_s"])):
                        continue
                    if not _tem_tema(f"{titulo} {legenda}", cfg.get("temas") or []):
                        continue
                    out.append({"plataforma": plat, "id": iid, "url": url, "titulo": titulo, "legenda": legenda[:300], "gancho": None, "publicado": str(pub)[:10], "idade_dias": idade,
                                "duracao_s": round(float(dur)) if dur is not None else None, "views": s["views"], "razao": round(float(s["ratio_vs_format_median"]), 1), "mediana": s["median_views_format"],
                                "origem": "gsi", "arquivo": None, "slug_origem": None, "codigo_origem": None})
        finally:
            con.close()
    out.sort(key=lambda c: (c["origem"] == "app", c["razao"] or 0), reverse=True)
    return out[:limite]


def reciclado_baixar(fonte: dict, entrada: Path):
    """Garante o arquivo da peça original e devolve o caminho relativo ao workspace. Peça do app: usa o final_9x16 local. GSI: baixa
    com yt-dlp em entrada/_reciclagem/<plataforma>-<id>/origem.mp4 (reaproveita se já existir). Levanta ErroReciclagem se não conseguir."""
    if fonte.get("arquivo"):
        return fonte["arquivo"]
    from servico import referencias as _refs
    pasta = Path(entrada) / "_reciclagem" / f"{fonte['plataforma']}-{fonte['id']}"; alvo = pasta / "origem.mp4"
    rel = f"{RECICLAGEM_REL}/{pasta.name}/origem.mp4"
    if alvo.exists() and alvo.stat().st_size > 1000:
        return rel
    if not fonte.get("url"):
        raise ErroReciclagem("original sem link para baixar")
    if not _refs.YTDLP.exists():
        raise ErroReciclagem("yt-dlp não instalado no venv do editor-gs")
    pasta.mkdir(parents=True, exist_ok=True)
    cmd = [str(_refs.YTDLP), "--no-playlist", "--no-warnings", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4", "-o", str(pasta / "origem.%(ext)s"), fonte["url"]]
    if _refs.NODE.exists():
        cmd[1:1] = ["--js-runtimes", f"node:{_refs.NODE}"]
    ck = _refs.cookies_para(fonte["url"])
    if ck:
        cmd[1:1] = ["--cookies", str(ck)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise ErroReciclagem("download passou de 10 min")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()[-300:] or "yt-dlp falhou"
        if "instagram" in fonte["url"].lower() and ("login" in msg.lower() or "cookies" in msg.lower() or "empty media" in msg.lower()):
            msg += " | Instagram pediu login: exporte os cookies para .cookies/instagram.txt (Ajuda → Referências do Instagram)."
        raise ErroReciclagem(msg)
    achado = next((p for p in pasta.iterdir() if p.name.startswith("origem.") and p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")), None)
    if not achado:
        raise ErroReciclagem("yt-dlp não gerou vídeo")
    if achado != alvo:
        shutil.move(str(achado), str(alvo))
    return rel


def reciclado_pedido(fonte: dict, arquivo_rel: str, cfg: dict = None, gancho_sugerido: str = ""):
    cfg = cfg or PADRAO_RECICLADO
    plat = {"instagram": "Instagram", "youtube": "YouTube"}.get(fonte["plataforma"], fonte["plataforma"])
    origem = f"peça {fonte.get('codigo_origem') or fonte.get('slug_origem')} deste app" if fonte.get("origem") == "app" else f"{'Reel' if fonte['plataforma'] == 'instagram' else 'Short'} do {plat}"
    return "\n".join([
        f"Reel reciclado: {fonte['titulo'][:80]}",  # primeira linha vira título do pedido e slug (precisa variar entre rodadas)
        "",
        "Reel reciclado com gancho novo (Automação 2 do Editor GS). Fluxo: `fluxos/reel-reciclado.md`.",
        "",
        f"Peça original escolhida pelo app ({origem}, publicada em {fonte.get('publicado') or '?'}, {fonte.get('views') or '?'} views, {fonte.get('razao')}× a mediana do formato; evergreen): `{arquivo_rel}`"
        + (f" ({fonte['duracao_s']} s)." if fonte.get("duracao_s") else "."),
        *([f"Legenda original: > {fonte['legenda'][:300]}"] if fonte.get("legenda") else []),
        *([f"Gancho registrado da original: {fonte['gancho']}"] if fonte.get("gancho") else []),
        *([f"Gancho escolhido pelo Raphael na biblioteca de ganchos (use como base do gancho novo, adaptado a esta peça; não copie se não couber na fala): \"{gancho_sugerido.strip()[:200]}\""] if (gancho_sugerido or "").strip() else []),
        "",
        "Experimento \"mesma peça, outro gancho\": entregue `final_9x16.mp4` com o MESMO corte e o MESMO áudio do original (não corte, não reordene, não troque a fala). Mude só: (1) a frase de impacto na tela nos 3 primeiros segundos (gancho novo, ângulo diferente do original: pergunta, número, erro comum ou contraste), (2) a capa (`capa.png`) com o gancho novo e (3) a legenda do post, nova."
        + (" Pode regravar só a abertura com a voz clonada do Thiago (`narrar`, `voz_nome=\"thiago\"`), rotulada como voz clonada (sintética) no `## Resumo`." if cfg.get("voz_clonada") else " Sem narração nova: a voz clonada não entra nesta rodada."),
        "Na mensagem final: `## Resumo`, `## Gancho` (só o novo, uma linha), `## Abertura original` (a primeira frase falada ou escrita na tela do original, para o registro do experimento), `## Legenda do post`, `## Hashtags`, `## Pendências` e `## Arquivos`.",
        "Sem preço, oferta, número de alunos ou link. O app vai mandar o vídeo à Publora só como rascunho de Reels; publicar é decisão do Raphael. Não escreva no Notion. Não altere `entrada/`" + (" nem a pasta da peça original em `saida/`." if fonte.get("origem") == "app" else "."),
        "Modo automático: poste o plano (gancho escolhido e por quê) e monte direto, sem pedir aprovação."])


def _reciclado_ultima(rods: list):
    minhas = [r for r in rods if r.get("automacao") == "reel_reciclado" and r.get("estado") != "sem_fonte"]
    return minhas[-1] if minhas else None


def reciclado_devida(agora: datetime, reg: dict = None, rods: list = None, cfg: dict = None):
    """(True, motivo) quando a automação está ligada, já passou da hora e a última rodada com pedido tem `cada_dias` ou mais."""
    reg = reg if reg is not None else registro(); cfg = cfg or reciclado_config()
    if not (reg.get("reel_reciclado") or {}).get("ligada"):
        return False, "desligada (chave na aba Automações)"
    if agora.hour < int(cfg["hora"]):
        return False, f"antes das {cfg['hora']}h"
    rods = rods if rods is not None else rodadas()
    ult = _reciclado_ultima(rods)
    if ult:
        dias = (agora.date() - datetime.fromisoformat(ult["quando"]).date()).days
        if dias < int(cfg["cada_dias"]):
            return False, f"última rodada há {dias} dia(s); a cada {cfg['cada_dias']}"
    hoje = [r for r in rods if r.get("automacao") == "reel_reciclado" and str(r.get("quando", ""))[:10] == agora.date().isoformat()]
    if hoje:
        return False, "já houve rodada hoje"
    return True, "na hora"


def reciclado_proxima(agora: datetime, cfg: dict = None, rods: list = None):
    cfg = cfg or reciclado_config(); rods = rods if rods is not None else rodadas()
    ult = _reciclado_ultima(rods)
    base = datetime.fromisoformat(ult["quando"]) + timedelta(days=int(cfg["cada_dias"])) if ult else agora
    alvo = base.replace(hour=int(cfg["hora"]), minute=0, second=0, microsecond=0)
    if alvo <= agora:
        alvo = agora.replace(hour=int(cfg["hora"]), minute=0, second=0, microsecond=0)
        if alvo <= agora:
            alvo += timedelta(days=1)
    return alvo.strftime("%d/%m %Hh") + f" ({DIAS[alvo.weekday()]})"


def reciclado_video_de(pasta: Path):
    for padrao in ("final_9x16.mp4", "final_*9x16*.mp4", "final_*.mp4"):
        achados = sorted(Path(pasta).glob(padrao)) if Path(pasta).exists() else []
        if achados:
            return achados[0]
    return None


def reciclado_capa_de(pasta: Path):
    for nome in ("capa.png", "capa.jpg", "capa_9x16.png"):
        if (Path(pasta) / nome).exists():
            return Path(pasta) / nome
    return None


def reciclado_legenda_de(secoes: list, fonte: dict = None):
    d = {s["chave"]: s["conteudo"] for s in (secoes or [])}
    leg = (d.get("descricao") or "").strip()
    if not leg and fonte:
        leg = (fonte.get("titulo") or "")[:140]
    tags = " ".join(re.findall(r"#\w+", d.get("hashtags") or ""))[:160]
    return (leg + ("\n\n" + tags if tags and tags not in leg else "")).strip()[:2000]


def reciclado_experimento(rod: dict, secoes: list, publora: dict = None, legenda: str = ""):
    d = {s["chave"]: s["conteudo"] for s in (secoes or [])}
    def _linha(txt):  # primeira linha, sem marcação Markdown nem aspas
        l = next((l for l in (txt or "").splitlines() if l.strip()), "")
        return re.sub(r"\*+|__|`", "", l).strip(" -\"“”'")
    gancho = _linha(d.get("gancho")); abertura = _linha(d.get("abertura-original")) or (rod.get("fonte") or {}).get("gancho") or ""
    return {"tipo": "mesma peça, outro gancho", "automacao": "reel_reciclado", "rodada": rod["id"], "codigo": rod.get("codigo"), "slug": rod.get("slug"), "quando": datetime.now().isoformat(timespec="seconds"),
            "original": {k: (rod.get("fonte") or {}).get(k) for k in ("plataforma", "id", "url", "titulo", "publicado", "views", "razao", "origem", "slug_origem", "codigo_origem")},
            "gancho_original": abertura[:200], "gancho_novo": gancho[:200], "legenda_nova": legenda[:500], "publora": publora,
            "como_ler": "quando a peça nova tiver 7 dias publicada, comparar a razão × mediana dela (pós-mortem D+7) com a razão da original; só o gancho, a capa e a legenda mudaram", "status": "aberto"}


def _reciclado_resumo(rods: list, cfg: dict, reg: dict, agora: datetime = None):
    agora = agora or datetime.now()
    minhas = [r for r in rods if r.get("automacao") == "reel_reciclado"]
    ult = minhas[-1] if minhas else None
    ligada = bool((reg.get("reel_reciclado") or {}).get("ligada"))
    est = {"pedido_aberto": "pedido aberto no Editor", "rascunho_publora": "rascunho de Reels na Publora", "entregue_sem_publora": "entregue; Publora não configurada", "entregue_sem_video": "entregue sem o vídeo",
           "bloqueado_revisor": "segurada pelo revisor de marca", "sem_fonte": "sem evergreen disponível", "sem_video_origem": "não conseguiu baixar o original", "cancelado": "pedido cancelado", "falhou": "falhou"}
    partes = [f"a cada {cfg['cada_dias']} dia(s) às {cfg['hora']}h", f"razão ≥ {cfg['min_razao']}× e {cfg['min_idade_dias']}+ dias", f"próxima {reciclado_proxima(agora, cfg, rods)}" if ligada else "ligue para agendar", f"{len(minhas)} rodada(s)"]
    if ult:
        partes.append(f"última {ult['quando'][:16].replace('T', ' ')} · {est.get(ult.get('estado'), ult.get('estado'))}" + (f" · {ult.get('codigo')}" if ult.get("codigo") else ""))
    return " · ".join(partes), (ult["quando"][:16].replace("T", " ") if ult else None)


# --- Fechamento do experimento "mesma peça, outro gancho" (02/11/2026) -----------------------------------------------------------------
GANHOU, PERDEU, DIAS_FECHAR = 1.2, 0.8, 7


def experimentos(saida: Path):
    out = []
    for p in sorted(Path(saida).glob("*/experimento.json")) if Path(saida).exists() else []:
        try:
            e = json.loads(p.read_text(encoding="utf-8")); e["_arquivo"] = str(p); out.append(e)
        except Exception:  # noqa
            pass
    return out


def experimento_veredito(razao_nova, razao_original):
    if razao_nova is None or razao_original in (None, 0):
        return None
    q = float(razao_nova) / float(razao_original)
    return "ganhou" if q >= GANHOU else ("perdeu" if q <= PERDEU else "empate")


def experimentos_fechar(saida: Path, db: Path, cache_textos: dict = None, hoje=None):
    """Para cada experimento aberto: se a peça nova já tem métrica no GSI e 7+ dias de publicada, compara a razão × mediana dela com a da
    original e grava status ganhou/perdeu/empate (+ resultado). Devolve os fechados nesta chamada. Nunca reabre."""
    from servico import pecas as _pcs, metricas as _mtr
    hoje = hoje or datetime.now().date(); fechados = []
    for e in experimentos(saida):
        if e.get("status") != "aberto" or not e.get("slug"):
            continue
        f = _pcs.ficha(e["slug"], Path(saida), db, cache_textos or {})
        m = next((x for x in (f.get("metricas") or []) if x.get("views") is not None), None)
        pub = next((r.get("quando") for r in f.get("publicacoes", []) if r.get("tipo") in ("publora", "youtube")), None)
        dia = _mtr._dia(pub) if pub else None
        if not m or not dia or (hoje - dia).days < DIAS_FECHAR:
            continue
        raz_nova = m.get("ratio_vs_format_median"); raz_orig = (e.get("original") or {}).get("razao")
        v = experimento_veredito(raz_nova, raz_orig)
        if not v:
            continue
        e.update(status=v, resultado={"razao_nova": raz_nova, "razao_original": raz_orig, "views_nova": m.get("views"), "views_original": (e.get("original") or {}).get("views"),
                                      "medido_em": m.get("computed_at"), "fechado_em": datetime.now().isoformat(timespec="minutes"), "dias": (hoje - dia).days,
                                      "leitura": {"ganhou": "o gancho novo rendeu pelo menos 20 % mais que o original (razão × mediana)", "perdeu": "o gancho novo rendeu pelo menos 20 % menos", "empate": "diferença menor que 20 %: sem conclusão"}[v]})
        arq = e.pop("_arquivo"); Path(arq).write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8"); fechados.append(e)
    return fechados


def experimentos_resumo(saida: Path):
    lst = experimentos(saida)
    for e in lst:
        e.pop("_arquivo", None)
    return {"itens": sorted(lst, key=lambda e: e.get("quando") or "", reverse=True), "abertos": sum(1 for e in lst if e.get("status") == "aberto"),
            "ganhou": sum(1 for e in lst if e.get("status") == "ganhou"), "perdeu": sum(1 for e in lst if e.get("status") == "perdeu"), "empate": sum(1 for e in lst if e.get("status") == "empate")}
