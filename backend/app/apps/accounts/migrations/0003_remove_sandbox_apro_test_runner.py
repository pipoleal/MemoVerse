"""TEST-ONLY / TEMPORARY.

Remove a conta técnica provisionada por 0002_sandbox_apro_test_runner.py
(is_staff=True, sem permissões de model, senha inutilizável). A rota que
ela autorizava (apps/payments/views/sandbox_apro_test.py) foi removida
junto com esta limpeza — a conta não tem mais nenhum uso no sistema.

A migration 0002 é mantida no repositório (já aplicada em produção, faz
parte do histórico do Django) — só o efeito dela (a conta) é desfeito aqui,
pelo mesmo identificador usado na criação original.
"""

from django.db import migrations

# Mesmo rótulo usado por 0002_sandbox_apro_test_runner.py para identificar
# a conta — não é um segredo, só a chave de busca para a remoção idempotente.
SANDBOX_RUNNER_LAST_NAME = "SandboxAproTestRunner"


def remove_sandbox_apro_runner(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_staff=True, last_name=SANDBOX_RUNNER_LAST_NAME).delete()


def noop_reverse(apps, schema_editor):
    # A reversão não recria a conta — a criação original vive em
    # 0002_sandbox_apro_test_runner.py, que continua no histórico.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_sandbox_apro_test_runner"),
    ]

    operations = [
        migrations.RunPython(remove_sandbox_apro_runner, noop_reverse),
    ]
