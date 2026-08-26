from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (  # type: ignore[import]
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import MAX_PASSWORD_RESET_ATTEMPTS, PasswordResetCode, User

from .email_service import send_password_reset_email

logger = logging.getLogger(__name__)

CODE_TTL_MINUTES = 10


class InvalidOrExpiredCode(Exception):
    """Código incorreto, expirado, já usado, ou com tentativas esgotadas —
    deliberadamente uma única exceção para todos esses casos: o chamador
    (view) nunca deve conseguir devolver uma mensagem que diferencie um
    motivo do outro, mesma lógica de "nunca revelar existência" já usada em
    PublicExperienceView/SaveExperienceToGalaxyView (ver apps.experiences)."""


def _generate_numeric_code() -> str:
    # secrets (não random) — mesma exigência de aleatoriedade
    # criptograficamente segura já aplicada a claim_token em
    # ExperienceDraft. 6 dígitos = 10^6 combinações; a proteção real contra
    # força bruta vem do limite de tentativas por código + rate limit por
    # IP abaixo, não do tamanho do código em si.
    return f"{secrets.randbelow(1_000_000):06d}"


@transaction.atomic
def request_password_reset(email: str) -> None:
    """Sempre silencioso quanto à existência da conta — o chamador (view)
    devolve a mesma resposta genérica independentemente do que acontece
    aqui dentro. Só gera/envia um código de verdade quando `email`
    corresponde a uma conta real."""

    user = User.objects.filter(email__iexact=email).select_for_update().first()
    if user is None:
        logger.info("auth.password_reset.request.unknown_email")
        return

    # Invalida qualquer código anterior ainda não usado deste usuário —
    # nunca mais de um código válido ao mesmo tempo.
    PasswordResetCode.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    raw_code = _generate_numeric_code()
    reset_code = PasswordResetCode(
        user=user,
        expires_at=timezone.now() + timedelta(minutes=CODE_TTL_MINUTES),
    )
    reset_code.set_code(raw_code)
    reset_code.save()

    # raw_code só existe aqui e dentro do corpo do e-mail — nunca é
    # retornado, logado, ou persistido em texto puro.
    send_password_reset_email(user.email, raw_code, ttl_minutes=CODE_TTL_MINUTES)
    logger.info("auth.password_reset.request.sent")


def verify_password_reset_code(email: str, code: str) -> None:
    """Só confere validade — nunca consome o código (ver
    views/serializers.password_reset: quem consome de verdade é
    confirm_password_reset, atomicamente junto da troca de senha, para que
    um código nunca seja "gasto" sem uma senha nova de fato aplicada).

    O `raise` fica FORA do `with transaction.atomic()` de propósito: uma
    exceção que escapa de um bloco atomic desfaz (rollback) tudo que
    aconteceu dentro dele, incluindo o incremento de `attempts` salvo
    momentos antes — sem essa separação, o contador de tentativas nunca
    persistiria de verdade entre chamadas (confirmado ao vivo: um teste com
    5 tentativas erradas seguidas nunca queimava o código, porque cada
    `raise` desfazia o `save()` da própria tentativa)."""

    is_invalid = False

    with transaction.atomic():
        reset_code = (
            PasswordResetCode.objects.select_for_update()
            .filter(user__email__iexact=email, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )

        if reset_code is None or not reset_code.is_valid:
            is_invalid = True
        elif not reset_code.check_code(code):
            reset_code.attempts += 1
            if reset_code.attempts >= MAX_PASSWORD_RESET_ATTEMPTS:
                reset_code.used_at = timezone.now()
            reset_code.save(update_fields=["attempts", "used_at"])
            is_invalid = True

    if is_invalid:
        logger.info("auth.password_reset.verify.failure")
        raise InvalidOrExpiredCode()

    logger.info("auth.password_reset.verify.success")


def invalidate_all_sessions(user: User) -> None:
    """Blacklista todo refresh token já emitido para `user` — mesma
    infraestrutura que LogoutView já usa (rest_framework_simplejwt.
    token_blacklist), sem nada novo. Chamado depois de uma troca de senha
    bem-sucedida; a pessoa precisa logar de novo em qualquer dispositivo
    (deliberado — ver PasswordResetConfirmView, que não faz login
    automático)."""

    outstanding = OutstandingToken.objects.filter(user=user)
    BlacklistedToken.objects.bulk_create(
        (BlacklistedToken(token=token) for token in outstanding),
        ignore_conflicts=True,
    )


def confirm_password_reset(email: str, code: str, new_password: str) -> None:
    """Revalida o código do zero (nunca confia que um /verify/ anterior
    ainda vale — expiração/tentativas podem ter mudado nesse meio tempo) e,
    se válido, consome-o e troca a senha na MESMA transação: um código só
    é marcado como usado se a senha realmente mudou.

    Mesmo cuidado de verify_password_reset_code: o `raise` do caminho de
    falha fica fora do `with transaction.atomic()`, senão o incremento de
    `attempts` seria desfeito pelo rollback da própria exceção."""

    is_invalid = False

    with transaction.atomic():
        reset_code = (
            PasswordResetCode.objects.select_for_update()
            .filter(user__email__iexact=email, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )

        if reset_code is None or not reset_code.is_valid:
            is_invalid = True
        elif not reset_code.check_code(code):
            reset_code.attempts += 1
            if reset_code.attempts >= MAX_PASSWORD_RESET_ATTEMPTS:
                reset_code.used_at = timezone.now()
            reset_code.save(update_fields=["attempts", "used_at"])
            is_invalid = True
        else:
            user = reset_code.user
            user.set_password(new_password)
            user.save(update_fields=["password"])

            reset_code.used_at = timezone.now()
            reset_code.save(update_fields=["used_at"])

            invalidate_all_sessions(user)

    if is_invalid:
        logger.info("auth.password_reset.confirm.failure")
        raise InvalidOrExpiredCode()

    logger.info("auth.password_reset.confirm.success")
