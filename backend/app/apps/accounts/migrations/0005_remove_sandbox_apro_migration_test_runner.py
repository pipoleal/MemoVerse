"""TEST-ONLY / TEMPORARY.

Remove a conta técnica provisionada por
0004_sandbox_apro_migration_checkout_test.py (last_name=
"SandboxAproMigrationTestRunner") e os dados que o único checkout Sandbox
APRO daquela migration gerou para ela: um ExperienceDraft (marcado por
title="__SANDBOX_APRO_MIGRATION_TEST__") e um Payment.

Mesmo padrão de 0003_remove_sandbox_apro_test_runner.py: Payment e Draft têm
on_delete=PROTECT em relação ao User dono, então a ordem de exclusão é
obrigatoriamente Payment -> ExperienceDraft -> User. Todas as exclusões são
filtradas por owner=user (nunca só pelo título ou por um id isolado), então
esta migration nunca apaga dado de outro usuário.

Idempotente: se o user não existir (já removido, ou migration reaplicada),
não faz nada. Se o Payment ou o Draft já tiverem sido removidos
individualmente por algum motivo, os `.filter(...).first()` simplesmente
retornam None e os passos seguintes são pulados sem erro.

Não faz nenhuma chamada de rede (nenhum CheckoutService, nenhum
MercadoPagoClient) — só DELETE local via ORM histórico.
"""

from django.db import migrations

# Mesmo rótulo definido em 0004_sandbox_apro_migration_checkout_test.py
# (SANDBOX_RUNNER_LAST_NAME) para identificar a conta.
SANDBOX_RUNNER_LAST_NAME = "SandboxAproMigrationTestRunner"

# Mesmo marcador definido em 0004_sandbox_apro_migration_checkout_test.py
# (SANDBOX_APRO_TEST_DRAFT_TITLE) para identificar o Draft de teste.
SANDBOX_APRO_TEST_DRAFT_TITLE = "__SANDBOX_APRO_MIGRATION_TEST__"


def remove_sandbox_apro_migration_test_runner(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Payment = apps.get_model("payments", "Payment")
    ExperienceDraft = apps.get_model("experiences", "ExperienceDraft")

    user = User.objects.filter(last_name=SANDBOX_RUNNER_LAST_NAME).first()
    if user is None:
        # Já removida (ex.: migration reaplicada) — nada a fazer.
        return

    # Localiza o Draft sempre por owner=user (nunca só pelo título), e o
    # Payment sempre por owner=user (nunca só pelo draft), para nunca apagar
    # uma linha que não pertença comprovadamente a esta conta técnica.
    draft = ExperienceDraft.objects.filter(owner=user, title=SANDBOX_APRO_TEST_DRAFT_TITLE).first()

    if draft is not None:
        Payment.objects.filter(owner=user, draft=draft).delete()
        draft.delete()
    else:
        # Draft já removido por algum motivo, mas pode existir um Payment
        # órfão desta conta — mesma trava owner=user na exclusão.
        Payment.objects.filter(owner=user).delete()

    user.delete()


def noop_reverse(apps, schema_editor):
    # A reversão não recria a conta nem os dados de teste — a criação
    # original vive em 0004_sandbox_apro_migration_checkout_test.py, que
    # continua no histórico.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_sandbox_apro_migration_checkout_test"),
        # Necessárias para que apps.get_model("payments"/"experiences", ...)
        # resolva no registro histórico desta migration.
        ("payments", "0004_alter_payment_idempotency_key"),
        ("experiences", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_sandbox_apro_migration_test_runner, noop_reverse),
    ]
