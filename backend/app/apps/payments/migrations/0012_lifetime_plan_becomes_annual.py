from django.db import migrations

# Decisão de produto: só o plano PREMIUM (lifetime_galaxy) pode ser
# genuinamente vitalício. O plano "normal" (code="lifetime" — o slug
# permanece por compatibilidade com Payment.plan/testes existentes, só o
# conteúdo comercial muda) passa a expirar 1 ano após a publicação, do
# mesmo jeito que "weekly" expira em 7 dias — ver
# PublicationService._compute_expires_at, que já lê duration_days/
# is_lifetime de Plan.features sem nenhuma mudança de código necessária.
#
# Isso também aposenta o hack de apresentação em frontend/lib/checkout.ts
# (displayPlanName/displayPlanHighlight trocavam "Vitalício"->"Anual" e
# "para sempre"->"por 1 ano" só na tela, mantendo os dois planos
# genuinamente vitalícios por baixo). Agora o texto gravado no banco já é
# o texto real: "lifetime" vira honestamente anual, "lifetime_galaxy"
# continua honestamente vitalício — nenhuma tradução de apresentação
# necessária.
BASE_HIGHLIGHTS = [
    "Experiência personalizada",
    "Fotos e vídeos",
    "Carta personalizada",
    "Música",
    "Link compartilhável",
]

NEW_NAME = "MemoVerse Anual"
NEW_FEATURES = {
    "duration_days": 365,
    "is_lifetime": False,
    "galaxy_live_enabled": False,
    "highlights": BASE_HIGHLIGHTS + ["Disponível por 1 ano"],
}

OLD_NAME = "MemoVerse Vitalício"
OLD_FEATURES = {
    "duration_days": None,
    "is_lifetime": True,
    "galaxy_live_enabled": False,
    "highlights": BASE_HIGHLIGHTS + ["Disponível para sempre"],
}


def make_lifetime_plan_annual(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code="lifetime").update(name=NEW_NAME, features=NEW_FEATURES)


def revert_lifetime_plan_to_forever(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    Plan.objects.filter(code="lifetime").update(name=OLD_NAME, features=OLD_FEATURES)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0011_seed_daily_plan"),
    ]

    operations = [
        migrations.RunPython(make_lifetime_plan_annual, revert_lifetime_plan_to_forever),
    ]
