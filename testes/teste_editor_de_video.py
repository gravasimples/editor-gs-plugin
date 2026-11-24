"""Testes isolados do MCP editor-de-video. Nunca tocam workspace/entrada: tudo em pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_editor_de_video.py
Transcrição real só roda se EDITOR_GS_AMOSTRA apontar para um vídeo com fala (é copiado para a pasta temporária)."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import silencios, cortes, legenda, montagem, sincronia, transcricao, acabamento, longos, rosto, capcut
from editor_video.util import info_midia, ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def video_sintetico(pasta, dur=8.0):
    """Vídeo 1280x720 com tom nos trechos 1-3 s e 4.5-6.5 s; silêncio no resto."""
    out = pasta / "sintetico.mp4"
    af = "aevalsrc='0.3*sin(2*PI*440*t)*(between(t,1,3)+between(t,4.5,6.5))':s=48000:d=%s" % dur
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:d={dur}",
                    "-f", "lavfi", "-i", af, "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)], check=True)
    return out

def palavras_falsas(pasta, dur=8.0):
    """Fala nos tons: bloco 1 (1-3 s) e bloco 2 (4.5-6.5 s); bloco 2 repete a frase do bloco 1 (refação)."""
    frase = ["olha", "como", "ficou", "a", "imagem"]
    def bloco(ini, fim):
        passo = (fim - ini) / len(frase)
        return [{"palavra": w, "inicio": round(ini + i * passo, 3), "fim": round(ini + (i + 1) * passo - 0.02, 3), "prob": 0.9} for i, w in enumerate(frase)]
    b1, b2 = bloco(1.0, 3.0), bloco(4.5, 6.5)
    b2.append({"palavra": "né", "inicio": 7.2, "fim": 7.35, "prob": 0.8})
    d = {"arquivo": "sintetico.mp4", "duracao_s": dur, "palavras": b1 + b2,
         "segmentos": [{"inicio": 1.0, "fim": 3.0, "texto": "olha como ficou a imagem"}, {"inicio": 4.5, "fim": 6.5, "texto": "olha como ficou a imagem"},
                       {"inicio": 7.2, "fim": 7.35, "texto": "né"}]}
    p = pasta / "palavras.json"; p.write_text(json.dumps(d), encoding="utf-8"); return p

def main():
    with tempfile.TemporaryDirectory(prefix="editor-gs-teste-", ignore_cleanup_errors=True) as tmp:  # Windows: o chdir segura a pasta
        pasta = Path(tmp); os.chdir(pasta)
        v = video_sintetico(pasta)
        i = info_midia(v); check(abs(i["duracao_s"] - 8.0) < 0.3 and i["tem_audio"], f"info_midia: {i['duracao_s']} s, áudio={i['tem_audio']}")
        s = silencios.detectar_silencios(v, limiar_db=-35, min_s=0.35)
        check(s["n_silencios"] == 3, f"detectar_silencios: {s['n_silencios']} silêncios (esperado 3) {[(x['inicio'], x['fim']) for x in s['silencios']]}")
        check(abs(s["silencio_total_s"] - 4.0) < 0.3, f"silêncio total {s['silencio_total_s']} s (esperado ~4)")
        pj = palavras_falsas(pasta)
        e = cortes.propor_cortes(pj, pasta / "edl.json", min_pausa_s=0.35, margem_s=0.08, max_remocao=0.25)
        edl = json.load(open(pasta / "edl.json"))
        motivos = {r["motivo"] for r in edl["removidos"]}
        check("refação (frase repetida)" in motivos, f"propor_cortes marca refação: {motivos}")
        check("vício de linguagem isolado" in motivos, "propor_cortes marca vício isolado")
        check(len(edl["manter"]) == 1 and abs(edl["manter"][0]["inicio"] - 4.42) < 0.05, f"mantém só a segunda tomada: {edl['manter']}")
        check(e["precisa_aprovacao"] is True, f"precisa_aprovacao (removeu {e['fracao_removida']*100:.0f}%)")
        aj = cortes.ajustar_edl(pasta / "edl.json", pasta / "edl2.json", manter_extra=[[1.0, 3.0]], remover_extra=[[5.0, 5.5]])
        edl2 = json.load(open(pasta / "edl2.json"))
        check(len(edl2["manter"]) == 3 and edl2["manter"][0]["inicio"] == 1.0 and abs(aj["duracao_final_s"] - 3.64) < 0.1, f"ajustar_edl devolve e tira trechos: {edl2['manter']} ({aj['duracao_final_s']} s)")
        a = cortes.aplicar_cortes(v, pasta / "edl.json", pasta / "cortado.mp4", saida_palavras=pasta / "palavras_cortado.json")
        check(abs(a["duracao_s"] - 2.16) < 0.25, f"aplicar_cortes: duração {a['duracao_s']} s (esperado ~2,2)")
        pc = json.load(open(pasta / "palavras_cortado.json"))
        check(pc["n_palavras"] == 5 and pc["palavras"][0]["inicio"] < 0.2, f"palavras remapeadas: {pc['n_palavras']} começando em {pc['palavras'][0]['inicio']}")
        estilo = json.load(open(RAIZ / "estilos" / "padrao.json"))
        l = legenda.gerar_legenda(pasta / "palavras_cortado.json", pasta / "legenda.ass", estilo, formato="9x16", saida_srt=pasta / "legenda.srt")
        ass = (pasta / "legenda.ass").read_text(encoding="utf-8")
        check("\\k" in ass and "PlayResX: 1080" in ass and "Inter ExtraBold" in ass, f"legenda ASS karaokê: {l['n_linhas']} linha(s)")
        check((pasta / "legenda.srt").exists(), "SRT separado gerado")
        m = montagem.montar(pasta / "cortado.mp4", pasta / "final_9x16.mp4", formato="9x16", legenda_ass=pasta / "legenda.ass", resolucao="720p")
        check(m["largura"] == 720 and m["altura"] == 1280, f"montar 9x16: {m['largura']}x{m['altura']}")
        m2 = montagem.montar(pasta / "cortado.mp4", pasta / "final_16x9.mp4", formato="16x9", resolucao="720p")
        check(m2["largura"] == 1280 and m2["altura"] == 720 and m2["enquadramento"] == "centro", f"montar 16x9: {m2['largura']}x{m2['altura']} ({m2['enquadramento']})")
        m3 = montagem.montar(pasta / "final_9x16.mp4", pasta / "de_vertical_16x9.mp4", formato="16x9", resolucao="720p")
        check(m3["largura"] == 1280 and m3["enquadramento"] == "desfocado", f"montar auto de vertical para 16x9: {m3['enquadramento']}")
        # sincronia: áudio separado = mesmo tom deslocado 0,7 s
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(v), "-vn", "-af", "adelay=700|700", "-c:a", "aac", str(pasta / "mic.m4a")], check=True)
        sy = sincronia.sincronizar_audio(v, pasta / "mic.m4a", pasta / "sincronizado.mp4")
        check(abs(sy["deslocamento_s"] - (-0.7)) < 0.08, f"sincronizar_audio: deslocamento {sy['deslocamento_s']} s (esperado -0,70), confiança {sy['confianca']}")
        cp = acabamento.gerar_capa(pasta / "cortado.mp4", pasta / "capa.png", "Webcam simples, imagem de qualidade", destaque="qualidade", instante_s=0.5, estilo=estilo)
        check(cp["largura"] == 1080 and cp["altura"] == 1920 and (pasta / "capa.png").stat().st_size > 10000, f"gerar_capa: {cp['linhas']}")
        try:
            rm = acabamento.montar_remotion(pasta / "cortado.mp4", pasta / "remotion.mp4", palavras_json=pasta / "palavras_cortado.json", edl_json=pasta / "edl.json", resolucao="720p", estilo=estilo, frase_impacto="Teste", legenda_ass=pasta / "legenda.ass", tela_final=True)  # 13/11: o padrao não tem tela final; pedida explícita
            check(rm["largura"] == 720 and rm["duracao_s"] > a["duracao_s"] + 2.5, f"montar_remotion: {rm['duracao_s']} s com tela final")
        except ErroFerramenta as e:
            print("SKIP montar_remotion:", str(e)[:120].replace("\n", " "))
        # vídeo longo: palavras sintéticas de 3 blocos de 25 s
        def bloco(ini, n=40): 
            return [{"palavra": ("erro" if i == 0 else f"w{i}"), "inicio": round(ini + i * 0.6, 3), "fim": round(ini + i * 0.6 + 0.5, 3), "prob": 0.9} for i in range(n)]
        pl = pasta / "longo.json"; pl.write_text(json.dumps({"arquivo": "longo.mp4", "duracao_s": 100, "palavras": bloco(0) + bloco(30) + bloco(60), "segmentos": []}), encoding="utf-8")
        cl = longos.propor_cortes_longos(pl, pasta / "cands.json", n=3, min_s=20, max_s=30)
        check(len(cl["candidatos"]) == 3 and all(20 <= c["duracao"] <= 30 for c in cl["candidatos"]), f"propor_cortes_longos: {[(c['inicio'], c['duracao']) for c in cl['candidatos']]}")
        tr = longos.extrair_trecho(v, 1.0, 3.5, pasta / "trecho.mp4", palavras_json=pj, saida_palavras=pasta / "trecho_palavras.json")
        check(abs(tr["duracao_s"] - 2.5) < 0.2 and json.load(open(pasta / "trecho_palavras.json"))["n_palavras"] == 5, f"extrair_trecho: {tr['duracao_s']} s, palavras rebaseadas")
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=4", "-c:a", "aac", str(pasta / "trilha.m4a")], check=True)
        mt = longos.adicionar_trilha(pasta / "cortado.mp4", pasta / "trilha.m4a", pasta / "com_trilha.mp4")
        check(abs(mt["duracao_s"] - a["duracao_s"]) < 0.3, f"adicionar_trilha com ducking: {mt['duracao_s']} s")
        drafts = pasta / "capcut-drafts"; drafts.mkdir()
        cc = capcut.exportar_capcut(v, "Teste GS", edl_json=pasta / "edl2.json", palavras_json=pj, pasta_drafts=drafts)
        dc = json.load(open(Path(cc["pasta_wsl"]) / "draft_content.json", encoding="utf-8"))
        check(cc["n_segmentos"] == 3 and [t["type"] for t in dc["tracks"]] == ["video", "text"] and cc["n_legendas"] >= 2 and (Path(cc["pasta_wsl"]) / "sintetico.mp4").exists(),
              f"exportar_capcut: {cc['n_segmentos']} segmentos, {cc['n_legendas']} legendas, vídeo copiado")
        check(dc["tracks"][0]["segments"][1]["target_timerange"]["start"] == dc["tracks"][0]["segments"][0]["target_timerange"]["duration"], "capcut: segmentos encadeados na linha do tempo")
        try:
            rf = rosto.reenquadrar(pasta / "cortado.mp4", pasta / "rosto.mp4", formato="9x16")
            check(False, f"reenquadrar deveria falhar sem rosto: {rf}")
        except ErroFerramenta as e:
            check("rosto" in str(e).lower(), f"reenquadrar sem rosto recusa: {str(e)[:60]}")
        # recusa gravar em entrada/
        (pasta / "entrada").mkdir()
        try:
            cortes.propor_cortes(pj, pasta / "entrada" / "x.json"); check(False, "deveria recusar gravar em entrada/")
        except ErroFerramenta:
            check(True, "recusa gravar em entrada/")
        amostra = os.environ.get("EDITOR_GS_AMOSTRA")
        if amostra and Path(amostra).exists():
            shutil.copy(amostra, pasta / "amostra.mp4")
            t = transcricao.transcrever(pasta / "amostra.mp4", pasta / "amostra.json", modelo="small")
            check(t["n_palavras"] > 0, f"transcrever amostra: {t['n_palavras']} palavras em {t['device']}")
        else:
            print("SKIP transcrever (defina EDITOR_GS_AMOSTRA)")
    os.chdir(RAIZ)
    print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
    sys.exit(1 if FALHAS else 0)

if __name__ == "__main__":
    main()
