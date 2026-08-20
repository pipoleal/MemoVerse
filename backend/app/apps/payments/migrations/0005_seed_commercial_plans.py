from decimal import Decimal

from django.db import migrations

# Etapa 3 do roadmap (Planos + Checkout): os 3 planos comerciais atuais.
# duration_days/is_lifetime/galaxy_live_enabled vivem em Plan.features (JSON)
# — nenhuma coluna nova em Plan é necessária. is_lifetime é a fonte de
# verdade sobre expiração (ver PublicationService._compute_expires_at);
# duration_days só é lido quando is_lifetime é False.
NEW_PLANS = [
    {
        "code": "weekly",
        "name": "MemoVerse 1 Semana",
        "price": Decimal("19.90"),
        "currency": "BRL",
        "features": {"duration_days": 7, "is_lifetime": False, "galaxy_live_enabled": False},
    },
    {
        "code": "lifetime",
        "name": "MemoVerse Vitalício",
        "price": Decimal("29.90"),
        "currency": "BRL",
        "features": {"duration_days": None, "is_lifetime": True, "galaxy_live_enabled": False},
    },
    {
        "code": "lifetime_galaxy",
        "name": "MemoVerse Vitalício + Galáxia Viva",
        "price": Decimal("39.90"),
        "currency": "BRL",
        "features": {"duration_days": None, "is_lifetime": True, "galaxy_live_enabled": True},
    },
]

# Não apagados: Payment.plan é on_delete=PROTECT, e pagamentos históricos já
# existentes continuam referenciando essential/stellar. Só deixam de ser
# compráveis (is_active=False) — CheckoutRequestSerializer.validate_plan_code
# já filtra por is_active=True, então isso basta para tirá-los de circulação
# sem quebrar nenhum Payment/relatório histórico.
LEGACY_PLAN_CODES = ["essential", "stellar"]


def seed_new_plans_and_deactivate_legacy(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")

    for plan_data in NEW_PLANS:
        # get_or_create por `code` torna a migration segura de reexecutar,
        # mesmo padrão de 0002_seed_initial_plans.
        Plan.objects.get_or_create(
            code=plan_data["code"],
            defaults={
                "name": plan_data["name"],
                "price": plan_data["price"],
                "currency": plan_data["currency"],
                "features": plan_data["features"],
                "is_active": True,
            },
        )

    Plan.objects.filter(code__in=LEGACY_PLAN_CODES).update(is_active=False)


def reactivate_legacy_and_deactivate_new(apps, schema_editor):
    # Reverse simétrico: nunca apaga nenhum Plan (mesma razão de
    # 0002_seed_initial_plans — PROTECT em Payment.plan). Só desfaz o
    # is_active dos dois lados, deixando os 3 planos novos no banco porém
    # inativos, do jeito que estariam se esta migration nunca tivesse rodado.
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code__in=LEGACY_PLAN_CODES).update(is_active=True)
    Plan.objects.filter(code__in=[p["code"] for p in NEW_PLANS]).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_alter_payment_idempotency_key"),
    ]

    operations = [
        migrations.RunPython(seed_new_plans_and_deactivate_legacy, reactivate_legacy_and_deactivate_new),
    ]
