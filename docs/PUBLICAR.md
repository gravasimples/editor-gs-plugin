# Publicar e guardar entregas (Publora e Google Drive)

Atualizado: 29/10/2026. No cartão de entrega do app aparecem **Agendar na Publora** e **Salvar no Drive**. Nada acontece sem o clique; o Editor (agente) não tem acesso a estas rotas por regra e nunca publica.

## O que o app faz
- **Agendar na Publora**: cria o post como rascunho (`create-post`), sobe o vídeo da entrega (`get-upload-url` + PUT) e, se você escolheu data e hora, agenda (`update-post` com `scheduledTime`). Sem data, fica como rascunho na Publora para você revisar lá. A legenda vem do `post.md` (descrição + hashtags) e pode ser editada antes de enviar. Instagram vai como Reels; YouTube recebe o título do `post.md`.
- **Salvar no Drive**: copia `final_9x16.mp4`, `final_16x9.mp4`, `capa.png`, `post.md`, `relatorio.md` e `legenda.srt` para `DRIVE_DESTINO/<slug>/` pelo rclone e mostra o link da pasta (link privado pelo ID da pasta: o app nunca usa `rclone link`, que tornaria a pasta pública).
- Tudo fica registrado em `saida/<slug>/publicacoes.json` (histórico no cartão; "Atualizar status" consulta a Publora).

## Configurar a Publora (uma vez)
1. Entrar em https://app.publora.com com a conta da Grava Simples. As contas (Instagram @thiago.obsstudio, YouTube, TikTok) precisam estar conectadas lá pelo OAuth; Instagram tem de ser conta Business.
2. Menu **API** → **Generate**. Copiar a chave (começa com `sk_`).
3. No notebook, acrescentar ao `~/projetos/editor-gs/.env` a linha `PUBLORA_API_KEY=sk_...` e reiniciar o gateway (passo 5 do HANDOFF).
4. No app, abrir qualquer entrega: o cartão passa a listar as contas conectadas.

Limites do plano gratuito (Starter, segundo a documentação em 29/10): 15 posts por mês, 3 contas, vídeo até 50 MB. Reels pela API: 3 s a 15 min, MP4 até 300 MB, legenda até 2.200 caracteres. Os finais do Editor em 720p costumam ter 3 a 25 MB.

## Configurar o Drive (uma vez, sem sudo)
O gateway usa o rclone, que guarda o próprio token do Google depois de um login no navegador.
1. Instalar sem root:
   ```bash
   cd /tmp && curl -LO https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -o rclone-current-linux-amd64.zip && mkdir -p ~/.local/bin && cp rclone-*-linux-amd64/rclone ~/.local/bin/ && ~/.local/bin/rclone version
   ```
2. `~/.local/bin/rclone config` → `n` (novo remote) → nome `gs` → tipo `drive` → client_id/secret em branco → scope `1` (acesso total) → `root_folder_id` em branco → auto config `y` (abre o navegador no Windows; logar com gravasimples@) → equipe/shared drive `n` → confirmar.
3. Conferir: `~/.local/bin/rclone lsd "gs:Grava Simples - Central/10. Mídias"` deve listar as subpastas.
4. No `.env`: `DRIVE_DESTINO=gs:Grava Simples - Central/10. Mídias/Editor GS` (a pasta é criada na primeira cópia). Reiniciar o gateway.

## Pendências conhecidas
- Capa do Reels: a Publora aceita capa por `upload-instagram-cover`, ainda não ligado. Por enquanto a capa vai só para o Drive.
- O `permalink` do post publicado costuma vir vazio na API da Publora; o status "publicado" é o sinal.
- TikTok: a rota aceita a conta, mas não foi testada (sem conta conectada em 29/10).


## Capa do Reels (29/10/2026)

Quando a entrega tem `capa.png` e a conta escolhida é o Instagram, o cartão mostra a caixa "Usar capa.png como capa do Reels" (marcada por padrão). O gateway sobe a imagem em `POST /upload-instagram-cover` (multipart, até 8 MB; PNG vira JPEG na Publora) depois do vídeo e prende ao post com `update-post` → `platformSettings.instagram.coverUrl`, antes de agendar. Só vale para Reels; no YouTube a capa é ignorada. O histórico mostra "capa enviada".
