# MemoVerse — Arquitetura (fatos confirmados)

> Atualize este arquivo apenas com fatos verificados no código, nunca com suposições.

## Backend (`backend/app/`)

- Django + Django REST Framework.
- `apps/experiences/`
  - Model `ExperienceDraft` com campos `slug` e `published_at` (migration `0002_experiencedraft_published_at_experiencedraft_slug.py`).
  - Endpoints confirmados por commits: draft CRUD, upload de mídia (`media/upload-intents/`), leitura presigned GET de mídia R2, endpoint público de experiência, endpoint de publicação (draft pago → publicado).
- `apps/payments/`
  - `backend/app/apps/payments/services/checkout_service.py` — `CheckoutService.start_checkout(draft, plan, mp_client=None)`.
    - Ponto de atenção conhecido: a linha `mp_client=mp_client or MercadoPagoClient()` roda **fora** do bloco `try/except MercadoPagoClientError`, então `MercadoPagoConfigurationError` (ex.: `MP_ACCESS_TOKEN` não configurado) não é convertida em `CheckoutGatewayError` — a view retorna 500 cru em vez do 502 esperado. Confirmado via log real (`backend/app/apps/payments/services/mercadopago_client.py:85`).
  - `backend/app/apps/payments/views/checkout.py` — `DraftCheckoutView.post` chama `CheckoutService.start_checkout`.
  - Webhook do Mercado Pago: `notification_id` foi tornado opcional (commit `66bf880`) para respeitar o contrato real da Orders API.
  - Infraestrutura de teste "Sandbox APRO TEST-ONLY" foi adicionada e depois **removida** do código de produção (commits `efe3e1c`, `2f26370`, `7617832`, `bcc31ad`, `58ce35e`) — não deve haver resquício disso em `apps/payments` ou `apps/accounts` fora de testes explícitos.
- `apps/accounts/` — autenticação de usuário.

## Frontend (`frontend/`)

- Next.js App Router, React 19.2.8.
- `app/e/[slug]/page.tsx` → renderiza `components/public/PublicExperienceView.tsx`.
  - **Bug conhecido e confirmado (não corrigido ainda):** a página fica presa em "Carregando experiência..." indefinidamente. Causa raiz: o `useEffect` combina uma guarda `hasFetchedRef` (persiste entre montagens do React StrictMode) com uma flag interna `cancelled` de cleanup — a segunda montagem (StrictMode) seta `cancelled = true` no cleanup da primeira, e o resultado do fetch real (que só roda na segunda montagem, pois a guarda bloqueia a primeira) é descartado porque `cancelled` já está `true`. Reproduzido 3 vezes, incluindo com o backend retornando 404 corretamente — é 100% um bug de frontend, independente do estado do backend/banco.
- `components/experience-view/ExperienceViewer.tsx` — tornado reutilizável via props (commit `80b06dd`) para ser compartilhado entre o wizard de criação e a página pública.
- `components/checkout/CheckoutView.tsx` — inclui o botão de publicação (commit `f8b89bc`), chama `frontend/lib/publish.ts::publishDraft()`.
- `frontend/lib/publish.ts` — `POST /experiences/drafts/<id>/publish/`, idempotente no backend (republicar um draft já publicado retorna o mesmo slug, sem novo efeito colateral).
- `components/auth/LoginForm.tsx` — problema conhecido (não corrigido): quando o login retorna 200 mas uma chamada subsequente (`savePendingExperienceDraft()`) falha com 500, a mensagem de erro genérica mostrada ao usuário sugere credenciais erradas, o que é enganoso.

## Migrações

- `apps/experiences/migrations/0002_experiencedraft_published_at_experiencedraft_slug.py` precisa estar aplicada (`python manage.py migrate experiences`) para o fluxo de criação de rascunho funcionar localmente — sem isso, ocorre `no such column: experience_drafts.slug`.
