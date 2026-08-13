"""Confirmação server-side de pagamentos: a única porta de entrada pela qual
um Payment pode chegar a APPROVED.

    Webhook (resource_id)
        -> localiza o Payment local (mp_order_id)
        -> consulta a Order real na Mercado Pago (Access Token do servidor)
        -> valida a correspondência (external_reference)
        -> aplica a transição de status (com defesa contra regressão)
        -> se aprovado: marca o ExperienceDraft como pago (idempotente)

O payload do webhook NUNCA decide o status: ele só aponta qual Order
consultar. A fonte da verdade é sempre a resposta de
MercadoPagoClient.get_order() — nunca o corpo da notificação.
"""

from __future__ import annotations

from django.db import transaction

from apps.experiences.models import ExperienceDraft

from ..models import Payment
from .mercadopago_client import MercadoPagoClient, MercadoPagoOrderResult
from .status_mapping import map_order_status

__all__ = [
    "PaymentConfirmationError",
    "PaymentNotFound",
    "OrderMismatch",
    "PaymentConfirmationService",
]


class PaymentConfirmationError(Exception):
    """Base para falhas de negócio da confirmação (não erros de programação).

    Não inclui falhas de comunicação com a Mercado Pago — essas continuam
    sendo MercadoPagoClientError (ver services.mercadopago_client), que o
    chamador deve tratar separadamente como transientes/retentáveis.
    """


class PaymentNotFound(PaymentConfirmationError):
    """Nenhum Payment local corresponde ao resource_id notificado."""


class OrderMismatch(PaymentConfirmationError):
    """A Order consultada na Mercado Pago não corresponde ao Payment local
    (id ou external_reference divergentes). Nunca aprovar nesse caso."""


class PaymentConfirmationService:
    """Ponto único de confirmação real de um Payment a partir de uma Order."""

    @staticmethod
    def confirm_from_order_id(*, mp_order_id: str, mp_client: MercadoPagoClient | None = None) -> Payment:
        try:
            payment = Payment.objects.select_related("draft", "owner").get(mp_order_id=mp_order_id)
        except Payment.DoesNotExist as exc:
            raise PaymentNotFound(f"Nenhum Payment local para mp_order_id={mp_order_id}.") from exc

        if payment.owner_id != payment.draft.owner_id:
            # Nunca deveria acontecer (CheckoutService sempre cria Payment com
            # owner=draft.owner) — defesa em profundidade, não um caminho
            # esperado. Ver regra "um usuário nunca acessa pagamento de outro".
            raise OrderMismatch(f"Payment {payment.id} tem owner divergente do seu próprio draft.")

        client = mp_client or MercadoPagoClient()
        # MercadoPagoClientError (falha de rede/gateway/resposta inválida) se
        # propaga para o chamador: é uma falha TRANSIENTE, não uma decisão de
        # negócio — quem decide como reagir (ex.: pedir novo envio do webhook)
        # é a view, não este service.
        result = client.get_order(order_id=mp_order_id)

        PaymentConfirmationService._validate_correlation(payment=payment, result=result)
        PaymentConfirmationService._apply_result(payment_id=payment.id, result=result)

        return Payment.objects.get(pk=payment.id)

    @staticmethod
    def _validate_correlation(*, payment: Payment, result: MercadoPagoOrderResult) -> None:
        if str(result.order_id) != str(payment.mp_order_id):
            # Correlação barata e explícita: buscamos pelo próprio order_id,
            # então isto não deveria acontecer — mas nunca aprovamos "por
            # coincidência" caso a resposta não bata com o que pedimos.
            raise OrderMismatch(
                f"Order retornada ({result.order_id}) não corresponde ao Payment "
                f"consultado ({payment.mp_order_id})."
            )

        order_external_reference = (result.raw or {}).get("external_reference")
        if order_external_reference and order_external_reference != payment.external_reference:
            raise OrderMismatch(
                f"external_reference da Order ({order_external_reference}) não corresponde "
                f"ao Payment {payment.id} ({payment.external_reference})."
            )

    @staticmethod
    def _apply_result(*, payment_id, result: MercadoPagoOrderResult) -> None:
        with transaction.atomic():
            # Trava o Draft antes do Payment, na MESMA ordem usada por
            # CheckoutService (Draft -> Payment). Ordem de lock consistente
            # entre os dois services evita deadlock em Postgres quando um
            # retry de checkout e uma confirmação de webhook para o mesmo
            # draft acontecem ao mesmo tempo.
            draft_id = Payment.objects.only("draft_id").get(pk=payment_id).draft_id
            draft = ExperienceDraft.objects.select_for_update().get(pk=draft_id)

            # Re-busca o Payment sob lock: dois webhooks para a mesma Order
            # não podem aplicar a mesma transição duas vezes nem correr uma
            # por cima da outra (requisito "dois webhooks simultâneos").
            payment = Payment.objects.select_for_update().get(pk=payment_id)

            mapped_status = map_order_status(result.status)
            next_status = PaymentConfirmationService._next_status(payment.status, mapped_status)

            update_fields = ["status", "last_sync_payload", "updated_at"]
            payment.status = next_status
            payment.last_sync_payload = result.raw
            if result.payment_id and result.payment_id != payment.mp_payment_id:
                payment.mp_payment_id = result.payment_id
                update_fields.append("mp_payment_id")
            payment.save(update_fields=update_fields)

            if next_status == Payment.Status.APPROVED:
                PaymentConfirmationService._mark_draft_paid(draft)

    @staticmethod
    def _next_status(current: str, mapped: str | None) -> str:
        """Aplica a transição, com defesa contra regressão de estados
        terminais (Fase 4.5):

        - status não reconhecido (ex.: charged_back) -> mantém o atual;
        - já APPROVED -> só avança para REFUNDED (nunca regride para
          rejected/cancelled/expired vindo de um webhook antigo/fora de ordem);
        - já em outro estado terminal (rejected/cancelled/expired/refunded)
          -> permanece; uma nova tentativa aprovada vive em um Payment novo
          (attempt_number seguinte), nunca reescreve esta linha;
        - caso contrário (pending/in_process/action_required) -> livre para
          avançar para o status mapeado.
        """

        if mapped is None:
            return current
        if current == mapped:
            return current

        terminal_statuses = set(Payment.Status.values) - set(Payment.ACTIVE_STATUSES)

        if current == Payment.Status.APPROVED:
            return mapped if mapped == Payment.Status.REFUNDED else current
        if current in terminal_statuses:
            return current
        return mapped

    @staticmethod
    def _mark_draft_paid(draft: ExperienceDraft) -> None:
        """Recebe o Draft já travado (select_for_update) por _apply_result."""

        if draft.status in (ExperienceDraft.Status.PAID, ExperienceDraft.Status.PUBLISHED):
            # Já processado (retry/segundo webhook) ou publicado — idempotente,
            # nunca reverte um Draft já pago/publicado (regra 11).
            return

        draft.status = ExperienceDraft.Status.PAID
        draft.save(update_fields=["status", "updated_at"])
