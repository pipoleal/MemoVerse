from decimal import Decimal

from django.db import migrations

INITIAL_PLANS = [
    {
        "code": "essential",
        "name": "MemoVerse Essencial",
        "price": Decimal("29.99"),
        "currency": "BRL",
        "features": {"stars_enabled": False},
    },
    {
        "code": "stellar",
        "name": "MemoVerse Estelar",
        "price": Decimal("39.99"),
        "currency": "BRL",
        "features": {"stars_enabled": True},
    },
]


def seed_initial_plans(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")

    for plan_data in INITIAL_PLANS:
        # get_or_create por `code` torna a migration segura de reexecutar:
        # se um Plan com esse code já existir (nesta ou em outra execução),
        # nenhum duplicado é criado e os dados existentes não são sobrescritos.
        Plan.objects.get_or_create(
            code=plan_data["code"],
            defaults={
                "name": plan_data["name"],
                "price": plan_data["price"],
                "currency": plan_data["currency"],
                "features": plan_data["features"],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        # Reverse intencionalmente é um no-op: desfazer a semeadura de planos
        # poderia colidir com Payment.plan (on_delete=PROTECT) em ambientes
        # onde já existam pagamentos referenciando esses planos.
        migrations.RunPython(seed_initial_plans, migrations.RunPython.noop),
    ]
