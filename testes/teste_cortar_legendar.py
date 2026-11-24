"""cortar_e_legendar (11/11/2026, GRA-66): corta pela EDL, remapeia as palavras pelas durações reais dos trechos e gera a legenda ASS.
Confere: palavra dentro do trecho com tempo certo, palavra na fronteira (esticada sobre o corte), palavra em trecho cortado descartada,
drift do vídeo gravado <= 1 quadro, ASS gerada. Isolado: vídeo sintético e saídas em pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_cortar_legendar.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import cortes as C
from editor_video.util import FFMPEG, info_midia

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-cortar-")); os.chdir(tmp)
vid = tmp / "v.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=10:r=30", "-f", "lavfi", "-i", "sine=f=300:d=10", "-shortest",
                "-c:v", "libx264", "-c:a", "aac", str(vid)], check=True)
# trechos mantidos com bordas fora da grade de quadros (30 fps): 0,5-2,53 | 4,017-6,5 | 8-9,6
manter = [{"inicio": 0.5, "fim": 2.53}, {"inicio": 4.017, "fim": 6.5}, {"inicio": 8.0, "fim": 9.6}]
ws = [("oi", 0.6, 0.9), ("pessoal", 1.0, 1.6),            # dentro do trecho 1
      ("esticada", 2.3, 4.4),                             # Whisper esticou sobre o corte 2,53-4,017: 0,23 s no trecho 1, 0,38 s no 2 -> fica no 2
      ("meio", 4.5, 5.0), ("tarde", 5.2, 5.5),            # dentro do trecho 2
      ("lixo", 6.8, 7.4),                                 # em trecho cortado: sai
      ("final", 8.1, 8.5), ("tchau", 9.0, 9.9)]           # trecho 3; "tchau" passa do fim (9,6): recortada
pal = {"arquivo": str(vid), "palavras": [{"palavra": w, "inicio": a, "fim": b} for w, a, b in ws],
       "segmentos": [{"inicio": 0.6, "fim": 1.6, "texto": "oi pessoal"}, {"inicio": 6.8, "fim": 7.4, "texto": "lixo"}], "duracao_s": 10.0}
(tmp / "p.json").write_text(json.dumps(pal), encoding="utf-8")
edl = {"origem": str(vid), "palavras_json": str(tmp / "p.json"), "duracao_original_s": 10.0, "manter": manter}
(tmp / "edl.json").write_text(json.dumps(edl), encoding="utf-8")

# remapeamento puro, com durações nominais (conta exata)
novas, segs, desc, bordas = C.remapear_palavras(pal["palavras"], manter, segmentos=pal["segmentos"])
por = {p["palavra"]: p for p in novas}
check(abs(por["oi"]["inicio"] - 0.1) < 1e-6 and abs(por["oi"]["fim"] - 0.4) < 1e-6, f"palavra dentro do trecho 1 com tempo certo ({por['oi']['inicio']}-{por['oi']['fim']})")
off2 = 2.03  # duração nominal do trecho 1
check(abs(por["meio"]["inicio"] - (off2 + 0.483)) < 1e-6, f"palavra do trecho 2 começa em {off2}+0,483 ({por['meio']['inicio']})")
check("esticada" in por and abs(por["esticada"]["inicio"] - off2) < 1e-6, "palavra na fronteira fica no trecho onde tem mais fala, recortada ao início dele (sem perder a palavra)")
check(abs(por["tchau"]["fim"] - (off2 + 2.483 + 1.6)) < 1e-6, "palavra que passa do fim do trecho é recortada no fim dele")
check([p["palavra"] for p in desc] == ["lixo"], f"palavra em trecho cortado é descartada ({[p['palavra'] for p in desc]})")
check(len(segs) == 1 and segs[0]["texto"] == "oi pessoal", "segmento em trecho cortado some")
check(all(a["fim"] <= b["inicio"] + 1e-9 for a, b in zip(novas, novas[1:])), "palavras em ordem, sem sobreposição")

# pipeline completo
r = C.cortar_e_legendar(str(vid), str(tmp / "p.json"), str(tmp / "edl.json"), str(tmp / "out" / "cortado.mp4"), str(tmp / "out" / "palavras.json"), formatos="9x16,16x9")
check("erro" not in r and Path(r["video"]).is_file(), "vídeo cortado gerado")
check(abs(r["duracao_real_s"] - info_midia(r["video"])["duracao_s"]) < 1e-6, "duração real vem do arquivo gravado")
check(abs(r["drift_quadros"]) <= 1.0, f"drift do fim <= 1 quadro ({r['drift_s']} s = {r['drift_quadros']} quadros; nominal {r['duracao_nominal_s']} s, esperada {r['duracao_esperada_s']} s, real {r['duracao_real_s']} s)")
check(r["palavras_mantidas"] == 7 and r["palavras_descartadas"] == 1, f"7 palavras mantidas e 1 descartada ({r['palavras_mantidas']}/{r['palavras_descartadas']})")
d = json.loads(Path(r["palavras_json"]).read_text(encoding="utf-8"))
check(d["arquivo"] == r["video"] and d["n_palavras"] == 7 and d["palavras"][-1]["fim"] <= r["duracao_real_s"] + 0.05, "palavras.json aponta o vídeo cortado e termina dentro dele")
check(any("lixo" in a for a in r["avisos"]), "aviso lista a palavra descartada")
for fm in ("9x16", "16x9"):
    ass = Path(r["legendas"][fm]["ass"])
    check(ass.is_file() and "Dialogue" in ass.read_text(encoding="utf-8") and r["legendas"][fm]["n_linhas"] > 0, f"ASS {fm} gerada com falas")
r2 = C.cortar_e_legendar(str(vid), str(tmp / "p.json"), str(tmp / "edl.json"), str(tmp / "out" / "c2.mp4"), str(tmp / "out" / "p2.json"), formatos="")
check(r2["legendas"] == {} and abs(r2["drift_quadros"]) <= 1.0, "formatos vazio: sem legenda")

os.chdir(RAIZ)
import shutil; shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
