"""Worker falso para os testes da ponte da voz clonada: mesmo protocolo dos workers reais (pronto → progresso → ok), sem modelo nem GPU.
Gera um WAV de silêncio com 0,3 s por palavra. Pedido com "falhar": true devolve ok=false; "demorar_s" dorme antes de responder."""
import json, sys, time, wave

print(json.dumps({"pronto": True, "motor": "falso", "device": "cpu", "dtype": "nenhum", "tempo_carga_s": 0.0, "modelo": "falso"}), flush=True)
for linha in sys.stdin:
    linha = linha.strip()
    if not linha:
        continue
    if linha == "sair":
        break
    pedido = json.loads(linha)
    if pedido.get("falhar"):
        print(json.dumps({"ok": False, "erro": "falha pedida"}), flush=True); continue
    partes = [f.strip() for f in pedido["texto"].replace("!", ".").replace("?", ".").split(".") if f.strip()]
    sr = 24000; quadros = 0
    for i, p in enumerate(partes):
        print(json.dumps({"progresso": {"parte": i + 1, "de": len(partes), "s_gerados": round(quadros / sr, 1)}}), flush=True)
        quadros += int(sr * 0.3 * len(p.split()))
        time.sleep(float(pedido.get("demorar_s", 0)))
    with wave.open(pedido["saida"], "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(b"\x00\x00" * quadros)
    print(json.dumps({"ok": True, "duracao_s": round(quadros / sr, 3), "partes": len(partes), "tempo_s": 0.1, "sr": sr}), flush=True)
