"""Revisor: o Gemini assiste ao vídeo final e aponta defeitos. Usa a API REST (sem SDK). Precisa de GEMINI_API_KEY no .env do projeto."""
import json, os, re, time, urllib.request, urllib.error
from pathlib import Path
from .util import caminho_saida, caminho, info_midia, ErroFerramenta

API = "https://generativelanguage.googleapis.com"
PROMPT = """Você é revisor de vídeo da Grava Simples (conteúdo do Thiago sobre gravar aulas e lives com OBS). Assista ao vídeo inteiro e responda em PT-BR, em JSON, com este formato:
{"nota_geral": 0-10, "resumo": "uma frase", "problemas": [{"instante_s": número, "gravidade": "alta|media|baixa", "tipo": "corte|legenda|audio|enquadramento|zoom|texto|ritmo|outro", "descricao": "o que está errado, curto", "sugestao": "o que fazer"}], "acertos": ["..."], "legenda_erros": [{"instante_s": número, "texto_visto": "...", "provavel_correto": "..."}]}
Procure: corte no meio de palavra ou frase; pausa longa que sobrou; legenda cobrindo rosto ou fora de sincronia; palavra errada na legenda; zoom brusco ou tremido; clarão exagerado; frase de impacto ou tela final ilegível; áudio estourado, baixo ou com clique; trecho mudo; ritmo arrastado. Seja específico com o instante em segundos. Não invente problema; se o vídeo estiver bom, diga."""


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


def revisar_video(video, saida_json=None, modelo=None, prompt_extra="", inicio_s=None, fim_s=None):
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
    texto = PROMPT + ("\n\n" + texto_trecho if texto_trecho else "") + ("\n\nContexto extra: " + prompt_extra if prompt_extra else "")
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
