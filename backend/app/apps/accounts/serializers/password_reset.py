import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers  # type: ignore[import]

from apps.accounts.models import User

CODE_PATTERN = re.compile(r"^\d{6}$")


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()

    def validate_code(self, value):
        if not CODE_PATTERN.match(value):
            # Mesma mensagem genérica de um código errado (ver
            # services.password_reset_service) — um formato inválido nunca
            # deve parecer, do lado do cliente, diferente de um código
            # simplesmente incorreto.
            raise serializers.ValidationError("Código inválido ou expirado.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_code(self, value):
        if not CODE_PATTERN.match(value):
            raise serializers.ValidationError("Código inválido ou expirado.")
        return value

    def validate(self, attrs):
        # Mesma regra de senha do cadastro (RegisterSerializer) — nenhuma
        # regra nova/diferente para recuperação, conforme solicitado.
        user = User(email=attrs.get("email", ""))
        try:
            password_validation.validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs
