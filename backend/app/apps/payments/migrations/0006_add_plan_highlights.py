from django.db import migrations

# Etapa 3 (Planos + Checkout): diferenciais comerciais dos 3 planos, prontos
# para renderização direta pelo frontend — cada lista já é o texto final que
# aparece nos cards, sem "Tudo do plano X" (cada plano deve ser compreensível
# sozinho). Só Plan.features["highlights"] muda aqui; duration_days/
# is_lifetime/galaxy_live_enabled (usados por lógica de negócio real —
# PublicationService._compute_expires_at e o entitlement da Galáxia Viva)
# são preservados exatamente como estão.
#
# BASE_HIGHLIGHTS existe só para não copiar/colar os 5 itens comuns três
# vezes neste arquivo — o valor gravado no banco para cada plano já é a
# lista completa e resolvida, nunca uma referência a outro plano.
BASE_HIGHLIGHTS = [
    "Experiência personalizada",
    "Fotos e vídeos",
    "Carta personalizada",
    "Música",
    "Link compartilhável",
]

PLAN_HIGHLIGHTS = {
    "weekly": BASE_HIGHLIGHTS + ["Disponível por 7 dias"],
    "lifetime": BASE_HIGHLIGHTS + ["Disponível para sempre"],
    "lifetime_galaxy": BASE_HIGHLIGHTS
    + ["Disponível para sempre", "Galáxia Viva", "Recursos especiais da Galáxia Viva"],
}


def add_highlights_to_existing_plans(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")

    for code, highlights in PLAN_HIGHLIGHTS.items():
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            # Defensivo: nunca deveria acontecer (0005 já garante que esses
            # 3 planos existem antes desta migration rodar), mas não é papel
            # desta migration criar planos — só enriquecer os já existentes.
            continue
        # Mescla — nunca sobrescreve duration_days/is_lifetime/
        # galaxy_live_enabled, só adiciona/atualiza a chave highlights.
        plan.features = {**plan.features, "highlights": highlights}
        plan.save(update_fields=["features"])


def remove_highlights(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")

    for code in PLAN_HIGHLIGHTS:
        plan = Plan.objects.filter(code=code).first()
        if plan is None:
            continue
        features = dict(plan.features)
        features.pop("highlights", None)
        plan.features = features
        plan.save(update_fields=["features"])


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0005_seed_commercial_plans"),
    ]

    operations = [
        migrations.RunPython(add_highlights_to_existing_plans, remove_highlights),
    ]
