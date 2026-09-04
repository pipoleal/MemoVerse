import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Modelo principal de usuário do MemoVerse.

    Utiliza autenticação por e-mail e serve como base para
    Galáxias, Experiências e todos os demais módulos da plataforma.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    email = models.EmailField(
        unique=True,
    )

    first_name = models.CharField(
        max_length=100,
    )

    last_name = models.CharField(
        max_length=100,
    )

    # Opcional, sempre em branco por padrão — coletado no cadastro (ver
    # RegisterSerializer) só para quem escolhe informar, como canal extra do
    # fluxo de recuperação de carrinho abandonado (ver apps.recovery). Nunca
    # obrigatório: exigir isso no /register reintroduziria a mesma fricção
    # que a correção do funil de conversão acabou de remover. Formato livre
    # (com DDI/DDD como o usuário digitar) — normalização/validação de
    # verdade fica para quando um provedor de WhatsApp real for integrado.
    phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )

    stars_count = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_staff = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
    ]

    class Meta:
        db_table = "users"
        ordering = ["first_name"]

    def __str__(self):
        return self.email


# "Esqueci minha senha" — recuperação por código de 6 dígitos enviado por
# e-mail. Só o hash do código é gravado (mesmo hasher de User.password,
# django.contrib.auth.hashers — comparação em tempo constante, sem
# dependência nova); o valor em texto puro nunca toca o banco nem os logs,
# só existe no corpo do e-mail enviado.
MAX_PASSWORD_RESET_ATTEMPTS = 5


class PasswordResetCode(models.Model):
    """Um código de recuperação de senha emitido para `user`.

    Uso único: `used_at` é setado tanto em consumo bem-sucedido (troca de
    senha concluída) quanto em esgotamento de tentativas (limite de
    força-bruta) — nos dois casos o código nunca mais serve, e a diferença
    entre os dois casos não precisa ser distinguida em lugar nenhum: um
    código com `used_at` setado é, para toda checagem de validade, idêntico
    a um já usado de verdade.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_codes",
    )

    code_hash = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    # Incrementado a cada tentativa de verificação errada (ver
    # services.password_reset_service). Ao atingir MAX_PASSWORD_RESET_ATTEMPTS,
    # o código é marcado como usado — força a pessoa a pedir um novo em vez
    # de continuar adivinhando o mesmo código indefinidamente mesmo que o
    # rate limit por IP não tenha sido atingido ainda (ex.: dois IPs
    # diferentes tentando o mesmo código).
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "password_reset_codes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "used_at"]),
        ]

    def set_code(self, raw_code: str) -> None:
        self.code_hash = make_password(raw_code)

    def check_code(self, raw_code: str) -> bool:
        return check_password(raw_code, self.code_hash)

    @property
    def is_valid(self) -> bool:
        return (
            self.used_at is None
            and self.attempts < MAX_PASSWORD_RESET_ATTEMPTS
            and self.expires_at > timezone.now()
        )