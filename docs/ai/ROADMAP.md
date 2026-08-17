# MemoVerse — Roadmap (visão da IA)

> Lista de itens conhecidos, derivados de trabalho já feito e bugs já diagnosticados nesta sessão. Não é uma lista de prioridades de negócio — isso é decisão do usuário. Atualize conforme tarefas forem concluídas ou novas forem identificadas.

## Itens pendentes conhecidos

- [ ] Corrigir o bug de carregamento infinito em `PublicExperienceView.tsx` (ver `docs/ai/CURRENT_STATE.md` e `docs/ai/ARCHITECTURE.md`).
- [x] Corrigir o tratamento de exceção em `CheckoutService.start_checkout` para que `MercadoPagoConfigurationError` vire `CheckoutGatewayError` (502) em vez de vazar como 500.
- [ ] Revisar a mensagem de erro em `LoginForm.tsx` para não implicar "credenciais erradas" quando o login em si teve sucesso.
- [ ] Testar upload real de vídeo (não testado ainda — sem `ffmpeg`/ativo de teste disponível no ambiente).
- [ ] Configurar credenciais reais (`MP_ACCESS_TOKEN`, R2) em `.env` local quando for necessário testar o fluxo de pagamento/upload real de ponta a ponta.

## Fora de escopo aqui

Prioridades de produto e sprint ficam em `PROJECT.md` e `docs/06-roadmap/` (ainda vazio) — este arquivo é só o que a IA sabe estar tecnicamente pendente.
