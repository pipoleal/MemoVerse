import logging

from rest_framework.exceptions import APIException
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView  # type: ignore[import]

from ..serializers.login import LoginSerializer

logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    """
    Endpoint responsável pelo login.
    """

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        # Etapa 6 — Fase D: só o evento, nunca e-mail/senha/token — a
        # resposta em si (status, corpo, mensagens) não é alterada.
        # Credenciais inválidas levantam APIException (AuthenticationFailed)
        # dentro de super().post() em vez de retornar uma Response não-200
        # — precisa ser capturada aqui e relançada, senão o log de falha
        # nunca é alcançado.
        try:
            response = super().post(request, *args, **kwargs)
        except APIException:
            logger.warning("auth.login.failure")
            raise
        logger.info("auth.login.success")
        return response