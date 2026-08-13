from rest_framework import serializers  # type: ignore[import]

from apps.accounts.models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()

    first_name = serializers.CharField(
        max_length=100,
    )

    last_name = serializers.CharField(
        max_length=100,
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este e-mail já está cadastrado.")

        return value