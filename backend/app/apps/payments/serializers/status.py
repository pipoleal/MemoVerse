from rest_framework import serializers


class PlanSummarySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class PaymentStatusSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    status = serializers.CharField()
    attempt_number = serializers.IntegerField()
    plan = PlanSummarySerializer()


class DraftPaymentStatusSerializer(serializers.Serializer):
    """Somente o estado já confirmado no banco. Este endpoint nunca consulta
    a Mercado Pago diretamente — isso é responsabilidade exclusiva do
    webhook/PaymentConfirmationService."""

    draft_status = serializers.CharField()
    payment = PaymentStatusSerializer(allow_null=True)
