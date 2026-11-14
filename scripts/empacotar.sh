#!/usr/bin/env bash
# Gera o pacote do Editor GS para instalar em outro computador (sem node_modules, sem vídeos, sem .env nem tokens).
# Uso: bash scripts/empacotar.sh [pasta_destino]   → editor-gs-instalador-AAAA-MM-DD.tar.gz
set -euo pipefail
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/.." && pwd)"
DEST="${1:-$HOME}"; NOME="editor-gs-instalador-$(date +%F).tar.gz"
tar -C "$(dirname "$RAIZ")" -czf "$DEST/$NOME" \
  --exclude='editor-gs/.env' --exclude='editor-gs/.env.local' --exclude='editor-gs/.cookies' --exclude='editor-gs/.git' \
  --exclude='*/node_modules' --exclude='editor-gs/app/dist' --exclude='editor-gs/docs/logs' --exclude='editor-gs/docs/evidencias' --exclude='editor-gs/docs/maquina' \
  --exclude='editor-gs/workspace/_trabalho' --exclude='editor-gs/workspace/entrada' --exclude='editor-gs/workspace/saida' --exclude='editor-gs/workspace/banco' \
  --exclude='editor-gs/workspace/voz' --exclude='editor-gs/workspace/estilos-previas' --exclude='editor-gs/workspace/referencias' --exclude='editor-gs/workspace/clipes' \
  --exclude='editor-gs/workspace/repertorio' --exclude='editor-gs/workspace/materiais' --exclude='editor-gs/workspace/anotacoes' --exclude='editor-gs/workspace/relatorios' \
  --exclude='editor-gs/workspace/atalho.json' --exclude='editor-gs/estilos/previas' --exclude='editor-gs/remotion/public/render' --exclude='editor-gs/trilhas/*.mp3' --exclude='editor-gs/trilhas/*.wav' \
  --exclude='editor-gs/servico/conversas.json' --exclude='editor-gs/servico/textos.json' --exclude='editor-gs/servico/pastas.json' --exclude='editor-gs/servico/*_token.json' \
  --exclude='editor-gs/servico/push_*.json' --exclude='editor-gs/servico/etiquetas.json' --exclude='editor-gs/servico/automacao*.json' --exclude='editor-gs/servico/campanhas.json' \
  --exclude='editor-gs/servico/pasta_vigiada_estado.json' --exclude='editor-gs/servico/automacoes_estado.json' --exclude='editor-gs/servico/marca_regras.json' --exclude='editor-gs/testes/*.wav' --exclude='*/__pycache__' --exclude='*.mp4' --exclude='*.mov' \
  editor-gs
du -h "$DEST/$NOME"
tar -tzf "$DEST/$NOME" | grep -c "editor-gs/.env.exemplo$" >/dev/null || { echo "ERRO: .env.exemplo não entrou no pacote"; exit 1; }
echo "Dentro do pacote NÃO vão: chaves (.env), tokens, vídeos, entregas, voz clonada, node_modules. O instalador baixa o que falta."
