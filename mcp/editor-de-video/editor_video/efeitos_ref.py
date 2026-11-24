"""Inventário de efeitos (15/11/2026, pedido do Raphael): o Gemini assiste a um vídeo editado (entrega do Máquina, criativo da pasta Criativos do
Drive) e lista TODO efeito, animação, transição, texto e som, com tempo e como se move, em vocabulário aberto. Cada item diz qual recurso nosso
equivale (ou "nenhum"); o catálogo junta todos os vídeos e mostra o que falta construir, do mais frequente ao mais raro.
Diferente da decupagem do repertório, que só usa o vocabulário dos nossos parâmetros e por isso não enxerga o que ainda não temos.
Inventários em workspace/referencias/_efeitos/<slug>.json (+ quadros em <slug>/). Referência é só estudo: nada da peça é reutilizado."""
import json, subprocess
from datetime import datetime
from .util import FFMPEG, caminho, info_midia, ler_json, salvar_json, ErroFerramenta
from . import repertorio as rep

FAMILIAS = {
    "camera": "zoom, tremor, giro, movimento de câmera virtual, reenquadramento",
    "transicao": "como um plano passa para o outro",
    "legenda": "legenda da fala (estilo, animação, cor da palavra atual)",
    "texto": "título, palavra-chave, número, rótulo que não é a legenda",
    "grafismo": "seta, círculo, sublinhado, ícone, emoji, logo, print, cartão, barra de progresso",
    "broll": "imagem de cobertura, janela, tela dividida, imagem por cima da fala",
    "cor": "correção, filtro, flash de cor, preto e branco, vinheta",
    "ritmo": "velocidade, congelar, rebobinar, rampa, corte no beat",
    "recorte": "rosto recortado, fundo removido, máscara",
    "overlay": "luz vazada, grão, textura, moldura",
    "som": "efeito sonoro, música, silêncio de impacto, abaixar a trilha",
}

# o que o Editor GS já faz (nome → onde); o Gemini escolhe daqui o equivalente de cada efeito visto
NOSSOS = {
    "punch": "zoom de impacto rápido no corte (Camera.tsx)", "tremor": "tremor de câmera curto", "zoom_blur": "zoom com desfoque na transição",
    "deslize": "plano entra deslizando", "luz": "vazamento de luz na transição", "giro": "giro rápido na transição", "flash": "flash branco no corte",
    "zoom_alternado": "enquadramento alterna 1,00/1,08 a cada corte", "zoom_lento": "aproximação lenta contínua", "zoom_tela": "câmera virtual segue a área ativa da tela",
    "legenda_cinetica": "legenda palavra por palavra com cor na palavra atual, pop, tremor, máquina de escrever, onda", "karaoke": "palavra atual pintada",
    "kicker": "rótulo pequeno com ponto laranja", "manchete": "título grande 1–2 linhas com palavra em destaque/caixa", "pilula": "termo numa pílula",
    "riscado": "palavra riscada e trocada", "checklist": "lista com marcações entrando", "fluxo": "ícones ligados por setas", "cartoes": "comparação em dois cartões",
    "numero": "número grande", "logos": "logo real de app/marca", "icone3d": "emoji/ícone 3D com pop e flutuação", "celular": "celular na tela com conversa digitando", "comentario": "cartão de comentário/avaliação com avatar e estrelas", "historia": "cartão de história (story) em tela cheia com páginas", "grade": "grade de cartões/ícones entrando em cascata", "ondas": "ondas sonoras animadas", "cta": "chamada final (seguir/comentar)",
    "barra_progresso": "barra de progresso do vídeo", "capitulos": "capítulos numerados", "gancho_palavra": "gancho escrito palavra por palavra",
    "painel": "fala com painel de grafismo ao lado", "moldura": "vídeo numa moldura", "tela_com_rosto": "tela + rosto recortado em caixa",
    "dividido": "tela dividida", "pip": "vídeo em janela sobre outro", "antes_depois": "antes e depois lado a lado", "cortina": "cortina laranja entre blocos",
    "broll_janela": "b-roll em janela enquanto fala", "broll_cheio": "b-roll em tela cheia",
    "whoosh": "whoosh/swipe no movimento", "pop": "pop/ding em texto", "clique": "clique", "riser": "subida antes do impacto", "trilha_ducking": "trilha que abaixa na fala",
}


def _dir():
    d = rep.WORKSPACE / "referencias" / "_efeitos"; d.mkdir(parents=True, exist_ok=True); return d


def _prompt(titulo, dur):
    fam = "\n".join(f"- {k}: {v}" for k, v in FAMILIAS.items())
    nossos = "\n".join(f"- {k}: {v}" for k, v in NOSSOS.items())
    return f"""Você é editor de vídeo sênior e está fazendo o inventário de edição de um vídeo pronto ("{titulo}", {dur:.1f} s), para outro editor
reproduzir o estilo. Assista ao vídeo inteiro com atenção a cada quadro e ao som.
Liste CADA efeito aplicado (não a fala em si): zoom, tremor, transição, animação de texto, legenda, grafismo, b-roll, cor, velocidade, recorte, overlay, efeito sonoro, música.
Seja granular: cada texto/grafismo DIFERENTE na tela é um item próprio (título de abertura, selo, preço, ícone, seta, print, CTA final), cada tipo de transição e
cada tipo de som também. Descreva a APARÊNCIA (fonte, peso, cor, contorno, sombra, caixa, cantos, 3D) e o MOVIMENTO, porque é o que o outro editor vai reproduzir.
Não invente: só o que dá para ver ou ouvir.
Para cada um diga, de forma literal e mensurável: quando começa e termina (segundos com 1 casa), como se move (direção, de quanto para quanto,
duração, aceleração: entra rápido e freia, linear, com mola/quique), o gatilho (palavra dita, corte, batida, troca de assunto) e onde fica na tela.
Efeito que se repete igual (ex.: zoom em todo corte) vira UM item com "vezes" e "tempos" (lista dos segundos).
Famílias:
{fam}
Recursos que o nosso editor JÁ tem. "equivalente" = o nome dele só se o efeito visto é IGUAL (mesma aparência E mesmo movimento); "parcial:<nome>" se é da
mesma ideia mas fica diferente (cor, forma, animação, estilo 3D, posição) e então "diferenca" diz exatamente o quê; "nenhum" se não temos nada parecido. Na dúvida, parcial:
{nossos}
Responda SÓ JSON:
{{"efeitos": [{{"familia": "...", "nome": "nome curto e descritivo em português", "inicio": s, "fim": s, "vezes": n, "tempos": [s],
  "como": "movimento/duração/aceleração", "gatilho": "...", "posicao": "...", "equivalente": "nome | parcial:nome | nenhum", "diferenca": "o que o nosso não faz igual (vazio se igual)",
  "dificuldade": "facil|media|dificil", "impacto": "alto|medio|baixo"}}],
 "legenda": {{"fonte": "descrição", "tamanho": "...", "posicao": "...", "palavras_por_bloco": n, "animacao": "...", "cores": "..."}},
 "ritmo": {{"cortes_por_min": n, "pausas": "como trata pausas", "musica": "tem? estilo? volume"}},
 "assinatura": ["5 traços que mais definem o estilo desta edição"],
 "nao_copiar": ["o que é específico da peça: preço, número de alunos, escassez, imagem de terceiro"]}}"""


def inventariar(video, titulo="", fonte="", refazer=False, quadros=True, modelo=None, _req_=None):
    """Gemini assiste ao vídeo e grava o inventário de efeitos; com quadros=True tira um quadro no meio de cada efeito (para a página de catálogo)."""
    v = caminho(video); slug = rep._slug(titulo or v.stem); arq = _dir() / f"{slug}.json"
    if arq.exists() and not refazer:
        return {"id": slug, "pulado": "já inventariado (refazer=True para refazer)", "efeitos": len(ler_json(arq).get("efeitos", []))}
    dur = float(info_midia(v)["duracao_s"])
    partes = rep._partes_video(v, _req_=_req_)
    try:
        d, uso, m = rep._gemini_partes(partes + [{"text": _prompt(titulo or v.stem, dur)}], modelo=modelo, _req_=_req_)
    finally:
        rep._apagar_remoto(partes, _req_=_req_)
    if isinstance(d, list):  # às vezes o Gemini devolve a lista de efeitos solta ou o objeto dentro de uma lista
        d = d[0] if len(d) == 1 and isinstance(d[0], dict) and "efeitos" in d[0] else {"efeitos": d}
    efeitos = []
    for e in d.get("efeitos") or []:
        try:
            ini, fim = round(float(e.get("inicio", 0)), 1), round(float(e.get("fim", e.get("inicio", 0))), 1)
        except (TypeError, ValueError):
            continue
        eq = str(e.get("equivalente", "nenhum")).strip(); parcial = eq.startswith("parcial:"); base = eq.split(":", 1)[1].strip() if parcial else eq
        eq = ("parcial:" + base if parcial else base) if base in NOSSOS else "nenhum"
        efeitos.append({"familia": e.get("familia") if e.get("familia") in FAMILIAS else "outro", "nome": str(e.get("nome", ""))[:80],
                        "inicio": ini, "fim": max(fim, ini), "vezes": int(e.get("vezes") or 1), "tempos": [round(float(t), 1) for t in (e.get("tempos") or []) if isinstance(t, (int, float))][:40],
                        "como": str(e.get("como", ""))[:300], "gatilho": str(e.get("gatilho", ""))[:120], "posicao": str(e.get("posicao", ""))[:80],
                        "equivalente": eq, "diferenca": str(e.get("diferenca", ""))[:240],
                        "dificuldade": e.get("dificuldade") if e.get("dificuldade") in ("facil", "media", "dificil") else "media",
                        "impacto": e.get("impacto") if e.get("impacto") in ("alto", "medio", "baixo") else "medio"})
    efeitos.sort(key=lambda x: x["inicio"])
    inv = {"id": slug, "titulo": titulo or v.stem, "fonte": fonte, "video": str(v), "duracao_s": round(dur, 2), "efeitos": efeitos,
           "legenda": d.get("legenda") or {}, "ritmo": d.get("ritmo") or {}, "assinatura": [str(x)[:200] for x in (d.get("assinatura") or [])][:6],
           "nao_copiar": [str(x)[:200] for x in (d.get("nao_copiar") or [])][:6],
           "feito_por": {"modelo": m, "em": datetime.now().isoformat(timespec="seconds"), "uso": uso}}
    if quadros:
        pasta = _dir() / slug; pasta.mkdir(exist_ok=True)
        for i, e in enumerate(efeitos):
            t = min(dur - 0.05, (e["inicio"] + e["fim"]) / 2 if e["fim"] > e["inicio"] else e["inicio"] + 0.1)
            q = pasta / f"{i:02d}.jpg"
            subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{max(0, t):.2f}", "-i", str(v), "-frames:v", "1", "-vf", "scale=-2:360", str(q)], capture_output=True)
            if q.exists():
                e["quadro"] = str(q)
    salvar_json(arq, inv)
    return {"id": slug, "efeitos": len(efeitos), "sem_equivalente": sum(1 for e in efeitos if e["equivalente"] == "nenhum"),
            "parciais": sum(1 for e in efeitos if e["equivalente"].startswith("parcial:")), "assinatura": inv["assinatura"]}


def _chave_efeito(e):
    return (e["familia"], rep._slug(e["nome"])[:30])


def catalogo(minimo_videos=1):
    """Junta todos os inventários: por equivalente nosso (quantos vídeos usam, diferenças apontadas) e, para os sem equivalente, agrupa por família +
    nome, com exemplos (vídeo, segundo, quadro). Ordena o que falta pelo número de vídeos que usam e pelo impacto."""
    invs = [ler_json(p) for p in sorted(_dir().glob("*.json"))]
    if not invs:
        raise ErroFerramenta("Nenhum inventário ainda: rode inventariar_efeitos num vídeo.")
    temos, faltam = {}, {}
    peso = {"alto": 3, "medio": 2, "baixo": 1}
    for inv in invs:
        for e in inv["efeitos"]:
            ex = {"video": inv["titulo"], "inicio": e["inicio"], "como": e["como"], "quadro": e.get("quadro", ""), "vezes": e["vezes"]}
            if e["equivalente"] != "nenhum":
                rec = e["equivalente"].split(":", 1)[-1]
                g = temos.setdefault(rec, {"recurso": rec, "descricao": NOSSOS.get(rec, ""), "videos": set(), "usos": 0, "igual": 0, "parcial": 0, "diferencas": []})
                g["igual" if rec == e["equivalente"] else "parcial"] += 1
                g["videos"].add(inv["id"]); g["usos"] += e["vezes"]
                if e["equivalente"].startswith("parcial:") and e["diferenca"] and len(g["diferencas"]) < 8:
                    g["diferencas"].append({"video": inv["titulo"], "inicio": e["inicio"], "diferenca": e["diferenca"], "quadro": e.get("quadro", "")})
            else:
                g = faltam.setdefault(_chave_efeito(e), {"familia": e["familia"], "nome": e["nome"], "videos": set(), "usos": 0, "impacto": 0, "dificuldade": e["dificuldade"], "exemplos": []})
                g["videos"].add(inv["id"]); g["usos"] += e["vezes"]; g["impacto"] = max(g["impacto"], peso[e["impacto"]])
                if len(g["exemplos"]) < 4:
                    g["exemplos"].append(ex)
    fmt = lambda g: {**g, "videos": len(g["videos"])}
    temos_l = sorted((fmt(g) for g in temos.values()), key=lambda g: (-g["parcial"], -g["videos"], -g["usos"]))
    faltam_l = sorted((fmt(g) for g in faltam.values() if len(g["videos"]) >= minimo_videos), key=lambda g: (-g["videos"], -g["impacto"], -g["usos"]))
    assinaturas = [{"video": inv["titulo"], "assinatura": inv["assinatura"]} for inv in invs]
    return {"videos": len(invs), "efeitos": sum(len(i["efeitos"]) for i in invs), "temos": temos_l, "faltam": faltam_l, "assinaturas": assinaturas}
