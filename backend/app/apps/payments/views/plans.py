from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Plan
from ..serializers.plans import PlanSerializer


class PlanListView(APIView):
    """GET /api/payments/plans/

    Catálogo dos planos comercializáveis no momento. Segundo endpoint desta
    API sem autenticação (mesmo padrão de PublicExperienceView em
    apps.experiences): preço e nome de planos não são dado sensível, e quem
    chega à tela de seleção de plano no checkout pode fazê-lo antes de
    qualquer chamada autenticada acontecer.

    is_active=True é o único filtro — Plan.Meta.ordering já é ["price"],
    então a resposta já sai ordenada (daily, weekly, lifetime, lifetime_galaxy)
    sem precisar de order_by() explícito aqui.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True)
        return Response(PlanSerializer(plans, many=True).data)
