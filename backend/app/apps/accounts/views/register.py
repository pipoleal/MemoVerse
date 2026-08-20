import logging
from typing import Any, cast

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.serializers import RegisterSerializer
from apps.accounts.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    """
    Endpoint responsável pelo cadastro de usuários.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            # Etapa 6 — Fase D: só o evento, nunca o e-mail/payload — a
            # mensagem/status de erro da API não muda, só é relogada.
            logger.warning("auth.register.failure")
            raise

        data = cast(dict[str, Any], serializer.validated_data)

        user = AuthService.register(
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            password=data["password"],
        )

        logger.info("auth.register.success")

        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status=status.HTTP_201_CREATED,
        )