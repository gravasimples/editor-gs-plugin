"""Testes do Clipador v2 (fronteiras de frase, tópicos, pontuação explicada, cenas, quadros, carrossel animado). Pasta temporária; ffmpeg real com vídeo sintético."""
import json, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import longos, imagem
from editor_video.util import salvar_json
from PIL import Image

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def fala(palavras, t0, dur_palavra=0.3, pausa=0.05):
    out, t = [], t0
    for w in palavras:
        out.append({"palavra": w, "inicio": round(t, 3), "fim": round(t + dur_palavra, 3), "prob": 0.9}); t += dur_palavra + pausa
    return out, t

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    # transcrição sintética: tópico A (webcam) 0–28 s, pausa, tópico B (microfone) 30–58 s, pausa, tópico A de novo
    A = "O erro que todo mundo comete na webcam é deixar no automático. A exposição muda sozinha e o rosto escurece. Você precisa travar a exposição e o obturador no aplicativo.".split()
    B = "Agora o microfone. Nunca grave com o microfone longe da boca. O áudio fica com eco e a pessoa desiste da aula. Aproxime o microfone e abaixe o ganho.".split()
    p1, t = fala(A * 2, 0.0); p2, t = fala(B * 2, t + 1.5); p3, t = fala(A, t + 1.5)
    palavras = p1 + p2 + p3
    segs = [{"inicio": p1[0]["inicio"], "fim": p1[-1]["fim"], "texto": " ".join(A * 2)}, {"inicio": p2[0]["inicio"], "fim": p2[-1]["fim"], "texto": " ".join(B * 2)}, {"inicio": p3[0]["inicio"], "fim": p3[-1]["fim"], "texto": " ".join(A)}]
    pj = salvar_json(str(tmp / "palavras.json"), {"arquivo": "x.mp4", "duracao_s": t, "palavras": palavras, "segmentos": segs})
    r = longos.propor_cortes_longos(pj, str(tmp / "cand.json"), n=6, min_s=8, max_s=40)
    check(r["n_blocos"] == 3 and len(r["candidatos"]) >= 2, f"candidatos propostos ({len(r['candidatos'])}, blocos {r['n_blocos']})")
    c0 = r["candidatos"][0]
    check("pontuacao_detalhe" in c0 and set(c0["pontuacao_detalhe"]) >= {"densidade", "gancho", "completude", "topico_novo", "emocao"}, "pontuação explicada por componente")
    check(abs(sum(c0["pontuacao_detalhe"].values()) - c0["pontuacao"]) < 0.05, "soma dos componentes = pontuação")
    check(all(c["termina_em_frase"] for c in r["candidatos"]), "todos os candidatos terminam em fim de frase")
    check(r["n_topicos"] >= 2, f"segmentação achou mudança de assunto ({r['n_topicos']} tópicos)")
    check(any(c["pontuacao_detalhe"]["gancho"] > 0 for c in r["candidatos"]), "palavra-gancho na abertura pontua")
    fins = longos._frases(palavras, segs); check(any(abs(f - p1[-1]["fim"]) < 0.01 for f in fins) and len(fins) >= 3, "fins de frase incluem fim de segmento e pontuação")
    ini, fim = longos._ajustar_a_frase(p2[3]["inicio"], p2[-1]["fim"] - 0.4, fins, palavras)
    check(fim >= p2[-1]["fim"] and abs(ini - (p2[0]["inicio"] - 0.15)) < 0.2 or ini <= p2[3]["inicio"], "limites puxados para fronteiras de frase")

    # cenas e quadros com vídeo sintético (duas cores = uma mudança de cena)
    v = tmp / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=640x360:d=3", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=3",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
    rc = longos.detectar_cenas(str(v), limiar=0.3)
    check(rc["n_cenas"] >= 1 and any(2.5 < c < 3.5 for c in rc["cenas"]), f"detectar_cenas acha a troca em ~3 s ({rc['cenas']})")
    q = imagem.extrair_quadros(str(v), str(tmp / "quadros"), n=3, preferir_rosto=False)
    check(q["n"] == 3 and all(Image.open(x["arquivo"]).size == (1080, 1350) for x in q["quadros"]) and q["quadros"][0]["instante_s"] < q["quadros"][-1]["instante_s"], "extrair_quadros: 3 quadros espalhados no tempo, 1080x1350")
    q2 = imagem.extrair_quadros(str(v), str(tmp / "q2"), instantes=[0.5, 4.5], formato="story", preferir_rosto=False)
    check(q2["n"] == 2 and Image.open(q2["quadros"][1]["arquivo"]).size == (1080, 1920), "extrair_quadros por instantes no formato story")
    for i in range(3):
        Image.new("RGB", (1080, 1350), (i * 60, 9, 33)).save(tmp / f"slide-{i + 1:02d}.png")
    a = imagem.animar_carrossel(str(tmp), str(tmp / "anim.mp4"), duracao_slide_s=1.0, transicao_s=0.3)
    check(a["n_slides"] == 3 and a["largura"] == 1080 and a["altura"] == 1350 and 2.0 <= a["duracao_s"] <= 3.2, f"animar_carrossel: 3 slides, 4x5, {a['duracao_s']} s")
    a2 = imagem.animar_carrossel([str(tmp / "slide-01.png")], str(tmp / "um.mp4"), duracao_slide_s=1.0, formato="9x16")
    check(a2["n_slides"] == 1 and a2["altura"] == 1920, "animar_carrossel com um slide em 9x16")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
