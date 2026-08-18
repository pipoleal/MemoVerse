"""Limpa uploads de mídia abandonados (upload_status=PENDING há mais de
settings.PENDING_MEDIA_EXPIRATION_MINUTES) de um draft.

Por que aqui, e não um job/cron separado: o único lugar que precisa de uma
contagem "ativa" de mídia correta é MediaUploadIntentView, ao checar a
quota (ver views.py) — plugar a limpeza direto nesse fluxo garante que a
quota nunca fica presa por um upload que o cliente nunca completou (aba
fechada, rede caiu antes do PUT, etc.), sem exigir infraestrutura de
agendamento só para isso.

Best-effort quanto ao R2 (mesmo contrato descrito em storage.delete_object):
uma falha ao remover o objeto do bucket nunca impede a remoção do registro
— uma pending expirada não deve travar a quota do usuário indefinidamente
só porque o R2 está indisponível no momento. Um objeto órfão no bucket,
se isso acontecer, nunca é servido a ninguém: generate_presigned_read_url só
é chamado para mídia com upload_status=UPLOADED.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from ..models import ExperienceDraft, Media
from ..storage import delete_object

logger = logging.getLogger(__name__)


def cleanup_abandoned_media(draft: ExperienceDraft) -> None:
    cutoff = timezone.now() - timedelta(minutes=settings.PENDING_MEDIA_EXPIRATION_MINUTES)
    abandoned = Media.objects.filter(
        draft=draft,
        upload_status=Media.UploadStatus.PENDING,
        created_at__lt=cutoff,
    )
    for media in abandoned:
        try:
            delete_object(media.storage_key)
        except (ImproperlyConfigured, ClientError):
            # Best-effort: o registro é removido de qualquer forma (ver
            # docstring do módulo) — só registra para investigação manual.
            logger.warning(
                "Falha ao remover objeto R2 %s durante limpeza de mídia abandonada.",
                media.storage_key,
            )
        media.delete()
