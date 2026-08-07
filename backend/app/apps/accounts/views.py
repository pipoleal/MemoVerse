from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer


class LoginView(TokenObtainPairView):
    """
    Endpoint responsável pelo login.
    """

    serializer_class = LoginSerializer