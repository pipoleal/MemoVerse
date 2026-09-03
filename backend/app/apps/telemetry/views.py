import logging

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import FunnelEventCreateSerializer

logger = logging.getLogger(__name__)


class FunnelEventCreateView(APIView):
    """POST /api/events/ — instrumentação pública e anônima do funil de
    conversão (ver apps.telemetry.models.FunnelEvent). O frontend
    (frontend/lib/analytics.ts) sempre chama isso fire-and-forget e ignora
    qualquer erro de resposta — por isso esta view não precisa de nenhum
    tratamento especial além da validação normal do DRF (o mesmo padrão de
    DraftListCreateView.post)."""

    permission_classes = [AllowAny]

    def get_throttles(self):
        # Mesmo padrão de DraftListCreateView (apps.experiences.views):
        # throttle_scope setado aqui, não como atributo de classe, porque
        # só faz sentido por request (nunca precisou variar por método
        # aqui, mas mantém a mesma forma usada no resto do projeto).
        self.throttle_scope = "funnel_event"
        return [ScopedRateThrottle()]

    def post(self, request):
        serializer = FunnelEventCreateSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            logger.warning("funnel_event.invalid")
            raise

        serializer.save()
        return Response(status=status.HTTP_201_CREATED)
