import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken  # type: ignore[import]

from .models import RecoveryLoginToken
from .serializers import RecoveryRedeemSerializer

logger = logging.getLogger(__name__)

GENERIC_INVALID_DETAIL = "Este link não é mais válido. Faça login normalmente para continuar."


class RecoveryTokenRedeemView(APIView):
    """POST /api/recovery/redeem/ — troca o token de uma vez do link de
    e-mail/WhatsApp por um par access/refresh de verdade (mesmo mecanismo
    de LoginView, sem senha) + o id do draft para o frontend redirecionar
    direto para /experience/edit/<draft_id>. Nunca distingue "não existe" de
    "expirado" de "já usado" na resposta — mesmo motivo de LoginView nunca
    dizer qual dos dois (e-mail ou senha) está errado."""

    permission_classes = [AllowAny]

    def get_throttles(self):
        self.throttle_scope = "recovery_redeem"
        return [ScopedRateThrottle()]

    def post(self, request):
        serializer = RecoveryRedeemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        try:
            record = RecoveryLoginToken.objects.select_related("user").get(token=token)
        except RecoveryLoginToken.DoesNotExist:
            logger.warning("recovery.redeem.not_found")
            return Response({"detail": GENERIC_INVALID_DETAIL}, status=status.HTTP_400_BAD_REQUEST)

        if record.used_at is not None or record.expires_at < timezone.now():
            logger.warning("recovery.redeem.expired_or_used")
            return Response({"detail": GENERIC_INVALID_DETAIL}, status=status.HTTP_400_BAD_REQUEST)

        if not record.user.is_active:
            logger.warning("recovery.redeem.inactive_user")
            return Response({"detail": GENERIC_INVALID_DETAIL}, status=status.HTTP_400_BAD_REQUEST)

        record.used_at = timezone.now()
        record.save(update_fields=["used_at"])

        refresh = RefreshToken.for_user(record.user)

        logger.info("recovery.redeem.success")
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "draft_id": str(record.draft_id),
                "first_name": record.user.first_name,
            }
        )
