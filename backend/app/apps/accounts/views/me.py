from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class MeView(APIView):
    """GET /api/auth/me/

    Devolve o perfil do próprio usuário autenticado — em particular
    is_superuser, que o token JWT emitido no login NUNCA carrega (LoginSerializer
    usa o TokenObtainPairSerializer padrão, sem custom claims) e que o
    refresh também não recalcularia mesmo se carregasse (RefreshView é o
    TokenRefreshView padrão). Único ponto de verdade para "este usuário é
    admin?" no frontend — ver apps.ops (Etapa 9B.4) e o painel /admin
    (Etapa 9B.5), que dependem disto para decidir se renderizam o painel.

    Nunca revela nada de outro usuário — sempre e só request.user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_superuser": user.is_superuser,
            }
        )
