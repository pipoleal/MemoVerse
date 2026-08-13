from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.experiences.models import ExperienceDraft

from ..models import Payment
from ..serializers.status import DraftPaymentStatusSerializer


class DraftPaymentStatusView(APIView):
    """GET /api/payments/drafts/<uuid:draft_id>/status/

    Retorna o estado de pagamento já confirmado no banco para um Draft do
    usuário autenticado. Nunca consulta a Mercado Pago diretamente — a
    confirmação real acontece de forma assíncrona via webhook
    (PaymentConfirmationService); este endpoint só lê o resultado.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, draft_id):
        # Mesmo padrão de DraftCheckoutView: draft de outro usuário -> 404,
        # nunca revelando que existe.
        draft = get_object_or_404(ExperienceDraft, id=draft_id, owner=request.user)

        payment = (
            Payment.objects.select_related("plan")
            .filter(draft=draft)
            .order_by("-attempt_number")
            .first()
        )

        data = {"draft_status": draft.status, "payment": None}
        if payment is not None:
            data["payment"] = {
                "payment_id": payment.id,
                "status": payment.status,
                "attempt_number": payment.attempt_number,
                "plan": {"code": payment.plan.code, "name": payment.plan.name},
            }

        return Response(DraftPaymentStatusSerializer(data).data)
