"""Biblioteca de edição (16/11/2026): receitas validadas contra o motor, varredura de privacidade, proposta → aprovação, padrões do pacote
quando não há fichas locais. Workspace temporário; a aprovação vai para a biblioteca local (EDITOR_GS_BIBLIOTECA_LOCAL=1), nunca para o repositório.
Rodar: python -X utf8 -I testes/teste_biblioteca_edicao.py"""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-bib-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws"); os.environ["EDITOR_GS_BIBLIOTECA_LOCAL"] = "1"
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import biblioteca_edicao as b, repertorio as rep
from editor_video.util import ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

oficiais = sorted((RAIZ / "biblioteca-edicao" / "estilos").glob("*.json"))
check(len(oficiais) >= 18, f"biblioteca oficial com receitas ({len(oficiais)})")
ruins = {p.stem: b.validar(json.loads(p.read_text(encoding="utf-8"))) for p in oficiais}
check(not any(ruins.values()), "todas as receitas oficiais passam na validação " + str({k: v for k, v in ruins.items() if v}))
check((RAIZ / "biblioteca-edicao" / "INDICE.md").exists() and (RAIZ / "biblioteca-edicao" / "padroes" / "formatos.json").exists(), "índice e padrões medidos no repositório")
pad = (RAIZ / "biblioteca-edicao" / "padroes" / "formatos.json").read_text(encoding="utf-8") + (RAIZ / "biblioteca-edicao" / "padroes" / "efeitos.json").read_text(encoding="utf-8")
check("maquina" not in pad.lower() and "http" not in pad and ".jpg" not in pad, "padrões publicados sem nome de referência, link ou quadro")

r = b.listar(formato="anuncio")
check(r["n"] >= 2 and all("anuncio" in x["formatos"] for x in r["receitas"]), "filtro por formato")
check(b.listar(busca="depoimento")["n"] >= 1, "busca por palavra")
v = b.ver("fala-tela-reels")
check("receita_transicoes=" in v["instrucao"] and "profissional" in v["instrucao"] and v["medido_nas_referencias"], "instrução com estilo base, transições e medidas")

base = json.loads(oficiais[0].read_text(encoding="utf-8"))
def com(**k): return {**base, "id": "teste-x", **k}
check(any("link" in e for e in b.validar(com(prompt="veja https://exemplo.com"))), "recusa link")
check(any("perfil" in e for e in b.validar(com(regras=["como faz o @fulano_edita"]))), "recusa @perfil")
check(any("referência" in e for e in b.validar(com(resumo="igual ao Máquina de Criativos"))), "recusa nome de referência")
check(any("aspas" in e for e in b.validar(com(prompt='abre com "isso aqui muda tudo pra você"'))), "recusa frase copiada entre aspas")
check(any("aspas" in e for e in b.validar(com(resumo='abre com o bordão "frase dele" no topo'))), "recusa bordão curto entre aspas")
check(any("link" in e for e in b.validar(com(alvos={"nota": "https://exemplo.com"}))), "varre também alvos")
check(any("perfil" in e for e in b.validar(com(nota="copiado de @fulano_edita"))), "varre também chave extra")
check(any("link" in e for e in b.validar(com(montagem={"trilha": "www.exemplo.com/musica"}))), "varre também valores de montagem")
check(any("link" in e for e in b.validar(com(resumo="igual ao instagram.com/fulano"))), "recusa domínio sem www")
(tmp / "ws" / "biblioteca-local").mkdir(parents=True, exist_ok=True)
(tmp / "ws" / "biblioteca-local" / "proibidos.txt").write_text("# local\nFulano de Tal\n", encoding="utf-8")
check(any("fulano de tal" in e for e in b.validar(com(resumo="no jeito do Fulano de Tal"))), "recusa termo da lista local de proibidos")
(tmp / "ws" / "biblioteca-local" / "proibidos.txt").unlink()
check(any("grafismo" in e for e in b.validar(com(grafismos={"tipos": ["holograma"]}))), "recusa grafismo que o motor não tem")
check(any("montagem" in e for e in b.validar(com(montagem={"turbo": True}))), "recusa chave de montagem desconhecida")
check(any("base_estilo" in e for e in b.validar(com(base_estilo="nao-existe"))), "recusa estilo base inexistente")

p = b.propor(json.dumps(com(nome="Teste local")), referencias=["ref-a", "ref-b"])
check(p["ok"] and not p["substitui"] and b.listar()["propostas"] == 1, "proposta guardada esperando decisão")
check(b.ver("teste-x")["origem"] == "proposta" and b.ver("teste-x")["proposta"]["referencias"] == ["ref-a", "ref-b"], "proposta visível com as referências de apoio")
a = b.aprovar("teste-x")
check(a["destino"] == "local" and not (RAIZ / "biblioteca-edicao" / "estilos" / "teste-x.json").exists(), "instalação de usuário aprova na biblioteca local, não no repositório")
check(any(x["id"] == "teste-x" and x["origem"] == "local" for x in b.listar()["receitas"]), "receita local aparece na lista")
b.propor(json.dumps(com(nome="Teste local v2")))
check(b.aprovar("teste-x")["versao"] == 2, "versão nova do mesmo id sobe a versão")
b.propor(json.dumps(com(id="teste-y", nome="Recusar")), referencias=["ref-c"])
b.recusar("teste-y", "não serve")
check(b.listar()["propostas"] == 0 and "teste-y" in (tmp / "ws" / "biblioteca-local" / "recusadas.jsonl").read_text(encoding="utf-8"), "recusa registra o motivo e tira da fila")
try:
    b.propor(json.dumps(com(prompt="www.site.com")), referencias=[]); ok = False
except ErroFerramenta:
    ok = True
check(ok, "propor com problema dá erro claro")

c = rep.consultar("anuncio")
check(c.get("fonte") == "pacote" and c["alvos"].get("pausa_max_s") and c["padroes"].get("transicoes"), "sem fichas locais, consultar_repertorio usa os padrões do pacote")
from editor_video import transicoes
check(bool(transicoes.receita_de("fala_tela")), "receita de transições funciona sem fichas locais")
srv = (RAIZ / "mcp" / "editor-de-video" / "servidor.py").read_text(encoding="utf-8")
check(all(f"def {n}" in srv for n in ("biblioteca_edicao", "ver_estilo_edicao", "propor_estilo_edicao", "destilar_conhecimento")), "ferramentas MCP da biblioteca existem")
check('"biblioteca-edicao"' in (RAIZ / "servico" / "caminhos.py").read_text(encoding="utf-8"), "workspace liga biblioteca-edicao/")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
