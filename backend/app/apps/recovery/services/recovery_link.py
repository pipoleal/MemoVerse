from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.experiences.models import ExperienceDraft

from ..models import RecoveryLoginToken

# Curto de propósito: o link só precisa sobreviver o tempo de alguém abrir o
# e-mail/WhatsApp e clicar — nunca uma sessão de longa duração (isso é o que
# o par access/refresh emitido em RecoveryTokenRedeemView passa a fazer,
# exatamente como um login normal).
TOKEN_TTL_HOURS = 72


def create_recovery_link(draft: ExperienceDraft) -> str:
    """Cria um RecoveryLoginToken novo para este draft e devolve a URL
    pronta para entrar no corpo do e-mail/WhatsApp (ver
    apps.recovery.content). Sempre um token NOVO por chamada — nunca
    reaproveita um já emitido, mesmo que ainda válido: cada mensagem
    enviada (1h/24h/72h) tem seu próprio link, então revogar/expirar um não
    afeta os outros."""

    if draft.owner_id is None:
        raise ValueError("Só é possível criar um link de recuperação para um draft já reivindicado (owner != None).")

    token = secrets.token_urlsafe(32)
    RecoveryLoginToken.objects.create(
        token=token,
        user_id=draft.owner_id,
        draft=draft,
        expires_at=timezone.now() + timedelta(hours=TOKEN_TTL_HOURS),
    )
    return f"{settings.FRONTEND_BASE_URL}/r/{token}"
