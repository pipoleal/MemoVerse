"""Orquestra a criação/retomada de checkout: Draft -> Plan -> Payment -> Order.

Regras de negócio que vivem aqui (e não na view):
- alocação de attempt_number sem reuso, protegida por transaction.atomic +
  select_for_update, com a UniqueConstraint do banco como última defesa;
- reaproveitamento de um Payment ativo (pending/in_process/action_required)
  em vez de criar um novo, tornando o endpoint seguro contra duplo clique,
  refresh, retry e abas simultâneas;
- geração de external_reference e idempotency_key no backend, nunca
  aceitos do cliente;
- chamada à MercadoPagoClient (única forma de a camada de domínio falar com
  a Mercado Pago) e persistência do resultado normalizado.

MVP: a Order é sempre criada com Pix (`payment_method={id: pix, type:
bank_transfer}`). É o único meio de pagamento cujos dados obrigatórios já
existem hoje no domínio (payer.email) e que não depende de um token gerado
no cliente — cartão via Checkout Bricks é escopo da Fase 6.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan
from .mercadopago_client import MercadoPagoClient, MercadoPagoClientError
from .status_mapping import map_order_status


class CheckoutError(Exception):
    """Base para erros de negócio do checkout (não erros de programação)."""


class ActiveCheckoutConflict(CheckoutError):
    """Já existe um Payment ativo para este draft, mas para outro plano."""

    def __init__(self, payment: Payment):
        self.payment = payment
        super().__init__(
            f"Já existe um checkout ativo para o draft {payment.draft_id} "
            f"com o plano '{payment.plan.code}'."
        )


class CheckoutGatewayError(CheckoutError):
    """A chamada à Mercado Pago falhou. O Payment local (status=pending, sem
    mp_order_id) permanece como está e pode ser retomado com segurança —
    mesma idempotency_key — em uma nova tentativa de checkout."""

    def __init__(self, payment: Payment, original: Exception):
        self.payment = payment
        self.original = original
        super().__init__(f"Falha ao criar a Order na Mercado Pago para o Payment {payment.id}.")


class CheckoutService:
    """Ponto único de orquestração do checkout de um ExperienceDraft."""

    @staticmethod
    def start_checkout(*, draft: ExperienceDraft, plan: Plan, mp_client: MercadoPagoClient | None = None) -> Payment:
        payment = CheckoutService._get_or_create_active_payment(draft=draft, plan=plan)

        if payment.mp_order_id:
            # Order já criada em uma tentativa anterior (retomada de checkout):
            # não repetir a chamada à MP.
            return payment

        return CheckoutService._create_order(payment=payment, draft=draft, mp_client=mp_client or MercadoPagoClient())

    @staticmethod
    def _get_or_create_active_payment(*, draft: ExperienceDraft, plan: Plan) -> Payment:
        try:
            with transaction.atomic():
                # select_for_update serializa tentativas concorrentes de checkout
                # para o MESMO draft (efetivo em Postgres; no-op seguro em SQLite,
                # onde a UniqueConstraint abaixo assume a defesa final).
                ExperienceDraft.objects.select_for_update().filter(pk=draft.pk).first()

                active_payment = (
                    Payment.objects.select_for_update()
                    .filter(draft=draft, status__in=Payment.ACTIVE_STATUSES)
                    .first()
                )
                if active_payment is not None:
                    return CheckoutService._reuse_or_conflict(active_payment, plan)

                return CheckoutService._create_attempt(draft=draft, plan=plan)
        except IntegrityError:
            # Última linha de defesa: duas requisições venceram a checagem acima
            # (backend sem locking real de linha) e colidiram na constraint
            # uniq_active_payment_per_draft. Recuperamos a tentativa que venceu
            # a corrida em vez de propagar o erro ao usuário.
            active_payment = Payment.objects.filter(draft=draft, status__in=Payment.ACTIVE_STATUSES).first()
            if active_payment is None:
                raise
            return CheckoutService._reuse_or_conflict(active_payment, plan)

    @staticmethod
    def _reuse_or_conflict(active_payment: Payment, plan: Plan) -> Payment:
        if active_payment.plan_id != plan.id:
            raise ActiveCheckoutConflict(active_payment)
        return active_payment

    @staticmethod
    def _create_attempt(*, draft: ExperienceDraft, plan: Plan) -> Payment:
        next_attempt = (
            Payment.objects.filter(draft=draft).aggregate(last=Max("attempt_number"))["last"] or 0
        ) + 1
        reference_suffix = f"draft-{draft.id}-attempt-{next_attempt}"

        return Payment.objects.create(
            draft=draft,
            owner=draft.owner,
            plan=plan,
            attempt_number=next_attempt,
            # Congelado a partir de Plan.price/currency agora. A partir daqui
            # Payment.amount é a fonte histórica deste pagamento — nunca
            # recalculado a partir do preço atual do Plan.
            amount=plan.price,
            currency=plan.currency,
            status=Payment.Status.PENDING,
            external_reference=f"memoverse:draft:{draft.id}:attempt:{next_attempt}",
            idempotency_key=f"memoverse:idem:{reference_suffix}",
        )

    @staticmethod
    def _create_order(*, payment: Payment, draft: ExperienceDraft, mp_client: MercadoPagoClient) -> Payment:
        try:
            result = mp_client.create_order(
                amount=payment.amount,
                currency=payment.currency,
                external_reference=payment.external_reference,
                idempotency_key=payment.idempotency_key,
                payer={"email": draft.owner.email},
                payments=[
                    {
                        "amount": f"{payment.amount:.2f}",
                        "payment_method": {"id": "pix", "type": "bank_transfer"},
                    }
                ],
            )
        except MercadoPagoClientError as exc:
            raise CheckoutGatewayError(payment, exc) from exc

        payment.mp_order_id = result.order_id
        payment.mp_payment_id = result.payment_id
        payment.status = map_order_status(result.status) or payment.status
        payment.last_sync_payload = result.raw
        payment.save(update_fields=["mp_order_id", "mp_payment_id", "status", "last_sync_payload", "updated_at"])

        # Confirmação real (paid/published) só acontece depois, via webhook.
        draft.status = ExperienceDraft.Status.AWAITING_PAYMENT
        draft.save(update_fields=["status", "updated_at"])

        return payment
