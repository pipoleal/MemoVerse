from rest_framework import serializers

from ..models import Plan


class CheckoutRequestSerializer(serializers.Serializer):
    """Aceita SOMENTE plan_code. Qualquer outro campo enviado (amount, price,
    currency, draft_id, external_reference, idempotency_key, ...) é ignorado
    pelo DRF por não estar declarado aqui — nunca influencia o fluxo."""

    plan_code = serializers.CharField(max_length=50)

    def validate_plan_code(self, value):
        try:
            plan = Plan.objects.get(code=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plano inválido ou indisponível.")
        return plan


class PlanSummarySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class CheckoutResponseSerializer(serializers.Serializer):
    """Somente os dados que o frontend precisa para continuar o fluxo nesta
    fase. Nunca inclui access token, secrets ou o payload bruto da MP."""

    payment_id = serializers.UUIDField()
    status = serializers.CharField()
    plan = PlanSummarySerializer()
    checkout = serializers.DictField()
