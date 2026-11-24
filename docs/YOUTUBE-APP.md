# YouTube direto (app próprio do Google, sem Publora)

Atualizado: 30/10/2026. O gateway sobe o vídeo da entrega direto no canal @gravasimples pela YouTube Data API v3, com OAuth do próprio Google. Custo: zero (só a cota da API: 10.000 unidades por dia; cada upload gasta 1.600, ou seja, uns 6 vídeos por dia). Nada é publicado sem o clique no app; o padrão é subir **privado**.

## Passo a passo (uma vez, pelo Raphael, logado na conta gravasimples@gmail.com)

1. https://console.cloud.google.com → criar projeto "Editor GS" (ou usar o projeto que já tem a chave YOUTUBE_API_KEY do GSI).
2. APIs e serviços → Biblioteca → **YouTube Data API v3** → Ativar.
3. APIs e serviços → **Tela de permissão OAuth** → tipo Externo → nome "Editor GS", e-mail de suporte, e-mail do desenvolvedor → Salvar. Em **Escopos**, adicionar `.../auth/youtube.upload` e `.../auth/youtube.readonly`. Em **Usuários de teste**, adicionar gravasimples@gmail.com.
   - Enquanto o app estiver em "Teste", o token de atualização vence em 7 dias (aí é só clicar em Conectar de novo). Para não vencer: Publicar o app ("Em produção"). O Google mostra um aviso de "app não verificado" na hora de conectar; para uso próprio basta clicar em Avançado → Continuar.
4. APIs e serviços → **Credenciais** → Criar credenciais → **ID do cliente OAuth** → tipo **Aplicativo da Web** → nome "Editor GS gateway" → em URIs de redirecionamento autorizados, colar:
   `https://<seu-endereco-publico>/api/gs/youtube/callback` (ou `http://127.0.0.1:3200/api/gs/youtube/callback` para conectar pelo próprio computador)
   → Criar → copiar o ID do cliente e a chave secreta.
5. No `.env` do Editor GS (`~/EditorGS/.env` quando instalado como plugin), acrescentar:
   ```
   YT_CLIENT_ID=cole-o-id-aqui.apps.googleusercontent.com
   YT_CLIENT_SECRET=cole-a-chave-secreta-aqui
   ```
   `EDITOR_GS_URL_PUBLICA` precisa estar com o mesmo endereço usado no redirecionamento.
6. Reiniciar o gateway (matar o uvicorn da porta 3200 e rodar `servico/rodar.sh`). No app: **Estilos → Conectar YouTube** (abre o Google, autoriza, volta). O app passa a mostrar o canal conectado.

## No dia a dia

No cartão da entrega → **Publicar e guardar → YouTube**: escolhe o arquivo (16:9 para vídeo normal, 9:16 vira Short automaticamente), título (até 100 caracteres; vem do `## Título (YouTube)` da mensagem), descrição (vem da legenda do post), tags, privacidade (privado, não listado ou público) e, se quiser, data e hora para agendar (o vídeo sobe privado e o YouTube publica sozinho na hora marcada). A capa vai junto quando o canal tem capa personalizada liberada (canal verificado por telefone); se o YouTube recusar, o histórico avisa.

O histórico da entrega mostra o link `youtu.be/...` e o status; "Atualizar status" consulta a API (views, likes, agendamento).

## Limites

- Cota diária de 10.000 unidades: ~6 uploads por dia; o contador zera à meia-noite do Pacífico.
- Capa personalizada só em canal verificado.
- Shorts: o YouTube decide pelo vídeo (vertical, até 3 min). Não há campo para forçar.
- Nada aqui lê comentários nem responde: isso continua no GSI (leitura) e humano (resposta).
