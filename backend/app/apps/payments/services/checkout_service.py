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


def _payer_email_for(*, email: str, environment: str) -> str:
    """Endereço a enviar como payer.email para a Orders API.

    Confirmado via chamada real à API (não especulação): em Sandbox, a
    Orders API rejeita com HTTP 400 "invalid_email_for_sandbox" qualquer
    payer.email que não termine em "@testuser.com" — mesmo com um payload
    por outro lado idêntico ao exigido. Preservamos o local-part do e-mail
    real do usuário (não um endereço fixo compartilhado) só para manter
    alguma correlação legível nos logs/dashboard da MP. Em produção,
    o e-mail real do usuário é sempre usado, sem transformação.
    """

    if environment != "sandbox":
        return email
    local_part = email.split("@", 1)[0]
    return f"{local_part}@testuser.com"


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
    def start_checkout(
        *,
        draft: ExperienceDraft,
        plan: Plan,
        mp_client: MercadoPagoClient | None = None,
        payer_first_name: str | None = None,
    ) -> Payment:
        # payer_first_name: opt-in explícito, nunca aceito via HTTP (a view
        # nunca passa esse argumento). Existe só para permitir, sob demanda
        # (ex.: manage.py shell), disparar o mecanismo oficial de
        # auto-aprovação "APRO" do Sandbox da Mercado Pago em um checkout
        # real — nunca ativado por um checkout Sandbox comum.
        payment = CheckoutService._get_or_create_active_payment(draft=draft, plan=plan)

        if payment.mp_order_id:
            # Order já criada em uma tentativa anterior (retomada de checkout):
            # não repetir a chamada à MP.
            return payment

        return CheckoutService._create_order(
            payment=payment,
            draft=draft,
            mp_client=mp_client or MercadoPagoClient(),
            payer_first_name=payer_first_name,
        )

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
            # A Orders API só aceita [A-Za-z0-9_-] em external_reference (rejeita
            # ":" com HTTP 400 "does not match pattern") e no máximo 64 chars.
            external_reference=f"memoverse-draft-{draft.id}-attempt-{next_attempt}",
            # Curto de propósito: o SDK da Mercado Pago rejeita
            # x-idempotency-key acima de 64 caracteres. "mv:<uuid>:<n>" fica
            # em ~41-42 chars (draft.id sozinho já ocupa 36), com folga.
            idempotency_key=f"mv:{draft.id}:{next_attempt}",
        )

    @staticmethod
    def _create_order(
        *,
        payment: Payment,
        draft: ExperienceDraft,
        mp_client: MercadoPagoClient,
        payer_first_name: str | None = None,
    ) -> Payment:
        payer = {"email": _payer_email_for(email=draft.owner.email, environment=mp_client.environment)}
        # Segunda trava, independente da chamadora: o mecanismo "APRO" de
        # auto-aprovação da Mercado Pago só é enviado se o ambiente também
        # for sandbox. Mesmo um payer_first_name="APRO" passado por engano
        # nunca chega à Mercado Pago em produção.
        if payer_first_name and mp_client.environment == "sandbox":
            payer["first_name"] = payer_first_name

        try:
            result = mp_client.create_order(
                amount=payment.amount,
                currency=payment.currency,
                external_reference=payment.external_reference,
                idempotency_key=payment.idempotency_key,
                payer=payer,
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
