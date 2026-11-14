"""Acabamento: montagem no Remotion (zoom, clarão, frase de impacto, tela final) e capa."""
import json, os, shutil, subprocess, time, uuid
from pathlib import Path
from .util import FFMPEG, caminho, caminho_saida, caminho_previa, ler_json, info_midia, rodar, ErroFerramenta, plataforma, CRF_PREVIA

RAIZ = Path(__file__).resolve().parents[3]
REMOTION = RAIZ / "remotion"
def _node_bin() -> Path:
    """Pasta do Node 24: EDITOR_GS_NODE_BIN, senão ~/EditorGS/bin/node (Windows), senão o node do PATH, senão a versão mais nova do nvm."""
    import shutil as _sh
    if plataforma:
        nb = plataforma.node_bin()
        if nb:
            return nb
    if os.environ.get("EDITOR_GS_NODE_BIN"):
        return Path(os.environ["EDITOR_GS_NODE_BIN"])
    n = _sh.which("node")
    if n:
        return Path(n).resolve().parent
    vers = sorted((Path.home() / ".nvm/versions/node").glob("v*/bin"))
    return vers[-1] if vers else Path("/usr/bin")
NODE_BIN = _node_bin()
NPX = plataforma.npx() if plataforma else str(NODE_BIN / "npx")
RES = {("9x16", "720p"): (720, 1280), ("9x16", "1080p"): (1080, 1920), ("16x9", "720p"): (1280, 720), ("16x9", "1080p"): (1920, 1080)}


def _cortes_no_tempo_final(edl):
    """Instantes (s, no vídeo cortado) onde houve corte: fim acumulado de cada trecho mantido, exceto o último."""
    acc, pontos = 0.0, []
    for i, m in enumerate(edl["manter"]):
        acc += m["fim"] - m["inicio"]
        if i < len(edl["manter"]) - 1:
            pontos.append(round(acc, 3))
    return pontos


CINETICAS = ("tipografica", "maquina", "onda")  # animações de legenda desenhadas pelo Remotion (GSAP), não pelo motor ASS
_PESOS = {"extrabold": 800, "black": 800, "bold": 700, "semibold": 700}


def legenda_cinetica_props(est, pal, formato, W, H, legenda_ass=None):
    """Legenda cinética (10/11/2026): quando o bloco `legenda` do estilo pede `animacao` tipografica | maquina | onda e há `palavras_json`,
    monta a prop `legenda_cinetica` do Remotion (linhas agrupadas como no motor ASS, uma palavra de ênfase por linha, tamanho em px
    na resolução do render). Devolve None quando a animação é do motor ASS, não há palavras ou veio `legenda_ass` (a ASS externa manda:
    nada muda). `legenda.tremor = true` liga o CustomWiggle na palavra de ênfase."""
    anim = str((est or {}).get("animacao") or "").strip().lower()
    palavras = (pal or {}).get("palavras") or [w for s in (pal or {}).get("segmentos", []) for w in (s.get("palavras") or [])]
    if anim not in CINETICAS or not palavras or legenda_ass:
        return None
    from . import nivel_pro
    from .legenda import _linhas
    chaves = nivel_pro.palavras_chave_auto(pal, est.get("palavras_chave_lista")) if pal else []
    def enfase_de(linha):
        for i, p in enumerate(linha):  # 1º: palavra-chave da fala (números, recursos, dor/benefício) que cai dentro da linha
            if any(abs(float(k["inicio"]) - float(p["inicio"])) < 0.05 for k in chaves):
                return i
        if len(linha) >= 2:  # 2º: a palavra mais longa com 4+ letras
            cand = max(range(len(linha)), key=lambda i: len(nivel_pro._norm(linha[i].get("palavra", ""))))
            if len(nivel_pro._norm(linha[cand].get("palavra", ""))) >= 4:
                return cand
        return -1
    mp = int(est.get("palavras_por_linha_max", 4))
    linhas = []
    for k, linha in enumerate(_linhas(palavras, max_palavras=mp)):
        ini = float(linha[0]["inicio"]); fim = float(linha[-1]["fim"]) + 0.12
        e = enfase_de(linha)
        ws = [{"texto": str(p.get("palavra") or p.get("texto") or "").strip(), "inicio": round(float(p["inicio"]), 3), "fim": round(float(p["fim"]), 3), **({"enfase": True} if i == e else {})}
              for i, p in enumerate(linha)]
        linhas.append({"inicio": round(ini, 3), "fim": round(fim, 3), "palavras": [w for w in ws if w["texto"]]})
    for a, b in zip(linhas, linhas[1:]):  # a cauda de 0,12 s nunca invade a linha seguinte
        a["fim"] = round(max(min(a["fim"], b["inicio"] - 0.01), a["palavras"][-1]["fim"] if a["palavras"] else a["inicio"], a["inicio"] + 0.05), 3)
    linhas = [l for l in linhas if l["palavras"]]
    base = 1080 if formato == "9x16" else 1920
    tam = float(est.get("tamanho_9x16" if formato == "9x16" else "tamanho_16x9", 64)) * W / base
    peso = _PESOS.get(str(est.get("peso", "ExtraBold")).lower(), 400)
    contorno_px = float(est["contorno_px"]) if est.get("contorno_px") is not None else max(2.0, tam / 14)
    return {"animacao": anim, "tremor": bool(est.get("tremor", False)), "linhas": linhas, "fonte": "InterGS", "peso": peso, "tamanho": round(tam, 1),
            "cor_texto": est.get("cor_texto", "#FFFFFF"), "cor_destaque": est.get("cor_destaque", "#F79615"), "contorno": est.get("contorno", "#000921"),
            "contorno_px": round(contorno_px * (1.0 if not est.get("caixa") else 0.0), 2), "posicao": est.get("posicao", "baixa"),
            "altura_pct": float(est["altura_pct"]) if est.get("altura_pct") is not None else None, "maiusculas": bool(est.get("maiusculas", False)),
            "caixa": bool(est.get("caixa")), "cor_caixa": est.get("cor_caixa") or None}


# 11/11/2026: medium → veryfast na compressão final do montar_remotion: 32 s → 14 s num corte de 36 s, PSNR 43,6 dB contra o medium (45,3), arquivo menor.
PRESET_FINAL = os.environ.get("EDITOR_GS_PRESET_FINAL", "veryfast")


def fundo_desfocado(video, destino, W, H, reducao=6):
    """Fundo do vídeo que muda de orientação (deitado → 9:16), já desfocado e escurecido, em 1/`reducao` do tamanho final.
    No navegador o fundo decodificava o vídeo inteiro uma segunda vez por quadro: +60% de render no 9:16 (medido em 11/11/2026).
    Mesmo visual do filtro CSS antigo (blur 28 px, brilho 0,55). Devolve o caminho ou None se o ffmpeg falhar (Montagem volta ao filtro CSS)."""
    w, h = max(2, W // reducao // 2 * 2), max(2, H // reducao // 2 * 2)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma={28 / reducao:.2f},"
          "colorchannelmixer=rr=0.55:gg=0.55:bb=0.55")
    try:
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-loglevel", "error", "-i", str(video), "-an", "-vf", vf,
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p", str(destino)])
    except Exception:
        Path(destino).unlink(missing_ok=True)
        return None
    return Path(destino) if Path(destino).exists() else None


def renderizar_remotion(composicao, props, saida, timeout=3600):
    """Renderiza uma composição do projeto remotion/ (Montagem, CenaTexto) com as props dadas para `saida` (.mp4, h264, sem áudio salvo se a composição tiver).
    Levanta ErroFerramenta com o fim do log quando o render falha."""
    out = caminho_saida(saida); pub = REMOTION / "public" / "render"; pub.mkdir(parents=True, exist_ok=True)
    props_path = pub / f"{uuid.uuid4().hex[:10]}.json"; props_path.write_text(json.dumps(props), encoding="utf-8")
    libs = Path.home() / ".local/lib-chromium/usr/lib/x86_64-linux-gnu"  # só existe onde o Chromium foi instalado sem sudo (Linux)
    env = {**os.environ, "PATH": f"{NODE_BIN}{os.pathsep}{os.environ.get('PATH', '')}"}
    if libs.exists():
        env["LD_LIBRARY_PATH"] = f"{libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"
    # o mp4 do Remotion é intermediário (montar_remotion recomprime com a legenda): x264 veryfast com crf baixo poupa CPU sem perder qualidade (11/11/2026)
    cmd = [NPX, "remotion", "render", "src/index.ts", composicao, str(out), f"--props={props_path}", "--codec=h264", "--log=error",
           f"--x264-preset={os.environ.get('EDITOR_GS_REMOTION_PRESET', 'veryfast')}", "--crf=16"]
    try:
        r = subprocess.run(cmd, cwd=str(REMOTION), capture_output=True, text=True, env=env, timeout=timeout)
    finally:
        props_path.unlink(missing_ok=True)
    if r.returncode != 0 or not out.exists():
        raise ErroFerramenta(f"Remotion falhou: {(r.stderr or r.stdout)[-900:]}")
    return out


def renderizar_remotion_alpha(composicao, props, saida_mov, timeout=3600):
    """Renderiza com fundo transparente para `saida_mov` (.mov, codec PNG com canal alfa). O CapCut 9.7 ignora o alfa do ProRes 4444 e do WebM VP9,
    mas respeita MOV PNG, MOV QTRLE, GIF e APNG (teste do Raphael em 12/11/2026). Remotion sai em sequência PNG; o ffmpeg empacota."""
    out = Path(saida_mov); out.parent.mkdir(parents=True, exist_ok=True)
    pub = REMOTION / "public" / "render"; pub.mkdir(parents=True, exist_ok=True)
    rid = uuid.uuid4().hex[:10]; props_path = pub / f"{rid}.json"; props_path.write_text(json.dumps(props), encoding="utf-8")
    quadros = out.parent / f"_quadros_{out.stem}_{rid}"
    env = {**os.environ, "PATH": f"{NODE_BIN}{os.pathsep}{os.environ.get('PATH', '')}"}
    cmd = [NPX, "remotion", "render", "src/index.ts", composicao, str(quadros), f"--props={props_path}", "--sequence", "--image-format=png", "--log=error"]
    try:
        r = subprocess.run(cmd, cwd=str(REMOTION), capture_output=True, text=True, env=env, timeout=timeout)
        pngs = sorted(quadros.glob("*.png"))
        if r.returncode != 0 or not pngs:
            raise ErroFerramenta(f"Remotion (camada transparente) falhou: {(r.stderr or r.stdout)[-900:]}")
        import re as _re
        m = _re.match(r"^(.*?)(\d+)\.png$", pngs[0].name)
        padrao = str(quadros / f"{m.group(1)}%0{len(m.group(2))}d.png")
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-framerate", str(props.get("fps") or 30), "-start_number", str(int(m.group(2))), "-i", padrao,
               "-c:v", "png", "-pix_fmt", "rgba", str(out)])
    finally:
        props_path.unlink(missing_ok=True); shutil.rmtree(quadros, ignore_errors=True)
    return out


DESLIGADO = {"nenhum", "nenhuma", "off", "nao", "não", "false", "0", "sem"}


def montar_remotion(video, saida_video, palavras_json=None, edl_json=None, formato="9x16", resolucao="1080p", estilo=None,
                    zoom=None, zoom_fator=1.08, clarao=None, frase_impacto=None, frase_destaque="", tela_final=None,
                    tela_titulo="Aprenda a gravar de forma simples", tela_destaque="simples", tela_cta="Siga o perfil", tela_marca="GRAVA SIMPLES",
                    legenda_ass=None, fps=30, crf=20, vinheta=False, vinheta_s=1.0, vinheta_titulo="Grava Simples", vinheta_destaque="Simples",
                    terco_texto="", terco_sub="", terco_inicio_s=1.0, terco_s=4.0,
                    palavras_chave="", capitulos="", barra_progresso=None, broll="", sfx=None, ritmo_zoom_s=0.0, palavras_chave_lista=None,
                    gancho_animacao="", trilha="", trilha_volume_db=None, grafismos="", serie="", parte=0,
                    layout="", tela="", focos="", passos="", rosto_recortado="auto", cortina=True, transicoes="", energia="", receita_transicoes="", previa=False,
                    legenda_modelo="", legenda_tremor=None):
    """previa=True (10/11/2026): render barato em 720p (crf mais alto, fps igual) para `<saida>_previa`, para aprovar antes do 1080p; resultado ganha
    `previa`, `resolucao` e `tempo_s` e nada mais muda.
    Nível profissional (02/11/2026): palavras_chave = "auto" (regras sobre o palavras_json) ou JSON [{texto, inicio, fim}]; capitulos = "Áudio@0; Luz@12" ou JSON;
    barra_progresso; broll = "arquivo@inicio@duracao[@cheio|janela]; …" ou JSON (imagem ou vídeo; cutaway com zoom lento); sfx = whoosh nos cortes, pop nas palavras-chave,
    ding na tela final (remotion/public/sfx); ritmo_zoom_s > 0 = enquadramento alterna a cada N s (pattern interrupt). O bloco `montagem` do estilo pode ligar tudo isso.
    Fase 2 (03/11/2026): broll="auto" acha no próprio vídeo os trechos de tela (sem rosto) e os usa como janela enquanto o Thiago fala; gancho_animacao="palavra"
    faz a frase de impacto entrar palavra por palavra; trilha="auto" usa a primeira de trilhas/ com ducking (pasta vazia = só a voz) ou um caminho.
    Fase B (07/11/2026): grafismos = caminho do grafismos.json, JSON inline ou "auto" (grafismos.plano_auto); quando há grafismos, as palavras-chave
    por regra saem (o plano substitui) e a legenda some nos trechos de tela cheia. serie/parte = abertura com o título da série e cartela "Parte N".
    Fase C (07/11/2026): layout = "painel" | "painel@0; tutorial@6; cheio@14" | JSON (modos em layouts.MODOS); tela = gravação de tela (com edl_json, recebe
    os mesmos cortes quando cobre o bruto); focos = "auto" ou JSON (câmera virtual + contorno); passos = "Exposição@3; ISO@8" ou JSON; rosto_recortado
    "auto" recorta o fundo do rosto quando há bloco aula; cortina = cortina laranja nas trocas de bloco.
    Fase E (08/11/2026): transicoes = "auto" (gramática de corte em transicoes.py: seco com troca de enquadramento, punch na ênfase, forte na troca de assunto,
    câmera sempre andando; substitui zoom alternado/clarão/ritmo), JSON {"segundo": "tipo"} para forçar tratamentos, ou "nenhuma"/"" (modo antigo).
    energia = calmo | normal | dinamico | bem_dinamico (vazio = deduz do ritmo_zoom_s).
    receita_transicoes = "" (proporção medida no Máquina, fala com tela) | formato do repertório (fala_tela, fala, anuncio, aula, animacao)
    | JSON {"seco": 0.4, "punch": 0.3, ...} | "regras" (gramática antiga, sem receita).
    Legenda cinética (10/11/2026, GSAP no Remotion): quando `estilo.legenda.animacao` é "tipografica" (palavras entram com stagger, rotação e
    escala), "maquina" (letras digitadas com cursor) ou "onda" (letras da palavra de ênfase sobem em onda) e há `palavras_json`, a legenda é
    desenhada pelo Remotion a partir dos tempos das palavras (modelos `estilos/legendas/cinetica-*.json`, ou estilo inline
    `{"legenda_modelo": "cinetica-tipografica"}` / `{"legenda": {"animacao": "onda", "tremor": true}}`); `legenda.tremor = true` põe um tremor
    (CustomWiggle) na palavra de ênfase de cada linha. Com `legenda_ass`, nada muda (a ASS externa é queimada como sempre e a cinética não entra).
    Atalhos sem estilo inline: legenda_modelo="cinetica-onda" aplica o modelo de estilos/legendas/ por cima do bloco `legenda` do estilo e
    legenda_tremor=True/False liga ou desliga o tremor (None = o que o modelo/estilo disser). O resultado traz `legenda_cinetica`
    (animacao, tremor, n_linhas) ou None, e `aviso_legenda` quando a cinética foi pedida junto com legenda_ass."""
    from . import nivel_pro, grafismos as grf, layouts as lay
    t0 = time.monotonic()
    v = caminho(video); info = info_midia(v)
    if previa:
        resolucao = "720p"; crf = max(int(crf), CRF_PREVIA); saida_video = caminho_previa(saida_video)
    mont = (estilo or {}).get("montagem", {}) if isinstance(estilo, dict) else {}
    # 13/11/2026: o estilo manda quando o parâmetro não foi dito. Antes zoom/clarão/tela final vinham True e só o estilo "montado" desligava:
    # o `padrao` ("limpo, sem efeitos") saía com zoom, clarão e tela final; sfx/barra do estilo não desligavam; "" caía no "auto" do estilo.
    # Agora: True/False explícito vence; None = estilo; "nenhum" (ou "nenhuma", "off") desliga mesmo com o estilo em "auto".
    pedidos = {"palavras_chave": palavras_chave, "broll": broll, "grafismos": grafismos, "trilha": trilha, "capitulos": capitulos, "gancho_animacao": gancho_animacao}
    desligar = {k for k, v in pedidos.items() if str(v or "").strip().lower() in DESLIGADO}
    mont = {**mont, **{k: "" for k in desligar}}
    palavras_chave, broll, grafismos, trilha, capitulos, gancho_animacao = ("" if k in desligar else v for k, v in pedidos.items())
    if isinstance(estilo, dict) and estilo.get("montado"):  # estilo montado na página Estilos: a escolha humana manda
        zoom = bool((zoom is not False) and (mont.get("zoom_por_frase", True) or mont.get("ritmo_zoom_s")))
        clarao = bool((clarao is not False) and mont.get("clarao_transicao", True))
        tela_final = bool((tela_final is not False) and mont.get("tela_final_cta", True))
        vinheta = bool(vinheta or mont.get("vinheta"))
    else:
        zoom = bool(mont.get("zoom_por_frase", True) or mont.get("ritmo_zoom_s")) if zoom is None else bool(zoom)
        clarao = bool(mont.get("clarao_transicao", True)) if clarao is None else bool(clarao)
        tela_final = bool(mont.get("tela_final_cta", True)) if tela_final is None else bool(tela_final)
    barra_progresso = bool(mont.get("barra_progresso")) if barra_progresso is None else bool(barra_progresso)
    sfx = bool(mont.get("sfx")) if sfx is None else bool(sfx)
    if not palavras_chave and mont.get("palavras_chave"):
        palavras_chave = mont["palavras_chave"]
    if not ritmo_zoom_s and mont.get("ritmo_zoom_s"):
        ritmo_zoom_s = float(mont["ritmo_zoom_s"])
    palavras_chave_lista = palavras_chave_lista or mont.get("palavras_chave_lista")
    if not broll and mont.get("broll"):
        broll = mont["broll"]
    gancho_animacao = gancho_animacao or mont.get("gancho_animacao", "")
    if not transicoes and mont.get("transicoes"):
        transicoes = mont["transicoes"]
    energia = energia or mont.get("energia", "")
    if not grafismos and mont.get("grafismos"):
        grafismos = mont["grafismos"]
    ser = grf.carregar_serie(serie) if serie else None
    if ser and not trilha and ser.get("trilha") and "trilha" not in desligar:
        trilha = ser["trilha"]
    if not trilha and mont.get("trilha"):
        trilha = mont["trilha"]
    if trilha_volume_db is None:
        trilha_volume_db = float(mont.get("trilha_volume_db", -20))
    if (formato, resolucao) not in RES:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    W, H = RES[(formato, resolucao)]
    est = (estilo or {}).get("legenda", estilo or {})
    if legenda_modelo:  # modelo da biblioteca por cima do bloco legenda (10/11/2026; o mesmo que {"legenda_modelo": id} no estilo inline)
        est = {**est, **ler_json(RAIZ / "estilos" / "legendas" / f"{str(legenda_modelo).strip()}.json")["legenda"]}
    if legenda_tremor is not None:
        est = {**est, "tremor": bool(legenda_tremor)}
    segs = [{"inicio": s["inicio"], "fim": s["fim"], "texto": s.get("texto", "")} for s in (ler_json(palavras_json).get("segmentos", []) if palavras_json else [])]
    cortes = _cortes_no_tempo_final(ler_json(edl_json)) if edl_json else []
    rid = uuid.uuid4().hex[:10]; pub = REMOTION / "public" / "render"; pub.mkdir(parents=True, exist_ok=True)
    link = pub / f"{rid}{v.suffix}"
    try:
        os.link(v, link)  # o bundle do Remotion não segue symlink; hardlink ou cópia
    except OSError:
        shutil.copy2(v, link)
    # nível profissional: palavras-chave, capítulos, b-roll, efeitos sonoros
    pal = ler_json(palavras_json) if palavras_json else {}
    if isinstance(palavras_chave, str) and palavras_chave.strip().lower() == "auto":
        chaves = nivel_pro.palavras_chave_auto(pal, palavras_chave_lista) if pal else []
    elif palavras_chave:
        chaves = [{"texto": str(k["texto"]), "inicio": float(k["inicio"]), "fim": float(k.get("fim", float(k["inicio"]) + 1.2))} for k in (json.loads(palavras_chave) if isinstance(palavras_chave, str) else palavras_chave) if k.get("texto")]
    else:
        chaves = []
    if not capitulos and mont.get("capitulos"):
        capitulos = mont["capitulos"]
    caps = (nivel_pro.capitulos_auto(pal) if pal else []) if str(capitulos).strip().lower() == "auto" else nivel_pro.capitulos_de(capitulos)
    brolls = []; links_extra = []
    fundo = None
    if (info["largura"] > info["altura"]) != (W > H):  # orientação muda: fundo desfocado pronto (11/11/2026)
        fundo = fundo_desfocado(v, pub / f"{rid}-fundo.mp4", W, H)
        if fundo:
            links_extra.append(fundo)
    broll_auto_info = None
    if isinstance(broll, str) and broll.strip().lower() == "auto":
        lista_b, broll_auto_info = _broll_auto(v, chaves, info["duracao_s"], pub, rid)
        links_extra += [pub / b["arquivo"] for b in lista_b]
    else:
        lista_b = nivel_pro.broll_de(broll)
    for b in lista_b:
        if b.get("_pronto"):  # quadro do próprio vídeo, já extraído em public/render por _broll_auto
            brolls.append({k: x for k, x in b.items() if k != "_pronto"} | {"video": False}); continue
        src = caminho(b["arquivo"]); alvo = pub / f"{rid}-b{len(brolls)}{src.suffix.lower()}"
        try:
            os.link(src, alvo)
        except OSError:
            shutil.copy2(src, alvo)
        links_extra.append(alvo)
        brolls.append({**b, "arquivo": alvo.name, "video": src.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv")})
    # fase B: plano de grafismos semântico (substitui as palavras-chave por regra) e abertura da série
    graf_itens, graf_avisos, graf_origem = [], [], None
    if grafismos:
        plano = grf.plano_auto(pal, palavras_chave_lista, info["duracao_s"]) if str(grafismos).strip().lower() == "auto" else grafismos
        graf_origem = "auto (regras)" if str(grafismos).strip().lower() == "auto" else "plano do agente"
        graf_itens, graf_avisos = grf.normalizar(plano, pal, info["duracao_s"])
        chaves = []
    if ser:
        titulo_s = ser.get("titulo") or ser.get("nome", "")
        graf_itens = [g for g in graf_itens if g["inicio"] >= 2.4 or g["posicao"] == "topo"]
        graf_itens.insert(0, {"tipo": "serie", "inicio": 0.0, "fim": round(min(info["duracao_s"], max(2.6, 1.4 + 0.16 * len(titulo_s.split()))), 2), "posicao": "peito",
                              "texto": titulo_s, "destaque": ser.get("destaque", ""), "parte": int(parte or 0) or None, "kicker": ser.get("kicker", "")})
        frase_impacto = None
    links_extra += grf.preparar_midias(graf_itens, pub, rid)
    # fase C: blocos de layout, tela com câmera virtual, passos, rosto recortado e cortina
    lay_cfg, lay_info = None, None
    composto = None
    if formato == "16x9" and info["largura"] and info["largura"] < info["altura"] and (not layout or "composto" in str(layout)):
        # 16:9 de vídeo vertical: se o bruto é composto (tela em cima, rosto embaixo), a tela vai à esquerda e o rosto à direita; senão, o fundo desfocado de sempre
        composto = lay.detectar_composto(v)
        if composto and not layout and composto["compostos_s"] >= 2.0:
            layout = "composto"
    if layout:
        lay_cfg, lay_info, extra = _layout(layout, tela, focos, passos, rosto_recortado, cortina, v, edl_json, pal, info["duracao_s"], pub, rid, composto=composto)
        links_extra += extra
    # SFX (10/11/2026): cada evento tem a sua categoria no catálogo CC0 (whoosh no corte, swipe na cortina, pop na palavra-chave, tick no capítulo,
    # erro/riser/impacto/ding por tipo de grafismo); sem catálogo ou sem a categoria, o evento fica sem som
    graf_sfx = [{"tipo": g["tipo"], "inicio": g["inicio"]} for g in graf_itens if g["tipo"] != "serie"]
    kw_sfx = dict(cortinas_s=list((lay_cfg or {}).get("cortinas_s", [])), capitulos=caps, grafismos=graf_sfx)
    # fase E: gramática de corte (planos da câmera) no lugar de zoom alternado + clarão igual em todo corte
    cam_cfg, cam_info = None, None
    trans_txt = str(transicoes or "").strip()
    if trans_txt and trans_txt.lower() not in ("nenhuma", "false", "0", "antigo"):
        from . import transicoes as trn
        forcar = None
        if trans_txt.startswith("{"):
            forcar = json.loads(trans_txt)
        elif isinstance(transicoes, dict):
            forcar = transicoes
        en = energia or ("bem_dinamico" if 0 < float(ritmo_zoom_s or 0) <= 3 else "calmo" if not (sfx or ritmo_zoom_s) else "dinamico")
        mud = trn.mudancas_de(graf_itens, caps, (lay_cfg or {}).get("cortinas_s"))
        rt = str(receita_transicoes or mont.get("receita_transicoes") or "").strip()
        receita = {} if rt == "regras" else json.loads(rt) if rt.startswith("{") else (trn.receita_de(rt) if rt else None)
        plano_cam = trn.planejar(cortes, info["duracao_s"], trn.enfases_de(graf_itens, chaves), mud, segs, en, forcar=forcar, sem_zoom=not zoom, sem_flash=not clarao,
                                 receita=receita)
        cam_cfg = {"planos": plano_cam["planos"]}
        if not lay_cfg:
            rp = lay.posicao_rosto(v)
            if rp:
                cam_cfg["origem"] = {"x": min(0.65, max(0.35, rp["x"])), "y": min(0.6, max(0.35, rp["y"]))}
        cam_info = plano_cam["resumo"] | {"origem": cam_cfg.get("origem")}
        efeitos = (trn.sfx_dos_planos(plano_cam["planos"]) + nivel_pro.sfx_auto([], chaves, info["duracao_s"] if tela_final else None, **kw_sfx)) if sfx else []
        efeitos.sort(key=lambda e: e["inicio"])
    else:
        efeitos = nivel_pro.sfx_auto(cortes, chaves, info["duracao_s"] if tela_final else None, **kw_sfx) if sfx else []
    props = {
        "video": link.name, "duracao_s": info["duracao_s"], "fps": fps, "largura": W, "altura": H, "largura_origem": info["largura"], "altura_origem": info["altura"],
        "segmentos": segs, "cortes_s": cortes,
        "zoom": {"ativo": bool(zoom), "fator": float(zoom_fator), "alternar": True},
        "clarao": {"ativo": bool(clarao), "duracao_s": 0.22, "opacidade": 0.85},
        "frase_impacto": ({"texto": frase_impacto, "destaque": frase_destaque, "animacao": gancho_animacao or "bloco",
                           "duracao_s": max(2.6, 1.6 + 0.12 * len(frase_impacto.split())) if gancho_animacao == "palavra" else 2.6} if frase_impacto else None),
        "tela_final": (({"ativo": True, "duracao_s": 3.0, "titulo": ser.get("titulo") or tela_titulo, "destaque": ser.get("destaque", ""), "cta": ser.get("handle") or tela_cta, "marca": tela_marca,
                         "selo": f"Parte {int(parte)}" if parte else (ser.get("kicker") or ser.get("nome", "")), "chamada": ser.get("chamada", ""), "ondas": True} if ser else
                        {"ativo": True, "duracao_s": 3.0, "titulo": tela_titulo, "destaque": tela_destaque, "cta": tela_cta, "marca": tela_marca}) if tela_final else None),
        "vinheta": ({"ativo": True, "duracao_s": max(0.6, min(2.5, float(vinheta_s))), "titulo": vinheta_titulo, "destaque": vinheta_destaque} if vinheta else None),
        "terco": ({"texto": terco_texto, "sub": terco_sub or "", "inicio_s": max(0.0, float(terco_inicio_s)), "duracao_s": max(1.5, float(terco_s))} if terco_texto else None),
        "estilo": {"cor_destaque": est.get("cor_destaque", "#F79615"), "cor_fundo": est.get("contorno", "#000921"), "cor_texto": est.get("cor_texto", "#FFFFFF"),
                   "fonte_titulo": "InterGS", "fonte_texto": "InterGS"},
        "palavras_chave": chaves, "capitulos": caps, "barra_progresso": bool(barra_progresso), "broll": brolls, "sfx": efeitos, "ritmo_zoom_s": float(ritmo_zoom_s or 0),
        "grafismos": graf_itens, "layout": lay_cfg, "camera": cam_cfg,
    }
    if fundo:
        props["video_fundo"] = fundo.name
    cin = legenda_cinetica_props(est, pal, formato, W, H, legenda_ass=legenda_ass)
    if cin:
        props["legenda_cinetica"] = cin
    bruto = pub / f"{rid}-remotion.mp4"
    proj = None
    if not previa:  # projeto editável (12/11/2026): props + mídias desta montagem, para o editor manual do app e o CapCut fiel
        try:
            proj = salvar_projeto(caminho_saida(saida_video), props, pub, rid, legenda_ass=legenda_ass, crf=crf, trilha=trilha, trilha_volume_db=trilha_volume_db, formato=formato,
                                  edl_json=edl_json, legenda_estilo={"id": str(legenda_modelo or "").strip() or None, "legenda": est})
        except Exception:  # noqa: BLE001  (projeto é extra: nunca derruba a entrega)
            proj = None
    try:
        renderizar_remotion("Montagem", props, bruto)
    finally:
        link.unlink(missing_ok=True)
        for l in links_extra:
            l.unlink(missing_ok=True)
    out = caminho_saida(saida_video)
    trechos, trilha_usada, aviso_trilha = _acabar_montagem(bruto, out, legenda_ass, graf_itens, crf, previa, trilha, trilha_volume_db, pub, rid)
    o = info_midia(out)
    extra_previa = {"previa": True, "resolucao": f"{o['largura']}x{o['altura']}", "tempo_s": round(time.monotonic() - t0, 1)} if previa else {}
    return extra_previa | {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "tamanho_mb": o["tamanho_mb"],
            "zoom": bool(zoom), "clarao_em": cortes, "frase_impacto": bool(frase_impacto), "tela_final": bool(tela_final), "vinheta_s": (props["vinheta"] or {}).get("duracao_s", 0),
            "terco": bool(terco_texto), "legenda_queimada": bool(legenda_ass),
            "nivel_pro": {"palavras_chave": [k["texto"] for k in chaves], "capitulos": len(caps), "broll": len(brolls), "sfx": len(efeitos), "barra_progresso": bool(barra_progresso), "ritmo_zoom_s": float(ritmo_zoom_s or 0),
                          "broll_auto": broll_auto_info, "gancho_animacao": (props["frase_impacto"] or {}).get("animacao"), "trilha": trilha_usada, "aviso_trilha": aviso_trilha},
            "grafismos": {"origem": graf_origem, "n": len([g for g in graf_itens if g["tipo"] != "serie"]), "tipos": sorted({g["tipo"] for g in graf_itens}),
                          "tela_cheia": trechos, "serie": (ser or {}).get("slug"), "parte": int(parte or 0) or None, "avisos": graf_avisos},
            "layout": lay_info, "transicoes": cam_info, "projeto": str(proj) if proj else None,
            "legenda_cinetica": ({"animacao": cin["animacao"], "tremor": cin["tremor"], "n_linhas": len(cin["linhas"])} if cin else None),
            "aviso_legenda": ("legenda_ass veio junto: a legenda cinética do estilo não entrou (a ASS externa manda; para a cinética, chame sem legenda_ass)"
                              if (legenda_ass and str(est.get("animacao") or "").lower() in CINETICAS) else None),
            "aviso": ("a vinheta atrasa o vídeo em %.1f s: gere a legenda com o palavras.json deslocado ou passe a legenda depois (montar) — os tempos do SRT original não batem mais" % props["vinheta"]["duracao_s"]) if (props["vinheta"] and legenda_ass) else None}


def _acabar_montagem(bruto, out, legenda_ass, graf_itens, crf, previa, trilha, trilha_volume_db, pub, rid):
    """Depois do Remotion: legenda ASS queimada (some onde o gráfico ocupa a tela), compressão final e trilha com ducking. Devolve (trechos, trilha_usada, aviso)."""
    from . import nivel_pro, grafismos as grf
    vf = []
    ass_tmp = None
    trechos = grf.trechos_tela_cheia(graf_itens)
    if legenda_ass and trechos:  # a legenda some onde o gráfico ocupa a tela
        ass_tmp = pub / f"{rid}-sem-tela-cheia.ass"; grf.ass_sem_trechos(caminho(legenda_ass), trechos, ass_tmp); legenda_ass = str(ass_tmp)
    if legenda_ass:
        fd = RAIZ / "fontes"
        esc = lambda s: str(s).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf.append(f"subtitles='{esc(caminho(legenda_ass))}':fontsdir='{esc(fd)}'")
    cmd2 = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", str(bruto)]
    if vf:
        cmd2 += ["-vf", ",".join(vf)]
    cmd2 += ["-c:v", "libx264", "-preset", "veryfast" if previa else PRESET_FINAL, "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    try:
        rodar(cmd2)
    finally:
        bruto.unlink(missing_ok=True)
        if ass_tmp:
            ass_tmp.unlink(missing_ok=True)
    trilha_usada = None; aviso_trilha = None
    if trilha:
        arq_t = nivel_pro.escolher_trilha(RAIZ / "trilhas") if str(trilha).strip().lower() == "auto" else caminho(trilha)
        if arq_t:
            from .longos import adicionar_trilha
            tmp_t = out.with_name(out.stem + ".trilha" + out.suffix)
            adicionar_trilha(out, arq_t, tmp_t, volume_db=trilha_volume_db, ducking=True); tmp_t.replace(out); trilha_usada = Path(arq_t).name
        else:
            aviso_trilha = "trilhas/ está vazia: o vídeo saiu só com a voz (vai em Pendências)."
    return trechos, trilha_usada, aviso_trilha


def pasta_projeto(video_final) -> Path:
    v = Path(video_final); return v.parent / "_projeto" / v.stem


def salvar_projeto(video_final, props, pub, rid, legenda_ass=None, crf=20, trilha="", trilha_volume_db=None, formato="9x16", edl_json=None, legenda_estilo=None):
    """Guarda ao lado da entrega (saida/<slug>/_projeto/<final>/) as props da Montagem e as mídias que ela usa (hardlink de public/render/<rid>*),
    a legenda ASS e os parâmetros do acabamento. O editor manual lê e regrava isto; `rerenderizar_projeto` refaz o vídeo a partir daqui.
    Fase 2 do editor (12/11/2026): com `edl_json`, guarda a referência do bruto (`edl.bruto`), os trechos mantidos (`edl.manter`, tempo do bruto)
    e uma cópia das palavras do bruto (palavras_bruto.json), para aparar/mover cortes recortando de novo; `legenda_estilo` = bloco `legenda` usado."""
    d = pasta_projeto(video_final); m = d / "midia" / "render"; m.mkdir(parents=True, exist_ok=True)
    for f in pub.glob(f"{rid}*"):
        if f.is_file() and not f.name.endswith("-remotion.mp4"):
            alvo = m / f.name
            if not alvo.exists():
                try:
                    os.link(f, alvo)
                except OSError:
                    shutil.copy2(f, alvo)
    if legenda_ass and Path(caminho(legenda_ass)).exists():
        shutil.copy2(caminho(legenda_ass), d / "legenda.ass")
    tr = None
    if trilha and str(trilha).strip().lower() == "auto":   # 12/11/2026: a trilha "auto" fica registrada (a mesma que _acabar_montagem escolhe), para o CapCut fiel
        from . import nivel_pro
        arq_auto = nivel_pro.escolher_trilha(RAIZ / "trilhas"); tr = str(arq_auto) if arq_auto else None
    elif trilha:
        try:
            tr = str(caminho(trilha))
        except Exception:  # noqa: BLE001
            tr = None
    proj = {"versao": 1, "criado": time.strftime("%Y-%m-%dT%H:%M:%S"), "composicao": "Montagem", "video_final": Path(video_final).name, "formato": formato,
            "acabamento": {"crf": crf, "legenda": (d / "legenda.ass").exists(), "trilha": tr, "trilha_volume_db": trilha_volume_db}, "props": props}
    if legenda_estilo:
        proj["legenda_estilo"] = legenda_estilo
    if edl_json:
        try:
            edl = ler_json(edl_json); pb = edl.get("palavras_json")
            if pb and Path(pb).exists():
                shutil.copy2(pb, d / "palavras_bruto.json")
            proj["edl"] = {"bruto": str(Path(edl["origem"])) if edl.get("origem") else None, "duracao_bruto_s": edl.get("duracao_original_s"),
                           "palavras": "palavras_bruto.json" if (d / "palavras_bruto.json").exists() else None,
                           "manter": [{"id": i, "inicio": float(m["inicio"]), "fim": float(m["fim"])} for i, m in enumerate(edl.get("manter") or [])]}
        except Exception:  # noqa: BLE001  (sem EDL o projeto continua editável, só não apara cortes)
            pass
    (d / "projeto.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def ligar_midia_projeto(d) -> list:
    """Põe as mídias do projeto salvo em public/render (hardlink) para o Remotion achar; devolve o que foi criado (para apagar depois)."""
    pub = REMOTION / "public" / "render"; pub.mkdir(parents=True, exist_ok=True); links = []
    for f in (Path(d) / "midia" / "render").iterdir():
        alvo = pub / f.name
        if not alvo.exists():
            try:
                os.link(f, alvo)
            except OSError:
                shutil.copy2(f, alvo)
            links.append(alvo)
    return links


def rerenderizar_projeto(pasta, saida_video, props=None, previa=False):
    """Refaz a entrega a partir de um projeto salvo (props editadas pelo editor manual, se vierem). As mídias voltam para public/render com os nomes
    que as props citam; o acabamento (legenda, compressão, trilha) é o mesmo da montagem original."""
    t0 = time.monotonic(); d = Path(pasta); proj = json.loads((d / "projeto.json").read_text(encoding="utf-8"))
    props = props or proj["props"]; ac = proj.get("acabamento") or {}
    pub = REMOTION / "public" / "render"; pub.mkdir(parents=True, exist_ok=True)
    rid = uuid.uuid4().hex[:10]; links = ligar_midia_projeto(d)
    bruto = pub / f"{rid}-remotion.mp4"
    try:
        renderizar_remotion("Montagem", props if not previa else {**props}, bruto)
    finally:
        for l in links:
            l.unlink(missing_ok=True)
    out = caminho_saida(saida_video)
    leg = str(d / "legenda.ass") if (d / "legenda.ass").exists() else None
    _acabar_montagem(bruto, out, leg, props.get("grafismos") or [], ac.get("crf", 20), previa, ac.get("trilha") or "", ac.get("trilha_volume_db"), pub, rid)
    o = info_midia(out)
    return {"video": str(out), "duracao_s": o["duracao_s"], "largura": o["largura"], "altura": o["altura"], "tempo_s": round(time.monotonic() - t0, 1)}


def _layout(layout, tela, focos, passos, rosto_recortado, cortina, v, edl_json, pal, duracao_s, pub, rid, composto=None):
    """Prepara a fase C para o Remotion: tela cortada como o rosto e linkada em public/render, blocos, focos, passos, recorte e cortinas.
    Devolve (cfg para as props, resumo para o resultado, arquivos a apagar depois do render)."""
    from . import layouts as lay
    from .cortes import aplicar_cortes
    extra, avisos = [], []
    tela_info = None; tela_nome = None; tela_src = None
    if tela:
        tela_src = caminho(tela); it = info_midia(tela_src)
        edl = ler_json(edl_json) if edl_json else None
        if edl and lay.tela_cobre_edl(edl, it["duracao_s"]):
            cortada = pub / f"{rid}-tela-cortada.mp4"
            aplicar_cortes(tela_src, edl_json, cortada); extra.append(cortada); tela_src = cortada; it = info_midia(cortada)
            avisos.append("tela recebeu os mesmos cortes do rosto (EDL)")
        elif edl:
            avisos.append("a tela não cobre o bruto todo: entrou sem cortes, alinhada no início (confira a sincronia)")
        alvo = pub / f"{rid}-tela{tela_src.suffix.lower()}"
        try:
            os.link(tela_src, alvo)
        except OSError:
            shutil.copy2(tela_src, alvo)
        extra.append(alvo); tela_nome = alvo.name; tela_info = it
    tem_aula = "aula" in str(layout)
    recorte_nome = None; recorte_info = None
    if tem_aula and tela and str(rosto_recortado).lower() not in ("false", "0", "nao", "não", ""):
        alvo = pub / f"{rid}-rosto.webm"
        recorte_info = lay.recortar_rosto(v, alvo); extra.append(alvo); recorte_nome = alvo.name
    blocos, av = lay.blocos_de(layout, duracao_s, tem_tela=bool(tela_nome), tem_recorte=bool(recorte_nome)); avisos += av
    usa_tela = any(b["modo"] in lay.PRECISA_TELA for b in blocos)
    focos_lista, focos_origem = [], None
    if usa_tela:
        if not focos or str(focos).strip().lower() == "auto":  # sem focos do agente, a câmera virtual segue as mudanças da tela
            focos_lista, resumo = lay.focos_auto(tela_src, limite_s=duracao_s); focos_origem = f"auto ({resumo['focos']} de {resumo['mudancas']} mudanças na tela)"
        else:
            focos_lista, av = lay.focos_de(focos, pal, duracao_s); avisos += av; focos_origem = "plano do agente"
    passos_lista, av = lay.passos_de(passos, pal, duracao_s) if passos else ([], []); avisos += av
    cortinas = lay.cortinas_de(blocos) if cortina else []
    cfg = {"blocos": blocos, "cortinas_s": cortinas, "focos": focos_lista, "passos": passos_lista}
    if tela_nome:
        cfg |= {"tela": tela_nome, "tela_largura": tela_info["largura"], "tela_altura": tela_info["altura"]}
    if recorte_nome:
        cfg["rosto_recortado"] = recorte_nome
    rosto_pos = None
    comp_info = None
    if any(b["modo"] == "composto" for b in blocos):
        comp = composto if composto is not None else lay.detectar_composto(v)
        iv = info_midia(v)
        if comp:
            cfg |= {"composto": comp, "rosto_largura": iv["largura"], "rosto_altura": iv["altura"]}
            comp_info = {"divisor": comp["divisor"], "compostos_s": comp["compostos_s"], "trechos": len(comp["trechos"]), "rosto_baixo": comp["rosto_baixo"], "rosto_cima": comp["rosto_cima"]}
            if not any(t["composto"] for t in comp["trechos"]):
                avisos.append("composto: nenhum trecho com tela em cima; no 16:9 o rosto fica na coluna da direita e a esquerda é painel marinho (planeje grafismos)")
        else:
            avisos.append("composto: o vídeo não é vertical com tela em cima e rosto embaixo (sem rosto ou sem linha divisória); ficou 'cheio'")
            for b in blocos:
                if b["modo"] == "composto":
                    b["modo"] = "cheio"
    if any(b["modo"] in ("painel", "tutorial", "moldura") or (b["modo"] == "aula" and not recorte_nome) for b in blocos):
        rosto_pos = lay.posicao_rosto(v)  # enquadra a caixa do rosto onde ele está (não no centro fixo)
        if rosto_pos:
            iv = info_midia(v); cfg |= {"rosto_pos": {"x": rosto_pos["x"], "y": rosto_pos["y"]}, "rosto_largura": iv["largura"], "rosto_altura": iv["altura"]}
        else:
            avisos.append("rosto não achado no vídeo: as caixas de rosto usam o enquadramento padrão (confira se a cabeça não ficou cortada)")
    t_tut = sum(b["fim"] - b["inicio"] for b in blocos if b["modo"] == "tutorial")
    if t_tut > duracao_s * 0.5:
        avisos.append("mais da metade é tutorial: gere a legenda com posicao 'centro' para ela cair na linha laranja do meio")
    resumo = {"blocos": [f"{b['modo']}@{b['inicio']}" for b in blocos], "cortinas": len(cortinas), "focos": len(focos_lista), "focos_origem": focos_origem,
              "passos": [p["texto"] for p in passos_lista], "rosto_recortado": bool(recorte_nome), "rosto_pos": rosto_pos and {"x": rosto_pos["x"], "y": rosto_pos["y"]}, "recorte": recorte_info and {k: recorte_info[k] for k in ("largura", "altura", "quadros")},
              "composto": comp_info, "avisos": avisos}
    return cfg, resumo, extra


def _broll_auto(v, chaves, duracao_s, pub, rid, passo_s=1.5):
    """Amostra o vídeo a cada passo_s (320 px), marca onde há rosto e, pelas regras de nivel_pro.broll_auto, extrai em resolução cheia os quadros de tela
    que viram cutaway. Devolve (lista para o Remotion, resumo para o resultado)."""
    import tempfile
    import numpy as np
    from PIL import Image
    from . import nivel_pro, rosto as _rosto
    det, nome = _rosto._detector()
    if nome == "nenhum":
        return [], {"n": 0, "motivo": "sem detector de rosto"}
    with tempfile.TemporaryDirectory() as td:
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", str(v), "-vf", f"fps=1/{passo_s},scale=320:-2", "-q:v", "4", f"{td}/a%04d.jpg"])
        amostras = [(i * passo_s, det(np.asarray(Image.open(f).convert("RGB"))) is not None) for i, f in enumerate(sorted(Path(td).glob("a*.jpg")))]
    plano = nivel_pro.broll_auto(amostras, chaves, duracao_s)
    out = []; usados = []; descartados = []

    def miniatura(arq):
        return np.asarray(Image.open(arq).convert("L").resize((32, 32)), dtype=np.float32)
    for i, b in enumerate(plano):
        alvo = pub / f"{rid}-ba{i}.jpg"; plano_alvo = pub / f"{rid}-bx{i}.jpg"
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-ss", str(b["fonte_t"]), "-i", str(v), "-frames:v", "1", "-q:v", "2", str(alvo)])
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-ss", str(b["inicio"] + b["duracao_s"] / 2), "-i", str(v), "-frames:v", "1", "-vf", "scale=320:-2", str(plano_alvo)])
        # travas (03/11): rosto no quadro em resolução cheia = falha do detector na amostra; quadro parecido com o plano em que entra = cutaway sem efeito
        com_rosto = det(np.asarray(Image.open(alvo).convert("RGB"))) is not None
        diferenca = float(np.abs(miniatura(alvo) - miniatura(plano_alvo)).mean())
        plano_alvo.unlink(missing_ok=True)
        if com_rosto or diferenca < 22:
            alvo.unlink(missing_ok=True); descartados.append({"quadro_de": b["fonte_t"], "motivo": "rosto no quadro" if com_rosto else f"parecido com o plano ({diferenca:.0f})"}); continue
        out.append({"arquivo": alvo.name, "inicio": b["inicio"], "duracao_s": b["duracao_s"], "modo": b["modo"], "_pronto": True}); usados.append(b)
    tela = sum(1 for _, r in amostras if not r)
    return out, {"n": len(out), "amostras": len(amostras), "amostras_tela": tela, "detector": nome, "quadros_de": [b["fonte_t"] for b in usados], "em": [b["inicio"] for b in usados],
                 "descartados": descartados,
                 "motivo": None if out else ("vídeo sem trechos de tela" if tela == 0 else "vídeo só de tela" if tela == len(amostras) else "quadros descartados pelas travas" if descartados else "sem trecho de tela firme ou sem momento livre com rosto")}


def gerar_capa(video, saida_png, texto, destaque="", instante_s=None, estilo=None, formato="9x16", posicao="auto", imagem=None):
    """posicao: auto (longe do rosto) | baixo | topo. Com `imagem` (foto real ou print), a capa usa essa imagem em vez de um quadro do vídeo
    (serve para vídeo feito só de slides tipográficos, em que o quadro cobriria o texto do próprio slide)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
    W, H = (1080, 1920) if formato == "9x16" else (1920, 1080)
    tmp = caminho_saida(str(Path(saida_png).with_suffix(".quadro.png")))
    if imagem:
        t = None; ImageOps.fit(Image.open(caminho(imagem)).convert("RGB"), (W, H), method=Image.LANCZOS).save(tmp)
    else:
        v = caminho(video); info = info_midia(v)
        t = float(instante_s) if instante_s is not None else min(1.0, info["duracao_s"] / 2)
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-ss", str(t), "-i", v, "-frames:v", "1", "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", str(tmp)])
    est = (estilo or {}).get("legenda", estilo or {})
    cor_dest = est.get("cor_destaque", "#F79615"); cor_txt = est.get("cor_texto", "#FFFFFF"); cor_fundo = est.get("contorno", "#000921")
    im = Image.open(tmp).convert("RGB")
    rosto_y = None
    if posicao == "auto":
        try:
            from . import rosto as _rosto
            import numpy as _np
            det, _ = _rosto._detector(); r = det(_np.asarray(im))
            rosto_y = (r[1] / H) if r else None
        except Exception:
            rosto_y = None
        posicao = "topo" if (rosto_y is not None and rosto_y > 0.55) else "baixo"
    # faixa escura no lado do texto
    grad = Image.new("L", (1, H))
    for y in range(H):
        f = (y - H * 0.45) / (H * 0.55) if posicao == "baixo" else (H * 0.55 - y) / (H * 0.55)
        grad.putpixel((0, y), int(255 * max(0.0, f) ** 1.2 * 0.85))
    sombra = Image.new("RGB", (W, H), cor_fundo); im = Image.composite(sombra, im, grad.resize((W, H)))
    d = ImageDraw.Draw(im)
    tam = int(W * (0.11 if formato == "9x16" else 0.075))
    fonte = ImageFont.truetype(str(RAIZ / "fontes" / "Inter-ExtraBold.ttf"), tam)
    palavras = texto.upper().split(); linhas, atual = [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=fonte) > W * 0.86 and atual:
            linhas.append(atual); atual = p
        else:
            atual = teste
    if atual: linhas.append(atual)
    y = (H - int(H * 0.09) - len(linhas) * int(tam * 1.12)) if posicao == "baixo" else int(H * 0.07)
    for linha in linhas:
        x = int(W * 0.07); 
        for p in linha.split(" "):
            cor = cor_dest if destaque and p.lower().strip(".,!?") == destaque.lower() else cor_txt
            d.text((x, y), p, font=fonte, fill=cor, stroke_width=max(2, tam // 18), stroke_fill=cor_fundo)
            x += int(d.textlength(p + " ", font=fonte))
        y += int(tam * 1.12)
    out = caminho_saida(saida_png); im.save(out, quality=92); tmp.unlink(missing_ok=True)
    return {"capa": str(out), "instante_s": t, "imagem": str(caminho(imagem)) if imagem else None, "linhas": linhas, "largura": W, "altura": H, "posicao": posicao, "rosto_y": rosto_y}
