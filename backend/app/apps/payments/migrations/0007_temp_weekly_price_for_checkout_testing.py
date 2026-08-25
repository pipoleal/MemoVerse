from decimal import Decimal

from django.db import migrations

# TEMPORÁRIO — ambiente de testes reais de checkout (Etapa de QA manual).
# Só o preço do plano "weekly" (o primeiro na ordenação por price, ver
# Plan.Meta.ordering) é alterado: 19.90 -> 0.10. Nenhum outro plano, nenhuma
# coluna nova, nenhuma mudança de schema. Reverter esta migration (ou
# reaplicar o forward com o valor original) restaura 19.90.
#
# Payment.amount continua congelado a partir de Plan.price no momento da
# criação (ver CheckoutService._create_attempt) — pagamentos já existentes
# não são afetados, só novas tentativas de checkout a partir de agora.
TEMP_PRICE = Decimal("0.10")
ORIGINAL_PRICE = Decimal("19.90")


def set_temp_price(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code="weekly").update(price=TEMP_PRICE)


def restore_original_price(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code="weekly").update(price=ORIGINAL_PRICE)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0006_add_plan_highlights"),
    ]

    operations = [
        migrations.RunPython(set_temp_price, restore_original_price),
    ]
