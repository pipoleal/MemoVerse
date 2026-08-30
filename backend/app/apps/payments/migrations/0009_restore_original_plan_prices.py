from decimal import Decimal

from django.db import migrations

# Fim da etapa de QA manual de checkout. Restaura os preços originais dos
# planos "weekly" e "lifetime_galaxy" que 0007/0008 haviam temporariamente
# baixado para 0.10 (compra real em produção para testar o fluxo ponta a
# ponta). Nenhum outro plano, nenhuma coluna nova, nenhuma mudança de schema.
#
# Payment.amount continua congelado a partir de Plan.price no momento da
# criação (ver CheckoutService._create_attempt) — pagamentos já existentes
# (inclusive os de 0.10 feitos durante o QA) não são afetados, só novas
# tentativas de checkout a partir de agora.
ORIGINAL_PRICES = {
    "weekly": Decimal("19.90"),
    "lifetime_galaxy": Decimal("39.90"),
}
TEMP_PRICE = Decimal("0.10")


def restore_original_prices(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    for code, price in ORIGINAL_PRICES.items():
        Plan.objects.filter(code=code).update(price=price)


def set_temp_prices(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code__in=ORIGINAL_PRICES.keys()).update(price=TEMP_PRICE)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0008_temp_lifetime_galaxy_price_for_checkout_testing"),
    ]

    operations = [
        migrations.RunPython(restore_original_prices, set_temp_prices),
    ]
