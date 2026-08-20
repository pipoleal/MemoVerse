import logging

from rest_framework.exceptions import APIException
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenBlacklistView  # type: ignore[import]

logger = logging.getLogger(__name__)


class LogoutView(TokenBlacklistView):
    """
    Endpoint responsável pelo logout: blacklista o refresh token enviado.

    Não exige IsAuthenticated (mesmo padrão de LoginView/RefreshView,
    herdado de TokenViewBase) — possuir um refresh token válido já é a
    prova necessária para revogá-lo, e exigir um access token ainda válido
    além disso falharia justamente no caso mais comum de logout (sessão já
    expirada). Só o refresh token é revogado; um access token em uso
    continua válido até expirar naturalmente (comportamento documentado do
    SimpleJWT — AccessToken não herda BlacklistMixin).
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "logout"

    def post(self, request, *args, **kwargs):
        # Etapa 8: só o evento, nunca o token — a resposta em si não muda.
        try:
            response = super().post(request, *args, **kwargs)
        except APIException:
            logger.warning("auth.logout.failure")
            raise
        logger.info("auth.logout.success")
        return response
