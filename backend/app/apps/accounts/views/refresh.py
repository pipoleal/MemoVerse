from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenRefreshView  # type: ignore[import]


class RefreshView(TokenRefreshView):
    """
    Endpoint responsável pela renovação do access token.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"
