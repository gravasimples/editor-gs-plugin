"""Repertório de edição (08/11/2026): fichas da base do Máquina, decupagem no vocabulário dos parâmetros, receita por formato e comparação da entrega.
Tudo em pasta temporária, Gemini falso, sem rede. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_repertorio.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-repertorio-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws"); os.environ["EDITOR_GS_MAQUINA"] = str(tmp / "maq"); os.environ["GEMINI_API_KEY"] = "falsa"
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import repertorio as R
from editor_video.util import FFMPEG
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

# base falsa do Máquina: dois episódios, uma duplicata, uma entrega nossa e um bruto (os três últimos ficam fora)
def pasta(nome, dur, pps, pmax=0.3):
    d = tmp / "maq" / nome; d.mkdir(parents=True)
    (d / "resumo.json").write_text(json.dumps({"duracao": dur, "pps": pps, "pausa_max": pmax, "lufs": -16.3, "inicio_fala": 0.0, "cortes_por_min": 6.0, "plano_medio_s": 7.0}))
    (d / "fala.json").write_text(json.dumps({"texto": "o óbvio", "palavras": [{"p": "O", "i": 0.0, "f": 0.2}, {"p": "óbvio", "i": 0.2, "f": 0.5}]}))
    (d / "folha.jpg").write_bytes(b"\xff\xd8\xff\xd9")
pasta("1-obvio-parte-2", 39.4, 3.72); pasta("3-obvio-parte-1", 37.9, 4.08); pasta("4-obvio-parte-1", 37.9, 4.08)
pasta("6-ads-video-5-obs", 65.4, 4.28); pasta("2026-11-02-edite-este-video", 89.6, 3.86); pasta("obvio03", 358.8, 1.27, 117.0)

r = R.importar_maquina()
check(len(r["criadas"]) == 3, f"importa 3 fichas (duplicata, entrega nossa e bruto fora): {r['criadas']}")
check(any("igual a" in p for p in r["puladas"]), "duplicata reconhecida pelo par duração/ritmo")
f = R.ficha("maq-obvio-parte-2")
check(f["formato"] == "fala_tela" and f["direitos"] == "so_referencia", "óbvio vira fala_tela e só referência")
check(R.ficha("maq-ads-video-5-obs")["formato"] == "anuncio", "ads vira anuncio")
check(f["metricas"]["palavras_por_s"] == 3.72 and "folha" in f["arquivos"], "medidas e arquivos da análise na ficha")
r2 = R.importar_maquina()
check(not r2["criadas"] and len(r2["atualizadas"]) == 3, "reimportar só atualiza as medidas")

# Gemini falso: devolve decupagem com um valor fora do vocabulário
PEDIDOS = []
def req_falso(metodo, url, dados=None, headers=None, raw=False):
    PEDIDOS.append((metodo, url, dados))
    if ":generateContent" in url:
        resposta = {"decupagem": [
            {"inicio": 0, "fim": 2.3, "assunto": "abertura", "layout": "cheio", "enquadramento": "medio", "transicao": "seco", "grafismo": {"tipo": "kicker", "texto": "PARTE 2", "palavra": "óbvio"}},
            {"inicio": 2.3, "fim": 6, "layout": "painel", "enquadramento": "medio", "transicao": "punch", "grafismo": {"tipo": "cartoes", "texto": "PC + WEBCAM"}},
            {"inicio": 6, "fim": 9, "layout": "inventado", "enquadramento": "medio", "transicao": "explosao", "grafismo": {"tipo": "manchete", "tela_cheia": True}},
            {"inicio": 9, "fim": 12, "layout": "cheio", "enquadramento": "fechado", "transicao": "seco", "grafismo": {"tipo": "nenhum"}}],
            "legenda": {"posicao": "peito"}, "abertura": "kicker no topo", "receita": ["kicker no topo", "cartões em painel"], "nao_copiar": ["número de alunos"]}
        return 200, {}, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(resposta)}]}}], "usageMetadata": {"totalTokenCount": 10}}).encode()
    if "upload/v1beta/files" in url:
        return 200, {"X-Goog-Upload-URL": "https://up"}, b"{}"
    if url == "https://up":
        return 200, {}, json.dumps({"file": {"name": "files/abc", "uri": "https://arquivo"}}).encode()
    if metodo == "GET":
        return 200, {}, json.dumps({"state": "ACTIVE"}).encode()
    return 200, {}, b"{}"

d = R.decupar_ficha("maq-obvio-parte-2", _req_=req_falso)
f = R.ficha("maq-obvio-parte-2")
check(d["trechos"] == 4 and f["decupado_por"]["fonte"] == "folha_de_quadros", "decupa pela folha de quadros")
envio = PEDIDOS[-1][2]["contents"][0]["parts"]
check(any("inline_data" in p for p in envio) and "kicker" in envio[-1]["text"], "manda a folha como imagem e o vocabulário no prompt")
t3 = f["decupagem"][2]
check(t3["layout"] == "outro" and t3["transicao"] == "outro", "valor fora do vocabulário vira 'outro'")
p = f["padroes"]
check(p["grafismos"] == 3 and p["tipos_grafismo"].get("kicker") == 1 and p["tela_cheia"] == 1, "padrões contam grafismos, tipos e tela cheia")
check(p["grafismo_a_cada_s"] == round(39.4 / 3, 2), "um gráfico a cada N s usa a duração medida")
check(R.decupar_ficha("maq-obvio-parte-2", _req_=req_falso).get("pulada"), "não decupa de novo sem refazer=True")
R.decupar_ficha("maq-obvio-parte-1", _req_=req_falso)

c = R.consultar("fala_tela", n=2, duracao_alvo_s=40)
check(c["n"] == 2 and c["decupadas"] == 2, "receita usa as fichas do formato")
check(c["alvos"]["palavras_por_s"] == round((3.72 + 4.08) / 2, 2), "alvo de palavras/s é a mediana")
check(c["padroes"]["tipos_grafismo"].get("kicker") == 2 and "seco" in c["padroes"]["transicoes"], "padrões agregados entre fichas")
check(c["exemplos"] and c["exemplos"][0]["receita"] and "nunca copie" in c["lembrete"], "exemplos com receita e lembrete de não copiar")
check(R.consultar("react")["n"] == 0, "formato sem ficha avisa em vez de inventar")

# comparação com medidas prontas e plano de grafismos
gj = tmp / "grafismos.json"; gj.write_text(json.dumps({"itens": [{"tipo": "kicker"}, {"tipo": "manchete"}]}))
cmp = R.comparar("fala_tela", metricas={"duracao_s": 40, "palavras_por_s": 3.0, "pausa_max_s": 0.25, "fala_comeca_s": 0, "lufs": -16.0}, grafismos_json=str(gj),
                 resultado_montagem={"transicoes": {"por_tipo": {"seco": 9, "punch": 1}}})
fora = " | ".join(cmp["fora_do_alvo"])
check("Palavras por segundo" in fora, "ritmo de fala abaixo da referência aparece")
check("Maior pausa" not in fora and "Volume" not in fora, "pausa menor e volume certo não são apontados")
check(any(x["medida"] == "Um gráfico a cada" for x in cmp["diferencas"]) and any(x["medida"] == "Emendas secas" for x in cmp["diferencas"]), "compara densidade de gráficos e emendas secas")

# medir um vídeo de verdade (gerado) e adicionar referência externa com upload falso
v = tmp / "ref.mp4"
subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x568:d=2", "-f", "lavfi", "-i", "aevalsrc='if(between(t,0.4,0.9),0,0.5*sin(2*PI*440*t))':d=2", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(v)], check=True)
m, cortes = R.medir(v, {"palavras": [{"palavra": "oi", "inicio": 0.1, "fim": 0.4}, {"palavra": "gente", "inicio": 0.9, "fim": 1.3}]})
check(abs(m["duracao_s"] - 2) < 0.2 and "lufs" in m and 0.4 <= m["pausa_max_s"] <= 0.6 and m["pausas_maiores_0_4"] == 1 and m["pausa_medida_por"] == "audio", "medir: duração, volume e pausa medida no áudio")
PEDIDOS.clear()
a = R.adicionar_referencia(str(v), "Reel que engajou", "fala", fonte="instagram.com/p/xyz", desempenho={"views": 120000}, _req_=req_falso)
fa = R.ficha(a["id"])
check(fa["origem"] == "externa" and fa["desempenho"]["views"] == 120000 and fa["decupado_por"]["fonte"] == "video", "referência externa medida e decupada pelo vídeo")
check(any(m_ == "DELETE" for m_, _, _ in PEDIDOS), "vídeo apagado do Gemini depois da decupagem")
check(R.adicionar_referencia(str(v), "Reel que engajou", "fala", decupar=False)["id"].endswith("-2"), "título repetido ganha id novo")
check("erro" in servidor.adicionar_referencia(str(v), "x", "formato-que-nao-existe"), "formato inválido devolve erro claro")

# ferramentas MCP
check(servidor.listar_repertorio("fala_tela")["n"] == 2, "MCP listar_repertorio filtra por formato")
check(servidor.consultar_repertorio("fala_tela")["n"] == 2, "MCP consultar_repertorio")
check("erro" in servidor.ver_ficha_repertorio("nao-existe"), "ficha inexistente devolve erro")
check("consultar_repertorio" in (RAIZ / "fluxos" / "reels-padrao.md").read_text() and "consultar_repertorio" in (RAIZ / "workspace" / "AGENTS.md").read_text(), "fluxo e AGENTS.md mandam consultar o repertório")
check(str(R.WORKSPACE).startswith(str(tmp)), "repertório do teste fica na pasta temporária")

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
