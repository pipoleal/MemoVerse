# MemoVerse — Decisões Arquiteturais (log)

> Registro de decisões confirmadas por commits/código, não interpretações. Formato: data aproximada (via commit), decisão, por quê (quando conhecido), commit(s).

## Infraestrutura de teste "Sandbox APRO" removida do código de produção

Uma infraestrutura de teste TEST-ONLY relacionada ao Sandbox APRO (Mercado Pago) foi adicionada e depois deliberadamente removida dos apps `payments` e `accounts`, incluindo uma migration one-off "gated" de teste e dados de teste associados.

Commits: `efe3e1c` (chore: remove Sandbox APRO TEST-ONLY infrastructure), `2f26370` (fix: remove sandbox-apro-runner's test Payment/Draft before the account), `7617832` (chore: remove temporary webhook diagnostic logging), `bcc31ad` (test: add gated one-off migration for Sandbox APRO checkout test), `58ce35e` (chore: remove Sandbox APRO migration test data).

**Implicação para IA:** não reintroduzir infraestrutura de teste específica do Sandbox APRO em código de produção. Se testes desse tipo forem necessários novamente, mantê-los claramente isolados/gated e removíveis.

## `notification_id` do webhook do Mercado Pago tornado opcional

Commit `66bf880` — o campo `notification_id` foi tornado opcional no processamento do webhook para respeitar o contrato real da Orders API do Mercado Pago (o campo nem sempre vem preenchido).

## `ExperienceViewer` tornado reutilizável via props

Commit `80b06dd` — o componente que renderiza a experiência foi refatorado para aceitar dados via props, permitindo reuso tanto no wizard de criação quanto na página pública `/e/[slug]`.

## Publicação de rascunho é idempotente

`POST /experiences/drafts/<id>/publish/` — republicar um draft já publicado retorna o mesmo slug sem novo efeito colateral (decisão de design confirmada em `frontend/lib/publish.ts` e no comportamento do backend).
