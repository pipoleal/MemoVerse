from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
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
        # Etapa 8 — Fase C: mensagem deliberadamente genérica — não confirma
        # que o e-mail já tem conta. Mitigação parcial: o texto não vaza
        # mais a existência, mas o status HTTP (400 aqui vs. 201 num
        # cadastro novo) continua sendo, por si só, um sinal de enumeração.
        # Fechar isso por completo exigiria o endpoint sempre responder como
        # sucesso sem criar conta duplicada — mudança maior de UX/escopo,
        # deliberadamente fora desta etapa (ver relatório da Etapa 8).
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Não foi possível concluir o cadastro com os dados informados."
            )

        return value

    def validate(self, attrs):
        # Etapa 8 — Fase D: AUTH_PASSWORD_VALIDATORS (settings.py) já existia
        # configurado, mas nunca era executado no registro — só o
        # min_length=8 do campo acima rodava. Roda em validate() (nível de
        # objeto, não do campo password sozinho) porque
        # UserAttributeSimilarityValidator precisa de email/first_name/
        # last_name já validados para comparar a senha contra eles.
        user = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            password_validation.validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs