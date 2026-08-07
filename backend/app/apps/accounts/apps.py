from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Configuração do aplicativo de contas.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Contas"