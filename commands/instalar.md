---
description: Instala o Editor GS nesta máquina (uma vez): Python e motor de edição, Node e Remotion, ffmpeg, build do app. Dados em ~/EditorGS.
allowed-tools: [Bash, Read]
---

# Instalar o Editor GS

A instalação demora de 10 a 30 min na primeira vez (baixa uns 4 GB) e passa do limite de tempo de um comando comum. Por isso:

1. Rode **em segundo plano** (`run_in_background: true`), com o maior timeout disponível:
   ```
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/editor-gs.sh" instalar
   ```
   No Windows isso chama `scripts\editor-gs.cmd instalar` (tudo no perfil do usuário, sem administrador). No Ubuntu/WSL pode pedir a senha do sudo; no Mac, o Homebrew.
2. A cada 1 a 2 minutos, leia o fim do log mais novo em `~/EditorGS/logs/instalacao-*.log` (no Windows, `%USERPROFILE%\EditorGS\logs\`) e diga à pessoa em uma linha em que etapa está (1/6 ferramentas, 2/6 Python, 3/6 Node e app, 4/6 pastas, 5/6 Claude Code, 6/6 conferência). Não reinicie a instalação por impaciência.
3. Quando o log terminar com "pronto", confira com `bash "${CLAUDE_PLUGIN_ROOT}/scripts/editor-gs.sh" status` e siga para `/editor-gs:chave GS1-...` (se a pessoa recebeu uma chave) e `/editor-gs:subir`.

Se der erro, leia o log e explique à pessoa em uma frase o que faltou (rede, espaço em disco, sudo, Smart App Control no Windows 11). O script é idempotente: rodar de novo só instala o que falta. No Windows 11, se o log avisar sobre o **Smart App Control**, a pessoa precisa desligá-lo (Segurança do Windows → Controle de aplicativos e navegador → Smart App Control → Desativado) e rodar de novo: ele bloqueia o motor de transcrição.

Avisos à pessoa, em linguagem simples: o Claude Code logado nesta máquina é o motor (gasta a janela da assinatura dela a cada edição); nada do vídeo sai do computador; a pasta de dados é `~/EditorGS` (vídeos em `workspace/entrada`, entregas em `workspace/saida`).
