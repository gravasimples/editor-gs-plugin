"""MCP editor-de-video: ferramentas de edição do Editor GS. Só grava fora de entrada/."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server.fastmcp import FastMCP
from editor_video import grafismos as grf
from editor_video import layouts as lay
from editor_video import repertorio as rep, garimpo
from editor_video import transcricao, silencios, cortes, legenda, montagem, sincronia, acabamento, longos, rosto, capcut, revisao, imagem, canva, depoimentos, voz, apostila, banco
from editor_video import diff_versoes, folha_contato as folha
from editor_video.util import ler_json, info_midia, ErroFerramenta, finalizar_audio

mcp = FastMCP("editor-de-video")
ESTILOS_DIR = Path(os.environ.get("EDITOR_GS_ESTILOS", Path(__file__).resolve().parents[2] / "estilos"))


def _ok(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ErroFerramenta as e:
        return {"erro": str(e)}
    except Exception as e:  # noqa
        return {"erro": f"{type(e).__name__}: {e}"}


def _final(res, saida):
    """Fase A (07/11/2026): toda entrega de vídeo sai no volume de rede social (−16 LUFS, pico −1,5 dBTP; util.finalizar_audio). O resultado ganha
    `audio_final` com as medidas. EDITOR_GS_AUDIO_FINAL=0 desliga. Falha aqui não derruba a entrega: vira aviso em `audio_final`."""
    if not isinstance(res, dict) or res.get("erro") or os.environ.get("EDITOR_GS_AUDIO_FINAL", "1") == "0":
        return res
    alvo = res.get("video") if isinstance(res.get("video"), str) and Path(res["video"]).exists() else saida
    if not alvo or not Path(alvo).exists() or Path(alvo).suffix.lower() not in (".mp4", ".mov", ".m4v", ".webm"):
        return res
    try:
        res["audio_final"] = finalizar_audio(alvo)
    except Exception as e:  # noqa: BLE001
        res["audio_final"] = {"feito": False, "aviso": f"{type(e).__name__}: {e}"}
    return res


def _estilo(nome_ou_caminho):
    """Nome em estilos/, caminho .json, ou JSON inline com ajustes por cima de uma base (02/11/2026, para vídeos fora da paleta da marca):
    '{"base": "profissional", "legenda": {"cor_destaque": "#F4C2D7", "cor_texto": "#FFF8F0", "contorno": "#3A2A33"}, "montagem": {"sfx": false}}'.
    "legenda_modelo": "<id>" aplica um modelo de legenda da biblioteca (estilos/legendas/: karaoke-pop, caixa-marinho, palavra-unica, digitar, serifada-historia…)."""
    t = str(nome_ou_caminho or "padrao").strip()
    if t.startswith("{"):
        import json as _json
        sobre = _json.loads(t); base = _estilo(sobre.pop("base", "padrao") or "padrao")
        modelo = sobre.pop("legenda_modelo", None)  # modelo da biblioteca (estilos/legendas/<id>.json), página Estilos 03/11/2026
        if modelo:
            base["legenda"] = {**base.get("legenda", {}), **ler_json(ESTILOS_DIR / "legendas" / f"{modelo}.json")["legenda"]}
        for k, v in sobre.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k] = {**base[k], **v}
            else:
                base[k] = v
        base["nome"] = f"{base.get('nome', 'padrao')}+ajustes"
        return base
    p = Path(t)
    if not p.suffix:
        p = ESTILOS_DIR / f"{t}.json"
    return ler_json(p)


@mcp.tool()
def info(midia: str) -> dict:
    """Dados de um vídeo ou áudio: duração, resolução, fps, codecs, se tem áudio, tamanho."""
    return _ok(info_midia, midia)


@mcp.tool()
def transcrever(midia: str, saida_json: str, modelo: str = "small", device: str = "auto", idioma: str = "pt", vad: bool = True, saida_srt: str = "") -> dict:
    """Transcreve com faster-whisper e grava palavras com início, fim e confiança em saida_json (e SRT opcional). Recusa áudio em silêncio digital."""
    return _ok(transcricao.transcrever, midia, saida_json, modelo=modelo, device=device, idioma=idioma, vad=vad, saida_srt=saida_srt or None)


@mcp.tool()
def detectar_silencios(midia: str, limiar_db: float = -35.0, min_s: float = 0.35) -> dict:
    """Lista os silêncios (ffmpeg silencedetect) com início, fim e duração, mais nível de áudio e fração de silêncio."""
    return _ok(silencios.detectar_silencios, midia, limiar_db=limiar_db, min_s=min_s)


@mcp.tool()
def propor_cortes(palavras_json: str, saida_edl: str, min_pausa_s: float = 0.3, margem_s: float = 0.08, max_remocao: float = 0.25,
                  remover_repeticoes: bool = True, janela_repeticao_s: float = 15.0, remover_vicios: bool = True, modo: str = "normal",
                  pausa_max_audio_s: float = -1) -> dict:
    """Gera a EDL (trechos a manter e removidos com motivo: pausa, refação, vício) a partir da transcrição. modo: normal | dinamico | bem_dinamico. Marca precisa_aprovacao quando remove mais que max_remocao.
    Também mede o silêncio no áudio e encurta pausas que o Whisper escondeu dentro das palavras (padrão por modo: 0,5 / 0,3 / 0,22 s; pausa_max_audio_s=0 desliga, -1 usa o padrão)."""
    return _ok(cortes.propor_cortes, palavras_json, saida_edl, min_pausa_s=min_pausa_s, margem_s=margem_s, max_remocao=max_remocao,
               remover_repeticoes=remover_repeticoes, janela_repeticao_s=janela_repeticao_s, remover_vicios=remover_vicios, modo=modo,
               pausa_max_audio_s=None if pausa_max_audio_s is None or pausa_max_audio_s < 0 else pausa_max_audio_s)


@mcp.tool()
def ajustar_edl(edl_json: str, saida_edl: str, manter_extra: list[list[float]] | None = None, remover_extra: list[list[float]] | None = None, motivo: str = "ajuste do editor") -> dict:
    """Ajusta uma EDL antes de aplicar: manter_extra devolve trechos [[inicio, fim], ...] (tempo do vídeo original) que tinham sido removidos; remover_extra tira trechos que estavam mantidos (ex.: uma refação que a regra não pegou). Recalcula duração e aprovação."""
    return _ok(cortes.ajustar_edl, edl_json, saida_edl, manter_extra=manter_extra, remover_extra=remover_extra, motivo=motivo)


@mcp.tool()
def aplicar_cortes(video: str, edl_json: str, saida_video: str, saida_palavras: str = "", crf: int = 18) -> dict:
    """Aplica a EDL com cortes secos (ffmpeg trim/concat) e, se pedido, grava a transcrição com tempos remapeados em saida_palavras."""
    return _ok(cortes.aplicar_cortes, video, edl_json, saida_video, saida_palavras=saida_palavras or None, crf=crf)


@mcp.tool()
def gerar_legenda(palavras_json: str, saida_ass: str, estilo: str = "padrao", formato: str = "9x16", saida_srt: str = "", max_palavras: int = 0) -> dict:
    """Gera legenda ASS (karaokê por palavra ou simples) no estilo (nome em estilos/ ou caminho .json) e SRT opcional. formato: 9x16 | 16x9 | 1x1."""
    try:
        est = _estilo(estilo)
    except Exception as e:
        return {"erro": f"estilo não encontrado: {e}"}
    return _ok(legenda.gerar_legenda, palavras_json, saida_ass, est, formato=formato, saida_srt=saida_srt or None, max_palavras=max_palavras or None)


@mcp.tool()
def legenda_de_srt(srt: str, saida_ass: str, estilo: str = "padrao", formato: str = "9x16", max_chars: int = 0) -> dict:
    """Legenda ASS no estilo da marca a partir de um SRT já traduzido ou revisado (um evento por bloco, sem karaokê; `*palavra*` no SRT vira destaque laranja).
    Quebra cada bloco em até duas linhas (22 caracteres no 9x16, 38 no 16x9); `blocos_longos` > 0 pede para dividir o bloco no SRT. formato: 9x16 | 16x9 | 1x1."""
    try:
        est = _estilo(estilo)
    except Exception as e:
        return {"erro": f"estilo não encontrado: {e}"}
    return _ok(legenda.legenda_de_srt, srt, saida_ass, est, formato=formato, max_chars=max_chars or None)


@mcp.tool()
def montar(video: str, saida_video: str, formato: str = "9x16", legenda_ass: str = "", resolucao: str = "1080p", fps: int = 30, crf: int = 20,
           enquadramento: str = "auto", previa: bool = False) -> dict:
    """Reenquadra e exporta MP4 H.264 com a legenda ASS queimada. enquadramento: auto (fundo desfocado quando a orientação muda, senão crop central) | centro | bordas | desfocado. formato 9x16 | 16x9 | 1x1; resolucao 720p | 1080p.
    previa=True (10/11/2026): render barato em 720p para `<saida>_previa.mp4` (mesmos parâmetros, crf alto), para a pessoa aprovar antes do 1080p; o resultado traz `previa`, `resolucao` e `tempo_s`."""
    return _final(_ok(montagem.montar, video, saida_video, formato=formato, legenda_ass=legenda_ass or None, resolucao=resolucao, fps=fps, crf=crf,
               enquadramento=enquadramento, previa=previa), saida_video)


@mcp.tool()
def montar_remotion(video: str, saida_video: str, palavras_json: str = "", edl_json: str = "", formato: str = "9x16", resolucao: str = "1080p", estilo: str = "padrao",
                    zoom: bool = True, zoom_fator: float = 1.08, clarao: bool = True, frase_impacto: str = "", frase_destaque: str = "", tela_final: bool = True,
                    tela_titulo: str = "Aprenda a gravar de forma simples", tela_destaque: str = "simples", tela_cta: str = "Siga o perfil", legenda_ass: str = "",
                    vinheta: bool = False, vinheta_s: float = 1.0, vinheta_titulo: str = "Grava Simples", vinheta_destaque: str = "Simples",
                    terco_texto: str = "", terco_sub: str = "", terco_inicio_s: float = 1.0, terco_s: float = 4.0,
                    palavras_chave: str = "", capitulos: str = "", barra_progresso: bool = False, broll: str = "", sfx: bool = False, ritmo_zoom_s: float = 0.0,
                    gancho_animacao: str = "", trilha: str = "", grafismos: str = "", serie: str = "", parte: int = 0,
                    layout: str = "", tela: str = "", focos: str = "", passos: str = "", rosto_recortado: str = "auto", cortina: bool = True,
                    transicoes: str = "", energia: str = "", receita_transicoes: str = "", previa: bool = False,
                    legenda_modelo: str = "", legenda_tremor: bool | None = None) -> dict:
    """LEGENDA CINÉTICA (10/11/2026, GSAP): legenda_modelo="cinetica-tipografica" | "cinetica-maquina" | "cinetica-onda" desenha a legenda no Remotion palavra por palavra
    a partir do palavras_json (sem gerar ASS; com legenda_ass, a ASS vence e sai aviso); legenda_tremor=True sacode a palavra de ênfase de cada linha (CustomWiggle).
    Resultado traz `legenda_cinetica` (animacao, tremor, n_linhas). Só use quando o pedido ou o estilo pedir legenda cinética; o `legenda.srt` da entrega continua vindo de `gerar_legenda`.
    PRÉVIA (10/11/2026): previa=True renderiza a mesma montagem em 720p e crf alto para `<saida>_previa.mp4` (rápido e leve) e devolve `previa`, `resolucao` e `tempo_s`;
    mostre à pessoa, espere o OK e só então rode de novo sem `previa` para o 1080p. Nada mais muda entre a prévia e o final.
    NÍVEL PROFISSIONAL (estilos `profissional` e `lista` ligam por padrão; qualquer estilo aceita os parâmetros): palavras_chave="auto" põe na tela, animada e sincronizada com a fala, a palavra que importa em cada frase (números, OBS, webcam, erro, grátis…; regras, sem modelo) ou JSON [{"texto","inicio","fim"}] para escolher você; capitulos="Áudio@0; Luz@12.5; Câmera@30" (texto@segundo no vídeo cortado) mostra a pílula "1/3 · Áudio" por 2,6 s em cada troca de assunto (obrigatório em lista/"3 erros"); barra_progresso=True (linha laranja crescendo na base); broll="materiais/print.png@8@3@janela; takes/obs.mp4@20@4@cheio" (arquivo@inicio@duração[@janela|cheio]: cutaway com zoom lento; imagem ou vídeo; use materiais reais do Drive/`buscar_material`, prints do OBS ou `extrair_quadros`); sfx=True mistura whoosh nos cortes, pop nas palavras-chave e ding na tela final (baixo volume); ritmo_zoom_s=4 alterna o enquadramento a cada 4 s (pattern interrupt) mesmo em frase longa. Resultado traz `nivel_pro` com o que entrou.
    Montagem com acabamento (Remotion): zoom alternado por frase (usa segmentos do palavras_json do vídeo cortado), clarão branco em cada ponto de corte (usa edl_json), frase de impacto no começo, tela final animada com CTA, e legenda ASS queimada no fim. Use o vídeo já cortado. Mais lento que `montar` (render por quadro). Animações de marca: vinheta=True abre com cartão marinho "Grava Simples" + barra laranja (vinheta_s, padrão 1 s; o vídeo e o áudio começam depois dela, então gere a legenda depois ou passe legenda_ass só sem vinheta);
    terco_texto/terco_sub = terço inferior animado (ex.: "Thiago Gomes" / "Grava Simples · OBS") entre terco_inicio_s e terco_inicio_s+terco_s. Use nos vídeos com fala do Thiago; não nos só de slides.
    FASE 2 (estilos profissional e lista já ligam): broll="auto" = quadros do PRÓPRIO vídeo onde a câmera mostra a tela (sem rosto) viram janela de 2,5 s enquanto o Thiago fala
    (sem você escolher; confira `nivel_pro.broll_auto` no resultado; passe broll="" para desligar ou a lista manual para mandar); gancho_animacao="palavra" = frase de impacto entra palavra
    por palavra ("bloco" desliga); trilha="auto" = primeira trilha de trilhas/ com ducking, pasta vazia = só a voz e aviso em `nivel_pro.aviso_trilha` (vai em Pendências).
    FASE B — GRAFISMOS (07/11/2026): grafismos = caminho do grafismos.json que você escreveu com `planejar_grafismos` (recomendado em vídeo de fala) ou "auto" (regras);
    com grafismos, as palavras-chave por regra saem. serie="<nome>" + parte=N abre com o título da série palavra por palavra + selo "Parte N" e fecha com a cartela da série
    (crie com `salvar_serie`). Resultado traz `grafismos` (tipos, avisos, trechos de tela cheia onde a legenda some).
    FASE C — LAYOUTS (07/11/2026): layout = blocos ao longo do vídeo, trocados por uma cortina laranja: "painel@0; tutorial@6.5; cheio@20" (modo@segundo no vídeo cortado)
    ou um modo só para o vídeo todo. Modos: cheio | painel (terço de cima marinho, manchete/logos/kicker entram nele, rosto embaixo) | moldura (rosto em moldura
    arredondada com borda laranja; bom para CTA e fala de personagem) | tutorial (tela em cima com câmera virtual, rosto embaixo; legenda 'centro' cai na linha do meio)
    | tela (só a gravação de tela, voz por baixo) | aula (tela inteira + rosto recortado sem fundo no canto; horizontal ou vertical). tutorial/tela/aula pedem
    tela = gravação de tela do OBS (com edl_json, recebe os mesmos cortes quando cobre o bruto). focos = câmera virtual: "auto" (padrão: aproxima onde a tela muda
    pouco e localizado — menu, janela de propriedades) ou JSON [{"inicio" ou "palavra", "fim", "x", "y", "zoom", "caixa": [x, y, w, h]}] com x/y/caixa de 0 a 1
    na tela (caixa = contorno laranja no item clicado; veja os quadros com `extrair_quadros` para achar). passos = "Exposição@3; ISO@8; Branco@15" ou JSON
    [{"texto", "palavra"}] → barra fixa no alto com o passo atual aceso (tutoriais de 2–5 passos). rosto_recortado="auto" tira o fundo do rosto no bloco aula
    (~2 s de processamento por segundo de vídeo). cortina=False troca seco. Resultado traz `layout` (blocos, focos, passos, avisos).
    COMPOSTO (09/11/2026): no 16x9 de um bruto vertical já composto (gravação do OBS com a tela em cima e o rosto embaixo, como a série "O óbvio"),
    a ferramenta detecta sozinha a linha divisória e os trechos e monta tela à esquerda (inteira, 64%) + rosto à direita; no trecho só de rosto, o rosto
    continua na coluna da direita (plano médio) e a esquerda vira painel marinho onde os grafismos entram (planeje grafismos: sem eles o painel fica vazio).
    Sem composição detectada, o 16x9 segue com o vertical no meio e fundo desfocado. layout="composto" força (vídeo só de rosto = coluna + painel);
    layout="cheio" mantém o fundo desfocado. Confira `layout.composto` (divisor, compostos_s) no resultado e cite no Resumo.
    FASE E — TRANSIÇÕES (08/11/2026): transicoes="auto" (estilos profissional e lista já ligam) troca o zoom alternado + clarão igual em todo corte por uma
    gramática de corte: a maioria das emendas é seco com troca de enquadramento (aberto/médio/fechado), palavra de ênfase logo depois do corte ganha punch-in
    (às vezes tremor), troca de assunto (capítulo, tela cheia, kicker "1 · …", troca de bloco) ganha transição forte variada (zoom_blur, deslize, luz, giro;
    flash no máximo 2), nunca a mesma forte duas vezes seguidas, e a câmera anda devagar em todo plano. Para mandar numa emenda: JSON {"35.1": "giro"}
    (tipos: seco, punch, tremor, zoom_blur, deslize, luz, giro, flash). energia = calmo | normal | dinamico | bem_dinamico (siga o painel Estilo do criativo).
    Com sfx=True, cada tipo tem o seu som (forte = whoosh/swish/riser, punch = tick, seco = nada). transicoes="nenhuma" volta ao modo antigo.
    RECEITA (08/11/2026): a proporção dos tipos segue o repertório (padrão: fala com tela do Máquina lida do repertório; em 09/11 seco 51%, punch 24%, deslize 22%, zoom_blur 3%;
    giro e luz só se você mandar). receita_transicoes = o formato que você usou em `consultar_repertorio` (fala_tela, fala, anuncio, aula, animacao) para
    seguir aquele formato, JSON de pesos, ou "regras" para a gramática antiga. A energia ajusta a proporção de seco (calmo mais, bem_dinamico menos).
    Resultado traz `transicoes` (planos, por_tipo, receita)."""
    try:
        est = _estilo(estilo)
    except Exception as e:
        return {"erro": f"estilo não encontrado: {e}"}
    return _final(_ok(acabamento.montar_remotion, video, saida_video, palavras_json=palavras_json or None, edl_json=edl_json or None, formato=formato, resolucao=resolucao,
               estilo=est, zoom=zoom, zoom_fator=zoom_fator, clarao=clarao, frase_impacto=frase_impacto or None, frase_destaque=frase_destaque, tela_final=tela_final,
               tela_titulo=tela_titulo, tela_destaque=tela_destaque, tela_cta=tela_cta, legenda_ass=legenda_ass or None,
               vinheta=vinheta, vinheta_s=vinheta_s, vinheta_titulo=vinheta_titulo, vinheta_destaque=vinheta_destaque,
               terco_texto=terco_texto, terco_sub=terco_sub, terco_inicio_s=terco_inicio_s, terco_s=terco_s,
               palavras_chave=palavras_chave, capitulos=capitulos, barra_progresso=barra_progresso, broll=broll, sfx=sfx, ritmo_zoom_s=ritmo_zoom_s,
               gancho_animacao=gancho_animacao, trilha=trilha, grafismos=grafismos, serie=serie, parte=parte,
               layout=layout, tela=tela, focos=focos, passos=passos, rosto_recortado=rosto_recortado, cortina=cortina, transicoes=transicoes, energia=energia, receita_transicoes=receita_transicoes,
               previa=previa, legenda_modelo=legenda_modelo, legenda_tremor=legenda_tremor), saida_video)


@mcp.tool()
def planejar_grafismos(palavras_json: str, saida_json: str = "", gestos_json: str = "") -> dict:
    """FASE B: primeiro passo do plano de grafismos semântico (o jeito Máquina: o gráfico certo entra na palavra certa e some quando a ideia acaba).
    Devolve a fala em linhas "[ini–fim] frase", o catálogo de tipos e um rascunho por regras; se `saida_json`, grava o rascunho lá para você editar.
    GESTOS (10/11/2026): com gestos_json (saída de `detectar_gestos` no vídeo cortado), o rascunho ganha sugestões: polegar para cima → `checklist` (✓ no gesto),
    dedo apontando para cima → `kicker`, cabeça virada para a tela → `cutaways` em texto (candidatos a b-roll/bloco tutorial; nada entra sozinho na montagem).
    Qualquer item do plano aceita `gesto` no lugar de `palavra` (ex.: {"tipo": "checklist", "gesto": "polegar_cima"}); o plano guarda o caminho em "gestos".
    Como planejar: um grafismo no peito a cada 3–6 s; cada um ilustra a ideia da frase (não repete a legenda); use `palavra` para entrar exatamente quando ela é dita;
    ferramenta citada → `logos` (logos reais); enumeração → `pilulas`/`checklist` acumulando; "não precisa X" → `riscado` com `troca`; número/preço → `numero`
    (tela_cheia=true no momento-chave, 2–4 s, a voz segue por baixo); comparação ruim × bom → `cartoes` no topo; tema áudio → `ondas`; fim → `cta`.
    Nada de número de alunos, preço/oferta não aprovada ou escassez. Depois: `validar_grafismos` e `montar_remotion(grafismos=<arquivo>)`."""
    try:
        pal = ler_json(palavras_json)
        rasc = grf.plano_auto(pal, gestos=gestos_json or None)
        if saida_json:
            Path(saida_json).parent.mkdir(parents=True, exist_ok=True)
            Path(saida_json).write_text(json.dumps(rasc, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"fala": grf.frases(pal), "tipos": grf.TIPOS, "rascunho": rasc, "arquivo": saida_json or None,
                "gestos": ({"sugestoes": rasc.get("sugestoes", []), "cutaways": rasc.get("cutaways", []), "gatilho": "use \"gesto\": \"polegar_cima\" | \"apontar_cima\" | \"vitoria\" | \"mao_aberta\" | \"punho\" | \"virada_esquerda\" | \"virada_direita\" no item, no lugar de palavra"} if gestos_json else None),
                "formato": {"itens": [{"tipo": "manchete", "palavra": "caro", "inicio": 3.1, "fim": 5.4, "rotulo": "Áudio bom", "texto": "Não custa caro", "destaque": "caro", "ondas": True},
                                      {"tipo": "logos", "inicio": 8.0, "itens": [{"logo": "meet", "palavra": "meet"}, {"logo": "zoom", "palavra": "zoom"}]},
                                      {"tipo": "numero", "inicio": 24.0, "fim": 27.5, "tela_cheia": True, "antes": [{"texto": "R$ 500", "em": 24.2}], "rotulo": "até", "texto": "R$ 100", "icone": "mic"}]},
                "midia": "logo = nome da ferramenta (obs, meet, zoom, instagram, youtube, tiktok, whatsapp, drive…; ou arquivo em workspace/marca/logos/); icone = nome Lucide (smartphone, usb, laptop, mic, webcam, camera, lightbulb, monitor, headphones); imagem = caminho de foto real"}
    except Exception as e:
        return {"erro": str(e)}


@mcp.tool()
def validar_grafismos(grafismos_json: str, palavras_json: str = "", duracao_s: float = 0.0, gestos_json: str = "") -> dict:
    """Confere o plano antes do render: tipos, palavras (ou gestos) ancorados, logos/ícones existentes, textos longos, sobreposição e densidade. Devolve os itens como vão para a tela e os avisos.
    gestos_json (opcional): eventos de `detectar_gestos` para os itens com `gesto`; sem ele, vale a chave "gestos" do plano."""
    try:
        itens, avisos = grf.normalizar(grafismos_json, ler_json(palavras_json) if palavras_json else None, duracao_s or None, gestos=gestos_json or None)
        for g in itens:
            for m in [g.get("midia")] + [i.get("midia") for i in g.get("itens", [])]:
                if m and m.get("svg"):
                    m["svg"] = f"<svg … {m.get('nome')}>"
        return {"itens": itens, "avisos": avisos, "ok": not any("desconhecido" in a or "sem " in a for a in avisos)}
    except Exception as e:
        return {"erro": str(e)}


@mcp.tool()
def salvar_serie(nome: str, titulo: str, destaque: str = "", handle: str = "@thiago.obsstudio", kicker: str = "", trilha: str = "", chamada: str = "Siga para mais dicas") -> dict:
    """Modo série: guarda a identidade de uma série (título montado na abertura, palavra em destaque, @ da cartela final, rótulo e trilha fixa) em workspace/series/.
    Depois, cada episódio usa montar_remotion(serie=nome, parte=N): mesma abertura, mesmo selo "Parte N", mesma cartela e trilha em todos."""
    return _ok(grf.salvar_serie, nome, titulo, destaque=destaque, handle=handle, kicker=kicker, trilha=trilha, chamada=chamada)


@mcp.tool()
def listar_series() -> dict:
    """Séries guardadas (workspace/series/*.json), para reaproveitar abertura e cartela em novos episódios."""
    return {"series": grf.listar_series()}


@mcp.tool()
def lembrar_preferencia(texto: str) -> dict:
    """Guarda uma preferência de edição que o Raphael deixou clara na conversa ("sempre use as logos reais", "legenda menor", "não quero
    clarão") para valer nos próximos pedidos. Aparece no painel Estilo do criativo do app (ele vê e pode apagar) e em
    preferencias/memorias.md, que você lê antes de editar. Só o que ele pediu como regra geral, uma frase curta; não grave gosto de um vídeo só."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    try:
        from servico import estilo_criativo as ecr
        return {"memoria": ecr.lembrar(texto, origem="Editor (aprendida na conversa)")}
    except ValueError as e:
        return {"erro": str(e)}


@mcp.tool()
def focos_da_tela(video_tela: str) -> dict:
    """FASE C: prévia da câmera virtual automática numa gravação de tela (onde ela aproximaria e por quanto tempo), para conferir ou ajustar antes de
    montar_remotion(focos=...). Cada foco: inicio, fim, x, y (0 a 1 na tela), zoom. Região que muda o tempo todo (webcam na prévia do OBS) é ignorada."""
    try:
        focos, resumo = lay.focos_auto(video_tela)
        return {"focos": focos, "resumo": resumo}
    except Exception as e:
        return {"erro": str(e)}


@mcp.tool()
def recortar_rosto(video: str, saida_webm: str, qualidade: str = "normal") -> dict:
    """FASE C: tira o fundo do vídeo do rosto (MediaPipe) e grava .webm com transparência (máx. 720 px de altura). qualidade "alta" = cabelo melhor, ~12× mais lento.
    montar_remotion já faz isso sozinho no layout aula; use esta só para reaproveitar o recorte em outra montagem."""
    return _ok(lay.recortar_rosto, video, saida_webm, qualidade=qualidade)


@mcp.tool()
def gerar_capa(video: str, saida_png: str, texto: str, destaque: str = "", instante_s: float | None = None, estilo: str = "padrao", formato: str = "9x16", posicao: str = "auto", imagem: str = "") -> dict:
    """Capa (thumbnail) 1080x1920 ou 1920x1080: quadro do vídeo no instante dado (escolha um com o rosto visível) + gancho em caixa alta com uma palavra em laranja. posicao auto coloca o texto longe do rosto (ou baixo | topo).
    `imagem` (foto real ou print) substitui o quadro do vídeo: use quando o vídeo é só de slides tipográficos (o quadro cobriria o texto do slide) — ou faça a capa com gerar_post_imagem."""
    try:
        est = _estilo(estilo)
    except Exception as e:
        return {"erro": f"estilo não encontrado: {e}"}
    if not imagem and not video:
        return {"erro": "informe `video` (quadro) ou `imagem` (foto/print)."}
    return _ok(acabamento.gerar_capa, video, saida_png, texto, destaque=destaque, instante_s=instante_s, estilo=est, formato=formato, posicao=posicao, imagem=imagem or None)


@mcp.tool()
def sincronizar_audio(video: str, audio: str, saida_video: str, deslocamento_s: float | None = None) -> dict:
    """Troca o áudio do vídeo pelo áudio separado do microfone. Alinha por correlação quando o vídeo tem som; senão exige deslocamento_s (positivo atrasa o áudio)."""
    return _ok(sincronia.sincronizar_audio, video, audio, saida_video, deslocamento_s=deslocamento_s)


@mcp.tool()
def propor_cortes_longos(palavras_json: str, saida_json: str, n: int = 5, min_s: float = 20.0, max_s: float = 75.0) -> dict:
    """Para live, aula, podcast ou call: propõe até n candidatos a corte curto a partir da transcrição, com limites ajustados a fronteiras de frase e pontuação explicada
    (pontuacao_detalhe: densidade, gancho, número, pergunta, emoção, duração, completude, tópico novo) e segmentação por assunto. Você escolhe, escreve o gancho e usa extrair_trecho em cada um."""
    return _ok(longos.propor_cortes_longos, palavras_json, saida_json, n=n, min_s=min_s, max_s=max_s)


@mcp.tool()
def detectar_cenas(video: str, limiar: float = 0.4) -> dict:
    """Instantes de mudança de plano (corte de câmera, troca para a tela) via ffmpeg. Use para não cortar no meio de um plano e para escolher o enquadramento (rosto, tela, dividido)."""
    return _ok(longos.detectar_cenas, video, limiar=limiar)


@mcp.tool()
def extrair_trecho(video: str, inicio_s: float, fim_s: float, saida_video: str, palavras_json: str = "", saida_palavras: str = "") -> dict:
    """Recorta um trecho exato do vídeo (recodificado) e, se der palavras_json e saida_palavras, grava a transcrição do trecho com tempos rebaseados para seguir o pipeline normal (propor_cortes, legenda, montagem)."""
    return _ok(longos.extrair_trecho, video, inicio_s, fim_s, saida_video, saida_palavras=saida_palavras or None, palavras_json=palavras_json or None)


@mcp.tool()
def traduzir_srt(srt: str, saida_srt: str, idioma: str = "en", contexto: str = "", destaque: bool = True, curto: bool = False) -> dict:
    """Traduz um SRT pelo Gemini (barato; poupa a sua cota): mesmos tempos e mesma quantidade de blocos; destaque=True marca *uma* palavra por bloco (o legenda_de_srt pinta);
    curto=True pede frases mais enxutas (dublagem). Use em vez de traduzir você mesmo nos fluxos traduzir-legenda e dublagem; depois LEIA o resultado, corrija termos de OBS
    e anote [CONFERIR] no que ficou em dúvida. Precisa de GEMINI_API_KEY no .env."""
    return _ok(revisao.traduzir_srt, srt, saida_srt, idioma=idioma, contexto=contexto, destaque=destaque, curto=curto)


@mcp.tool()
def buscar_material(tema: str, tipos: str = "video,imagem", fontes: str = "drive,pexels,pixabay", n: int = 5, orientacao: str = "vertical", baixar: bool = True) -> dict:
    """Material para um tema, na ordem certa: (1) Drive da empresa (`materiais/`, takes/fotos/prints/trilhas reais, por palavras do tema e sinônimos) e (2) bancos gratuitos
    Pexels e Pixabay (vídeos e fotos; precisa de PEXELS_API_KEY / PIXABAY_API_KEY no .env; sem chave vira pendência). O que vem do banco é baixado em `banco/<fonte>/<id>.mp4|.jpg`
    com `<id>.licenca.json` (origem, autor, URL, licença, texto de atribuição). tipos: video,imagem (áudio só do Drive). orientacao vertical (9:16) ou horizontal.
    REGRA DO MANUAL: banco de imagem é só apoio (b-roll de contexto, fundo, trilha, efeito); nunca no lugar de foto/print real do Thiago, do setup ou do OBS, nem como se fosse.
    Cite a origem no ## Resumo e, quando a cena merecer material real, anote em ## Pendências."""
    return _ok(banco.buscar_material, tema, tipos=tipos, fontes=fontes, n=n, orientacao=orientacao, baixar=baixar)


@mcp.tool()
def listar_banco() -> dict:
    """O que já foi baixado dos bancos gratuitos em `banco/` (reaproveitável), com a licença de cada arquivo."""
    return _ok(banco.listar_banco)


@mcp.tool()
def listar_trilhas() -> dict:
    """Trilhas disponíveis em `trilhas/` (licença livre, colocadas pelo Raphael) e em `materiais/` (espelho do Drive), com duração. Lista vazia = sem trilha: não inventar arquivo."""
    exts = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"}
    raiz = Path(__file__).resolve().parents[2]
    pastas = [raiz / "trilhas", raiz / "workspace" / "materiais"]
    itens = []
    for pasta in pastas:
        if not pasta.exists():
            continue
        for f in sorted(pasta.rglob("*")):
            if f.suffix.lower() in exts and f.is_file() and (pasta.name == "trilhas" or "trilha" in f.as_posix().lower()):
                try:
                    itens.append({"arquivo": str(f), "nome": f.stem, "duracao_s": info_midia(f)["duracao_s"]})
                except Exception:  # noqa
                    itens.append({"arquivo": str(f), "nome": f.stem, "duracao_s": None})
    return {"trilhas": itens, "n": len(itens), "pasta": str(pastas[0]), "nota": "Sem arquivo aqui, o vídeo sai sem trilha e isso vai em Pendências."}


@mcp.tool()
def adicionar_trilha(video: str, trilha: str, saida_video: str, volume_db: float = -18.0, ducking: bool = True) -> dict:
    """Mistura uma trilha (arquivo de áudio de `trilhas/`, licença livre) por baixo da voz, com ducking automático quando há fala e fade no início e no fim. Use no vídeo final."""
    return _final(_ok(longos.adicionar_trilha, video, trilha, saida_video, volume_db=volume_db, ducking=ducking), saida_video)


@mcp.tool()
def exportar_capcut(video: str, nome: str, edl_json: str = "", palavras_json: str = "", legenda: bool = True) -> dict:
    """Projeto editável para o CapCut (Windows): cria a pasta do rascunho com o vídeo ORIGINAL, um segmento por trecho mantido da EDL (cortes editáveis) e a legenda como camada de texto (uma caixa por linha, com tempos por palavra). Use o vídeo bruto + edl.json + palavras.json do original. O Raphael abre o CapCut e o projeto aparece na lista."""
    return _ok(capcut.exportar_capcut, video, nome, edl_json=edl_json or None, palavras_json=palavras_json or None, legenda=legenda)


@mcp.tool()
def reenquadrar(video: str, saida_video: str, formato: str = "9x16", resolucao: str = "1080p", modo: str = "rosto") -> dict:
    """Recorta um vídeo (ex.: 16:9 → 9:16) seguindo pessoas. modo: rosto (um rosto, câmera suave) | falante (duas ou mais pessoas: segue quem está falando pelo movimento da boca) |
    dividido (duas pessoas empilhadas no 9:16, câmera parada). Se o modo falhar (sem rostos suficientes), devolve erro: use montar com fundo desfocado ou outro modo."""
    if modo == "falante":
        return _ok(rosto.reenquadrar_falante, video, saida_video, formato=formato, resolucao=resolucao)
    if modo == "dividido":
        return _ok(rosto.reenquadrar_dividido, video, saida_video, formato=formato, resolucao=resolucao)
    return _ok(rosto.reenquadrar, video, saida_video, formato=formato, resolucao=resolucao)


@mcp.tool()
def revisar_video(video: str, saida_json: str = "", prompt_extra: str = "", inicio_s: float = -1.0, fim_s: float = -1.0) -> dict:
    """Revisor (Gemini assiste ao vídeo final): devolve nota, problemas com instante em segundos (corte, legenda, áudio, zoom, enquadramento, ritmo) e erros de legenda. Use no final_9x16 depois do acabamento; se vier erro de chave ou cota, siga sem revisão e avise. O vídeo é apagado do Gemini após a análise.
    inicio_s/fim_s (10/11/2026): quando o problema é num trecho (segunda rodada, conferir um corte), passe os dois e o Gemini olha só esse pedaço (start_offset/end_offset; mais barato). Negativo = vídeo inteiro."""
    return _ok(revisao.revisar_video, video, saida_json=saida_json or None, prompt_extra=prompt_extra,
               inicio_s=inicio_s if inicio_s >= 0 else None, fim_s=fim_s if fim_s >= 0 else None)


@mcp.tool()
def comparar_versoes(edl_a: str = "", edl_b: str = "", grafismos_a: str = "", grafismos_b: str = "", estilo_a: str = "", estilo_b: str = "") -> dict:
    """O QUE MUDOU (10/11/2026) entre a versão anterior (a) e a nova (b): EDLs (trechos tirados/devolvidos, com segundos e motivo), planos de grafismos
    (gráfico que entrou, saiu ou mudou de instante/palavra) e estilos (chaves que mudaram; nome em estilos/, caminho ou JSON inline). Cada par é opcional;
    passe ao menos um. Devolve `cortes`, `grafismos`, `estilo`, `mudou` e `resumo` (frases curtas em PT-BR): ao refazer uma versão, cole o `resumo`
    no tópico **Mudou:** do `## Resumo`."""
    try:
        ea, eb = (_estilo(estilo_a) if estilo_a else None), (_estilo(estilo_b) if estilo_b else None)
    except Exception as e:
        return {"erro": f"estilo não encontrado: {e}"}
    return _ok(diff_versoes.comparar_versoes, edl_a=edl_a or None, edl_b=edl_b or None, grafismos_a=grafismos_a or None, grafismos_b=grafismos_b or None,
               estilo_a=ea, estilo_b=eb)


@mcp.tool()
def folha_contato(video: str, saida_png: str, max_quadros: int = 16, por_cena: bool = True, limiar_cena: float = 0.3, inicio_s: float = -1.0, fim_s: float = -1.0) -> dict:
    """FOLHA DE CONTATO (10/11/2026): um PNG em grade 4×4 (ou menor) com até `max_quadros` quadros do vídeo, um por mudança de cena (quadros quase iguais
    saem), cada um com o instante gravado em laranja. Serve para você olhar o vídeo inteiro de uma vez (Read da imagem) antes/depois do acabamento:
    enquadramento, legenda sobre o rosto, grafismo no lugar errado, tela final. por_cena=False amostra por igual; inicio_s/fim_s limitam a um trecho
    (negativo = tudo). Devolve `quadros` (instante, m:ss, coluna, linha), `grade`, `cenas_detectadas` e o caminho da imagem. Grave em `_trabalho/`."""
    return _ok(folha.folha_contato, video, saida_png, max_quadros=max_quadros, por_cena=por_cena, limiar_cena=limiar_cena,
               inicio_s=inicio_s if inicio_s >= 0 else None, fim_s=fim_s if fim_s >= 0 else None)


@mcp.tool()
def consultar_repertorio(formato: str, n: int = 3, duracao_alvo_s: float = 0) -> dict:
    """REPERTÓRIO (08/11/2026): ANTES de planejar cortes, grafismos e transições, consulte a receita do formato. Formatos: fala_tela (fala com trechos de tela do OBS,
    ex.: série O óbvio), fala, anuncio, aula, animacao, react, carrossel_video. Devolve `alvos` (medianas das referências: palavras_por_s, pausa_max_s, fala_comeca_s,
    lufs, duração), `padroes` (um gráfico a cada N s, tipos de grafismo, transições e layouts mais usados) e `exemplos` (fichas decupadas com abertura, receita,
    trechos e o que não copiar). Use os alvos para escolher energia e modo de corte, a cadência e os tipos no plano de grafismos e as transições por emenda.
    Decupagem feita da folha de quadros (2 por segundo) acerta layout e grafismo; a transição exata é aproximada. Referência é estudo: nunca copie texto, imagem ou áudio."""
    return _ok(rep.consultar, formato, n=n, duracao_alvo_s=duracao_alvo_s or None)


@mcp.tool()
def comparar_com_repertorio(formato: str, video: str, palavras_json: str = "", grafismos_json: str = "", resultado_montagem_json: str = "") -> dict:
    """Depois do acabamento (antes do revisar_video): mede a entrega e compara com a receita do formato (palavras/s, maior pausa, começo da fala, volume e, com o
    plano de grafismos e o JSON devolvido pelo montar_remotion, densidade de gráficos e proporção de emendas secas). `fora_do_alvo` vazio = no ritmo das referências;
    senão corrija o que der (pausa, densidade, transições) ou explique no `## Resumo`. palavras_json = palavras do vídeo cortado."""
    res_m = ler_json(resultado_montagem_json) if resultado_montagem_json else None
    return _ok(rep.comparar, formato, video=video, palavras_json=palavras_json, grafismos_json=grafismos_json, resultado_montagem=res_m)


@mcp.tool()
def listar_repertorio(formato: str = "") -> dict:
    """Lista as fichas do repertório (id, título, formato, origem maquina/externa/propria, decupada, desempenho)."""
    return _ok(rep.listar, formato)


@mcp.tool()
def ver_ficha_repertorio(id: str) -> dict:
    """Ficha completa de uma referência: medidas, decupagem trecho a trecho no vocabulário dos nossos parâmetros, legenda, abertura, receita, por que funciona e o que não copiar.
    Use quando o pedido disser "edita como a referência X" e traduza os trechos em layout=, grafismos (tipo/palavra/entrada) e transicoes='{"seg": "tipo"}'."""
    return _ok(rep.ficha, id)


@mcp.tool()
def adicionar_referencia(video: str, titulo: str, formato: str, fonte: str = "", desempenho_json: str = "", palavras_json: str = "", decupar: bool = True) -> dict:
    """Só quando o Raphael pedir para guardar uma referência: cria ficha de um vídeo local (Reel/Short baixado ou entrega nossa que deu certo), mede e, com decupar=True,
    o Gemini assiste e decupa. desempenho_json = o que a fonte informar ({"views": n, "curtidas": n, "data": "AAAA-MM-DD", "mediana_perfil": n}); nunca invente número."""
    desemp = json.loads(desempenho_json) if desempenho_json else None
    return _ok(rep.adicionar_referencia, video, titulo, formato, fonte=fonte, desempenho=desemp, palavras_json=palavras_json, decupar=decupar)


@mcp.tool()
def buscar_referencias_youtube(termos: str, dias: int = 120, n: int = 15, min_outlier: float = 3.0, curtos: bool = True, min_views: int = 10000) -> dict:
    """Garimpo grátis (YouTube Data API): Shorts em PT-BR sobre os termos que passaram de min_outlier × a mediana do próprio canal. Os achados viram
    CANDIDATOS (não fichas) e esperam o Raphael decidir. Use só quando ele pedir referências novas; mostre a lista com link, views, mediana e outlier."""
    return _ok(garimpo.buscar_youtube, termos, dias=dias, n=n, min_outlier=min_outlier, curtos=curtos, min_views=min_views)


@mcp.tool()
def listar_candidatos_referencia(estado: str = "aguardando") -> dict:
    """Candidatos a referência achados pelo garimpo (YouTube API, vidIQ): aguardando | aprovado | rejeitado | erro ("" = todos), do maior outlier ao menor."""
    return _ok(garimpo.listar_candidatos, estado)


@mcp.tool()
def decidir_candidato_referencia(id: str, decisao: str, por: str, formato: str = "", motivo: str = "") -> dict:
    """Só com a decisão do Raphael na conversa (por="Raphael"): aprovar baixa o vídeo público e cria a ficha no repertório (formato: fala_tela, fala,
    anuncio, aula, animacao, react, carrossel_video) com medida e decupagem; rejeitar só marca. Nunca decida sozinho."""
    return _ok(garimpo.decidir_candidato, id, decisao, por, formato=formato, motivo=motivo)


@mcp.tool()
def testar_gemini() -> dict:
    """Confere se a chave do Gemini funciona (chamada mínima de texto)."""
    return _ok(revisao.testar_gemini)


@mcp.tool()
def listar_estilos() -> dict:
    """Lista os estilos de legenda disponíveis em estilos/."""
    return {"estilos": sorted(p.stem for p in ESTILOS_DIR.glob("*.json")), "pasta": str(ESTILOS_DIR)}



@mcp.tool()
def gerar_carrossel(slides_json: str, saida_dir: str, modelo: str = "tipografico", logo: str = "", foto_capa: str = "", nome_base: str = "slide") -> dict:
    """Carrossel 1080x1350 no manual da Grava Simples. slides_json = caminho de um JSON com lista de slides [{"titulo","destaque","apoio":[até 6 linhas],"foto"?,"cta"?,"selo"?}]; o último slide com "cta" vira a tela final com botão.
    modelo: tipografico (Inter, alterna marinho e papel) | historia (foto real + caixa marinho no terço inferior) | tweet (capa clara, interiores marinho, destaque laranja). Logo só se houver arquivo oficial. Devolve os PNGs."""
    return _ok(imagem.gerar_carrossel, slides_json, saida_dir, modelo=modelo, logo=logo, foto_capa=foto_capa, nome_base=nome_base)


@mcp.tool()
def editar_foto(foto: str, saida: str, formato: str = "feed", brilho: float = 1.0, contraste: float = 1.0, saturacao: float = 1.0, nitidez: float = 1.0, desfoque_fundo: bool = False,
                texto: str = "", destaque: str = "", posicao: str = "baixo", borda: int = 0, cantos: int = 0, logo: str = "", escurecer: float = 0.0) -> dict:
    """Edita uma foto: enquadra no formato (feed 1080x1350 | quadrado | story | capa_yt | 16x9 | 9x16), brilho/contraste/saturação/nitidez (1.0 = sem mudança), fundo desfocado para caber inteira,
    texto com uma palavra em laranja numa caixa marinho (posicao baixo | topo), borda marinho, cantos arredondados, logo oficial. Não cobrir o rosto com texto."""
    return _ok(imagem.editar_foto, foto, saida, formato=formato, brilho=brilho, contraste=contraste, saturacao=saturacao, nitidez=nitidez, desfoque_fundo=desfoque_fundo,
               texto=texto, destaque=destaque, posicao=posicao, borda=borda, cantos=cantos, logo=logo, escurecer=escurecer)


@mcp.tool()
def gerar_post_imagem(saida: str, titulo: str, destaque: str = "", apoio: str = "", foto: str = "", formato: str = "feed", modelo: str = "tipografico", cta: str = "", logo: str = "", selo: str = "", fundo: str = "") -> dict:
    """Post de imagem única (feed 1080x1350 | quadrado | story) no manual da marca: título com uma palavra em laranja, apoio curto, foto real opcional, CTA em pílula, selo de uma palavra.
    fundo = papel | marinho (vazio = o do modelo). formato story é nativo: desenhado na área segura, com 250 px livres em cima e embaixo para a interface do Instagram."""
    return _ok(imagem.gerar_post_imagem, saida, titulo, destaque=destaque, apoio=apoio, foto=foto, formato=formato, modelo=modelo, cta=cta, logo=logo, selo=selo, fundo=fundo)


@mcp.tool()
def extrair_quadros(video: str, saida_dir: str, n: int = 6, instantes: list[float] | None = None, formato: str = "carrossel") -> dict:
    """Tira quadros nítidos de um vídeo para virar fotos de slide (prioriza rosto, espalha no tempo) ou nos instantes dados. PNG no formato carrossel 1080x1350 | feed | quadrado | story."""
    return _ok(imagem.extrair_quadros, video, saida_dir, n=n, instantes=instantes, formato=formato)


@mcp.tool()
def montar_dividido(video_rosto: str, video_tela: str, saida_video: str, formato: str = "9x16", resolucao: str = "1080p", proporcao_rosto: float = 0.42,
                    audio: str = "rosto", inicio_tela_s: float = 0.0, legenda_ass: str = "") -> dict:
    """Tela dividida estilo tutorial: câmera do Thiago + gravação da tela do OBS no mesmo quadro. 9x16/1x1: rosto em cima (proporcao_rosto da altura) e tela embaixo;
    16x9: rosto à esquerda e tela à direita. audio: rosto (padrão) | tela | mix. inicio_tela_s alinha a tela (use sincronizar_audio para achar o deslocamento).
    A duração é a do vídeo do rosto (corte antes com aplicar_cortes se precisar; a tela deve ser o mesmo trecho). Legenda ASS opcional queimada."""
    return _final(_ok(montagem.montar_dividido, video_rosto, video_tela, saida_video, formato=formato, resolucao=resolucao, proporcao_rosto=proporcao_rosto, audio=audio,
               inicio_tela_s=inicio_tela_s, legenda_ass=legenda_ass or None), saida_video)


@mcp.tool()
def montar_pip(video_tela: str, video_rosto: str, saida_video: str, formato: str = "9x16", resolucao: str = "1080p", tamanho: float = 0.34, posicao: str = "inferior-direita",
               forma: str = "circulo", audio: str = "rosto", inicio_tela_s: float = 0.0, legenda_ass: str = "") -> dict:
    """Formato "olha a tela": gravação do OBS em tela cheia com o rosto do Thiago numa bolha por cima (circulo com borda laranja, ou cartao de cantos 20 px).
    tamanho = fração da largura (0,2–0,5); posicao inferior-direita | inferior-esquerda | superior-direita | superior-esquerda; audio rosto | tela | mix;
    inicio_tela_s alinha a tela (sincronizar_audio acha o deslocamento). Duração = a do rosto. Use quando o que importa é a tela e o rosto só acompanha;
    para rosto e tela com o mesmo peso, montar_dividido. Legenda: bolha em cima + legenda baixa, ou bolha embaixo + legenda centro."""
    return _final(_ok(montagem.montar_pip, video_tela, video_rosto, saida_video, formato=formato, resolucao=resolucao, tamanho=tamanho, posicao=posicao, forma=forma, audio=audio,
               inicio_tela_s=inicio_tela_s, legenda_ass=legenda_ass or None), saida_video)


@mcp.tool()
def montar_react(video_reacao: str, video_referencia: str, saida_video: str, credito: str, direitos: str, formato: str = "9x16", resolucao: str = "1080p",
                 layout: str = "empilhado", volume_referencia: float = 0.35, inicio_referencia_s: float = 0.0, legenda_ass: str = "") -> dict:
    """React a uma referência: referência em cima e rosto embaixo (layout empilhado; 16x9 lado a lado) ou referência cheia com o rosto em bolha (layout bolha).
    SÓ COM DIREITOS: direitos = proprio | autorizado | licenca (sem isso a ferramenta recusa; vídeo de terceiro sem autorização não entra) e credito ("@perfil")
    fica na tela o tempo todo. Áudio: a fala de quem reage + a referência baixa (volume_referencia). Duração = a da reação."""
    return _final(_ok(montagem.montar_react, video_reacao, video_referencia, saida_video, credito, direitos, formato=formato, resolucao=resolucao, layout=layout,
               volume_referencia=volume_referencia, inicio_referencia_s=inicio_referencia_s, legenda_ass=legenda_ass or None), saida_video)


@mcp.tool()
def montar_antes_depois(video_antes: str, video_depois: str, saida_video: str, formato: str = "9x16", resolucao: str = "1080p", rotulo_antes: str = "ANTES", rotulo_depois: str = "DEPOIS",
                        modo: str = "auto", audio: str = "depois", legenda_ass: str = "") -> dict:
    """Formato antes/depois (luz, áudio, cenário, enquadramento): os dois vídeos no mesmo quadro com rótulos em pílula (antes cinza, depois laranja) e divisória laranja.
    9x16/1x1 empilham (antes em cima); 16x9 lado a lado; modo força empilhado | lado_a_lado. audio antes | depois | mix. Duração = a do mais curto. Combine com
    montar_remotion depois (frase de impacto, tela final) ou entregue direto."""
    return _final(_ok(montagem.montar_antes_depois, video_antes, video_depois, saida_video, formato=formato, resolucao=resolucao, rotulo_antes=rotulo_antes, rotulo_depois=rotulo_depois,
               modo=modo, audio=audio, legenda_ass=legenda_ass or None), saida_video)


@mcp.tool()
def animar_carrossel(slides: list[str] | str, saida_video: str, duracao_slide_s: float = 3.0, transicao_s: float = 0.6, formato: str = "4x5", transicao: str = "fade", audio: str = "") -> dict:
    """Carrossel em vídeo: slides em sequência com zoom leve e transição (Reels/Story do carrossel, ou slide em vídeo). slides = lista de PNG/JPG, "a.png;b.png" ou pasta;
    formato 4x5 | 9x16 | 1x1 (slide 4:5 no 9:16 fica inteiro sobre fundo desfocado, nada cortado); transicao = nome do xfade (fade, smoothleft, smoothup, …) ou "" (corte seco);
    audio opcional (trilha de trilhas/ ou narração). Bom para reaproveitar um carrossel aprovado como Reel."""
    return _final(_ok(imagem.animar_carrossel, slides, saida_video, duracao_slide_s=duracao_slide_s, transicao_s=transicao_s, formato=formato, transicao=transicao, audio=audio or None), saida_video)


@mcp.tool()
def gerar_carrossel_depoimentos(prints_json: str, saida_dir: str, molde: str = "depoimentos-semanais", nome_base: str = "final_tela") -> dict:
    """Carrossel semanal de depoimentos no molde fixo do designer (estilos/<molde>/: preto com brilho, "QUEM GRAVA SIMPLES / APROVA!", três prints por tela como cartões 3D, última tela CTA "Comenta DESCOMPLICA").
    prints_json = JSON com [{"arquivo","nome"?,"corte":[x0,y0,x1,y1]?}] (ou pasta com os prints), 1 a 12 prints em ordem de leitura. Gera final_tela-NN.png, carrossel.pptx (fundo + cada print como camada) e carrossel.pdf;
    devolve avisos (print pequeno, cartão cobre outro). Este post não segue o manual marinho/laranja: é o padrão vigente do post de depoimentos."""
    return _ok(depoimentos.gerar_carrossel_depoimentos, prints_json, saida_dir, molde_dir=str(ESTILOS_DIR / molde), nome_base=nome_base)


@mcp.tool()
def exportar_canva(slides_json: str, saida: str, modelo: str = "tipografico", logo: str = "", foto_capa: str = "", formato: str = "pptx") -> dict:
    """Editável do carrossel para o Canva com camadas reais (mesma composição do gerar_carrossel): formato pptx (texto, selo, botão, foto, barra; fontes Inter pelo nome) ou pdf (texto real com Inter embutida).
    Gere os dois junto com os PNGs (carrossel.pptx e carrossel.pdf). O Raphael importa no Canva e edita."""
    if formato == "pdf":
        return _ok(canva.exportar_canva_pdf, slides_json, saida, modelo=modelo, logo=logo, foto_capa=foto_capa)
    return _ok(canva.exportar_canva, slides_json, saida, modelo=modelo, logo=logo, foto_capa=foto_capa)


@mcp.tool()
def gerar_apostila(conteudo_json: str, saida_pdf: str, formato: str = "apostila", logo: str = "") -> dict:
    """Apostila (A4, capa + sumário + seções corridas) ou slides (16:9, uma seção por página) em PDF no manual da marca, Inter embutida.
    conteudo_json: {"titulo", "destaque", "subtitulo", "autor", "data", "cta", "secoes": [{"titulo", "destaque", "blocos": [ "parágrafo" | {"subtitulo"} | {"lista": [..]} | {"passos": [..]} | {"dica"} | {"atencao"} | {"imagem": png, "legenda"} | {"tabela": [[..]]} ]}]}.
    Imagens só reais (prints do OBS, fotos de materiais/). Sem preço, oferta ou número de alunos."""
    return _ok(apostila.gerar_apostila, conteudo_json, saida_pdf, formato=formato, logo=logo)


@mcp.tool()
def listar_vozes() -> dict:
    """Vozes sintéticas disponíveis: edge-tts (gratuitas, precisam de internet: antonio e francisca em pt-BR, en-andrew/en-ava em inglês, es-alvaro em espanhol, ou um ShortName
    da Microsoft) e, em "clonadas", as vozes clonadas locais (ex.: voz_nome="thiago": referência do próprio Thiago, autorizada em 31/10/2026, no motor escolhido em voz.json:
    Qwen3-TTS desde 31/10/2026 15h30, ~11 s de processamento por segundo de fala na GPU, ou Chatterbox pt-BR como reserva, ~3 s por segundo). Cada item traz "motor" e "tempo_estimado".
    Voz clonada só quando o pedido pedir a voz do Thiago; a entrega sempre diz que é voz sintética clonada (e o motor), nunca gravação dele."""
    return voz.listar_vozes()


@mcp.tool()
def narrar(texto: str, saida_audio: str, voz_nome: str = "", velocidade: int = 0, idioma: str = "pt", saida_palavras: str = "") -> dict:
    """Narração sintética de um texto (até 6000 caracteres): grava o áudio (.mp3 direto; .wav/.m4a convertido) e, se saida_palavras, um JSON de palavras
    com tempos no mesmo formato da transcrição (serve para gerar_legenda). velocidade em % (-30 a +30). Voz padrão pelo idioma (pt → antonio).
    voz_nome="thiago" usa a voz clonada local (ver listar_vozes): a resposta vem com "motor" (qwen | chatterbox), origem tts-clonada e um aviso que deve ir na entrega.
    No Qwen a síntese é lenta (~11 s por segundo de fala): para narração acima de ~60 s, avise o tempo e prefira narrar por trechos."""
    return _ok(voz.narrar, texto, saida_audio, voz=voz_nome, velocidade=velocidade, idioma=idioma, saida_palavras=saida_palavras or None)


@mcp.tool()
def montar_locucao(cenas_json: str, saida_video: str, formato: str = "9x16", estilo: str = "padrao", voz_nome: str = "", velocidade: int = 0, idioma: str = "pt",
                   resolucao: str = "1080p", pausa_s: float = 0.4, zoom: float = 1.08, trilha: str = "", saida_palavras: str = "",
                   transicao: str = "fade", transicao_s: float = 0.35, movimento: str = "alternar", jcut_s: float = 0.0) -> dict:
    """Vídeo do zero com locução (modo Locução / Sem fala). cenas_json = lista de cenas; cada cena tem "texto" (fala narrada) e UMA fonte visual:
    "imagem" (png/jpg real: print do OBS, foto; print 16:9 em 9:16 ganha fundo desfocado), "video" (clipe + "inicio_s", sem o áudio dele) ou
    "slide" ({"titulo", "destaque"?, "apoio"?: [até 6], "fundo"?: marinho|papel, "selo"?, "animacao"?: palavras|linhas|nenhuma}) = texto animado no Remotion no manual da marca
    (prefira "slide" a gerar_post_imagem para cena sem material real; se o Remotion falhar, cai sozinho para o PNG parado). PNG tipográfico já pronto: marque "tipo": "slide".
    A narração define a duração de cada cena (+ pausa_s). movimento das imagens: alternar (aproxima e afasta, cena sim cena não) | entrar | sair | parado (também por cena).
    transicao: fade (padrão) | auto (varia) | nenhuma | nome do xfade (dissolve, smoothleft, slideleft, circleopen, zoomin…), também por cena; dura transicao_s e acontece na pausa antes da fala.
    Queima a legenda karaokê do estilo ("" = sem legenda), grava <saida>_palavras.json e .srt, e devolve capa_sugerida (instante de cena com imagem/vídeo real; se só houver slides, a capa deve vir de gerar_post_imagem ou gerar_capa(imagem=)) e avisos.
    Formatos 9x16 | 16x9 | 1x1 | 4x5 (legenda só nos três primeiros). Narração por cena fica em cache (`_trabalho/cache_narracao/`): remontar com a mesma fala não
    narra de novo (`cenas_do_cache` na resposta), então "refaça só a cena 3" custa só essa cena."""
    est = None
    if estilo:
        try:
            est = _estilo(estilo)
        except Exception as e:
            return {"erro": f"estilo não encontrado: {e}"}
    return _final(_ok(voz.montar_locucao, cenas_json, saida_video, formato=formato, estilo=est, voz=voz_nome, velocidade=velocidade, idioma=idioma, resolucao=resolucao,
               pausa_s=pausa_s, zoom=zoom, trilha=trilha or None, saida_palavras=saida_palavras or None, transicao=transicao, transicao_s=transicao_s, movimento=movimento, jcut_s=jcut_s), saida_video)


@mcp.tool()
def dublar(video: str, srt: str, saida_video: str, idioma: str = "en", voz_nome: str = "", velocidade: int = 0, original_db: float = -22.0, max_acelerar: float = 1.35,
           estilo: str = "padrao", formato: str = "9x16", resolucao: str = "1080p", auto_velocidade: bool = True) -> dict:
    """Dublagem: narra cada bloco de um SRT já traduzido no instante do bloco, acelera até max_acelerar quando a fala não cabe, abaixa a voz original
    (original_db; -99 remove) e, com estilo, queima a legenda karaokê no idioma novo (estilo "" = só o áudio). Com auto_velocidade (padrão), se metade ou mais
    dos blocos não cabe, renarra tudo com a voz um pouco mais rápida (até +20 %, soa natural) antes de usar atempo; o JSON devolve `velocidade` usada.
    Devolve acelerados e atraso_max_s para você conferir; se o atraso passar de 1 s ou acelerados continuar alto, encurte as frases do SRT e rode de novo.
    Use o vídeo sem legenda queimada (cortado.mp4)."""
    est = None
    if estilo:
        try:
            est = _estilo(estilo)
        except Exception as e:
            return {"erro": f"estilo não encontrado: {e}"}
    return _final(_ok(voz.dublar, video, srt, saida_video, idioma=idioma, voz=voz_nome, velocidade=velocidade, original_db=(None if original_db <= -90 else original_db),
               max_acelerar=max_acelerar, estilo=est, formato=formato, resolucao=resolucao, auto_velocidade=auto_velocidade), saida_video)


@mcp.tool()
def grafismo_hyperframes(video: str, bloco: str, dados_json: str = "{}", saida: str = "", inicio_s: float = 0.0, duracao_s: float = 0.0) -> dict:
    """Grafismo pelo HyperFrames (motor ALTERNATIVO em teste, 10/11/2026; só use quando o pedido citar HyperFrames — o padrão continua montar_remotion/grafismos).
    Renderiza um bloco HTML da marca de hyperframes/blocos/ (`manchete`: {"kicker", "manchete", "destaque"}; `legenda-cinetica`: {"palavras": [{"palavra", "inicio", "fim"}...],
    "destaques", "posicao": baixo|centro, "max_palavras"}, tempos relativos a inicio_s) como WebM VP9 com alpha, no tamanho e fps do vídeo, e sobrepõe no vídeo a partir
    de inicio_s por duracao_s (0 = até o fim), áudio intacto; o overlay fica em _trabalho/ ao lado da saída. Devolve video, overlay (alpha, tempo_s), motor.
    Precisa do HyperFrames instalado localmente (scripts/instalar-hyperframes.cmd ou .sh; ~100 MB, usa o Chrome do sistema): sem ele devolve `erro` com o comando.
    Render de 3 s em 1080x1920 leva ~35 s nesta máquina. Detalhes e veredito em docs/HYPERFRAMES.md."""
    from editor_video import hyperframes as hf
    if not hf.instalado():
        return {"erro": f"HyperFrames não está instalado. Rode uma vez `{hf.COMANDO_INSTALAR}` (npm install local em hyperframes/, ~100 MB) e tente de novo; "
                        "ou siga com montar_remotion/grafismos, que é o motor padrão."}
    try:
        dados = json.loads(dados_json or "{}")
        if not isinstance(dados, dict):
            raise ValueError("esperava um objeto JSON")
    except ValueError as e:
        return {"erro": f"dados_json inválido ({e}); exemplo para manchete: {{\"kicker\": \"Áudio\", \"manchete\": \"Microfone caro não resolve\", \"destaque\": \"não resolve\"}}"}
    if not saida:
        return {"erro": "informe `saida` (.mp4 fora de entrada/)."}
    return _final(_ok(hf.grafismo_no_video, video, bloco, dados, saida, inicio_s=inicio_s, duracao_s=duracao_s), saida)


@mcp.tool()
def detectar_gestos(video: str, saida_json: str = "", fps_amostra: int = 5, inicio_s: float = -1.0, fim_s: float = -1.0, min_dur_s: float = 0.4) -> dict:
    """GESTOS E OLHAR (10/11/2026): reconhece no vídeo (rode no vídeo CORTADO, para os tempos baterem com o plano de grafismos) os gestos de mão do Thiago
    (polegar_cima, polegar_baixo, vitoria, apontar_cima, mao_aberta, punho, amo_voce; MediaPipe Gesture Recognizer) e a pose da cabeça (virada_esquerda,
    virada_direita, olhando_camera; MediaPipe Face Landmarker, pelo yaw estimado). Devolve `eventos` [{tipo, inicio, fim, confianca}] (só os que duram
    min_dur_s ou mais), `resumo` em uma frase e `olhar` (% do tempo olhando para a câmera); com saida_json grava o mesmo JSON (ex.: saida/<slug>/_trabalho/gestos.json).
    Uso: passe o arquivo em `planejar_grafismos(gestos_json=)` para o rascunho sugerir checklist no polegar, kicker no dedo apontando e cutaway nas viradas;
    no plano, `"gesto": "polegar_cima"` no lugar de `palavra` faz o gráfico entrar no gesto. Cabeça virada é só sugestão de cutaway: você decide com broll=/layout=.
    Primeira vez: baixa gesture_recognizer.task (8 MB) do storage oficial do Google para ~/EditorGS/modelos/ (sem rede, devolve `erro` com a URL para baixar à mão).
    fps_amostra=5 cobre gesto de 0,4 s; vídeo de 60 s leva ~20–40 s. inicio_s/fim_s (-1 = todo) limitam o trecho. Zero eventos é resultado válido."""
    from editor_video import gestos as gst
    return _ok(gst.detectar_gestos, video, saida_json or None, fps_amostra=fps_amostra, inicio_s=(None if inicio_s is None or inicio_s < 0 else inicio_s),
               fim_s=(None if fim_s is None or fim_s < 0 else fim_s), min_dur_s=min_dur_s)


if __name__ == "__main__":
    mcp.run()
