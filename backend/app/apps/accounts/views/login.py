from rest_framework_simplejwt.views import TokenObtainPairView  # type: ignore[import]

from ..serializers.login import LoginSerializer


class LoginView(TokenObtainPairView):
    """
    Endpoint responsável pelo login.
    """

    serializer_class = LoginSerializer