"""Publica um ExperienceDraft já pago, gerando um slug público estável.

Regras de negócio que vivem aqui (e não na view):
- só aceita publicar um draft com status PAID (nunca draft/awaiting_payment/
  payment_failed) — apps.experiences.views.DraftPublishView traduz a recusa
  em HTTP 409, mas quem decide é este service;
- idempotente: publicar um draft já PUBLISHED retorna o mesmo resultado
  (mesmo slug, mesmo published_at), sem gerar um slug novo nem regredir
  nenhum estado — mesma filosofia de
  PaymentConfirmationService._mark_draft_paid;
- o slug é gerado só no momento da primeira publicação (nunca antes, nunca a
  partir de título ou outro dado editável pelo usuário — evita vazar um
  identificador estável de algo que pode nunca ser pago/publicado, e evita
  que editar o título depois mude a URL pública);
- unicidade garantida pela constraint UNIQUE do banco
  (ExperienceDraft.slug), com retry em caso de colisão — mesmo padrão de
  defesa em profundidade já usado em
  CheckoutService._get_or_create_active_payment.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import ExperienceDraft

logger = logging.getLogger(__name__)

# 6 bytes -> 8 caracteres URL-safe (base64). Curto, mas com entropia
# suficiente (2**48 combinações) para colisão ser praticamente só um evento
# de "duas tentativas aleatórias bateram", nunca um vetor de enumeração.
SLUG_BYTES = 6
MAX_SLUG_ATTEMPTS = 5


class PublicationError(Exception):
    """Base para falhas de negócio da publicação (não erros de programação)."""


class DraftNotPayable(PublicationError):
    """O draft não está com status PAID — não pode ser publicado."""

    def __init__(self, draft: ExperienceDraft):
        self.draft = draft
        super().__init__(f"ExperienceDraft {draft.id} não pode ser publicado no status '{draft.status}'.")


def _generate_slug() -> str:
    return secrets.token_urlsafe(SLUG_BYTES)


class PublicationService:
    """Ponto único de publicação de um ExperienceDraft."""

    @staticmethod
    def publish(draft: ExperienceDraft) -> ExperienceDraft:
        with transaction.atomic():
            # select_for_update serializa tentativas concorrentes de publicar
            # o MESMO draft (efetivo em Postgres; no-op seguro em SQLite, nos
            # testes) — mesmo padrão de CheckoutService/PaymentConfirmationService.
            locked = ExperienceDraft.objects.select_for_update().get(pk=draft.pk)

            if locked.status == ExperienceDraft.Status.PUBLISHED:
                # Já publicado (retry do cliente, duplo clique, nova visita à
                # tela) — idempotente: nunca gera um segundo slug nem
                # sobrescreve published_at.
                return locked

            if locked.status != ExperienceDraft.Status.PAID:
                raise DraftNotPayable(locked)

            return PublicationService._assign_unique_slug(locked)

    @staticmethod
    def _assign_unique_slug(draft: ExperienceDraft) -> ExperienceDraft:
        last_error: IntegrityError | None = None

        for _ in range(MAX_SLUG_ATTEMPTS):
            try:
                # Savepoint aninhado: uma colisão de slug (chocar com o slug
                # de OUTRO draft) só desfaz esta tentativa, não a transação
                # externa que já segura o lock de `draft` acima.
                with transaction.atomic():
                    now = timezone.now()
                    draft.slug = _generate_slug()
                    draft.status = ExperienceDraft.Status.PUBLISHED
                    draft.published_at = now
                    draft.expires_at = PublicationService._compute_expires_at(draft, published_at=now)
                    draft.save(
                        update_fields=["slug", "status", "published_at", "expires_at", "updated_at"]
                    )
                return draft
            except IntegrityError as exc:
                last_error = exc
                continue

        raise last_error

    @staticmethod
    def _compute_expires_at(draft: ExperienceDraft, *, published_at):
        # Import tardio: evita import circular no carregamento dos apps (o
        # model Payment referencia ExperienceDraft só por string, mas
        # apps.experiences importar apps.payments no nível do módulo
        # inverteria essa dependência já no import).
        from apps.payments.models import Payment

        # A duração é sempre a do Plan do pagamento que efetivamente aprovou
        # este draft — nunca um dado que o cliente possa influenciar. Um
        # draft PAID sempre tem exatamente um Payment aprovado (regra de
        # negócio: DraftAlreadyPaid impede qualquer novo checkout depois
        # disso) — o fallback None (nunca expira) é só defensivo.
        approved_payment = (
            Payment.objects.filter(draft=draft, status=Payment.Status.APPROVED)
            .select_related("plan")
            .order_by("-created_at")
            .first()
        )
        if approved_payment is None:
            logger.warning(
                "Draft %s publicado sem nenhum Payment aprovado encontrado; expires_at ficará None.",
                draft.id,
            )
            return None

        plan = approved_payment.plan
        # is_lifetime é a fonte de verdade: default True cobre tanto planos
        # antigos (essential/stellar, que não têm essa chave em features)
        # quanto qualquer plano futuro que esqueça de declará-la — o
        # comportamento seguro é sempre "nunca expira", nunca o oposto.
        if plan.get_feature("is_lifetime", True):
            return None

        duration_days = plan.get_feature("duration_days")
        if not duration_days:
            return None

        return published_at + timedelta(days=duration_days)
