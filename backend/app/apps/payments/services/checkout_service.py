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

Dois meios de pagamento suportados, sempre pela mesma Orders API:
- Pix: `payment_method={id: pix, type: bank_transfer}` — payload construído
  inteiramente pelo backend, nenhum dado vindo do cliente.
- Cartão (Card Payment Brick): `payment_method={id, type: credit_card,
  token, installments}` — id/token/installments vêm do Brick (nunca número
  de cartão/CVV, que o Brick nunca entrega a este backend); type é fixo
  "credit_card" neste primeiro escopo (débito fica para uma iteração
  seguinte: o formData do Brick, confirmado via documentação oficial, não
  distingue credit/debit, só payment_method_id/token/installments).
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan
from .mercadopago_client import MercadoPagoClient, MercadoPagoClientError
from .payment_confirmation_service import PaymentConfirmationError, PaymentConfirmationService

logger = logging.getLogger(__name__)


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


class DraftAlreadyPaid(CheckoutError):
    """O draft já foi pago (ou publicado) — nenhuma nova tentativa de
    checkout é permitida, mesmo que o Payment aprovado seja um estado
    terminal e por isso não colida com uniq_active_payment_per_draft (essa
    constraint só cobre pending/in_process/action_required).

    Checar Draft.status (e não Payment.status == APPROVED diretamente) cobre
    os dois casos pedidos ("Payment approved" e "Draft PAID") com uma única
    verificação: PaymentConfirmationService._mark_draft_paid é o único lugar
    que leva um Payment a APPROVED, e sempre marca o Draft como PAID (ou o
    encontra já PUBLISHED) no mesmo passo — esse invariante nunca diverge."""

    def __init__(self, draft: ExperienceDraft):
        self.draft = draft
        super().__init__(
            f"O draft {draft.id} já está com status '{draft.status}' — não é permitido iniciar um novo checkout."
        )


class CheckoutService:
    """Ponto único de orquestração do checkout de um ExperienceDraft."""

    @staticmethod
    def start_checkout(
        *,
        draft: ExperienceDraft,
        plan: Plan,
        mp_client: MercadoPagoClient | None = None,
        payer_first_name: str | None = None,
        payment_method: str = "pix",
        card_token: str | None = None,
        card_payment_method_id: str | None = None,
        card_installments: int | None = None,
    ) -> Payment:
        # payer_first_name: opt-in explícito, nunca aceito via HTTP (a view
        # nunca passa esse argumento). Existe só para permitir, sob demanda
        # (ex.: manage.py shell), disparar o mecanismo oficial de
        # auto-aprovação "APRO" do Sandbox da Mercado Pago em um checkout
        # real — nunca ativado por um checkout Sandbox comum.
        payment = CheckoutService._get_or_create_active_payment(draft=draft, plan=plan)

        if payment.mp_order_id:
            # Order já criada em uma tentativa anterior (retomada de checkout):
            # não repetir a chamada à MP. payment_method/card_* do chamador
            # atual são ignorados neste caso — a Order já existe com o método
            # da tentativa que a criou.
            return payment

        if mp_client is None:
            try:
                mp_client = MercadoPagoClient()
            except MercadoPagoClientError as exc:
                # Configuração ausente/inválida (ex.: MP_ACCESS_TOKEN não setado)
                # é uma falha de gateway do ponto de vista do chamador — mesmo
                # tratamento/502 que uma falha na chamada real à Mercado Pago,
                # nunca um 500 cru vazando detalhe de configuração do servidor.
                raise CheckoutGatewayError(payment, exc) from exc

        return CheckoutService._create_order(
            payment=payment,
            draft=draft,
            mp_client=mp_client,
            payer_first_name=payer_first_name,
            payment_method=payment_method,
            card_token=card_token,
            card_payment_method_id=card_payment_method_id,
            card_installments=card_installments,
        )

    @staticmethod
    def _get_or_create_active_payment(*, draft: ExperienceDraft, plan: Plan) -> Payment:
        try:
            with transaction.atomic():
                # select_for_update serializa tentativas concorrentes de checkout
                # para o MESMO draft (efetivo em Postgres; no-op seguro em SQLite,
                # onde a UniqueConstraint abaixo assume a defesa final). Também
                # serializa a checagem de "já pago" logo abaixo: duas requisições
                # simultâneas num draft já PAID nunca correm essa checagem em
                # paralelo — a segunda só lê o status depois que a primeira já
                # liberou o lock (commit/rollback), nunca antes.
                locked_draft = ExperienceDraft.objects.select_for_update().get(pk=draft.pk)

                if locked_draft.status in (ExperienceDraft.Status.PAID, ExperienceDraft.Status.PUBLISHED):
                    # Levanta ANTES de qualquer leitura/escrita de Payment e antes
                    # de qualquer construção de MercadoPagoClient (isso acontece
                    # depois, em start_checkout) — garante que nenhuma chamada de
                    # rede à Mercado Pago é feita para um draft já pago.
                    raise DraftAlreadyPaid(locked_draft)

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

    # TEMPORÁRIO — teste controlado de produção com cobrança real de R$1,00.
    # Restrito ao e-mail exato do dono do draft (nunca a um valor vindo do
    # cliente) — nenhum outro usuário consegue disparar isso. Remover este
    # bloco e a referência em _create_attempt logo após o teste.
    _TEMP_R1_TEST_OWNER_EMAIL = "felipeleal12345678910@gmail.com"

    @staticmethod
    def _create_attempt(*, draft: ExperienceDraft, plan: Plan) -> Payment:
        next_attempt = (
            Payment.objects.filter(draft=draft).aggregate(last=Max("attempt_number"))["last"] or 0
        ) + 1

        # Congelado a partir de Plan.price/currency agora. A partir daqui
        # Payment.amount é a fonte histórica deste pagamento — nunca
        # recalculado a partir do preço atual do Plan. TEMPORÁRIO: exceção
        # de R$1,00 restrita ao e-mail exato do dono do draft (ver acima).
        amount = plan.price
        if draft.owner.email == CheckoutService._TEMP_R1_TEST_OWNER_EMAIL:
            amount = Decimal("1.00")

        return Payment.objects.create(
            draft=draft,
            owner=draft.owner,
            plan=plan,
            attempt_number=next_attempt,
            amount=amount,
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
        payment_method: str = "pix",
        card_token: str | None = None,
        card_payment_method_id: str | None = None,
        card_installments: int | None = None,
    ) -> Payment:
        payer = {"email": _payer_email_for(email=draft.owner.email, environment=mp_client.environment)}
        # Segunda trava, independente da chamadora: o mecanismo "APRO" de
        # auto-aprovação da Mercado Pago só é enviado se o ambiente também
        # for sandbox. Mesmo um payer_first_name="APRO" passado por engano
        # nunca chega à Mercado Pago em produção.
        if payer_first_name and mp_client.environment == "sandbox":
            payer["first_name"] = payer_first_name

        if payment_method == "card":
            # Payload confirmado via documentação oficial da Orders API
            # (não inventado): id/type/token/installments. issuer_id
            # deliberadamente NUNCA incluído aqui — não confirmado no
            # schema documentado deste endpoint, mesmo sendo devolvido pelo
            # Brick ao frontend.
            order_payment_method = {
                "id": card_payment_method_id,
                "type": "credit_card",
                "token": card_token,
                "installments": card_installments,
            }
        else:
            order_payment_method = {"id": "pix", "type": "bank_transfer"}

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
                        "payment_method": order_payment_method,
                    }
                ],
            )
        except MercadoPagoClientError as exc:
            raise CheckoutGatewayError(payment, exc) from exc

        payment.mp_order_id = result.order_id
        payment.mp_payment_id = result.payment_id
        payment.last_sync_payload = result.raw
        payment.save(update_fields=["mp_order_id", "mp_payment_id", "last_sync_payload", "updated_at"])

        # Pix normalmente volta action_required nesta resposta síncrona
        # (nunca aprovado aqui, ver _payer_email_for/payer_first_name) — o
        # Draft precisa refletir "pagamento em andamento" mesmo antes de
        # qualquer confirmação. A chamada abaixo só avança o Draft além
        # disso quando o resultado já vier aprovado (cartão); para Pix é
        # um no-op e o Draft permanece exatamente aqui.
        draft.status = ExperienceDraft.Status.AWAITING_PAYMENT
        draft.save(update_fields=["status", "updated_at"])

        # Confirmação síncrona: se a Mercado Pago já respondeu aprovado
        # (cartão), aplica Payment=APPROVED/Draft=PAID agora, sem esperar o
        # webhook — reaproveita a mesma decisão de estado que o webhook usa
        # (PaymentConfirmationService.confirm_from_result), com o `result`
        # que acabamos de receber: nenhuma chamada HTTP extra à Mercado
        # Pago. O webhook continua sendo o mecanismo de reconciliação: se
        # chegar depois, encontra tudo já aplicado e não faz nada
        # (idempotente); numa corrida hipotética em que chegasse antes, o
        # mesmo vale no sentido inverso.
        try:
            payment = PaymentConfirmationService.confirm_from_result(payment=payment, result=result)
        except PaymentConfirmationError:
            # Falha de negócio na confirmação (ex.: correlação divergente) —
            # não deveria acontecer aqui (é a mesma Order que acabamos de
            # criar), mas a Mercado Pago já aprovou o pagamento do lado
            # dela: não é seguro transformar isso num erro para quem só quer
            # saber que o pagamento foi aceito. Registrado para investigação
            # (nunca escondido), e o webhook reconcilia depois.
            logger.warning(
                "Confirmação síncrona falhou para o Payment %s logo após a criação da Order %s; "
                "Payment/Draft ficam como estavam até o webhook reconciliar.",
                payment.id,
                result.order_id,
                exc_info=True,
            )

        return payment
