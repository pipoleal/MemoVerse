"""TEST-ONLY / TEMPORARY.

Provisiona UMA conta técnica dedicada (is_staff=True, NUNCA is_superuser,
NENHUMA permissão de model, senha inutilizável) usada apenas para autorizar
a rota temporária de teste do checkout Pix Sandbox com o mecanismo "APRO"
de auto-aprovação da Mercado Pago (ver apps/payments/views/sandbox_apro_test.py).

Esta conta nunca é alcançável via /api/auth/register/ (AuthService.register
nunca define is_staff), então não abre nenhuma brecha para usuários comuns.

Esta migration e a view que ela protege devem ser REMOVIDAS assim que o
teste manual do APRO for concluído e confirmado.
"""

import uuid

from django.contrib.auth.hashers import make_password
from django.db import migrations

# Marca a conta provisionada por esta migration, usada para tornar a
# criação idempotente e a reversão precisa — não é um segredo, é só um
# rótulo descritivo (não concede nem verifica autorização em lugar nenhum;
# a view protegida checa exclusivamente is_staff).
SANDBOX_RUNNER_LAST_NAME = "SandboxAproTestRunner"


def create_sandbox_apro_runner(apps, schema_editor):
    User = apps.get_model("accounts", "User")

    if User.objects.filter(is_staff=True, last_name=SANDBOX_RUNNER_LAST_NAME).exists():
        # Idempotente: já provisionada (ex.: migration reaplicada).
        return

    user = User(
        email=f"sandbox-apro-runner-{uuid.uuid4().hex}@memoverse.local",
        first_name="Sandbox",
        last_name=SANDBOX_RUNNER_LAST_NAME,
        is_staff=True,
        is_superuser=False,
        is_active=True,
        # Ninguém consegue logar como esta conta via senha — nunca houve
        # uma. O model histórico da migration não herda os métodos de
        # AbstractBaseUser (ex.: set_unusable_password), então o mesmo
        # resultado é obtido diretamente via make_password(None), que é
        # exatamente o que set_unusable_password() faz por baixo dos panos.
        password=make_password(None),
    )
    user.save()

    # A rota temporária que consumia este JWT (apps/payments/views/
    # sandbox_apro_test.py) já foi removida (ver 0003_remove_sandbox_apro_test_runner
    # e o commit que a excluiu) — nada mais lê este token, e 0003 já apaga
    # esta conta logo em seguida. Gerar e imprimir um JWT aqui não teria mais
    # nenhum uso e só exporia um access token válido nos logs de deploy sem
    # necessidade nenhuma; removido de propósito (auditoria de produção).
    print(f"[sandbox-apro-runner] Conta técnica provisionada (id={user.pk}).")


def remove_sandbox_apro_runner(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_staff=True, last_name=SANDBOX_RUNNER_LAST_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_sandbox_apro_runner, remove_sandbox_apro_runner),
    ]
