"""Laboratório (13/11/2026): o que ficou pronto para o Raphael testar, com o passo a passo, e o retorno dele (funcionou / deu problema).

- servico/novidades.json (no repositório): um item por recurso novo, escrito por quem construiu (id, data, area, titulo, o_que_e, como_testar, onde).
- workspace/laboratorio/avaliacoes.json: o que o Raphael marcou em cada item (estado, nota, quem, quando). Item novo começa em "para_testar".
- "Deu problema" também vira anotação (Ideias › Anotações do celular) para entrar na próxima rodada de construção.
Para a próxima conversa de construção ler os retornos: `python -X utf8 -m servico.novidades retornos`."""
import json, sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTADOS = ("para_testar", "funcionou", "com_problema", "ignorado")


def _ws() -> Path:
    import os
    v = os.environ.get("EDITOR_GS_WORKSPACE")
    if v:
        return Path(v)
    from servico import caminhos as _cam
    return _cam.WORKSPACE


def _arq() -> Path:
    return _ws() / "laboratorio" / "avaliacoes.json"


def _ler(p: Path, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def registro() -> list:
    return _ler(RAIZ / "servico" / "novidades.json", [])


def listar() -> dict:
    av = _ler(_arq(), {})
    itens = []
    for it in registro():
        a = av.get(it["id"], {})
        itens.append({**it, "estado": a.get("estado", "para_testar"), "nota": a.get("nota", ""), "avaliado_por": a.get("por", ""), "avaliado_em": a.get("quando", ""),
                      "historico": a.get("historico", [])})
    itens.sort(key=lambda x: ({"para_testar": 0, "com_problema": 1, "funcionou": 2, "ignorado": 3}[x["estado"]], [-ord(c) for c in x["data"]]))
    return {"itens": itens, "para_testar": sum(1 for i in itens if i["estado"] == "para_testar"), "com_problema": sum(1 for i in itens if i["estado"] == "com_problema")}


def avaliar(id_: str, estado: str, nota: str = "", por: str = "Raphael") -> dict:
    if estado not in ESTADOS:
        raise ValueError(f"estado deve ser um de: {', '.join(ESTADOS)}")
    it = next((i for i in registro() if i["id"] == id_), None)
    if not it:
        raise KeyError(f"novidade não encontrada: {id_}")
    nota = (nota or "").strip()
    if estado == "com_problema" and not nota:
        raise ValueError("conte o que aconteceu (o que fez e o que viu)")
    av = _ler(_arq(), {})
    a = av.get(id_, {})
    agora = datetime.now().isoformat(timespec="seconds")
    hist = (a.get("historico") or []) + [{"estado": estado, "nota": nota, "por": por, "quando": agora}]
    av[id_] = {"estado": estado, "nota": nota, "por": por, "quando": agora, "historico": hist[-20:]}
    _arq().parent.mkdir(parents=True, exist_ok=True)
    tmp = _arq().with_suffix(".tmp")
    tmp.write_text(json.dumps(av, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_arq())
    return {**it, **av[id_]}


def retornos() -> list:
    """O que o Raphael marcou (menos para_testar), do mais recente para o mais antigo."""
    return sorted((i for i in listar()["itens"] if i["estado"] != "para_testar"), key=lambda x: x["avaliado_em"], reverse=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["retornos"]:
        for i in retornos():
            print(f"{i['avaliado_em'][:16]}  {i['estado']:<13} {i['id']}: {i['titulo']}" + (f"\n    nota: {i['nota']}" if i["nota"] else ""))
    else:
        r = listar()
        print(f"para testar: {r['para_testar']} · com problema: {r['com_problema']}")
        for i in r["itens"]:
            print(f"  {i['estado']:<13} {i['data']} {i['id']}: {i['titulo']}")
