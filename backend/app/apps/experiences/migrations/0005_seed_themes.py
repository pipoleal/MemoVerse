from django.db import migrations

# Etapa 4 (Sistema de Temas Real): os 6 temas já em uso hoje pelo wizard —
# mesmos códigos exatos já gravados em ExperienceDraft.theme por drafts e
# experiências publicadas existentes (StyleStep.tsx era, até agora, a única
# fonte desses códigos). sort_order preserva a ordem em que já apareciam no
# seletor.
THEMES = [
    {"code": "universe", "name": "Universo", "sort_order": 0},
    {"code": "cinema", "name": "Cinema", "sort_order": 1},
    {"code": "beach", "name": "Praia", "sort_order": 2},
    {"code": "flowers", "name": "Flores", "sort_order": 3},
    {"code": "night", "name": "Noite", "sort_order": 4},
    {"code": "minimal", "name": "Minimalista", "sort_order": 5},
]


def seed_themes(apps, schema_editor):
    Theme = apps.get_model("experiences", "Theme")

    for theme_data in THEMES:
        # get_or_create por `code` torna a migration segura de reexecutar —
        # mesmo padrão de payments/migrations/0002_seed_initial_plans.py.
        Theme.objects.get_or_create(
            code=theme_data["code"],
            defaults={
                "name": theme_data["name"],
                "sort_order": theme_data["sort_order"],
                "is_active": True,
                "features": {},
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("experiences", "0004_theme"),
    ]

    operations = [
        # Reverse intencionalmente é um no-op: um tema nunca é apagado por
        # migration (mesmo raciocínio de payments/0002 — ExperienceDraft.theme
        # não tem FK para Theme, então não há PROTECT a temer aqui, mas
        # apagar retroativamente um tema que já foi usado por experiências
        # publicadas não é uma operação segura de se automatizar).
        migrations.RunPython(seed_themes, migrations.RunPython.noop),
    ]
