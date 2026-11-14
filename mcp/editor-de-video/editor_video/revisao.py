"""Revisor: o Gemini assiste ao vídeo final e aponta defeitos. Usa a API REST (sem SDK). Precisa de GEMINI_API_KEY no .env do projeto."""
import json, os, re, time, urllib.request, urllib.error
from pathlib import Path
from .util import caminho_saida, caminho, info_midia, ErroFerramenta

API = "https://generativelanguage.googleapis.com"
PROMPT = """Você é revisor de vídeo da Grava Simples (conteúdo do Thiago sobre gravar aulas e lives com OBS). Assista ao vídeo inteiro e responda em PT-BR, em JSON, com este formato:
{"nota_geral": 0-10, "resumo": "uma frase", "problemas": [{"instante_s": número, "gravidade": "alta|media|baixa", "tipo": "corte|continuidade|take_repetido|efeito_sem_motivo|excesso|legenda|audio|enquadramento|zoom|texto|ritmo|outro", "descricao": "o que está errado, curto", "sugestao": "o que fazer"}], "acertos": ["..."], "legenda_erros": [{"instante_s": número, "texto_visto": "...", "provavel_correto": "..."}]}
Procure, nesta ordem de importância:
1. Sentido da fala: frase que começa e não termina; ideia que pula sem ligação com a anterior (continuidade); a mesma frase dita duas vezes ou um take abandonado que ficou (take_repetido); conectivo solto ("e", "mas", "porque") ligando coisas que não se ligam.
2. Corte: no meio de palavra ou sílaba comida; respiração ou estalo na emenda; pausa longa que sobrou.
3. Efeitos: transição forte, zoom, tremor, som ou gráfico sem motivo na fala (efeito_sem_motivo: não marca troca de assunto, ênfase, número, ferramenta citada nem lista); gráfico que só repete a legenda ou não casa com a frase; efeitos colados demais (excesso: mais de uma transição forte em 8 s, gráfico em cima de gráfico, tremor em texto que está sendo lido).
4. Acabamento: legenda cobrindo rosto ou fora de sincronia; palavra errada na legenda; zoom brusco ou tremido; clarão exagerado; frase de impacto ou tela final ilegível; áudio estourado, baixo ou com clique; trecho mudo; ritmo arrastado. Seja específico com o instante em segundos. Não invente problema; se o vídeo estiver bom, diga."""


def _chave():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        env = Path(__file__).resolve().parents[3] / ".env"
        if env.exists():
            for l in env.read_text(encoding="utf-8").splitlines():
                if l.startswith("GEMINI_API_KEY="):
                    k = l.split("=", 1)[1].strip().strip('"')
    if not k:
        raise ErroFerramenta("GEMINI_API_KEY ausente: cole a chave em ~/projetos/editor-gs/.env (linha GEMINI_API_KEY=...).")
    return k


def _req(metodo, url, dados=None, headers=None, raw=False):
    h = {"Content-Type": "application/json"}; h.update(headers or {})
    body = dados if raw else (json.dumps(dados).encode() if dados is not None else None)
    r = urllib.request.Request(url, method=metodo, data=body, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="ignore")
        try:
            msg = json.loads(corpo).get("error", {}).get("message", corpo)
        except Exception:
            msg = corpo
        raise ErroFerramenta(f"Gemini HTTP {e.code}: {msg[:400]}")


def testar_gemini(modelo=None):
    """Chamada mínima de texto para validar chave, modelo e cota."""
    k = _chave(); m = modelo or os.environ.get("GEMINI_MODELO", "gemini-3.5-flash")
    st, _, corpo = _req("POST", f"{API}/v1beta/models/{m}:generateContent?key={k}", {"contents": [{"parts": [{"text": "Responda só: ok"}]}]})
    d = json.loads(corpo); txt = d["candidates"][0]["content"]["parts"][0]["text"].strip()
    return {"ok": True, "modelo": m, "resposta": txt[:40], "uso": d.get("usageMetadata")}


def trecho_video(inicio_s=None, fim_s=None, duracao_s=None):
    """Trecho para o Gemini olhar (10/11/2026): devolve (video_metadata com start_offset/end_offset no formato "12.5s", texto para o prompt) ou (None, "").
    Sem os dois, o comportamento é o antigo (vídeo inteiro). Valida ordem e limites."""
    if inicio_s is None and fim_s is None:
        return None, ""
    a = max(0.0, float(inicio_s or 0.0)); z = float(fim_s) if fim_s is not None else (float(duracao_s) if duracao_s else None)
    if z is None:
        raise ErroFerramenta("informe fim_s junto com inicio_s (ou a duração do vídeo)")
    if duracao_s:
        z = min(z, float(duracao_s))
    if z <= a:
        raise ErroFerramenta(f"trecho inválido: fim_s ({z}) deve ser maior que inicio_s ({a})")
    meta = {"start_offset": f"{a:.3f}s", "end_offset": f"{z:.3f}s"}
    return meta, f"Olhe só o trecho de {a:.1f} s a {z:.1f} s do vídeo (os instantes que você citar são os do vídeo inteiro, não do trecho)."


def contexto_revisao(palavras_json=None, grafismos_json=None, pedido="", max_chars=6000):
    """Texto de apoio para o revisor (13/11/2026): o que é falado (frases com o segundo no vídeo cortado), o plano de gráficos e o que foi pedido.
    Sem isso o Gemini não tinha como julgar se a fala liga nem se um gráfico casa com a frase."""
    from .util import ler_json
    partes = []
    if pedido:
        partes.append("O que foi pedido (estilo e objetivo): " + str(pedido)[:600])
    if palavras_json:
        try:
            d = ler_json(palavras_json); segs = d.get("segmentos") or []
            if not segs and d.get("palavras"):  # sem segmentos: linhas de 12 palavras
                ps = d["palavras"]
                segs = [{"inicio": ps[i]["inicio"], "texto": " ".join(x["palavra"].strip() for x in ps[i:i + 12])} for i in range(0, len(ps), 12)]
            linhas = [f"{float(x['inicio']):.1f}: {str(x.get('texto', '')).strip()}" for x in segs]
            partes.append("Fala esperada no vídeo (segundo: frase):\n" + "\n".join(linhas))
        except Exception:  # noqa
            pass
    if grafismos_json:
        try:
            g = ler_json(grafismos_json); itens = g.get("itens") if isinstance(g, dict) else g
            linhas = []
            for it in (itens or [])[:60]:
                lista = it.get("itens") if isinstance(it.get("itens"), list) else []
                txt = it.get("texto") or it.get("titulo") or ", ".join(str(x.get("texto") or x.get("rotulo") or "") if isinstance(x, dict) else str(x) for x in lista[:4])
                linhas.append(f"{it.get('inicio', it.get('t', '?'))}: {it.get('tipo', '?')} {str(txt)[:60]} (dispara em: {it.get('palavra', it.get('gesto', ''))})")
            partes.append("Gráficos planejados (segundo: tipo, texto, o que dispara):\n" + "\n".join(linhas))
        except Exception:  # noqa
            pass
    txt = "\n\n".join(partes)
    return txt[:max_chars] + (" …" if len(txt) > max_chars else "")


def revisar_video(video, saida_json=None, modelo=None, prompt_extra="", inicio_s=None, fim_s=None, palavras_json=None, grafismos_json=None, pedido=""):
    """Envia o vídeo pela Files API (upload resumível), espera processar e pede a revisão estruturada.
    inicio_s/fim_s (opcionais) limitam a análise a um trecho (video_metadata.start_offset/end_offset do Gemini): mais barato quando o problema é localizado."""
    v = caminho(video); info = info_midia(v); k = _chave(); m = modelo or os.environ.get("GEMINI_MODELO", "gemini-3.5-flash")
    meta_trecho, texto_trecho = trecho_video(inicio_s, fim_s, info["duracao_s"])
    tamanho = v.stat().st_size
    if tamanho > 1_900_000_000:
        raise ErroFerramenta("Vídeo acima de 1,9 GB: envie uma versão menor (720p).")
    # 1) inicia upload resumível
    st, h, _ = _req("POST", f"{API}/upload/v1beta/files?key={k}", {"file": {"display_name": v.name}},
                    headers={"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(tamanho),
                             "X-Goog-Upload-Header-Content-Type": "video/mp4"})
    url_up = h.get("X-Goog-Upload-URL") or h.get("x-goog-upload-url")
    if not url_up:
        raise ErroFerramenta("Files API não devolveu URL de upload.")
    with open(v, "rb") as f:
        dados = f.read()
    st, _, corpo = _req("POST", url_up, dados, headers={"Content-Type": "video/mp4", "Content-Length": str(tamanho), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}, raw=True)
    arq = json.loads(corpo)["file"]; nome = arq["name"]; uri = arq["uri"]
    # 2) espera processar
    for _ in range(120):
        st, _, corpo = _req("GET", f"{API}/v1beta/{nome}?key={k}")
        estado = json.loads(corpo).get("state")
        if estado == "ACTIVE":
            break
        if estado == "FAILED":
            raise ErroFerramenta("Gemini não conseguiu processar o vídeo.")
        time.sleep(3)
    else:
        raise ErroFerramenta("Tempo esgotado esperando o Gemini processar o vídeo.")
    # 3) revisão
    parte_video = {"file_data": {"mime_type": "video/mp4", "file_uri": uri}}
    if meta_trecho:
        parte_video["video_metadata"] = meta_trecho
    apoio = contexto_revisao(palavras_json, grafismos_json, pedido)
    texto = PROMPT + ("\n\n" + texto_trecho if texto_trecho else "") + ("\n\n" + apoio if apoio else "") + ("\n\nContexto extra: " + prompt_extra if prompt_extra else "")
    pedido = {"contents": [{"parts": [parte_video, {"text": texto}]}],
              "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}}
    st, _, corpo = _req("POST", f"{API}/v1beta/models/{m}:generateContent?key={k}", pedido)
    d = json.loads(corpo)
    try:
        txt = d["candidates"][0]["content"]["parts"][0]["text"]; rev = json.loads(txt)
    except Exception:
        rev = {"bruto": str(d)[:2000]}
    # 4) apaga o arquivo remoto (não deixa o vídeo guardado lá)
    try:
        _req("DELETE", f"{API}/v1beta/{nome}?key={k}")
    except ErroFerramenta:
        pass
    res = {"video": str(v), "duracao_s": info["duracao_s"], "modelo": m, "revisao": rev, "uso": d.get("usageMetadata")}
    if meta_trecho:
        res["trecho"] = {"inicio_s": float(meta_trecho["start_offset"][:-1]), "fim_s": float(meta_trecho["end_offset"][:-1])}
    if saida_json:
        from .util import salvar_json
        res["revisao_json"] = salvar_json(saida_json, res)
    return res


# --- textos baratos pelo Gemini (poupa a cota do Claude) ---------------------------------------------
def _gemini_json(prompt, modelo=None, _req_=None, temperatura=0.2):
    """Chamada de texto ao Gemini pedindo JSON; devolve o objeto parseado e o uso."""
    k = _chave(); m = modelo or os.environ.get("GEMINI_MODELO", "gemini-3.5-flash")
    corpo = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperatura, "responseMimeType": "application/json"}}
    st, _, raw = (_req_ or _req)("POST", f"{API}/v1beta/models/{m}:generateContent?key={k}", corpo)
    d = json.loads(raw); txt = d["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return json.loads(txt), d.get("usageMetadata"), m
    except Exception:
        raise ErroFerramenta(f"Gemini não devolveu JSON válido: {txt[:200]}")


IDIOMAS = {"en": "inglês (EUA)", "es": "espanhol (neutro, latino-americano)", "pt": "português do Brasil", "fr": "francês", "it": "italiano", "de": "alemão"}


def traduzir_srt(srt, saida_srt, idioma="en", contexto="", destaque=True, curto=False, modelo=None, _req_=None):
    """Traduz um SRT com o Gemini (barato e rápido), mantendo os tempos e a ordem dos blocos. destaque=True marca *uma* palavra por bloco com asteriscos
    (o `legenda_de_srt` pinta de laranja). curto=True pede frases mais enxutas (para dublagem caber no tempo). Devolve o SRT novo e os blocos."""
    import pysubs2
    try:
        subs = pysubs2.load(str(caminho(srt)), encoding="utf-8")
    except Exception as e:
        raise ErroFerramenta(f"SRT inválido: {e}")
    blocos = [ev for ev in subs if not ev.is_comment and ev.plaintext.strip()]
    if not blocos:
        raise ErroFerramenta("SRT sem blocos com texto.")
    if len(blocos) > 400:
        raise ErroFerramenta("SRT com mais de 400 blocos: divida em partes.")
    alvo = IDIOMAS.get(idioma, idioma)
    linhas = "\n".join(f"{i + 1}|{ev.plaintext.replace(chr(10), ' ').strip()}" for i, ev in enumerate(blocos))
    prompt = (f"Você traduz legendas de vídeos curtos sobre gravação de vídeo/OBS Studio para {alvo}. Público: criador iniciante. Tom: conversa direta, frases curtas, natural de falar.\n"
              f"Regras: traduza bloco a bloco, mesma ordem, mesma quantidade ({len(blocos)} blocos); não junte nem divida blocos; mantenha números, nomes de produto, menus e siglas (OBS, Meet, C922); "
              f"não adicione informação; sem emoji; nada de preço ou oferta. {'Prefira frases 20% mais curtas que o original (vai virar dublagem e precisa caber no tempo). ' if curto else ''}"
              f"{'Em cada bloco, marque UMA palavra-chave com asteriscos, assim: *palavra* (a mais importante para o sentido; nunca artigos). ' if destaque else ''}"
              f"{('Contexto: ' + contexto + '. ') if contexto else ''}"
              f"Responda SÓ com JSON: {{\"blocos\": [\"texto do bloco 1\", \"texto do bloco 2\", ...]}}.\n\nBLOCOS:\n{linhas}")
    d, uso, m = _gemini_json(prompt, modelo=modelo, _req_=_req_)
    novos = d.get("blocos") if isinstance(d, dict) else d
    if not isinstance(novos, list) or len(novos) != len(blocos):
        raise ErroFerramenta(f"Tradução devolveu {len(novos) if isinstance(novos, list) else '?'} blocos para {len(blocos)}: rode de novo ou divida o SRT.")
    out = pysubs2.SSAFile()
    for ev, txt in zip(blocos, novos):
        t = re.sub(r"\s+", " ", str(txt)).strip()
        if not destaque or t.count("*") not in (0, 2):
            t = t.replace("*", "")
        out.append(pysubs2.SSAEvent(start=ev.start, end=ev.end, text=t))
    dest = caminho_saida(saida_srt); out.save(str(dest), format_="srt")
    return {"srt": str(dest), "idioma": idioma, "n_blocos": len(blocos), "modelo": m, "uso": uso, "blocos": [{"inicio": ev.start / 1000, "fim": ev.end / 1000, "texto": t} for ev, t in zip(blocos, [e.text for e in out])],
            "nota": "Tradução automática (Gemini): leia antes de usar; termos técnicos marcados [CONFERIR] nas pendências se tiver dúvida."}
