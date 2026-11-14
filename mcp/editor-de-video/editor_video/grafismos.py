"""Fase B (07/11/2026): plano de grafismos semântico, no jeito do Máquina (docs/maquina/ANALISE-2026-11-06.md, seção 3).
O agente lê a fala com tempo e decide, frase a frase, que gráfico entra e em que palavra; o Remotion desenha (remotion/src/Grafismos.tsx).
- grafismos.json = {"itens": [{tipo, inicio, fim, palavra?, ...campos do tipo}]} em tempos do vídeo cortado. Tipos em TIPOS.
- "palavra": ancora o início na palavra dita (a mais próxima de `inicio`, ou a primeira) — o gráfico entra quando ela é falada.
- "gesto" (10/11/2026): alternativa à palavra; ancora no evento de gestos.py (detectar_gestos) do mesmo tipo mais próximo de `inicio`
  (polegar_cima, apontar_cima, vitoria, mao_aberta, punho, virada_esquerda/direita…); os eventos vêm de `gestos=` ou da chave "gestos" do plano.
- Logos reais: workspace/marca/logos/<nome>.png|svg|jpg primeiro, depois Simple Icons (CC0, cor oficial); ícones de objeto: Lucide (ISC).
- plano_auto: regras sem modelo (marcas citadas, números, "sem X" repetido, "não precisa de X", palavras-chave) para quando o agente não escreve o plano.
- Séries: workspace/series/<slug>.json guarda título, destaque, @, trilha e kicker; montar_remotion(serie=, parte=) abre com o título e fecha com a cartela."""
import json, os, re, shutil, unicodedata
from pathlib import Path
from .util import ErroFerramenta, caminho, ler_json

RAIZ = Path(__file__).resolve().parents[3]
# 11/11/2026: sem EDITOR_GS_WORKSPACE, usa o workspace da instalação (EDITOR_GS_HOME ou ~/EditorGS) antes do do repositório.
WORKSPACE = Path(os.environ.get("EDITOR_GS_WORKSPACE") or (Path(os.environ["EDITOR_GS_HOME"]) / "workspace" if os.environ.get("EDITOR_GS_HOME") else (Path.home() / "EditorGS" / "workspace" if (Path.home() / "EditorGS" / "workspace").is_dir() else RAIZ / "workspace")))
LOGOS_DIR = WORKSPACE / "marca" / "logos"
SERIES_DIR = WORKSPACE / "series"
NODE_MODULES = RAIZ / "remotion" / "node_modules"

TIPOS = {
    "kicker": "rótulo pequeno de contexto com ponto laranja (\"OBS Studio · 2 formatos\", \"PARTE 2\"); padrão no topo",
    "manchete": "texto grande em 1–2 linhas com `destaque` (palavra laranja), `rotulo` pequeno em pílula acima, `caixa`=true pinta o destaque numa caixa laranja, `ondas`=true põe ondas sonoras embaixo",
    "pilula": "um termo numa pílula laranja (\"MICROFONE SIMPLES\")",
    "riscado": "`texto` riscado em laranja na palavra e, opcional, `troca` entrando no lugar em `troca_em`",
    "checklist": "`itens` [{texto, em|palavra}] acumulando com ✓ laranja (até 5)",
    "pilulas": "`itens` [{texto, em|palavra, logo?}] acumulando lado a lado (enumeração; até 5)",
    "fluxo": "`itens` [{icone|logo, em|palavra, texto?}] ligados por linha (celular → USB → notebook; até 4)",
    "cartoes": "`itens` [{rotulo, texto, sinal: ok|nao, imagem|logo|icone, em|palavra}] — 1 ou 2 cartões no topo (comparação ruim × bom)",
    "numero": "número grande (`texto` \"R$ 100\", \"1 TARDE\"), `rotulo` acima, `sub` abaixo, `antes` [{texto, em}] riscáveis acima, `imagem|logo|icone` ao lado; bom com tela_cheia",
    "logos": "`itens` [{logo, em|palavra, texto?}] logos reais entrando quando a ferramenta é citada (até 4)",
    "ondas": "ondas sonoras laranja animadas (assunto áudio), `texto` opcional acima",
    "cta": "cartão de perfil: `handle` (@), `texto` pequeno, `botao` (\"Seguir\") que vira \"Seguindo\" na metade",
}
DUR_PADRAO = {"kicker": 2.6, "manchete": 2.4, "pilula": 1.8, "riscado": 2.4, "ondas": 2.2, "cta": 3.0, "numero": 3.0}
POSICOES = ("peito", "topo", "centro")
POS_PADRAO = {"kicker": "topo", "cartoes": "topo"}
MAX_ITENS = {"checklist": 5, "pilulas": 5, "fluxo": 4, "cartoes": 2, "logos": 4}
# nomes falados → slug do Simple Icons (o arquivo em marca/logos/ com o mesmo nome tem prioridade)
ALIAS_LOGO = {
    "obs": "obsstudio", "obs studio": "obsstudio", "obsstudio": "obsstudio", "meet": "googlemeet", "google meet": "googlemeet", "googlemeet": "googlemeet",
    "zoom": "zoom", "instagram": "instagram", "insta": "instagram", "reels": "instagram", "youtube": "youtube", "tiktok": "tiktok", "tik tok": "tiktok",
    "whatsapp": "whatsapp", "zap": "whatsapp", "drive": "googledrive", "google drive": "googledrive", "facebook": "facebook", "telegram": "telegram",
    "discord": "discord", "twitch": "twitch", "elgato": "elgato", "stream deck": "elgato", "notion": "notion", "claude": "claude", "chrome": "googlechrome",
    "apple": "apple", "iphone": "apple", "mac": "apple", "android": "android", "twitter": "x", "x": "x", "threads": "threads", "gemini": "googlegemini",
    "spotify": "spotify", "google": "google",
}
CITACAO_LOGO = {"obs", "meet", "zoom", "instagram", "youtube", "tiktok", "whatsapp", "drive", "discord", "twitch", "notion", "gemini", "iphone", "android", "telegram", "facebook", "threads"}


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).strip(".,;:!?\"'()…")


def palavras_planas(pal: dict):
    """Lista plana [{p, i, f}] a partir do palavras.json (segmentos com palavras ou lista `palavras`)."""
    itens = pal.get("palavras") or [w for s in pal.get("segmentos", []) for w in (s.get("palavras") or [])]
    return [{"p": (w.get("palavra") or w.get("texto") or "").strip(), "i": float(w.get("inicio", 0)), "f": float(w.get("fim", w.get("inicio", 0)))} for w in itens if (w.get("palavra") or w.get("texto"))]


def ancorar(palavra, ws, perto=None, janela_s=2.5):
    """Início da palavra dita (ou da expressão de até 3 palavras) mais próxima de `perto`; sem `perto`, a primeira. None se não achar."""
    alvo = [_norm(x) for x in str(palavra).split() if _norm(x)]
    if not alvo:
        return None
    achados = [ws[k]["i"] for k in range(len(ws) - len(alvo) + 1) if all(_norm(ws[k + j]["p"]) == alvo[j] for j in range(len(alvo)))]
    if not achados:
        return None
    if perto is None:
        return achados[0]
    melhor = min(achados, key=lambda t: abs(t - perto))
    return melhor if abs(melhor - perto) <= janela_s else None


# ---------- mídia: logo, ícone, imagem ----------
def _svg_limpo(texto):
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    return re.sub(r"<title>.*?</title>", "", texto, flags=re.S).strip()


def resolver_logo(nome):
    """{"tipo": "img", "origem": caminho} (marca/logos) ou {"tipo": "svg", "svg", "cor"} (Simple Icons). None se não existir."""
    n = _norm(nome)
    base = n.replace(" ", "-")
    if LOGOS_DIR.exists():
        extra = ler_json(LOGOS_DIR / "logos.json") if (LOGOS_DIR / "logos.json").exists() else {}
        base = _norm(extra.get(n, base)).replace(" ", "-")
        for ext in (".png", ".svg", ".jpg", ".jpeg", ".webp"):
            p = LOGOS_DIR / f"{base}{ext}"
            if p.exists():
                return {"tipo": "img", "origem": str(p), "nome": nome}
    slug = ALIAS_LOGO.get(n) or ALIAS_LOGO.get(base) or base.replace("-", "")
    arq = NODE_MODULES / "simple-icons" / "icons" / f"{slug}.svg"
    if not arq.exists():
        return None
    cor = "#FFFFFF"
    dados = NODE_MODULES / "simple-icons" / "data" / "simple-icons.json"
    if dados.exists():
        try:
            lst = json.loads(dados.read_text(encoding="utf-8"))
            lst = lst.get("icons", lst) if isinstance(lst, dict) else lst
            for ic in lst:
                if ic.get("slug") == slug or _norm(ic.get("title", "")).replace(" ", "") == slug:
                    cor = "#" + ic["hex"]; break
        except (OSError, ValueError, KeyError):
            pass
    return {"tipo": "svg", "svg": _svg_limpo(arq.read_text(encoding="utf-8")), "cor": cor, "nome": nome, "marca": True}


def resolver_icone(nome):
    arq = NODE_MODULES / "lucide-static" / "icons" / f"{_norm(nome).replace(' ', '-')}.svg"
    return {"tipo": "svg", "svg": _svg_limpo(arq.read_text(encoding="utf-8")), "cor": "currentColor", "nome": nome, "marca": False} if arq.exists() else None


def _midia(obj, avisos):
    for chave, fn in (("logo", resolver_logo), ("icone", resolver_icone)):
        if obj.get(chave):
            m = fn(obj[chave])
            if not m:
                avisos.append(f"{chave} '{obj[chave]}' não existe (logos: Simple Icons ou workspace/marca/logos/; ícones: nomes do Lucide, ex. smartphone, usb, laptop, mic, webcam)")
            return m
    if obj.get("imagem"):
        try:
            return {"tipo": "img", "origem": str(caminho(obj["imagem"])), "nome": Path(obj["imagem"]).name}
        except ErroFerramenta:
            avisos.append(f"imagem não encontrada: {obj['imagem']}")
    return None


# ---------- normalização ----------
def normalizar(plano, palavras=None, duracao_s=None, gestos=None):
    """Valida e completa o plano: tipos, tempos ancorados na palavra (ou no gesto), fim padrão, limites, mídia resolvida, sobreposição na mesma posição.
    Devolve (itens, avisos). Itens com mídia trazem "midia" pronta para o Remotion ("origem" ainda local; preparar_midias copia).
    Gestos (10/11/2026): item com `gesto` ("polegar_cima", "apontar_cima", "virada_esquerda"…) entra no evento desse tipo mais próximo de `inicio`
    (gestos.py). Os eventos vêm de `gestos` (caminho/JSON/lista) ou, sem ele, da chave "gestos" do próprio plano (caminho do gestos.json)."""
    from . import gestos as gst
    if isinstance(plano, (str, Path)) and not str(plano).strip().startswith(("{", "[")):
        plano = ler_json(plano)
    elif isinstance(plano, str):
        plano = json.loads(plano)
    brutos = plano.get("itens", []) if isinstance(plano, dict) else list(plano or [])
    ws = palavras_planas(palavras) if isinstance(palavras, dict) else (palavras or [])
    dur = float(duracao_s or (ws[-1]["f"] + 0.5 if ws else 0) or 0)
    avisos, itens = [], []
    try:
        evs = gst.eventos_de(gestos if gestos is not None else (plano.get("gestos") if isinstance(plano, dict) else None))
    except Exception as e:  # noqa: BLE001
        evs = []; avisos.append(f"gestos: não li os eventos ({e}); itens com `gesto` ficam no tempo dado")

    def por_gesto(obj, rotulo, perto):
        if not obj.get("gesto"):
            return None
        if not evs:
            avisos.append(f"{rotulo}: tem `gesto` '{obj['gesto']}' mas não há eventos (rode detectar_gestos e passe o gestos.json)"); return None
        a = gst.ancorar_gesto(obj["gesto"], evs, perto)
        if a is None:
            avisos.append(f"{rotulo}: gesto '{obj['gesto']}' não aconteceu perto de {perto}; mantive o tempo dado")
        return a
    for n, g in enumerate(brutos, 1):
        g = dict(g); tipo = str(g.get("tipo", "")).strip().lower()
        if tipo not in TIPOS:
            avisos.append(f"item {n}: tipo '{tipo}' desconhecido (use {', '.join(TIPOS)})"); continue
        ini = g.get("inicio")
        if g.get("palavra") and ws:
            a = ancorar(g["palavra"], ws, float(ini) if ini is not None else None)
            if a is None:
                avisos.append(f"item {n}: palavra '{g['palavra']}' não foi dita perto de {ini}; mantive o tempo dado")
            else:
                ini = a
        elif g.get("gesto"):
            a = por_gesto(g, f"item {n}", float(ini) if ini is not None else None)
            if a is not None:
                ini = a
        if ini is None:
            avisos.append(f"item {n}: sem `inicio` nem `palavra`/`gesto` encontrado"); continue
        ini = max(0.0, float(ini))
        sub = []
        for m, it in enumerate((g.get("itens") or [])[:MAX_ITENS.get(tipo, 5)]):
            it = dict(it) if isinstance(it, dict) else {"texto": str(it)}
            em = it.get("em")
            if it.get("palavra") and ws:
                a = ancorar(it["palavra"], ws, float(em) if em is not None else ini + 0.3 * m, janela_s=4)
                em = a if a is not None else em
            elif it.get("gesto"):
                a = por_gesto(it, f"item {n}, subitem {m + 1}", float(em) if em is not None else ini + 0.3 * m)
                em = a if a is not None else em
            it["em"] = round(max(ini, float(em if em is not None else ini + 0.45 * m)), 2)
            md = _midia(it, avisos)
            if md:
                it["midia"] = md
            sub.append(it)
        if len(g.get("itens") or []) > MAX_ITENS.get(tipo, 99):
            avisos.append(f"item {n} ({tipo}): só os {MAX_ITENS[tipo]} primeiros entram")
        if tipo in MAX_ITENS and not sub:
            avisos.append(f"item {n} ({tipo}): sem itens"); continue
        ultimo = max([it["em"] for it in sub] + [float(g.get("troca_em") or 0), ini])
        fim = g.get("fim")
        fim = float(fim) if fim is not None else max(ini + DUR_PADRAO.get(tipo, 2.4), ultimo + 1.6)
        if dur:
            fim = min(fim, dur)
        if fim - ini < 0.6:
            avisos.append(f"item {n} ({tipo}): curto demais depois do ajuste ({ini:.2f}–{fim:.2f}); ignorado"); continue
        pos = g.get("posicao") or ("centro" if g.get("tela_cheia") else POS_PADRAO.get(tipo, "peito"))
        if pos not in POSICOES:
            avisos.append(f"item {n}: posição '{pos}' vira peito"); pos = "peito"
        out = {k: v for k, v in g.items() if k not in ("itens", "palavra", "gesto", "inicio", "fim", "posicao", "logo", "icone", "imagem")}
        out.update({"tipo": tipo, "inicio": round(ini, 2), "fim": round(fim, 2), "posicao": pos, "tela_cheia": bool(g.get("tela_cheia"))})
        if sub:
            out["itens"] = sub
        if g.get("troca_em") is not None:
            out["troca_em"] = round(float(g["troca_em"]), 2)
        md = _midia(g, avisos)
        if md:
            out["midia"] = md
        if tipo == "numero" and g.get("antes"):
            out["antes"] = [{"texto": str(a.get("texto", a)) if isinstance(a, dict) else str(a), "em": round(float(a.get("em", ini)) if isinstance(a, dict) else ini, 2)} for a in g["antes"][:3]]
        texto = str(g.get("texto", ""))
        if tipo in ("manchete", "pilula", "kicker", "riscado") and not texto:
            avisos.append(f"item {n} ({tipo}): sem texto"); continue
        if len(texto) > 34:
            avisos.append(f"item {n} ({tipo}): texto com {len(texto)} caracteres; na tela fica melhor até ~28")
        itens.append(out)
    itens.sort(key=lambda x: x["inicio"])
    # mesma posição não sobrepõe: o anterior sai 0,1 s antes do próximo entrar (tela cheia ocupa todas)
    for k, a in enumerate(itens):
        for b in itens[k + 1:]:
            if (b["posicao"] == a["posicao"] or a["tela_cheia"] or b["tela_cheia"]) and b["inicio"] < a["fim"]:
                if b["inicio"] - a["inicio"] < 0.7:
                    avisos.append(f"{a['tipo']} em {a['inicio']} e {b['tipo']} em {b['inicio']} brigam pelo mesmo lugar; o segundo atrasa")
                    b["inicio"] = round(a["inicio"] + 0.7, 2); b["fim"] = max(b["fim"], b["inicio"] + 0.6)
                a["fim"] = round(max(a["inicio"] + 0.6, b["inicio"] - 0.1), 2)
    for g in itens:
        tardios = [it["em"] for it in g.get("itens", []) if it["em"] > g["fim"] - 0.3] + ([g["troca_em"]] if g.get("troca_em") and g["troca_em"] > g["fim"] - 0.3 else [])
        if tardios:
            avisos.append(f"{g['tipo']} em {g['inicio']}: parte dele entra em {tardios[0]} mas o gráfico sai em {g['fim']} (o seguinte ocupa o lugar); adiante o próximo ou use outra posição")
    variar_animacoes(itens, avisos)
    if dur and itens:
        dens = len([g for g in itens if g["posicao"] == "peito"]) / max(dur, 1) * 60
        if dens > 15:  # 13/11/2026: teto, não meta (era "um a cada 3–6 s", que o agente lia como cota e enchia de pílula)
            avisos.append(f"{dens:.0f} grafismos por minuto no peito: acima do teto (no máximo 1 a cada 4 s); tire os que não ilustram uma ideia da fala")
    return itens, avisos


# Fase E (08/11/2026): repertório de entrada/saída. O GRA-49 tinha tudo entrando com a mesma mola e saindo no mesmo fade ("animações genéricas").
ENTRADAS = ("mola", "mascara", "desfoque", "deslize", "elastico", "cair", "subir")
SAIDAS = ("some", "sobe", "mascara", "encolhe", "desfoque", "deslize")
AFINIDADE = {  # tipo → (entradas que combinam, saídas que combinam), em ordem de preferência
    "kicker": (("deslize", "mascara", "subir"), ("deslize", "mascara")),
    "manchete": (("mascara", "desfoque", "cair", "mola"), ("sobe", "desfoque", "mascara")),
    "pilula": (("elastico", "deslize", "mola"), ("encolhe", "sobe")),
    "riscado": (("cair", "desfoque", "mola"), ("desfoque", "encolhe")),
    "numero": (("elastico", "desfoque"), ("desfoque", "encolhe")),
    "checklist": (("subir", "deslize", "mola"), ("sobe", "deslize")),
    "pilulas": (("subir", "mola", "deslize"), ("sobe", "encolhe")),
    "fluxo": (("deslize", "subir"), ("sobe", "deslize")),
    "cartoes": (("cair", "subir"), ("sobe", "mascara")),
    "logos": (("elastico", "subir"), ("encolhe", "sobe")),
    "ondas": (("desfoque", "mola"), ("desfoque", "some")),
    "cta": (("subir", "elastico"), ("sobe", "some")),
    "serie": (("mola",), ("some",)),
}


def variar_animacoes(itens, avisos=None):
    """Dá a cada item uma entrada e uma saída do repertório pela afinidade com o tipo, sem repetir a entrada do item anterior
    (nem a saída, quando há opção). O que o agente escreveu em `entrada`/`saida` vale e só é conferido."""
    uso = {}; ult_e = ult_s = None
    for g in itens:
        ents, sais = AFINIDADE.get(g["tipo"], (ENTRADAS[:3], SAIDAS[:2]))
        e = g.get("entrada")
        if e and e not in ENTRADAS:
            (avisos if avisos is not None else []).append(f"{g['tipo']} em {g['inicio']}: entrada '{e}' desconhecida (use {', '.join(ENTRADAS)})"); e = None
        if not e:
            cand = [x for x in ents if x != ult_e] or list(ents)
            e = min(cand, key=lambda x: (uso.get(x, 0), cand.index(x)))
        sd = g.get("saida")
        if sd and sd not in SAIDAS:
            (avisos if avisos is not None else []).append(f"{g['tipo']} em {g['inicio']}: saída '{sd}' desconhecida (use {', '.join(SAIDAS)})"); sd = None
        if not sd:
            cand = [x for x in sais if x != ult_s] or list(sais)
            sd = cand[0]
        g["entrada"], g["saida"] = e, sd
        uso[e] = uso.get(e, 0) + 1; ult_e, ult_s = e, sd
    return itens


def trechos_tela_cheia(itens):
    return [(g["inicio"], g["fim"]) for g in itens if g.get("tela_cheia")]


def preparar_midias(itens, pub: Path, rid: str):
    """Copia (hardlink) as imagens locais para remotion/public/render e troca "origem" por "arquivo". Devolve a lista de arquivos criados."""
    criados = []
    def prep(m):
        if not m or m.get("tipo") != "img" or "origem" not in m:
            return m
        src = Path(m.pop("origem")); alvo = pub / f"{rid}-g{len(criados)}{src.suffix.lower()}"
        try:
            os.link(src, alvo)
        except OSError:
            shutil.copy2(src, alvo)
        criados.append(alvo); m["arquivo"] = alvo.name
        return m
    for g in itens:
        prep(g.get("midia"))
        for it in g.get("itens", []):
            prep(it.get("midia"))
    return criados


def ass_sem_trechos(ass, trechos, saida):
    """Cópia da legenda ASS sem as falas que caem nos trechos de tela cheia (lá o gráfico ocupa o quadro; a legenda some, como no Máquina)."""
    def seg(t):
        h, m, s = t.split(":"); return int(h) * 3600 + int(m) * 60 + float(s)
    linhas = Path(ass).read_text(encoding="utf-8").splitlines()
    out = []
    for ln in linhas:
        if ln.startswith("Dialogue:"):
            partes = ln.split(",", 3)
            ini, fim = seg(partes[1]), seg(partes[2]); meio = (ini + fim) / 2
            if any(a - 0.05 <= meio <= b + 0.05 for a, b in trechos):
                continue
        out.append(ln)
    Path(saida).write_text("\n".join(out) + "\n", encoding="utf-8")
    return saida


# ---------- leitura para o agente e plano automático ----------
def frases(pal: dict, max_chars=90):
    """Fala em linhas "[ini–fim] texto" (por segmento) para o agente planejar sem abrir o JSON inteiro."""
    linhas = []
    for s in pal.get("segmentos", []):
        txt = (s.get("texto") or " ".join(w.get("palavra", "") for w in s.get("palavras", []))).strip()
        linhas.append(f"[{float(s.get('inicio', 0)):.2f}–{float(s.get('fim', 0)):.2f}] {txt[:max_chars]}")
    return linhas


NUM = re.compile(r"^(r\$)?\d+([.,]\d+)?(%|x|k|mil)?$", re.I)


SUGESTAO_GESTO = {"polegar_cima": "checklist", "apontar_cima": "kicker"}


def sugestoes_de_gestos(eventos, ws=None):
    """Do que o detector viu, o que vale sugerir no rascunho (10/11/2026): polegar para cima → `checklist` (um ✓ no gesto), apontar para cima
    → `kicker`, cabeça virada para o lado → cutaway (só texto; a montagem não corta sozinha). Devolve {"itens": [...], "cutaways": [...], "texto": [...]}.
    O texto dos itens fica como "(preencha)" com a palavra dita no instante, quando há transcrição: o agente escreve a ideia."""
    itens, cutaways, texto = [], [], []
    def dita(t):
        if not ws:
            return ""
        perto = [w for w in ws if abs(w["i"] - t) <= 0.6]
        return " ".join(w["p"].strip(".,;:!?") for w in perto[:3])
    for e in sorted(eventos or [], key=lambda e: float(e["inicio"])):
        t = float(e["inicio"]); tipo = str(e.get("tipo"))
        if tipo == "polegar_cima":
            itens.append({"tipo": "checklist", "gesto": "polegar_cima", "inicio": round(t, 2), "itens": [{"texto": f"(preencha: {dita(t) or 'o que ele confirma'})", "gesto": "polegar_cima", "em": round(t, 2)}], "_sugestao": "polegar para cima no vídeo"})
            texto.append(f"{t:.1f} s: polegar para cima → checklist/✓ (confiança {e.get('confianca', '?')})")
        elif tipo == "apontar_cima":
            itens.append({"tipo": "kicker", "gesto": "apontar_cima", "inicio": round(t, 2), "texto": f"(preencha: {dita(t) or 'contexto da fala'})", "_sugestao": "dedo apontando para cima"})
            texto.append(f"{t:.1f} s: apontar para cima → kicker (confiança {e.get('confianca', '?')})")
        elif tipo in ("virada_esquerda", "virada_direita"):
            cutaways.append({"inicio": round(t, 2), "fim": round(float(e.get("fim", t)), 2), "lado": tipo.split("_")[1], "sugestao": "cutaway: ele olha para a tela; cobrir com print/tela do OBS (broll=) ou bloco tutorial"})
            texto.append(f"{t:.1f}–{float(e.get('fim', t)):.1f} s: cabeça virada para a {tipo.split('_')[1]} → candidato a cutaway (b-roll da tela), nada automático")
    return {"itens": itens, "cutaways": cutaways, "texto": texto}


def plano_auto(pal: dict, lista=None, duracao_s=None, gestos=None):
    """Plano sem modelo: logos quando a ferramenta é citada, número dito com R$/% ou seguido de unidade, "sem X" repetido vira checklist,
    "não precisa (de) X" vira riscado, e o resto das palavras-chave vira pílula. No máximo um grafismo no peito a cada ~3,5 s.
    Com `gestos` (eventos do detectar_gestos), acrescenta as sugestões de sugestoes_de_gestos: itens com `gesto` (quando o instante está livre)
    e `sugestoes` em texto (cutaways nunca entram como item)."""
    from .nivel_pro import palavras_chave_auto
    from . import gestos as gst
    ws = palavras_planas(pal); itens = []; ocupado = []
    def livre(t, dur=2.4, folga=1.0):
        return all(t + dur + folga <= a or t >= b + folga for a, b in ocupado)
    def marca(t, dur):
        ocupado.append((t, t + dur))
    k = 0
    while k < len(ws):
        n = _norm(ws[k]["p"]); n2 = n + " " + _norm(ws[k + 1]["p"]) if k + 1 < len(ws) else ""
        t = ws[k]["i"]
        # "sem configurar ... sem depender" → checklist
        if n == "sem" and k + 1 < len(ws):
            semis = [j for j in range(k, min(len(ws), k + 40)) if _norm(ws[j]["p"]) == "sem" and ws[j]["i"] - t < 7]
            if len(semis) >= 2 and livre(t, ws[semis[-1]]["i"] - t + 2):
                its = [{"texto": "Sem " + " ".join(w["p"].strip(".,;:!?") for w in ws[j + 1:j + 3] if _norm(w["p"]) not in ("e", "o", "a"))[:22], "em": round(ws[j]["i"], 2)} for j in semis[:4]]
                itens.append({"tipo": "checklist", "inicio": round(t, 2), "itens": its}); marca(t, ws[semis[-1]]["i"] - t + 2); k = semis[-1] + 2; continue
        # "não precisa (de) X" → riscado
        if n == "nao" and k + 2 < len(ws) and _norm(ws[k + 1]["p"]).startswith("precis"):
            j = k + 2 + (1 if _norm(ws[k + 2]["p"]) in ("de", "do", "da", "ter", "mais") else 0)
            if j < len(ws) and len(_norm(ws[j]["p"])) > 2 and livre(ws[j]["i"]):
                itens.append({"tipo": "riscado", "inicio": round(ws[j]["i"], 2), "texto": ws[j]["p"].strip(".,;:!?").upper()}); marca(ws[j]["i"], 2.4); k = j + 1; continue
        # número com unidade
        if NUM.match(n.replace(" ", "")) or (n == "r$" and k + 1 < len(ws)):
            txt = ws[k]["p"].strip(".,;:!?")
            if n == "r$":
                txt = "R$ " + ws[k + 1]["p"].strip(".,;:!?")
            elif k + 1 < len(ws) and _norm(ws[k + 1]["p"]) in ("reais", "minutos", "segundos", "horas", "dias", "mil", "anos", "vezes", "cliques", "passos"):
                txt = f"{txt} {ws[k + 1]['p'].strip('.,;:!?')}"
            forte = n == "r$" or " " in txt or "%" in txt or sum(c.isdigit() for c in txt) >= 2  # "5" solto quase sempre é contagem fraca
            if forte and any(c.isdigit() for c in txt) and livre(t):
                itens.append({"tipo": "numero", "inicio": round(t, 2), "texto": txt.upper()}); marca(t, 3.0); k += 2; continue
        # ferramenta citada → logo
        nome = n2 if n2 in ("google meet", "obs studio", "tik tok", "google drive") else n
        if nome in CITACAO_LOGO or nome in ("google meet", "obs studio", "tik tok", "google drive"):
            if livre(t, 2.2) and resolver_logo(nome):
                grupo = [{"logo": nome, "em": round(t, 2)}]
                for j in range(k + 1, min(len(ws), k + 25)):
                    nj = _norm(ws[j]["p"])
                    if ws[j]["i"] - t > 4:
                        break
                    if nj in CITACAO_LOGO and nj not in [g["logo"] for g in grupo] and resolver_logo(nj):
                        grupo.append({"logo": nj, "em": round(ws[j]["i"], 2)})
                itens.append({"tipo": "logos", "inicio": round(t, 2), "itens": grupo}); marca(t, grupo[-1]["em"] - t + 2); k += 1; continue
        k += 1
    vistos = set()
    for c in palavras_chave_auto(pal, lista):
        if _norm(c["texto"]) not in vistos and livre(c["inicio"], 1.8, 1.4):
            vistos.add(_norm(c["texto"]))
            itens.append({"tipo": "pilula", "inicio": c["inicio"], "texto": c["texto"].upper()}); marca(c["inicio"], 1.8)
    out = {"itens": itens, "origem": "auto (regras)"}
    evs = gst.eventos_de(gestos)
    if evs:
        sug = sugestoes_de_gestos(evs, ws)
        for g in sug["itens"]:
            # o gesto é sinal mais forte que a pílula por regra: pílula que cai em cima sai; outro tipo em cima fica e vira nota
            perto = [x for x in itens if abs(float(x["inicio"]) - g["inicio"]) < 3.0]
            if all(x["tipo"] == "pilula" for x in perto):
                for x in perto:
                    itens.remove(x)
                itens.append(g); marca(g["inicio"], 2.4)
            else:
                sug["texto"].append(f"{g['inicio']} s: {g['tipo']} pelo gesto não entrou (já há {perto[0]['tipo']} ali); escolha um dos dois")
        out["sugestoes"] = sug["texto"]; out["cutaways"] = sug["cutaways"]; out["origem"] = "auto (regras + gestos)"
        if isinstance(gestos, (str, Path)) and not str(gestos).strip().startswith(("{", "[")):
            out["gestos"] = str(gestos)  # o plano carrega o caminho: normalizar/montar_remotion ancoram os itens com `gesto` sem parâmetro extra
    itens.sort(key=lambda g: g["inicio"])
    return out


# ---------- séries ----------
def _slug(t):
    return re.sub(r"[^a-z0-9]+", "-", _norm(t)).strip("-")[:40] or "serie"


def salvar_serie(nome, titulo, destaque="", handle="@thiago.obsstudio", kicker="", trilha="", chamada="Siga para mais dicas"):
    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(nome); p = SERIES_DIR / f"{slug}.json"
    antigo = ler_json(p) if p.exists() else {}
    dados = {**antigo, "slug": slug, "nome": nome, "titulo": titulo, "destaque": destaque, "handle": handle, "kicker": kicker, "trilha": trilha, "chamada": chamada}
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"serie": dados, "arquivo": str(p)}


def carregar_serie(nome):
    p = SERIES_DIR / f"{_slug(nome)}.json"
    if not p.exists():
        raise ErroFerramenta(f"série '{nome}' não existe; crie com salvar_serie (existentes: {', '.join(s['slug'] for s in listar_series()) or 'nenhuma'})")
    return ler_json(p)


def listar_series():
    return [ler_json(p) for p in sorted(SERIES_DIR.glob("*.json"))] if SERIES_DIR.exists() else []
