from decimal import Decimal

from django.db import migrations

# TEMPORÁRIO — mesmo padrão de 0007_temp_weekly_price_for_checkout_testing,
# agora para "lifetime_galaxy" (Galáxia Viva): compra real em produção para
# QA manual do fluxo GalaxiaViva.tsx de ponta a ponta (checkout -> webhook
# -> publish -> /dashboard/galaxia-viva). Só o preço deste plano muda:
# 39.90 -> 0.10. Nenhum outro plano, nenhuma coluna nova, nenhuma mudança de
# schema. Reverter esta migration (voltar para 0007) restaura 39.90.
#
# Payment.amount continua congelado a partir de Plan.price no momento da
# criação (ver CheckoutService._create_attempt) — pagamentos já existentes
# não são afetados, só novas tentativas de checkout a partir de agora.
TEMP_PRICE = Decimal("0.10")
ORIGINAL_PRICE = Decimal("39.90")


def set_temp_price(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code="lifetime_galaxy").update(price=TEMP_PRICE)


def restore_original_price(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code="lifetime_galaxy").update(price=ORIGINAL_PRICE)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0007_temp_weekly_price_for_checkout_testing"),
    ]

    operations = [
        migrations.RunPython(set_temp_price, restore_original_price),
    ]
