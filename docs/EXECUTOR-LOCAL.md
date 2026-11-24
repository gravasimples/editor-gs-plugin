# Executor local (sem Paperclip) — 10/11/2026

## O que é
Até 09/11 cada pedido do app virava uma issue no Paperclip (porta 3100, Postgres embutido, login próprio da assinatura), e o Paperclip chamava o `claude`. Desde 10/11 o próprio gateway faz isso: `servico/executor_local.py` guarda fila, conversas, comentários, rodadas e decisões em SQLite (`workspace/executor/executor.db`) e roda o agente direto com `claude -p` (stream-json), usando `workspace/AGENTS.md` como system prompt e o MCP `editor-de-video`.

O que não mudou: o app, o `AGENTS.md`, os fluxos, as ferramentas e os 76 pontos do gateway que falavam com o Paperclip. O executor expõe as mesmas rotas e os mesmos campos (`/api/companies/{id}/issues`, `/api/issues/{id}`, `/comments`, `/runs`, `/interactions`, `/api/heartbeat-runs/{id}/cancel|log`, `/api/companies/{id}/agents`, `/api/health`). O gateway chama em processo (`_pc` → `EXECUTOR.chamar`); o agente chama por HTTP no próprio gateway (`PAPERCLIP_API_URL=http://127.0.0.1:3200`), como fazia antes.

## Ligar e desligar
`servico/config.json → executor.modo`: `"local"` (atual) ou `"paperclip"` (modo antigo, ainda funciona se o Paperclip estiver no ar). Mudou o modo → `bash scripts/subir.sh` (no modo local ele não sobe o Paperclip).

Config do bloco `executor`: `max_simultaneos` (1: GPU e cota), `tentativas` (2: falha volta à fila, depois `blocked` com o motivo em comentário), `timeout_s` (3 h), `intervalo_s` (2 s), `agentes` (id, nome, motor `claude`, modelo, `effort`, `env` como `CLAUDE_CONFIG_DIR` para agente por pessoa, `comando` para trocar o binário). Os ids dos agentes são os mesmos do Paperclip, por isso `conversas.json` e o histórico continuam válidos.

## Ciclo de um pedido
1. App cria a issue (`todo`) com `assigneeAgentId`.
2. Laço (a cada 2 s) pega a mais antiga em `todo` com agente configurado, cria a rodada (`running`), põe a issue em `in_progress` e dispara `claude --print --output-format stream-json --verbose --dangerously-skip-permissions --append-system-prompt-file workspace/AGENTS.md --model <modelo> --mcp-config workspace/.mcp.json --strict-mcp-config`, cwd `workspace/`, prompt pelo stdin com: pedido, conversa inteira em ordem, decisões pendentes, API local e a regra de entrega ("sua mensagem final é a entrega").
3. Durante a rodada o agente posta plano e avisos por `POST /api/issues/{id}/comments` (atribuído ao agente porque a issue tem rodada ativa) e pede aprovação por `POST /api/issues/{id}/interactions`.
4. Fim da rodada: `result` do stream-json → se o texto final tem conteúdo e o agente não postou o mesmo, vira comentário do agente; com interaction pendente a issue fica `in_progress` sem rodada (aguardando a pessoa); senão `in_review`. Falha/`is_error`/tempo esgotado → volta à fila até `tentativas`, depois `blocked` + comentário (a reserva automática do gateway continua valendo).
5. Decisão no app (aceitar/recusar/responder) vira comentário da pessoa e devolve a issue à fila (`wake_assignee`). Parar cancela o processo (grupo inteiro) e o app deixa em `blocked`; Retomar devolve a `todo`.

Logs: `workspace/executor/run-logs/<run>.ndjson` (linhas `{"chunk": <evento stream-json>}` e `{"stderr": ...}`), no formato que a rede de segurança de mensagem final já lia. Rodadas que ficaram `running` quando o gateway caiu voltam à fila na subida (`recuperar_orfas`).

## Migração feita em 10/11
`python -m servico.executor_local importar` (Paperclip no ar) copiou 52 issues, 176 comentários, 120 rodadas (com `logRef` para os logs antigos em `~/.paperclip/...`) e 17 interactions; numeração continua (GRA-53 foi o primeiro pedido local). Issues `in_progress` com interaction pendente continuaram `in_progress` (GRA-52, aguardando o Raphael aprovar o corte de 30%); sem interaction voltariam para `todo`. Depois: Paperclip desligado, `executor.modo=local`, gateway religado, validação real com GRA-53 (info() de um vídeo: 14 s, 4 turnos, US$ 0,38, plano postado pela rota HTTP, entrega em `in_review`).

Motores: `claude` e, desde 10/11 (3h30), `codex` (`codex exec --json --dangerously-bypass-approvals-and-sandbox -C workspace -o <run>.ultima.txt -m <modelo>`, MCP passado por `-c mcp_servers...` a partir do `workspace/.mcp.json`; o Codex lê o `AGENTS.md` da pasta sozinho; eventos `item.completed/agent_message`, `turn.completed` (uso), `turn.failed` (falha); a mensagem final vem do arquivo `-o`). Gemini (Antigravity) ficou sem adaptador (`executor.agentes_sem_adaptador.gemini`); as ferramentas Gemini do MCP continuam.

## Comandos
- `python -m servico.executor_local status | fila | importar` (na raiz, sem `-I`).
- `bash scripts/editor-gs.sh status` (porta única: instalar, subir, parar, status, abrir, caminhos).
- Testes: `~/.venvs/editor-gs/bin/python -I testes/teste_executor_local.py` (48 verificações, claude falso em pasta temporária).

## Limites conhecidos
- `max_simultaneos=1` global: agente por pessoa (Thiago) espera o anterior terminar.
- Sem `--max-turns`: uma rodada longa só para por tempo (`timeout_s`) ou pelo botão Parar.
- O Paperclip ainda existe em `~/.paperclip` (741 MB) como histórico; pode ser apagado depois de uma semana sem necessidade de consulta aos logs antigos.
