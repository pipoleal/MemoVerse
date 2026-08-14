"""TEST-ONLY / TEMPORARY.

Endpoint de diagnóstico para validar manualmente o fluxo completo de
Checkout Pix usando o mecanismo oficial "APRO" de auto-aprovação da
Mercado Pago em Sandbox — necessário porque o plano Free do Render não
oferece Shell nem Jobs avulsos para rodar isso via `manage.py shell`.

Este arquivo (e a rota correspondente em urls.py) devem ser REMOVIDOS assim
que o teste manual for concluído e confirmado. Não é parte permanente do
produto.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.experiences.models import ExperienceDraft

from ..models import Plan
from ..services.checkout_service import CheckoutGatewayError, CheckoutService

# Draft fixo e sempre o mesmo por owner: garante que a idempotência já
# existente do CheckoutService (reaproveita Payment ativo / não repete a
# chamada à MP se mp_order_id já estiver setado) seja o único mecanismo de
# proteção contra criar mais de uma Order por execução.
_TEST_DRAFT_TITLE = "__SANDBOX_APRO_TEST_DRAFT__"


class SandboxAproTestView(APIView):
    """POST /api/payments/sandbox-apro-test/  — TEST-ONLY / TEMPORARY.

    Autorização: JWT (mecanismo já existente) + request.user.is_staff. A
    única conta com is_staff=True é a provisionada pela migration
    accounts/0002_sandbox_apro_test_runner.py — nenhum usuário registrado
    via /api/auth/register/ jamais recebe is_staff.

    Só funciona com settings.MP_ENV == "sandbox"; em qualquer outro valor,
    recusa completamente (403), sem tocar em Draft/Payment/Mercado Pago.

    Ignora todo o corpo da requisição: payer_first_name="APRO" é fixo no
    código, nunca aceito do cliente.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if settings.MP_ENV != "sandbox":
            return Response(
                {"detail": "Disponível apenas em Sandbox."},
                status=status.HTTP_403_FORBIDDEN,
            )

        draft, _ = ExperienceDraft.objects.get_or_create(
            owner=request.user,
            title=_TEST_DRAFT_TITLE,
            defaults={
                "experience_type": "letter",
                "theme": "stars",
                "recipient_name": "Test Recipient",
                "creator_name": "Test Creator",
                "letter": "Draft para teste APRO (TEST-ONLY).",
            },
        )
        plan = Plan.objects.get(code="essential")

        try:
            payment = CheckoutService.start_checkout(draft=draft, plan=plan, payer_first_name="APRO")
        except CheckoutGatewayError:
            return Response(
                {"detail": "Falha ao criar a Order na Mercado Pago."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        draft.refresh_from_db()
        return Response(
            {
                "draft_id": str(draft.id),
                "payment_id": str(payment.id),
                "mp_order_id": payment.mp_order_id,
                "mp_payment_id": payment.mp_payment_id,
                "payment_status": payment.status,
                "draft_status": draft.status,
            }
        )
