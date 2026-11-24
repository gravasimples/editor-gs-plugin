"""Banco de skills (10/11/2026): catálogo, importação de achados, decisões, instalação de skill (git falso), ensinar e pesquisa devida. Sem rede."""
import json, os, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(RAIZ))
TMP = Path(tempfile.mkdtemp(prefix="gs-skills-")); os.environ["EDITOR_GS_WORKSPACE"] = str(TMP)
(TMP / "preferencias").mkdir(parents=True)
from servico import skills_banco as sb  # noqa: E402

falhas = 0


def check(cond, msg):
    global falhas
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        falhas += 1


r = sb.registrar([{"nome": "Video Use", "tipo": "skill-claude", "url": "https://github.com/browser-use/video-use", "licenca": "MIT", "resumo": "skill de edição", "o_que_aproveitar": ["EDL revisável", "autoavaliação"], "evidencia": "10k estrelas"},
                  {"nome": "Sem url", "tipo": "curso", "resumo": "curso de edição"}, {"url": "https://github.com/browser-use/video-use/"}], por="Raphael")
check(r["novos"] == ["video-use", "sem-url"] and r["ja_tinha"] == ["video-use"], f"registrar: dedupe por url e id ({r})")
cat = sb.catalogo()
check(len(cat) == 2 and cat[0]["estado"] == "achado" and cat[0]["o_que_aproveitar"] == ["EDL revisável", "autoavaliação"], "catálogo com os campos normalizados")

ach = sb._dir() / "achados"; ach.mkdir(exist_ok=True)
(ach / "achados-x.json").write_text(json.dumps({"por": "Editor (pesquisa)", "itens": [{"nome": "Kinocut", "tipo": "repo", "url": "https://github.com/KyaniteLabs/kinocut", "licenca": "Apache-2.0"},
                                                                                   {"nome": "Video Use", "tipo": "skill-claude", "url": "https://github.com/browser-use/video-use", "preco": "grátis"}]}), encoding="utf-8")
cat = sb.catalogo()
check(len(cat) == 3 and any(i["id"] == "kinocut" and i["fonte"].startswith("pesquisa") for i in cat) and sb.item("video-use")["preco"] == "grátis", "achados do agente entram no catálogo e completam campos vazios")
check(not (ach / "achados-x.json").exists() and (ach / "_importados" / "achados-x.json").exists(), "arquivo de achados movido para _importados")

try:
    sb.decidir("kinocut", "instalado", "Raphael"); check(False, "transição inválida barrada")
except ValueError:
    check(True, "transição inválida barrada (achado → instalado)")
try:
    sb.decidir("kinocut", "aprovado", ""); check(False, "decisão sem pessoa barrada")
except ValueError:
    check(True, "decisão sem pessoa barrada")
it = sb.decidir("kinocut", "avaliar", "Raphael", nota="ver o dry-run")
check(it["estado"] == "avaliar" and it["notas"][-1]["texto"] == "ver o dry-run" and it["decidido_por"] == "Raphael", "decidir muda estado e anota")
check(sb.anotar("kinocut", "segunda nota", "Raphael")["notas"][-1]["texto"] == "segunda nota", "anotar")
check(sb.editar("kinocut", {"tipo": "ferramenta", "o_que_aproveitar": "a; b"})["o_que_aproveitar"] == ["a", "b"], "editar campos")
check(sb.catalogo(estado="avaliar")[0]["id"] == "kinocut" and sb.catalogo(q="apache")[0]["id"] == "kinocut" and sb.catalogo(tipo="curso")[0]["id"] == "sem-url", "filtros do catálogo")


def git_falso(dono, repo, ramo, clone):
    (clone / "skills" / "cortes").mkdir(parents=True); (clone / "skills" / "cortes" / "SKILL.md").write_text("---\nname: cortes-pro\ndescription: corta pausas\n---\n# Cortes\n", encoding="utf-8")
    (clone / "skills" / "outra").mkdir(parents=True); (clone / "skills" / "outra" / "SKILL.md").write_text("---\nname: outra\n---\n", encoding="utf-8")


try:
    sb.instalar("kinocut", _baixar_=git_falso); check(False, "tipo errado não instala")
except ValueError as e:
    check("skill, plugin" in str(e), "tipo errado não instala")
sb.decidir("video-use", "aprovado", "Raphael")
pac = sb.instalar("video-use", _baixar_=git_falso)  # 13/11/2026: repositório com várias skills vira pacote <slug>--<pasta>
check(len(pac["skills"]) == 2 and (TMP / "skills_biblioteca" / "video-use--cortes" / "SKILL.md").is_file() and (TMP / "skills_biblioteca" / "video-use--outra").is_dir(), "repositório com 2 skills instala o pacote")
sb.desinstalar("video-use")
check(not any((TMP / "skills_biblioteca").glob("video-use--*")), "desinstalar apaga o pacote inteiro")


def git_plugin(dono, repo, ramo, clone):  # marketplace com cópias para outros agentes: só a pasta source do plugin conta
    for ag in ("claude", "cursor", "codex"):
        (clone / ag / "skills" / "corte").mkdir(parents=True); (clone / ag / "skills" / "corte" / "SKILL.md").write_text(f"---\nname: corte-{ag}\n---\n", encoding="utf-8")
    (clone / ".claude-plugin").mkdir(); (clone / ".claude-plugin" / "marketplace.json").write_text('{"plugins":[{"name":"x","source":"./claude"}]}', encoding="utf-8")
    (clone / "claude" / "skills" / "corte" / "modelo.onnx").write_bytes(b"0" * (26 * 1024 * 1024))


pl = sb.instalar("video-use", _baixar_=git_plugin)
check(len(pl["skills"]) == 1 and pl["skill"] == "corte-claude" and pl["pulados"] and not (TMP / "skills_biblioteca" / "video-use" / "modelo.onnx").exists(), "plugin do marketplace: só a pasta source, arquivo grande fica de fora")
sb.desinstalar("video-use")
sb.editar("video-use", {"url": "https://github.com/browser-use/video-use/tree/main/skills/cortes"})
inst = sb.instalar("video-use", _baixar_=git_falso)
check(inst["skill"] == "cortes-pro" and (TMP / "skills_biblioteca" / "video-use" / "SKILL.md").is_file() and not (TMP / ".claude" / "skills" / "video-use").exists() and sb.item("video-use")["estado"] == "instalado", f"instala a subpasta em quarentena, fora de .claude/skills ({inst['pasta']})")
check(sb.instaladas()[0]["pasta"] == "video-use" and not sb.instaladas()[0]["ativa"] and "corta pausas" in sb.instaladas()[0]["descricao"] and sb.estado()["tokens_ativas"] == 0, "lista instaladas pela descrição; em quarentena não custa token")
check(sb.instaladas()[0]["raiox"] and sb.instaladas()[0]["raiox"]["sugestao"] == "dissecar", "instalar já gera o raio-x")
at = sb.ativar("video-use", "Raphael")
check(at["ativa"] and (TMP / ".claude" / "skills" / "video-use" / "SKILL.md").is_file() and sb.estado()["tokens_ativas"] > 0 and sb.item("video-use")["instalacao"]["pasta"] == ".claude/skills/video-use", "ativar move para .claude/skills e corrige a pasta no catálogo")
try:
    sb.ativar("video-use", ""); check(False, "ativar sem pessoa barrado")
except (ValueError, KeyError):
    check(True, "ativar sem pessoa barrado")
(TMP / ".claude" / "skills" / "gs-cortes").mkdir(parents=True); (TMP / ".claude" / "skills" / "gs-cortes" / "SKILL.md").write_text("---\nname: gs-cortes\ndescription: nossa\n---\n", encoding="utf-8")
q = sb.quarentena_tudo()
check(q["movidas"] == ["video-use"] and (TMP / ".claude" / "skills" / "gs-cortes").is_dir() and (TMP / "skills_biblioteca" / "video-use").is_dir(), "quarentena tira as de terceiros e mantém as nossas (gs-)")


def git_binario(dono, repo, ramo, clone):
    clone.mkdir(parents=True); (clone / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8"); (clone / "tool.exe").write_bytes(b"MZ")


sb.editar("video-use", {"url": "https://github.com/x/y"})
try:
    sb.instalar("video-use", _baixar_=git_binario); check(False, "skill com binário recusada")
except ValueError as e:
    check("binário" in str(e), "skill com binário recusada")
check(sb.item("video-use")["estado"] == "instalado" and (TMP / "skills_biblioteca" / "video-use" / "SKILL.md").is_file(), "instalação anterior preservada quando a nova falha")
sb.desinstalar("video-use")
check(not (TMP / "skills_biblioteca" / "video-use").exists() and sb.item("video-use")["estado"] == "aprovado", "desinstalar apaga a pasta e volta a aprovado")

r = sb.ensinar("conhecimento", "Ritmo de corte em tutorial", "Em tutorial de OBS, cortar na troca de janela e manter 0,5 s depois do clique para o aluno ver o resultado. " * 2, por="Raphael", fonte="aula do Thiago")
check(r["arquivo"].startswith("conhecimento/") and (TMP / r["arquivo"]).is_file() and "Ritmo de corte" in (TMP / "conhecimento" / "INDICE.md").read_text(encoding="utf-8"), "conhecimento vira arquivo e entra no índice")
check(sb.conhecimento()[0]["titulo"] == "Ritmo de corte em tutorial", "lista conhecimento")
try:
    sb.ensinar("conhecimento", "", "curto", por="Raphael"); check(False, "conhecimento curto barrado")
except ValueError:
    check(True, "conhecimento curto barrado")
r = sb.ensinar("regra", "", "Nunca usar clarão em vídeo de aula", por="Raphael")
check(r["tipo"] == "regra" and r["memoria"]["texto"].startswith("Nunca usar clarão") and "Banco de skills" in r["memoria"]["origem"], "regra vira memória do painel Estilo do criativo")
check(sb.conhecimento_apagar(Path(sb.conhecimento()[0]["arquivo"]).name) and sb.conhecimento() == [] and "(nada ainda)" in (TMP / "conhecimento" / "INDICE.md").read_text(encoding="utf-8"), "apagar conhecimento reindexa")

dev, motivo = sb.pesquisa_devida()
check(dev and "nenhuma" in motivo, "pesquisa devida sem rodada")
sb.rodada_gravar({"id": "r1", "quando": (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds"), "por": "Raphael"})
check(not sb.pesquisa_devida()[0] and sb.pesquisa_devida(datetime.now() + timedelta(days=6))[0], "pesquisa semanal: não devida com 2 dias, devida com 8")
ped = sb.pedido_pesquisa("legendas animadas")
check("achados-" in ped and "github.com/kyanitelabs/kinocut" in ped.lower() and "Foco pedido" in ped, "pedido de pesquisa lista URLs conhecidas e foco")
ped = sb.pedido_reproduzir(sb.item("kinocut"), modo="avaliar")
check("Só avalie" in ped and "ver o dry-run" in ped, "pedido de avaliação leva as notas do Raphael")
est = sb.estado()
check(est["n"] == 3 and est["por_estado"].get("avaliar") == 1 and est["rodadas"][-1]["id"] == "r1" and "estados" in est, "estado resume catálogo, rodadas e listas")
print(f"\n{falhas} falha(s)")
sys.exit(1 if falhas else 0)
