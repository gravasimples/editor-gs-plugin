# Editor GS

Editor de vídeo por conversa da Grava Simples, instalado como plugin do Claude Code. Roda inteiro no seu computador: o Claude Code logado na sua máquina é quem edita, e nada do vídeo sai do computador. Precisa de uma chave de uso (`GS1-...`) fornecida pela Grava Simples.

## Instalar (Windows 10/11)

1. Baixe `scripts/instalar-editor-gs.ps1` deste repositório.
2. Abra o PowerShell na pasta onde salvou e rode, com a sua chave:
   ```
   powershell -ExecutionPolicy Bypass -File .\instalar-editor-gs.ps1 -Chave GS1-...
   ```
3. O navegador abre para você entrar na sua conta Claude (Pro ou Max). Em 10 a 30 min o app abre em http://localhost:3200.

Mac ou Ubuntu: `bash instalar-editor-gs.sh GS1-...`.

Depois de reiniciar o computador: no Claude Code, `/editor-gs:subir`.

## À mão

```
claude plugin marketplace add gravasimples/editor-gs-plugin
claude plugin install editor-gs@editor-gs
```
No Claude Code: `/editor-gs:instalar`, `/editor-gs:chave GS1-...`, `/editor-gs:subir`.

## Requisitos

Conta Claude Pro ou Max; 6 GB livres mais espaço para os vídeos; Windows 64 bits, macOS 13+ ou Ubuntu 22.04+. Placa NVIDIA é opcional (acelera a transcrição). No Windows 11, o Smart App Control precisa estar desligado (ele bloqueia o motor de transcrição).

## Atualizar

`claude plugin update editor-gs@editor-gs` e depois `/editor-gs:subir`. Seus dados (vídeos, pedidos, chaves) ficam em `~/EditorGS` e não são tocados.

## Licença

Código proprietário da Grava Simples. O uso do app exige chave válida. Fontes, sons e logos de terceiros incluídos têm licença própria, registrada em `fontes/`, `remotion/public/sfx/LICENCA.md` e `estilos/`.
