"""Backend read-only do painel administrativo (frontend em /admin) —
nasceu na Etapa 9B.4 como os 3 relatórios de lifecycle/reconciliação, e
agora também serve as listagens (usuários/experiências/pagamentos/logs) e
o snapshot de configuração que o painel consome. Toda view aqui é GET-only
e exige IsAuthenticated + IsProductionAdmin (ver
apps.accounts.permissions) — nenhuma exceção, nenhuma mutação.

Não tem nenhum model (logo, nenhuma migration). Nenhum outro app depende
dele.
"""
