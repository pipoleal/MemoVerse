"""Etapa 9B.4 — painel administrativo read-only, exclusivamente para gerar
os relatórios de lifecycle/reconciliação em ambientes sem acesso a shell
(ex.: produção no Render sem Render Shell disponível).

Este app existe só enquanto durar a 9B.4. Não tem nenhum model (logo,
nenhuma migration) — remover depois é: apagar este diretório, tirar
"apps.ops" de INSTALLED_APPS e o include() correspondente de config/urls.py.
Nenhum outro app depende dele.
"""
