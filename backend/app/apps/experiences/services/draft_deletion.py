"""Exclusão segura de um ExperienceDraft ainda em rascunho.

Regras de negócio que vivem aqui (e não na view), mesma filosofia de
PublicationService/CheckoutService:
- só aceita excluir um draft com status DRAFT e sem slug (nunca
  awaiting_payment/payment_failed/paid/published) — quem decide isso é este
  service, a view só traduz a recusa em HTTP 409;
- nunca exclui um draft com qualquer Payment associado, em qualquer status
  — checado explicitamente aqui, e reforçado por uma segunda rede de
  segurança independente: Payment.draft é on_delete=PROTECT, então mesmo
  que este check fosse burlado por algum caminho futuro, o próprio Django
  recusaria o delete (ProtectedError) em vez de silenciosamente apagar um
  draft com histórico de pagamento;
- Media.draft é on_delete=CASCADE — apagar o draft já remove os registros
  de Media no banco automaticamente; este service só precisa remover os
  objetos correspondentes no R2 antes (o CASCADE não alcança storage
  externo).

R2: reutiliza exatamente a mesma infraestrutura e o mesmo contrato
best-effort já usados por views.MediaDeleteView e
services.media_cleanup.cleanup_abandoned_media (ver docstring de
storage.delete_object) — uma falha ao remover um objeto do R2 nunca impede
a remoção do draft/registros no banco. Isso nunca deixa "mídia órfã" no
sentido que importa: um objeto órfão no bucket, se isso acontecer, nunca é
servido a ninguém (generate_presigned_read_url só é chamado para mídia com
upload_status=UPLOADED referenciada por um draft que ainda existe); o que
existiria é, na pior das hipóteses, um objeto esquecido no bucket, nunca um
registro no banco apontando para um draft que não existe mais.
"""

from __future__ import annotations

import logging

from botocore.exceptions import ClientError
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from apps.payments.models import Payment

from ..models import ExperienceDraft, Media
from ..storage import delete_object

logger = logging.getLogger(__name__)


class DraftDeletionError(Exception):
    """Base para falhas de negócio da exclusão (não erros de programação)."""


class DraftNotDeletable(DraftDeletionError):
    """O draft não está em status DRAFT sem slug, ou tem Payment associado
    — não pode ser excluído."""

    def __init__(self, draft: ExperienceDraft):
        self.draft = draft
        super().__init__(f"ExperienceDraft {draft.id} não pode ser excluído no status '{draft.status}'.")


class DraftDeletionService:
    """Ponto único de exclusão de um ExperienceDraft ainda em rascunho."""

    @staticmethod
    def delete(draft: ExperienceDraft) -> None:
        with transaction.atomic():
            # select_for_update serializa tentativas concorrentes sobre o
            # MESMO draft (ex.: duplo clique, ou uma corrida com um checkout
            # que está sendo criado neste exato momento) — mesmo padrão de
            # CheckoutService/PublicationService.
            locked = ExperienceDraft.objects.select_for_update().get(pk=draft.pk)

            if locked.status != ExperienceDraft.Status.DRAFT or locked.slug:
                raise DraftNotDeletable(locked)

            if Payment.objects.filter(draft=locked).exists():
                raise DraftNotDeletable(locked)

            media_items = list(Media.objects.filter(draft=locked))

            for media in media_items:
                try:
                    delete_object(media.storage_key)
                except (ImproperlyConfigured, ClientError):
                    # Best-effort, mesmo contrato de storage.delete_object /
                    # MediaDeleteView / media_cleanup: o registro é removido
                    # de qualquer forma (ver docstring do módulo) — só
                    # registra para investigação manual.
                    logger.warning(
                        "Falha ao remover objeto R2 %s durante exclusão do draft %s.",
                        media.storage_key,
                        locked.id,
                    )

            # Media.draft é on_delete=CASCADE: apagar o draft já remove os
            # registros de Media no banco, sem precisar de um loop de
            # media.delete() adicional. Payment.draft é on_delete=PROTECT:
            # se por algum motivo um Payment tivesse sido criado entre o
            # SELECT FOR UPDATE acima e esta linha, o Django recusaria este
            # delete com ProtectedError em vez de apagar silenciosamente —
            # segunda rede de segurança, independente do check explícito
            # feito acima.
            locked.delete()
