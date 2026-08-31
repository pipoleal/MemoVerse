from decimal import Decimal

from django.db import migrations

# Novo plano comercial: "1 Dia", mais barato que o semanal (Etapa: Planos —
# pedido explícito do produto). Mesmo padrão de 0005_seed_commercial_plans:
# duration_days/is_lifetime/galaxy_live_enabled vivem em Plan.features (JSON),
# nenhuma coluna nova. is_lifetime=False + duration_days=1 é lido por
# PublicationService._compute_expires_at exatamente como o plano "weekly".
#
# highlights segue o mesmo BASE_HIGHLIGHTS de 0006_add_plan_highlights (lista
# resolvida e gravada por completo, nunca uma referência a outro plano).
BASE_HIGHLIGHTS = [
    "Experiência personalizada",
    "Fotos e vídeos",
    "Carta personalizada",
    "Música",
    "Link compartilhável",
]

DAILY_PLAN = {
    "code": "daily",
    "name": "MemoVerse 1 Dia",
    "price": Decimal("9.90"),
    "currency": "BRL",
    "features": {
        "duration_days": 1,
        "is_lifetime": False,
        "galaxy_live_enabled": False,
        "highlights": BASE_HIGHLIGHTS + ["Disponível por 1 dia"],
    },
}


def seed_daily_plan(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")

    # get_or_create por `code` torna a migration segura de reexecutar, mesmo
    # padrão de 0005/0002.
    Plan.objects.get_or_create(
        code=DAILY_PLAN["code"],
        defaults={
            "name": DAILY_PLAN["name"],
            "price": DAILY_PLAN["price"],
            "currency": DAILY_PLAN["currency"],
            "features": DAILY_PLAN["features"],
            "is_active": True,
        },
    )


def deactivate_daily_plan(apps, schema_editor):
    # Reverse simétrico: nunca apaga o Plan (mesma razão de 0005 — Payment.plan
    # é on_delete=PROTECT, e qualquer Payment já criado contra "daily" ficaria
    # órfão de FK). Só desativa, tirando-o de circulação em
    # PlanListView/CheckoutRequestSerializer.
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code=DAILY_PLAN["code"]).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0010_plandiscount"),
    ]

    operations = [
        migrations.RunPython(seed_daily_plan, deactivate_daily_plan),
    ]
