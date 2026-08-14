"""TEST-ONLY / TEMPORARY.

Remove a conta técnica provisionada por 0002_sandbox_apro_test_runner.py
(is_staff=True, sem permissões de model, senha inutilizável). A rota que
ela autorizava (apps/payments/views/sandbox_apro_test.py) foi removida
junto com esta limpeza — a conta não tem mais nenhum uso no sistema.

A primeira versão desta migration tentava apagar o User direto e falhou em
produção com ProtectedError: essa conta é dona do ExperienceDraft/Payment
criados pelo único teste APRO executado (Payment.owner e Payment.draft são
on_delete=PROTECT). Esta versão remove esses dois registros de teste,
nessa ordem, antes de remover a conta — e só toca em linhas confirmadamente
pertencentes a esta conta técnica (nunca dados de outro usuário).

A migration 0002 é mantida no repositório (já aplicada em produção, faz
parte do histórico do Django) — só o efeito dela (a conta e os dados de
teste que ela gerou) é desfeito aqui.
"""

from django.db import migrations

# Mesmo rótulo usado por 0002_sandbox_apro_test_runner.py para identificar
# a conta — não é um segredo, só a chave de busca para a remoção idempotente.
SANDBOX_RUNNER_LAST_NAME = "SandboxAproTestRunner"

# Payment criado pelo único teste APRO executado nesta conta técnica
# (ver histórico da investigação: mp_order_id=ORDTST01KZZYDZJB31PVPMPDW22NSHH7).
SANDBOX_APRO_TEST_PAYMENT_ID = "df6269ce-24ff-4ed6-b3ed-8210868755b0"


def remove_sandbox_apro_runner(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Payment = apps.get_model("payments", "Payment")
    ExperienceDraft = apps.get_model("experiences", "ExperienceDraft")

    user = User.objects.filter(is_staff=True, last_name=SANDBOX_RUNNER_LAST_NAME).first()
    if user is None:
        # Já removida (ex.: migration reaplicada) — nada a fazer.
        return

    # Filtra sempre por owner=user, mesmo já sabendo o pk: nunca apaga uma
    # linha que não pertença comprovadamente a esta conta técnica.
    payment = Payment.objects.filter(pk=SANDBOX_APRO_TEST_PAYMENT_ID, owner=user).first()
    draft_id = payment.draft_id if payment is not None else None
    if payment is not None:
        payment.delete()

    if draft_id is not None:
        ExperienceDraft.objects.filter(pk=draft_id, owner=user).delete()

    user.delete()


def noop_reverse(apps, schema_editor):
    # A reversão não recria a conta nem os dados de teste — a criação
    # original vive em 0002_sandbox_apro_test_runner.py, que continua no
    # histórico.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_sandbox_apro_test_runner"),
        # Necessárias para que apps.get_model("payments"/"experiences", ...)
        # resolva no registro histórico desta migration.
        ("payments", "0004_alter_payment_idempotency_key"),
        ("experiences", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_sandbox_apro_runner, noop_reverse),
    ]
