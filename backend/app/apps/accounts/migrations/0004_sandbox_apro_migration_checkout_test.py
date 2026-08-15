"""TEST-ONLY / TEMPORARY.

Executa, uma única vez, um checkout Sandbox real usando o mecanismo oficial
de auto-aprovação "APRO" da Mercado Pago — já suportado, mas nunca chamado,
por CheckoutService.start_checkout(..., payer_first_name=...) (ver
apps/payments/services/checkout_service.py). Não cria nenhuma rota HTTP:
roda inteiramente dentro do `manage.py migrate` do próprio deploy, o mesmo
mecanismo já usado por 0002_sandbox_apro_test_runner.py e
0003_remove_sandbox_apro_test_runner.py.

NÃO toca na Order Pix já existente (ORDTST01M01EJ36WCDD1EAWB76BFD7GJ, criada
pelo checkout normal) — cria um User/Draft/Payment totalmente novos e
isolados, exclusivos deste teste.

Duas travas independentes, nessa ordem:
1. RUN_SANDBOX_APRO_MIGRATION_TEST != "true" -> no-op absoluto. Sem essa
   variável (que não existe em nenhum ambiente por padrão), a migration
   nunca faz nada — inclusive durante `manage.py test`, que recria um banco
   do zero e aplica TODAS as migrations nele. Sem esta trava, toda execução
   local da suíte de testes chamaria a Mercado Pago de verdade e criaria uma
   Order Sandbox nova a cada vez. Definir essa variável é um passo manual e
   temporário: só no Render, só para o deploy que deve rodar este teste.
2. MP_ENV != "sandbox" -> no-op absoluto (mesma trava usada em
   0002_sandbox_apro_test_runner.py). CheckoutService também tem sua própria
   trava independente: payer_first_name só é enviado à Mercado Pago se
   mp_client.environment == "sandbox" (ver _create_order).

Idempotência: User técnico e Draft de teste são localizados por um marcador
fixo (get-or-create manual, mesmo padrão de 0002) antes de qualquer chamada
de rede. A garantia de "nunca criar uma segunda Order" vem do próprio
CheckoutService.start_checkout: se o Payment já tiver mp_order_id de uma
execução anterior bem-sucedida, ele retorna sem chamar a Mercado Pago de
novo (start_checkout: "if payment.mp_order_id: return payment").

Falha segura: nenhum transaction.atomic explícito é necessário aqui —
migrations do Django em Postgres já rodam dentro de uma transação por
padrão (confirmado nesta mesma investigação quando
0003_remove_sandbox_apro_test_runner.py falhou e reverteu de forma limpa,
sem deixar nenhum dado parcial). Se CheckoutGatewayError for levantada (a
Mercado Pago recusar a Order), ela sobe sem ser capturada aqui: a transação
inteira desta migration (User + Draft + Payment) é revertida, sem deixar
nenhum dado de teste órfão no banco.
"""

import os
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import migrations

from apps.experiences.models import ExperienceDraft
from apps.payments.models import Payment, Plan
from apps.payments.services.checkout_service import CheckoutService

SANDBOX_RUNNER_LAST_NAME = "SandboxAproMigrationTestRunner"
SANDBOX_APRO_TEST_DRAFT_TITLE = "__SANDBOX_APRO_MIGRATION_TEST__"
SANDBOX_APRO_TEST_PLAN_CODE = "essential"
ENABLE_FLAG = "RUN_SANDBOX_APRO_MIGRATION_TEST"


def _get_or_create_test_user(User):
    existing = User.objects.filter(last_name=SANDBOX_RUNNER_LAST_NAME).first()
    if existing is not None:
        return existing

    user = User(
        email=f"sandbox-apro-migration-{uuid.uuid4().hex}@memoverse.local",
        first_name="Sandbox",
        last_name=SANDBOX_RUNNER_LAST_NAME,
        is_staff=False,
        is_superuser=False,
        is_active=False,
        # Ninguém consegue logar como esta conta — mesmo padrão de
        # 0002_sandbox_apro_test_runner.py.
        password=make_password(None),
    )
    user.save()
    return user


def _get_or_create_test_draft(user):
    existing = ExperienceDraft.objects.filter(owner=user, title=SANDBOX_APRO_TEST_DRAFT_TITLE).first()
    if existing is not None:
        return existing

    return ExperienceDraft.objects.create(
        owner=user,
        title=SANDBOX_APRO_TEST_DRAFT_TITLE,
        experience_type="sandbox-apro-migration-test",
    )


def run_sandbox_apro_checkout_test(apps, schema_editor):
    if os.environ.get(ENABLE_FLAG, "false").lower() != "true":
        return
    if getattr(settings, "MP_ENV", "sandbox") != "sandbox":
        return

    User = get_user_model()
    user = _get_or_create_test_user(User)
    draft = _get_or_create_test_draft(user)
    plan = Plan.objects.get(code=SANDBOX_APRO_TEST_PLAN_CODE, is_active=True)

    payment = CheckoutService.start_checkout(draft=draft, plan=plan, payer_first_name="APRO")

    print(
        "[sandbox-apro-migration-test] Checkout Sandbox APRO executado. "
        f"draft_id={draft.id} payment_id={payment.id} mp_order_id={payment.mp_order_id}"
    )


def noop_reverse(apps, schema_editor):
    # Não desfaz o teste (User/Draft/Payment/Order) — limpeza fica para uma
    # migration de cleanup dedicada, como já feito para
    # 0002_sandbox_apro_test_runner.py -> 0003_remove_sandbox_apro_test_runner.py.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_remove_sandbox_apro_test_runner"),
        ("payments", "0004_alter_payment_idempotency_key"),
        ("experiences", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(run_sandbox_apro_checkout_test, noop_reverse),
    ]
