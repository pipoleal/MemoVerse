from rest_framework import serializers


class PlanSerializer(serializers.Serializer):
    """Catálogo público de planos ativos — GET /api/payments/plans/. Espelha
    exatamente os campos comerciais de Plan; nunca expõe is_active/id/
    created_at/updated_at, que não são assunto do frontend."""

    code = serializers.CharField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    features = serializers.DictField()
