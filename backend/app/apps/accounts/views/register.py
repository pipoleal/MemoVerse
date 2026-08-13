from typing import Any, cast

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import RegisterSerializer
from apps.accounts.services.auth_service import AuthService


class RegisterView(APIView):
    """
    Endpoint responsável pelo cadastro de usuários.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = cast(dict[str, Any], serializer.validated_data)

        user = AuthService.register(
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            password=data["password"],
        )

        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status=status.HTTP_201_CREATED,
        )