import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.serializers.password_reset import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
)
from apps.accounts.services.password_reset_service import (
    InvalidOrExpiredCode,
    confirm_password_reset,
    request_password_reset,
    verify_password_reset_code,
)

logger = logging.getLogger(__name__)

GENERIC_REQUEST_MESSAGE = (
    "Se existir uma conta associada a este e-mail, enviaremos um código de recuperação."
)
INVALID_CODE_MESSAGE = "Código inválido ou expirado."


class PasswordResetRequestView(APIView):
    """POST /api/auth/password-reset/request/

    Sempre responde 200 com a MESMA mensagem genérica, exista ou não uma
    conta com esse e-mail — nunca revela existência (ver
    services.password_reset_service.request_password_reset, que já decide
    internamente se de fato há algo para enviar).
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_request"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_password_reset(serializer.validated_data["email"])

        return Response({"detail": GENERIC_REQUEST_MESSAGE}, status=status.HTTP_200_OK)


class PasswordResetVerifyView(APIView):
    """POST /api/auth/password-reset/verify/

    Só confere se o código atual é válido — não o consome (quem consome é
    PasswordResetConfirmView, atomicamente junto da troca de senha).
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_verify"

    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            verify_password_reset_code(data["email"], data["code"])
        except InvalidOrExpiredCode:
            return Response({"detail": INVALID_CODE_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Código válido."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/

    Revalida o código do zero e, se válido, troca a senha + invalida todas
    as sessões existentes (refresh tokens) do usuário. Não faz login
    automático — a resposta de sucesso não inclui tokens, a pessoa loga de
    novo com a senha nova (ver PasswordResetFlow no frontend).
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_verify"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            confirm_password_reset(data["email"], data["code"], data["new_password"])
        except InvalidOrExpiredCode:
            return Response({"detail": INVALID_CODE_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Senha alterada com sucesso."}, status=status.HTTP_200_OK)
