---
description: Sobe o app do Editor GS (http://localhost:3200) e abre no navegador.
allowed-tools: [Bash]
---

# Subir o Editor GS

1. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/editor-gs.sh" subir` (termina com `Editor GS: 200`). Se disser que não está instalado, use `/editor-gs:instalar`.
2. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/editor-gs.sh" abrir` e diga o endereço à pessoa: http://localhost:3200 (no navegador dá para "instalar como aplicativo", vira ícone no computador).

O app fica rodando em segundo plano até `bash "${CLAUDE_PLUGIN_ROOT}/scripts/editor-gs.sh" parar` ou o computador desligar. Pedidos são feitos no app ou pelas ferramentas MCP `editor-gs` (novo_pedido, listar_pedidos, ver_pedido, responder_pedido, fila).
