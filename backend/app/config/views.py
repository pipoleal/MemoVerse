from django.db import connections
from django.db.utils import Error as DatabaseError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """GET /api/health/ — barato, público, sem detalhe interno na resposta.

    Verifica só a conexão com o banco (uma consulta trivial, não uma
    inspeção de schema) — deliberadamente NÃO chama Mercado Pago nem R2
    (ver Etapa 6 Fase B): este endpoint precisa responder rápido mesmo
    quando um provedor externo estiver lento/fora do ar.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        if self._database_is_healthy():
            return Response({"status": "ok"})
        return Response({"status": "unavailable"}, status=503)

    @staticmethod
    def _database_is_healthy() -> bool:
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return False
        return True
