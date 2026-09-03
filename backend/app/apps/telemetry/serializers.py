from rest_framework import serializers

from .models import FunnelEvent

MAX_METADATA_KEYS = 10
MAX_METADATA_VALUE_LENGTH = 200


class FunnelEventCreateSerializer(serializers.Serializer):
    """POST /api/events/ body. Nunca aceita e-mail/nome/payload livre — ver
    docstring de FunnelEvent para o porquê."""

    name = serializers.ChoiceField(choices=FunnelEvent.Name.choices)
    session_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    draft_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    metadata = serializers.DictField(required=False)

    def validate_metadata(self, value):
        if len(value) > MAX_METADATA_KEYS:
            raise serializers.ValidationError("Metadados demais.")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 40:
                raise serializers.ValidationError("Chave de metadado inválida.")
            if isinstance(item, str):
                if len(item) > MAX_METADATA_VALUE_LENGTH:
                    raise serializers.ValidationError("Valor de metadado grande demais.")
            elif not isinstance(item, (int, float, bool)):
                raise serializers.ValidationError("Valor de metadado inválido.")
        return value

    def create(self, validated_data):
        return FunnelEvent.objects.create(**validated_data)
