# MemoVerse — Contexto do Projeto

> Este arquivo é consumido por ferramentas de IA (Claude, GPT via orquestrador). Mantenha-o factual — apenas o que está confirmado no repositório. Não é documentação voltada a humanos (para isso, ver `docs/00-*` a `docs/08-*`).

## O que é

MemoVerse é uma plataforma onde um usuário cria uma "experiência" (memória) — texto, fotos, vídeo, música — paga por ela via checkout, e recebe uma página pública compartilhável (`/e/<slug>`) depois da publicação.

## Fluxo principal (confirmado via teste E2E)

1. Registro / login (`/register`, `/login`)
2. Criação de rascunho de experiência (wizard multi-step: tipo, informações, carta, música, estilo)
3. Upload de mídia (fotos/vídeo) via URL pré-assinada do Cloudflare R2
4. Checkout (Pix via Mercado Pago)
5. Pagamento confirmado via webhook do Mercado Pago
6. Publicação do rascunho (`POST /api/experiences/drafts/<id>/publish/`) → gera `slug`
7. Página pública em `/e/<slug>` renderiza a experiência (`PublicExperienceView.tsx`)

## Stack confirmada

- **Backend:** Django (projeto em `backend/app/`), Django REST Framework
- **Frontend:** Next.js (App Router) em `frontend/`, React 19
- **Pagamento:** Mercado Pago (Pix), integração em `backend/app/apps/payments/`
- **Storage de mídia:** Cloudflare R2 (uploads via presigned URL)
- **Banco local:** SQLite (`db.sqlite3`) — dev apenas; `PROJECT.md` cita PostgreSQL como alvo de produção
- **Outros itens citados em `PROJECT.md`** (não confirmados em código ainda): Redis, Celery

## Apps Django confirmados

- `apps.accounts` — autenticação/usuário
- `apps.payments` — checkout, `CheckoutService`, `MercadoPagoClient`, webhook
- `apps.experiences` — `ExperienceDraft` (campos incluindo `slug`, `published_at`), endpoints de draft/upload/publish/público

## Ambiente de desenvolvimento local

- Não existem arquivos `.env` reais no backend nem no frontend nesta máquina de desenvolvimento — apenas `.env.example`. Isso significa que credenciais externas (Mercado Pago `MP_ACCESS_TOKEN`, credenciais R2) **não estão configuradas localmente** por padrão. Isso é esperado, não é um bug de código.
- `backend/.venv/Scripts/python.exe` é o Python do projeto backend.
- Python 3.13 do sistema está disponível em `C:\Users\felip\AppData\Local\Programs\Python\Python313\python.exe`.
- Node.js v24 está disponível no PATH.
