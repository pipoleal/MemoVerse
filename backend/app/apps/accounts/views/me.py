from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import is_production_admin


class MeView(APIView):
    """GET /api/auth/me/

    Devolve o perfil do próprio usuário autenticado — em particular
    is_admin, que o token JWT emitido no login NUNCA carrega
    (LoginSerializer usa o TokenObtainPairSerializer padrão, sem custom
    claims) e que o refresh também não recalcularia mesmo se carregasse
    (RefreshView é o TokenRefreshView padrão). Único ponto de verdade para
    "este usuário é admin?" no frontend — ver apps.ops e o painel /admin,
    que dependem deste campo para decidir se renderizam o painel.

    is_admin (Etapa 9B.6) é calculado por is_production_admin() — a MESMA
    função que IsProductionAdmin usa para de fato liberar os endpoints
    /api/ops/9b4/*. O frontend nunca precisa (nem deve) olhar is_superuser
    diretamente: is_admin já é a decisão completa (is_superuser OU e-mail
    configurado em MEMOVERSE_ADMIN_EMAIL). is_superuser continua no corpo
    da resposta só como informação adicional, não como o que o guard usa.

    Nunca revela nada de outro usuário — sempre e só request.user. Nunca
    inclui senha, hash ou qualquer outro dado sensível.
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
                "is_admin": is_production_admin(user),
            }
        )
