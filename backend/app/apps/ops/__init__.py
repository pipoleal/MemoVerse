"""Backend do painel administrativo (frontend em /admin) — nasceu na
Etapa 9B.4 como os 3 relatórios de lifecycle/reconciliação, e agora também
serve as listagens (usuários/experiências/pagamentos/logs), o detalhe de
experiência (moderação) e o snapshot de configuração. Toda view exige
IsAuthenticated + IsProductionAdmin (ver apps.accounts.permissions), sem
exceção.

Quase tudo é GET-only. 2 exceções, explicitamente autorizadas pelo dono do
produto: excluir um usuário (UserDeleteView, só quando não há NENHUM
Payment associado) e cancelar localmente um Payment ainda ativo
(PaymentCancelView) — ver os docstrings dessas duas classes em views.py
para as salvaguardas completas. Nenhuma escreve na Mercado Pago; histórico
financeiro nunca é apagado.

Não tem nenhum model (logo, nenhuma migration). Nenhum outro app depende
dele.
"""
