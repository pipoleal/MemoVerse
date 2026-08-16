# MemoVerse — Estado Atual

> Atualizado manualmente / pelo orquestrador. Reflete o estado no momento da última atualização — sempre confira `git log` / `git status` antes de confiar cegamente neste arquivo se ele parecer desatualizado.

**Última atualização:** 2026-08-16
**HEAD no momento da criação deste arquivo:** `f8b89bc` (branch `master`)

## Bugs confirmados, não corrigidos

1. **`PublicExperienceView.tsx` fica preso em "Carregando experiência..." indefinidamente.**
   Causa raiz diagnosticada (não corrigida): interação entre `hasFetchedRef` e uma flag `cancelled` dentro do mesmo `useEffect`, agravada pelo StrictMode do React. Ver `docs/ai/ARCHITECTURE.md`.
2. **Checkout retorna 500 cru em vez de 502 quando `MP_ACCESS_TOKEN` não está configurado.**
   Causa raiz diagnosticada (não corrigida): construção de `MercadoPagoClient()` fora do bloco `try/except` em `CheckoutService.start_checkout`.
3. **Mensagem de erro de login enganosa** quando o login em si funciona (200) mas uma chamada subsequente falha (500) — a UI sugere "credenciais erradas" incorretamente.

## Bloqueios de ambiente local (não são bugs de código)

- `MP_ACCESS_TOKEN` não configurado localmente → checkout real não pode ser testado ponta a ponta sem essa credencial.
- Credenciais do Cloudflare R2 não configuradas localmente → upload de mídia real falha graciosamente (502), mas não pode ser testado de ponta a ponta.
- Nenhum arquivo `.env` real existe no backend nem no frontend nesta máquina — apenas `.env.example`.

## Confirmado funcionando (testado via E2E no navegador)

- Registro, login
- Criação de rascunho de experiência (após aplicar a migration `0002` do app `experiences`)
- Dashboard
- Redirecionamento para checkout
- Backend retorna 404 corretamente para slug inexistente em `/api/public/experiences/<slug>/`

## Commits recentes (mais novo primeiro)

```
f8b89bc feat(checkout): add experience publication flow
c09b322 feat(experience): add public experience page
80b06dd refactor(experience): allow viewer to render via props
46dfec7 feat(experiences): add public experience endpoint
0172098 feat(experiences): add presigned GET URL generation for R2 media reads
e46c5f6 feat(experiences): add draft publication endpoint (paid -> published)
ffb0e76 feat(frontend): add checkout/Pix payment screen
```
