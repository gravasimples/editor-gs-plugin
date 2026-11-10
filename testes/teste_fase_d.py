"""Fase D (07/11/2026): painel Estilo do criativo (energia, chaves, padrão salvo, memórias), "Continuar numa conversa nova", especialista
Roteiro de aula e fade nas emendas do corte. Paperclip por dublê, workspace e índice em pasta temporária; nunca toca workspace/ real.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_fase_d.py"""
import asyncio, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-fase-d-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from fastapi.testclient import TestClient
from servico import api, estilo_criativo as ecr

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

# módulo
check(ecr.arq() == tmp / "ws" / "preferencias" / "estilo.json", "preferências ficam no workspace (pasta temporária no teste)")
d = ecr.ler()
check(d["padrao"]["energia"] == "dinamico" and d["padrao"]["chaves"]["corte_inteligente"] and not d["padrao"]["chaves"]["sem_pausa"] and d["memorias"] == [], "sem arquivo: padrão dinâmico, corte inteligente ligado, sem pausa desligado, sem memórias")
n = ecr.normalizar({"energia": "turbo", "chaves": {"zoom_ritmo": False, "inventada": True}, "legenda": "lado"})
check(n["energia"] == "dinamico" and n["chaves"]["zoom_ritmo"] is False and "inventada" not in n["chaves"] and n["legenda"] == "baixa", "valores desconhecidos caem no padrão; chave inventada sai")
t = ecr.texto_instrucoes({"energia": "bem_dinamico", "chaves": {"clarao": False, "sem_pausa": True}, "legenda": "centro"})
check(t.startswith("Estilo do criativo (painel):") and "BEM DINÂMICA" in t and "ritmo_zoom_s=3" in t and "clarao=False" in t and "nenhuma pausa acima de 0,25 s" in t and "posicao centro" in t, "texto: energia, chave desligada, sem pausa e legenda no centro viram instrução")
t = ecr.texto_instrucoes({"energia": "calmo"})
check("CALMA" in t and "min_pausa_s=0.4" in t and "sem pausa entre cenas" not in t, "calmo: cortes que respiram; chave desligada sem texto de desligado não aparece")
ecr.salvar_padrao({"energia": "bem_dinamico", "chaves": {"efeitos": False}})
check(ecr.ler()["padrao"]["energia"] == "bem_dinamico" and ecr.ler()["padrao"]["chaves"]["efeitos"] is False, "Salvar como meu padrão grava a escolha")
m = ecr.lembrar("  usar as logos reais de Zoom,   Meet e OBS  ")
m2 = ecr.lembrar("Usar as logos reais de zoom, meet e obs")
check(m["texto"] == "usar as logos reais de Zoom, Meet e OBS" and m2["id"] == m["id"] and len(ecr.ler()["memorias"]) == 1, "memória limpa espaços e não duplica (sem diferença de caixa)")
try:
    ecr.lembrar("ok"); check(False, "memória curta recusada")
except ValueError:
    check(True, "memória curta recusada")
md = (tmp / "ws" / "preferencias" / "memorias.md").read_text(encoding="utf-8")
check("usar as logos reais" in md and "BEM DINÂMICA" in md and "sem efeitos sonoros" in md, "memorias.md espelha memórias e o padrão salvo (o Editor lê)")
check(ecr.esquecer(m["id"]) and not ecr.esquecer("nao-existe") and ecr.ler()["memorias"] == [], "esquecer apaga e avisa quando não acha")

# ferramenta MCP
import servidor
r = servidor.lembrar_preferencia("nunca usar clarão nos cortes")
check(r["memoria"]["origem"].startswith("Editor") and any(x["texto"] == "nunca usar clarão nos cortes" for x in ecr.ler()["memorias"]), "lembrar_preferencia do MCP grava memória marcada como aprendida")
check("erro" in servidor.lembrar_preferencia(""), "lembrar_preferencia vazia devolve erro")

# gateway
api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.ENTRADA = tmp / "entrada"; api.SAIDA = tmp / "saida"
api.ENTRADA.mkdir(); api.SAIDA.mkdir()
criadas = []
async def pc_falso(metodo, url, **kw):
    if metodo == "POST" and url.endswith("/issues"):
        criadas.append(kw["json"]); return {"id": f"novo-{len(criadas)}", "identifier": f"GRA-{90 + len(criadas)}", **kw["json"]}
    return []
api._pc = pc_falso
async def sinc(forcar=False):
    return None
api._sincronizar_instrucoes = sinc
c = TestClient(api.app)
j = c.get("/api/gs/estilo-criativo").json()
check(j["padrao"]["energia"] == "bem_dinamico" and len(j["opcoes"]["energias"]) == 3 and len(j["opcoes"]["chaves"]) == len(ecr.CHAVES) and j["texto_padrao"].startswith("Estilo do criativo"), "GET devolve padrão, opções e texto do padrão")
j = c.post("/api/gs/estilo-criativo/padrao", json={"energia": "calmo"}).json()
check(j["padrao"]["energia"] == "calmo", "POST padrão grava")
check("CALMA" in c.post("/api/gs/estilo-criativo/texto", json={"energia": "calmo"}).json()["texto"], "prévia do texto")
r = c.post("/api/gs/estilo-criativo/memorias", data={"texto": "legenda sempre no rodapé"}); mid = r.json()["id"]
check(r.status_code == 200 and c.post("/api/gs/estilo-criativo/memorias", data={"texto": "x"}).status_code == 400, "memória pela API; curta dá 400")
check(c.delete(f"/api/gs/estilo-criativo/memorias/{mid}").status_code == 200 and c.delete("/api/gs/estilo-criativo/memorias/zzz").status_code == 404, "apagar memória pela API; inexistente dá 404")
c.post("/api/gs/conversas", data={"pedido": "Edite este vídeo", "fluxo": "reels-padrao", "estilo": "profissional", "estilo_criativo": json.dumps({"energia": "bem_dinamico"})})
check("Estilo do criativo (painel): energia BEM DINÂMICA" in criadas[-1]["description"], "pedido novo leva o parágrafo do painel")
c.post("/api/gs/conversas", data={"pedido": "Edite este vídeo", "estilo_criativo": "{quebrado"})
check("Estilo do criativo" not in criadas[-1]["description"] and c.post("/api/gs/conversas", data={"pedido": "Edite"}).status_code == 200, "JSON quebrado ou ausente: pedido segue sem o parágrafo")

# continuar numa conversa nova
api._indice_atualizar("i9", slug="s9") if hasattr(api, "_indice_atualizar") else None
idx = json.loads(api.INDICE.read_text()) if api.INDICE.exists() else {}
idx["i9"] = {"slug": "s9", "fluxo": "reels-padrao", "estilo": "profissional"}; api.INDICE.write_text(json.dumps(idx))
async def conversa_falsa(cid):
    return {"codigo": "GRA-49", "titulo": "Óbvio parte 3", "pasta": "Testes", "mensagens": [
        {"autor": "voce", "texto": "Edite este vídeo no nível profissional\n\nArquivos enviados:\n- `entrada/s9/obvio03.mp4`"},
        {"autor": "editor", "texto": "## Resumo\nDuração: 358 s → 90 s.\n- Corte: tempo morto.\n## Pendências\n- nada"}],
        "entregas": [{"nome": "final_9x16.mp4", "caminho": "s9/final_9x16.mp4"}, {"nome": "_trabalho", "caminho": "s9/_trabalho"}]}
api.conversa = conversa_falsa
j = c.get("/api/gs/conversas/i9/continuar").json()
check(j["pedido"].startswith("Continuação de GRA-49") and "Pedido original: Edite este vídeo no nível profissional" in j["pedido"] and "Arquivos enviados" not in j["pedido"], "continuação cita a conversa e o pedido original sem a lista de anexos")
check("Duração: 358 s → 90 s." in j["pedido"] and "Pendências" not in j["pedido"] and "`saida/s9/final_9x16.mp4`" in j["pedido"] and "_trabalho" not in j["pedido"], "leva o resumo e os arquivos entregues (sem pasta de trabalho)")
check(j["pasta"] == "Testes" and j["fluxo"] == "reels-padrao" and j["estilo"] == "profissional" and j["pedido"].rstrip().endswith("Agora quero:"), "mantém pasta, fluxo e estilo; termina pronto para o Raphael escrever")

# especialista e AGENTS.md
fl = (RAIZ / "fluxos" / "roteiro-aula.md").read_text(encoding="utf-8")
check(all(x in fl for x in ("## Plano da aula", "## Roteiro", "[TELA]", "## Exercício", "## Para gravar", "[CONFERIR]", 'layout="aula"')), "fluxo roteiro-aula: plano, roteiro com [TELA], exercício, para gravar, conferir e layout de edição")
ini = (RAIZ / "app" / "src" / "paginas" / "Inicio.tsx").read_text(encoding="utf-8")
check("ESPECIALISTAS" in ini and "roteiro-aula" in ini and "estilo_criativo" in ini and "PainelEstilo" in ini, "Novo pedido: especialistas, painel Estilo e envio do estilo_criativo")
conv = (RAIZ / "app" / "src" / "paginas" / "Conversa.tsx").read_text(encoding="utf-8")
check("continuarNova" in conv and "refazerComEstilo" in conv, "conversa: Continuar numa conversa nova e Refazer com este estilo")
ag = (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8")
check("preferencias/memorias.md" in ag and "lembrar_preferencia" in ag, "AGENTS.md manda ler as memórias e guardar regra geral")

# fade nas emendas do corte
from editor_video import cortes
from editor_video.util import FFMPEG
v = tmp / "tom.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=4:r=10", "-f", "lavfi", "-i", "sine=f=440:d=4", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(v)], check=True)
edl = tmp / "edl.json"; edl.write_text(json.dumps({"manter": [{"inicio": 0.0, "fim": 1.0}, {"inicio": 2.0, "fim": 3.5}]}))
r = cortes.aplicar_cortes(v, edl, tmp / "cortado.mp4")
check(abs(r["duracao_s"] - 2.5) < 0.12 and r["n_trechos"] == 2, f"corte com fade mantém a duração ({r['duracao_s']})")
import inspect
check("afade=t=in" in inspect.getsource(cortes.aplicar_cortes) and cortes.FADE_CORTE_S <= 0.01, "emenda do áudio tem fade curto (≤ 10 ms)")

# pausa escondida pelo Whisper (08/11): a palavra "esticada" cobre 1,2 s de silêncio; o corte mede no áudio e encurta
v2 = tmp / "pausa.wav"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=1", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono:d=1.2",
                "-f", "lavfi", "-i", "sine=f=300:d=1", "-filter_complex", "[0:a]aresample=16000,aformat=channel_layouts=mono[a];[2:a]aresample=16000,aformat=channel_layouts=mono[c];[a][1:a][c]concat=n=3:v=0:a=1",
                str(v2)], check=True)
pj = tmp / "pausa_palavras.json"
pj.write_text(json.dumps({"arquivo": str(v2), "duracao_s": 3.2, "palavras": [{"palavra": "olha", "inicio": 0.0, "fim": 2.1}, {"palavra": "só", "inicio": 2.15, "fim": 3.2}], "segmentos": []}))
r = cortes.propor_cortes(pj, tmp / "pausa_edl.json", modo="dinamico")
p = json.loads((tmp / "pausa_edl.json").read_text())["parametros"]
check(2.0 < r["duracao_final_s"] < 2.4 and p["pausa_max_audio_s"] == 0.3 and p["pausas_encurtadas_no_audio_s"] > 0.9, f"pausa de 1,2 s escondida na palavra sai pelo áudio ({r['duracao_final_s']} s)")
r = cortes.propor_cortes(pj, tmp / "pausa_edl0.json", modo="dinamico", pausa_max_audio_s=0)
check(r["duracao_final_s"] > 3.0, "pausa_max_audio_s=0 desliga a medição no áudio")
check(cortes._silencios_audio(tmp / "nao-existe.wav", 0.3) == [], "sem áudio legível: nenhuma pausa inventada")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
