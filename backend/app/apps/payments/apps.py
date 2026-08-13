from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """
    Configuração do aplicativo de pagamentos.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Pagamentos"
