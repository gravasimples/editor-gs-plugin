"""Repertório de edição (08/11/2026): cada vídeo de referência vira uma ficha com medidas (ritmo, pausas, cortes, som) e uma decupagem
no vocabulário dos NOSSOS parâmetros (layout, grafismo, transição, legenda), para o agente traduzir referência em edição e para o Revisor
comparar a entrega com o que já funciona. Base inicial: as entregas do Máquina medidas em 06/11 (~/maquina-analise/saida).
Fichas em workspace/repertorio/<id>/ficha.json. Referência é só estudo: nunca reutilizar imagem, áudio ou texto dela."""
import base64, json, os, re, statistics, subprocess, time, unicodedata
from datetime import datetime
from pathlib import Path
from .util import FFMPEG, caminho, info_midia, ler_json, salvar_json, ErroFerramenta
from . import revisao
from .grafismos import TIPOS as TIPOS_GRAFISMO
from .transicoes import TIPOS as TIPOS_TRANSICAO

RAIZ = Path(__file__).resolve().parents[3]
# 11/11/2026: sem EDITOR_GS_WORKSPACE, usa o workspace da instalação (EDITOR_GS_HOME ou ~/EditorGS) antes do do repositório.
WORKSPACE = Path(os.environ.get("EDITOR_GS_WORKSPACE") or (Path(os.environ["EDITOR_GS_HOME"]) / "workspace" if os.environ.get("EDITOR_GS_HOME") else (Path.home() / "EditorGS" / "workspace" if (Path.home() / "EditorGS" / "workspace").is_dir() else RAIZ / "workspace")))
MAQUINA = Path(os.environ.get("EDITOR_GS_MAQUINA", Path.home() / "maquina-analise" / "saida"))

FORMATOS = {
    "fala_tela": "fala para a câmera com trechos de tela do OBS (ex.: série O óbvio precisa ser dito)",
    "fala": "fala para a câmera, opinião ou história, sem tutorial",
    "anuncio": "anúncio 9:16 de 20–70 s com gancho, demonstração e CTA",
    "aula": "aula ou tutorial longo (horizontal), tela com rosto",
    "animacao": "vídeo montado só com cenas animadas ou encenação",
    "react": "reação a vídeo de terceiro (só com direitos)",
    "carrossel_video": "slides de carrossel animados",
}
LAYOUTS = ("cheio", "painel", "moldura", "tutorial", "tela", "aula", "dividido", "pip", "grafico_cheio")
ENQUADRAMENTOS = ("aberto", "medio", "fechado", "tela", "grafico")
TRANSICOES = TIPOS_TRANSICAO + ("cortina", "nenhuma")

# entradas da pasta do Máquina: nome → (formato, título); nomes 2026-* são entregas do Editor GS e obvio03/Obvio04 são brutos (ficam fora)
_MAQUINA_FORMATO = (("obvio-parte", "fala_tela"), ("ads-", "anuncio"), ("black-friday", "anuncio"), ("black-obs", "anuncio"), ("chamada-black", "anuncio"),
                    ("oferta-", "anuncio"), ("aula-", "aula"), ("implementacao", "aula"), ("novelinha", "animacao"), ("em-animacao", "animacao"),
                    ("react", "react"), ("carrossel", "carrossel_video"), ("adiei", "fala"), ("acaba-com", "fala"), ("nunca-fiz", "fala"), ("editor-de-bolso", "fala"))
_FORA = re.compile(r"^(2026-|obvio0|Obvio0|referencia-|video-de-referencia)")


def _dir():
    d = WORKSPACE / "repertorio"; d.mkdir(parents=True, exist_ok=True); return d


def _slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "ref"


def _formato_maquina(nome):
    for chave, fmt in _MAQUINA_FORMATO:
        if chave in nome:
            return fmt
    return "fala"


def _metricas(resumo):
    r = resumo or {}
    m = {"duracao_s": r.get("duracao"), "cortes_por_min": r.get("cortes_por_min"), "plano_medio_s": r.get("plano_medio_s"), "palavras_por_s": r.get("pps"),
         "pausa_max_s": r.get("pausa_max"), "pausas_maiores_0_4": r.get("pausas_maiores_0_4"), "lufs": r.get("lufs"), "lra": r.get("lra"),
         "true_peak": r.get("true_peak"), "fala_comeca_s": r.get("inicio_fala")}
    return {k: v for k, v in m.items() if v is not None}


def ficha(id_):
    p = _dir() / id_ / "ficha.json"
    if not p.exists():
        raise ErroFerramenta(f"Ficha '{id_}' não existe no repertório (veja listar_repertorio).")
    return ler_json(p)


def _salvar(f):
    f["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_json(_dir() / f["id"] / "ficha.json", f); return f


def listar(formato=""):
    out = []
    for p in sorted(_dir().glob("*/ficha.json")):
        f = ler_json(p)
        if formato and f.get("formato") != formato:
            continue
        out.append({"id": f["id"], "titulo": f.get("titulo"), "formato": f.get("formato"), "origem": f.get("origem"), "decupada": bool(f.get("decupagem")),
                    "duracao_s": f.get("metricas", {}).get("duracao_s"), "desempenho": f.get("desempenho") or None})
    return {"n": len(out), "fichas": out, "formatos": FORMATOS}


def importar_maquina(pasta=None):
    """Cria (ou atualiza as medidas de) uma ficha por vídeo do Máquina medido em 06/11. Duplicatas (mesmo vídeo baixado duas vezes) entram uma vez.
    Não chama modelo: a decupagem vem depois, com decupar_ficha."""
    base = Path(pasta) if pasta else MAQUINA
    if not base.exists():
        raise ErroFerramenta(f"Pasta da análise do Máquina não encontrada: {base}")
    vistos, criadas, atualizadas, puladas = {}, [], [], []
    for d in sorted(base.iterdir()):
        if not (d / "resumo.json").exists() or _FORA.match(d.name):
            puladas.append(d.name); continue
        r = ler_json(d / "resumo.json")
        chave = (round(r.get("duracao") or 0, 1), r.get("pps"))
        if chave in vistos:
            puladas.append(f"{d.name} (igual a {vistos[chave]})"); continue
        nome = re.sub(r"^\d+-", "", d.name); vistos[chave] = d.name; id_ = "maq-" + _slug(nome)
        existente = (_dir() / id_ / "ficha.json"); ja_tinha = existente.exists()
        f = ler_json(existente) if ja_tinha else {"id": id_, "origem": "maquina", "titulo": nome.replace("-", " "), "formato": _formato_maquina(nome),
                                                          "fonte": "Máquina de Criativos (entrega editada para a Grava Simples)", "direitos": "so_referencia",
                                                          "decupagem": [], "criado_em": datetime.now().isoformat(timespec="seconds")}
        f["metricas"] = _metricas(r)
        f["arquivos"] = {k: str(d / v) for k, v in (("folha", "folha.jpg"), ("fala", "fala.json"), ("cortes", "cortes.json")) if (d / v).exists()}
        _salvar(f); (atualizadas if ja_tinha else criadas).append(id_)
    return {"criadas": criadas, "atualizadas": atualizadas, "puladas": puladas, "total": len(listar()["fichas"])}


# --- medir um vídeo novo (mesmas medidas da análise do Máquina) ---------------------------------------
def medir(video, palavras=None):
    """Medidas sem modelo: cortes de cena, loudness e, com palavras (transcrição), ritmo de fala e pausas."""
    v = caminho(video); info = info_midia(v); dur = float(info["duracao_s"])
    r = subprocess.run([FFMPEG, "-v", "info", "-i", str(v), "-vf", "select='gt(scene,0.28)',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True)
    cortes = [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    m = {"duracao_s": round(dur, 2), "cortes_por_min": round(len(cortes) / dur * 60, 1) if dur else 0, "plano_medio_s": round(dur / (len(cortes) + 1), 2)}
    if info.get("tem_audio"):
        r = subprocess.run([FFMPEG, "-v", "info", "-i", str(v), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
        s = r.stderr[r.stderr.rfind("Summary:"):]
        for chave, rx in (("lufs", r"I:\s+(-?[\d.]+) LUFS"), ("lra", r"LRA:\s+([\d.]+) LU"), ("true_peak", r"Peak:\s+(-?[\d.]+) dBFS")):
            g = re.search(rx, s)
            if g: m[chave] = float(g.group(1))
    if palavras:
        pal = palavras.get("palavras", palavras) if isinstance(palavras, dict) else palavras
        if pal:
            ini, fim = pal[0]["inicio"], pal[-1]["fim"]
            pausas = [round(b["inicio"] - a["fim"], 2) for a, b in zip(pal, pal[1:])]
            m.update({"fala_comeca_s": round(ini, 2), "palavras_por_s": round(len(pal) / max(0.1, fim - ini), 2), "pausa_max_s": max(pausas) if pausas else 0,
                      "pausas_maiores_0_4": sum(1 for p in pausas if p > 0.4)})
            if info.get("tem_audio"):
                # a pausa vale pelo áudio: o Whisper estica palavra sobre silêncio e abre buraco onde há fala (achado de 08/11)
                silencios = _silencios(v, ini, fim)
                m.update({"pausa_max_s": max(silencios, default=0.0), "pausas_maiores_0_4": sum(1 for x in silencios if x > 0.4), "pausa_medida_por": "audio"})
    return m, cortes


def _silencios(v, ini, fim, limiar_db=-35, min_s=0.25):
    r = subprocess.run([FFMPEG, "-v", "info", "-i", str(v), "-af", f"silencedetect=n={limiar_db}dB:d={min_s}", "-vn", "-f", "null", "-"], capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [round(b - a, 2) for a, b in zip(starts, ends) if a >= ini - 0.05 and b <= fim + 0.05]


# --- decupagem pelo Gemini ------------------------------------------------------------------------------
def _prompt_decupagem(f, transcricao):
    return f"""Você decupa vídeos curtos de referência para o editor de vídeo da Grava Simples (Thiago, conteúdo sobre gravar aulas e lives com OBS).
Formato declarado: {f.get('formato')} ({FORMATOS.get(f.get('formato'), '')}). Duração: {f.get('metricas', {}).get('duracao_s')} s.
Use SÓ este vocabulário (é o dos parâmetros do nosso editor):
- layout: {', '.join(LAYOUTS)}
- enquadramento do rosto: {', '.join(ENQUADRAMENTOS)}
- grafismo.tipo: {', '.join(TIPOS_GRAFISMO)} (ou "nenhum"); grafismo.texto = o que aparece escrito; grafismo.palavra = palavra dita quando entra; grafismo.tela_cheia true se cobre o quadro e a legenda some
- transicao (na entrada do trecho): {', '.join(TRANSICOES)}
- legenda: posicao (rodape, peito, centro, topo, nenhuma) e palavras_por_bloco
Divida o vídeo em trechos onde algo muda (enquadramento, layout, gráfico ou assunto). Seja literal: descreva o que se vê, sem inventar.
Responda SÓ JSON:
{{"decupagem": [{{"inicio": s, "fim": s, "assunto": "curto", "layout": "...", "enquadramento": "...", "transicao": "...", "grafismo": {{"tipo": "...", "texto": "...", "palavra": "...", "tela_cheia": false}}, "som": "voz|voz+sfx|voz+trilha|trilha"}}],
 "legenda": {{"posicao": "...", "palavras_por_bloco": n, "maiusculas": true, "destaque": "cor da palavra atual"}},
 "abertura": "o que acontece nos primeiros 3 s (gancho visual e falado)",
 "fechamento": "como termina (CTA, cartela)",
 "por_que_funciona": ["3 a 5 itens objetivos, ligados ao que se vê"],
 "receita": ["5 a 8 instruções de edição reutilizáveis, no vocabulário acima, sem copiar o texto da referência"],
 "nao_copiar": ["o que é específico desta peça ou fora das regras (número de alunos, preço, escassez, imagem de terceiro)"]}}
Transcrição com tempos (s):
{transcricao}"""


def _transcricao_curta(fala, limite=6000):
    pal = (fala or {}).get("palavras") or []
    if not pal:
        return (fala or {}).get("texto", "")[:limite]
    linhas, atual, t0 = [], [], None
    for p in pal:
        t0 = p.get("inicio", p.get("i", 0)) if t0 is None else t0; atual.append(p.get("palavra") or p.get("texto") or p.get("p") or "")
        if len(atual) >= 8:
            linhas.append(f"[{t0:.1f}] {' '.join(atual)}"); atual, t0 = [], None
    if atual:
        linhas.append(f"[{t0:.1f}] {' '.join(atual)}")
    return "\n".join(linhas)[:limite]


def _gemini_partes(partes, modelo=None, _req_=None):
    k = revisao._chave(); m = modelo or os.environ.get("GEMINI_MODELO", "gemini-3.5-flash")
    corpo = {"contents": [{"parts": partes}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
    _, _, raw = (_req_ or revisao._req)("POST", f"{revisao.API}/v1beta/models/{m}:generateContent?key={k}", corpo)
    d = json.loads(raw)
    try:
        return json.loads(d["candidates"][0]["content"]["parts"][0]["text"]), d.get("usageMetadata"), m
    except Exception:
        raise ErroFerramenta(f"Gemini não devolveu JSON válido: {str(d)[:300]}")


def _normalizar_decupagem(d):
    """Mantém só valores do vocabulário (o resto vira 'outro'), ordena por tempo e calcula os padrões da ficha."""
    trechos = []
    for t in (d.get("decupagem") or []):
        try:
            ini, fim = float(t.get("inicio", 0)), float(t.get("fim", 0))
        except (TypeError, ValueError):
            continue
        g = t.get("grafismo") or {}
        tipo = g.get("tipo") if g.get("tipo") in TIPOS_GRAFISMO else ("nenhum" if g.get("tipo") in (None, "", "nenhum") else "outro")
        trechos.append({"inicio": round(ini, 2), "fim": round(max(fim, ini), 2), "assunto": str(t.get("assunto", ""))[:80],
                        "layout": t.get("layout") if t.get("layout") in LAYOUTS else "outro",
                        "enquadramento": t.get("enquadramento") if t.get("enquadramento") in ENQUADRAMENTOS else "outro",
                        "transicao": t.get("transicao") if t.get("transicao") in TRANSICOES else "outro",
                        "grafismo": {"tipo": tipo, "texto": str(g.get("texto", ""))[:120], "palavra": str(g.get("palavra", ""))[:40], "tela_cheia": bool(g.get("tela_cheia"))},
                        "som": str(t.get("som", ""))[:20]})
    trechos.sort(key=lambda x: x["inicio"])
    return trechos


def padroes(trechos, duracao=None):
    """Contagens que viram alvo para o agente: um gráfico a cada N s, tipos mais usados, transições, layouts, trechos de tela cheia."""
    if not trechos:
        return {}
    dur = duracao or max(t["fim"] for t in trechos) or 1
    graf = [t for t in trechos if t["grafismo"]["tipo"] not in ("nenhum", "outro")]
    conta = lambda chave: dict(sorted({v: sum(1 for t in trechos if t[chave] == v) for v in {t[chave] for t in trechos}}.items(), key=lambda kv: -kv[1]))
    tipos = {}
    for t in graf:
        tipos[t["grafismo"]["tipo"]] = tipos.get(t["grafismo"]["tipo"], 0) + 1
    return {"trechos": len(trechos), "trecho_medio_s": round(dur / len(trechos), 2), "grafismos": len(graf),
            "grafismo_a_cada_s": round(dur / len(graf), 2) if graf else None, "tipos_grafismo": dict(sorted(tipos.items(), key=lambda kv: -kv[1])),
            "tela_cheia": sum(1 for t in graf if t["grafismo"]["tela_cheia"]), "transicoes": conta("transicao"), "layouts": conta("layout"),
            "enquadramentos": conta("enquadramento")}


def decupar_ficha(id_, video="", modelo=None, refazer=False, _req_=None):
    """Decupa uma ficha com o Gemini. Com `video` (arquivo), o Gemini assiste ao vídeo; sem, usa a folha de quadros (2 por segundo, com o tempo escrito)
    e a transcrição da ficha. Grava decupagem, padrões, receita e o que não copiar."""
    f = ficha(id_)
    if f.get("decupagem") and not refazer:
        return {"id": id_, "pulada": "já decupada (refazer=True para refazer)", "padroes": f.get("padroes")}
    arqs = f.get("arquivos", {})
    fala = ler_json(arqs["fala"]) if arqs.get("fala") and Path(arqs["fala"]).exists() else None
    if not fala and f.get("arquivos", {}).get("palavras") and Path(arqs["palavras"]).exists():
        fala = ler_json(arqs["palavras"])
    prompt = _prompt_decupagem(f, _transcricao_curta(fala))
    if video:
        partes = _partes_video(video, _req_=_req_)
    elif arqs.get("folha") and Path(arqs["folha"]).exists():
        img = Path(arqs["folha"]).read_bytes()
        partes = [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img).decode()}},
                  {"text": "A imagem é uma folha de quadros do vídeo: 2 quadros por segundo, da esquerda para a direita e de cima para baixo, com o tempo escrito acima de cada quadro."}]
    else:
        raise ErroFerramenta("Ficha sem folha de quadros e sem vídeo: passe video=<arquivo>.")
    d, uso, m = _gemini_partes(partes + [{"text": prompt}], modelo=modelo, _req_=_req_)
    if video:
        _apagar_remoto(partes, _req_=_req_)
    trechos = _normalizar_decupagem(d)
    if not trechos:
        raise ErroFerramenta("Decupagem veio vazia: tente de novo.")
    f.update({"decupagem": trechos, "padroes": padroes(trechos, f.get("metricas", {}).get("duracao_s")), "legenda": d.get("legenda") or {},
              "abertura": str(d.get("abertura", ""))[:400], "fechamento": str(d.get("fechamento", ""))[:400],
              "por_que_funciona": [str(x)[:200] for x in (d.get("por_que_funciona") or [])][:6], "receita": [str(x)[:240] for x in (d.get("receita") or [])][:8],
              "nao_copiar": [str(x)[:200] for x in (d.get("nao_copiar") or [])][:6],
              "decupado_por": {"modelo": m, "fonte": "video" if video else "folha_de_quadros", "em": datetime.now().isoformat(timespec="seconds"), "uso": uso}})
    _salvar(f)
    return {"id": id_, "trechos": len(trechos), "padroes": f["padroes"], "receita": f["receita"]}


def _partes_video(video, _req_=None):
    """Sobe o vídeo pela Files API (mesmo caminho do Revisor) e devolve a parte file_data."""
    v = caminho(video); k = revisao._chave(); req = _req_ or revisao._req; tamanho = v.stat().st_size
    if tamanho > 1_900_000_000:
        raise ErroFerramenta("Vídeo acima de 1,9 GB: envie uma versão menor (720p).")
    _, h, _ = req("POST", f"{revisao.API}/upload/v1beta/files?key={k}", {"file": {"display_name": v.name}},
                  headers={"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(tamanho),
                           "X-Goog-Upload-Header-Content-Type": "video/mp4"})
    url_up = h.get("X-Goog-Upload-URL") or h.get("x-goog-upload-url")
    if not url_up:
        raise ErroFerramenta("Files API não devolveu URL de upload.")
    _, _, corpo = req("POST", url_up, v.read_bytes(), headers={"Content-Type": "video/mp4", "Content-Length": str(tamanho), "X-Goog-Upload-Offset": "0",
                                                            "X-Goog-Upload-Command": "upload, finalize"}, raw=True)
    arq = json.loads(corpo)["file"]
    for _ in range(120):
        _, _, c = req("GET", f"{revisao.API}/v1beta/{arq['name']}?key={k}")
        estado = json.loads(c).get("state")
        if estado == "ACTIVE":
            break
        if estado == "FAILED":
            raise ErroFerramenta("Gemini não conseguiu processar o vídeo.")
        time.sleep(0 if _req_ else 3)
    return [{"file_data": {"mime_type": "video/mp4", "file_uri": arq["uri"]}, "_nome": arq["name"]}]


def _apagar_remoto(partes, _req_=None):
    for p in partes:
        nome = p.pop("_nome", None)
        if nome:
            try:
                (_req_ or revisao._req)("DELETE", f"{revisao.API}/v1beta/{nome}?key={revisao._chave()}")
            except ErroFerramenta:
                pass


def adicionar_referencia(video, titulo, formato, fonte="", desempenho=None, palavras_json="", decupar=True, modelo=None, _req_=None):
    """Ficha nova a partir de um vídeo local (Reel/Short baixado, entrega boa nossa). Mede, guarda a fonte e o desempenho (views, curtidas, data, mediana do
    perfil: o que a fonte informar) e, com decupar=True, manda o Gemini assistir. O vídeo não é copiado: a ficha guarda o caminho."""
    if formato not in FORMATOS:
        raise ErroFerramenta(f"formato deve ser um de: {', '.join(FORMATOS)}")
    v = caminho(video); pal = ler_json(palavras_json) if palavras_json else None
    m, cortes = medir(v, pal)
    id_ = "ref-" + _slug(titulo); n = 2
    while (_dir() / id_).exists():
        id_ = f"ref-{_slug(titulo)}-{n}"; n += 1
    f = {"id": id_, "origem": "externa" if fonte and "grava" not in fonte.lower() else "propria", "titulo": titulo, "formato": formato, "fonte": fonte,
         "direitos": "so_referencia", "desempenho": desempenho or {}, "metricas": m, "cortes": cortes, "decupagem": [],
         "arquivos": {"video": str(v), **({"palavras": str(caminho(palavras_json))} if palavras_json else {})}, "criado_em": datetime.now().isoformat(timespec="seconds")}
    _salvar(f)
    res = {"id": id_, "metricas": m}
    if decupar:
        res["decupagem"] = decupar_ficha(id_, video=str(v), modelo=modelo, _req_=_req_)
    return res


# --- consulta do agente -----------------------------------------------------------------------------------
def _mediana(valores):
    v = [x for x in valores if isinstance(x, (int, float))]
    return round(statistics.median(v), 2) if v else None


def consultar(formato, n=3, duracao_alvo_s=None):
    """Receita do formato: medianas das medidas (alvos de ritmo, pausa, som), padrões agregados das decupagens (um gráfico a cada N s, tipos, transições,
    layouts) e as N fichas decupadas mais parecidas com a duração alvo, cada uma com abertura, receita e o que não copiar."""
    todas = [ler_json(p) for p in sorted(_dir().glob("*/ficha.json"))]
    fs = [f for f in todas if f.get("formato") == formato]
    if not fs:
        return {"formato": formato, "n": 0, "aviso": f"Sem fichas de '{formato}'. Formatos com fichas: {sorted({f.get('formato') for f in todas})}"}
    med = {k: _mediana([f.get("metricas", {}).get(k) for f in fs]) for k in ("duracao_s", "palavras_por_s", "pausa_max_s", "plano_medio_s", "cortes_por_min", "lufs", "fala_comeca_s")}
    dec = [f for f in fs if f.get("padroes")]
    agreg = {}
    if dec:
        agreg["grafismo_a_cada_s"] = _mediana([f["padroes"].get("grafismo_a_cada_s") for f in dec])
        agreg["trecho_medio_s"] = _mediana([f["padroes"].get("trecho_medio_s") for f in dec])
        for chave in ("tipos_grafismo", "transicoes", "layouts"):
            soma = {}
            for f in dec:
                for k, v in (f["padroes"].get(chave) or {}).items():
                    soma[k] = soma.get(k, 0) + v
            agreg[chave] = dict(sorted(soma.items(), key=lambda kv: -kv[1]))
        agreg["tela_cheia_por_video"] = _mediana([f["padroes"].get("tela_cheia") for f in dec])
    alvo = duracao_alvo_s or med["duracao_s"] or 0
    exemplos = sorted(dec or fs, key=lambda f: abs((f.get("metricas", {}).get("duracao_s") or 0) - alvo))[:n]
    return {"formato": formato, "descricao": FORMATOS.get(formato), "n": len(fs), "decupadas": len(dec), "alvos": med, "padroes": agreg,
            "exemplos": [{"id": f["id"], "titulo": f.get("titulo"), "origem": f.get("origem"), "duracao_s": f.get("metricas", {}).get("duracao_s"),
                          "desempenho": f.get("desempenho") or None, "abertura": f.get("abertura"), "receita": f.get("receita"), "fechamento": f.get("fechamento"),
                          "nao_copiar": f.get("nao_copiar"), "trechos": [{k: t[k] for k in ("inicio", "fim", "layout", "transicao")} | {"grafismo": t["grafismo"]["tipo"]}
                                                                          for t in (f.get("decupagem") or [])][:40]} for f in exemplos],
            "lembrete": "Referência é estudo: traduza ritmo e estrutura para os parâmetros; nunca copie texto, imagem ou áudio da referência."}


def comparar(formato, metricas=None, video="", palavras_json="", grafismos_json="", resultado_montagem=None):
    """Compara uma entrega com a receita do formato. Aceita as medidas prontas ou mede o vídeo; com o plano de grafismos e o resultado do
    montar_remotion, compara também a densidade de gráficos e as transições. Devolve diferenças em linguagem simples, sem nota."""
    rec = consultar(formato, n=0)
    if not rec.get("n"):
        return rec
    if metricas is None:
        if not video:
            raise ErroFerramenta("Passe metricas ou video.")
        metricas, _ = medir(video, ler_json(palavras_json) if palavras_json else None)
    alvos, difs = rec["alvos"], []
    def comp(chave, nome, unidade, fmt="{:.2f}", tolerancia=0.15, menor_melhor=False):
        a, v = alvos.get(chave), metricas.get(chave)
        if a is None or v is None:
            return
        dif = (v - a) / abs(a) if a else (0 if abs(v) <= 0.3 else 1)
        estado = "ok" if abs(dif) <= tolerancia else ("acima" if dif > 0 else "abaixo")
        if menor_melhor and v <= a:
            estado = "ok"
        difs.append({"medida": nome, "nossa": round(v, 2), "referencia": a, "estado": estado, "texto": f"{nome}: nossa {fmt.format(v)}{unidade}, referência {fmt.format(a)}{unidade}" + ("" if estado == "ok" else f" ({estado})")})
    comp("palavras_por_s", "Palavras por segundo", "", tolerancia=0.25)  # 13/11/2026: 10% empurrava o agente a apertar a borda da fala
    comp("pausa_max_s", "Maior pausa", " s", menor_melhor=True)
    comp("fala_comeca_s", "Fala começa em", " s", menor_melhor=True, tolerancia=0.5)
    comp("lufs", "Volume (LUFS)", "", fmt="{:.1f}", tolerancia=0.06)
    if grafismos_json:
        plano = ler_json(grafismos_json); itens = plano.get("itens", plano) if isinstance(plano, dict) else plano
        dur = metricas.get("duracao_s") or 1
        if itens and rec["padroes"].get("grafismo_a_cada_s"):
            nossa = round(dur / len(itens), 2); ref = rec["padroes"]["grafismo_a_cada_s"]
            tipos = {}
            for it in itens:
                tipos[it.get("tipo")] = tipos.get(it.get("tipo"), 0) + 1
            # 13/11/2026: só aponta excesso. Menos gráfico que a referência não é defeito; gráfico sem motivo é.
            difs.append({"medida": "Um gráfico a cada", "nossa": nossa, "referencia": ref, "estado": "ok" if nossa >= ref * 0.7 else "abaixo",
                         "texto": f"Um gráfico a cada {nossa:.1f} s (referência {ref:.1f} s); tipos nossos {len(tipos)}, referência usa {len(rec['padroes'].get('tipos_grafismo') or {})}"})
    if resultado_montagem and (resultado_montagem.get("transicoes") or {}).get("por_tipo") and rec["padroes"].get("transicoes"):
        nossas = resultado_montagem["transicoes"]["por_tipo"]; total_n = sum(nossas.values()) or 1; ref = rec["padroes"]["transicoes"]; total_r = sum(ref.values()) or 1
        seco_n, seco_r = nossas.get("seco", 0) / total_n, (ref.get("seco", 0) + ref.get("nenhuma", 0)) / total_r
        difs.append({"medida": "Emendas secas", "nossa": round(seco_n, 2), "referencia": round(seco_r, 2), "estado": "ok" if seco_n >= seco_r - 0.2 else "abaixo",  # mais seco que a referência não é defeito
                     "texto": f"Emendas secas: nossa {seco_n:.0%}, referência {seco_r:.0%}"})
    return {"formato": formato, "base": f"{rec['n']} fichas ({rec['decupadas']} decupadas)", "diferencas": difs,
            "fora_do_alvo": [d["texto"] for d in difs if d["estado"] != "ok"]}
