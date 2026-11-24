# Abrir o carrossel editável direto no Canva (Canva Connect)

Atualizado: 29/10/2026. Com a integração conectada, o botão **Abrir no Canva** no cartão de entrega importa o `carrossel.pptx` (ou o PDF) pela API oficial e abre o design já editável, como o botão do CapCut faz com o vídeo. Sem a integração, continua valendo baixar o arquivo e importar à mão.

## Por que Connect e não Funnel
A importação por URL também exige um app Connect; o Funnel só deixaria o arquivo público. Com o Connect o arquivo sobe direto do gateway (binário), sem expor nada.

## Criar a integração (uma vez, com o login do Canva da Grava Simples)
1. https://www.canva.com/developers → **Your integrations** → **Create an integration** → tipo **Public** não é preciso: escolha **Private** (só para a sua equipe) se aparecer; nome "Editor GS".
2. Em **Configuration → Scopes**, marcar: `design:content:write` e `design:meta:read`.
3. Em **Authentication → Redirect URLs**, adicionar exatamente: `https://<seu-endereco-publico>/api/gs/canva/callback` (e, se for conectar pelo próprio computador, também `http://127.0.0.1:3200/api/gs/canva/callback`).
4. Em **Credentials**, copiar o **Client ID** e gerar o **Client secret**.
5. No `.env` do Editor GS (`~/EditorGS/.env` quando instalado como plugin):
   ```
   CANVA_CLIENT_ID=...
   CANVA_CLIENT_SECRET=...
   EDITOR_GS_URL_PUBLICA=https://<seu-endereco-publico>
   ```
   Nunca colar as credenciais no chat.
6. Reiniciar o gateway. No app → **Estilos** → **Conectar Canva** → autorizar na tela do Canva. O token fica em `servico/canva_token.json` (fora do git) e renova sozinho (acesso de 4 h, refresh automático).

## Uso
- Cartão de entrega → **Abrir no Canva**: importa e abre. Cada importação cria um design novo; os links ficam listados no cartão (válidos por 30 dias; reimportar gera outro).
- Formatos aceitos pela importação: PPTX e PDF (também DOCX, PSD, AI). Limite de 20 importações por minuto.

## Se der erro
- "Canva não conectado": clicar em Conectar Canva.
- "Canva refresh 400": o refresh token venceu ou foi revogado; reconectar.
- Fontes: o PPTX usa Inter pelo nome (o Canva tem Inter); o PDF leva a Inter embutida.
