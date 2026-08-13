from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.experiences.models import ExperienceDraft

from ..models import Payment
from ..serializers.checkout import CheckoutRequestSerializer, CheckoutResponseSerializer
from ..services.checkout_service import ActiveCheckoutConflict, CheckoutGatewayError, CheckoutService


def _checkout_payload_for(payment: Payment) -> dict:
    """Só os dados de continuação de checkout que já existem hoje (Pix). Nada
    específico do Checkout Bricks (Fase 6) é inventado aqui."""

    checkout = {"mp_order_id": payment.mp_order_id}
    order_payments = ((payment.last_sync_payload or {}).get("transactions") or {}).get("payments") or []
    if order_payments:
        payment_method = order_payments[0].get("payment_method") or {}
        for key in ("qr_code", "qr_code_base64", "ticket_url"):
            if key in payment_method:
                checkout[key] = payment_method[key]
    return checkout


class DraftCheckoutView(APIView):
    """POST /api/payments/drafts/<uuid:draft_id>/checkout/

    Cria ou retoma o checkout (Payment + Order na Mercado Pago) de um
    ExperienceDraft pertencente ao usuário autenticado.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id):
        # Mesmo padrão de apps.experiences: filtrar por owner=request.user faz
        # um draft de outro usuário resultar em 404, nunca revelando que existe.
        draft = get_object_or_404(ExperienceDraft, id=draft_id, owner=request.user)

        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan_code"]

        try:
            payment = CheckoutService.start_checkout(draft=draft, plan=plan)
        except ActiveCheckoutConflict as exc:
            return Response(
                {
                    "detail": "Já existe um checkout ativo para este draft com outro plano.",
                    "active_plan_code": exc.payment.plan.code,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except CheckoutGatewayError:
            return Response(
                {"detail": "Não foi possível iniciar o pagamento com a Mercado Pago. Tente novamente."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_data = {
            "payment_id": payment.id,
            "status": payment.status,
            "plan": {"code": payment.plan.code, "name": payment.plan.name},
            "checkout": _checkout_payload_for(payment),
        }
        return Response(CheckoutResponseSerializer(response_data).data, status=status.HTTP_200_OK)
