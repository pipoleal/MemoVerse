from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan
from ..services.mercadopago_client import MercadoPagoGatewayError, MercadoPagoOrderResult
from ..services.payment_confirmation_service import (
    OrderMismatch,
    PaymentConfirmationService,
    PaymentNotFound,
)

User = get_user_model()


def make_user(email="user@example.com"):
    return User.objects.create_user(email=email, first_name="Test", last_name="User", password="strong-pass-123")


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, plan, attempt_number=1, status=Payment.Status.ACTION_REQUIRED, **overrides):
    defaults = {
        "draft": draft,
        "owner": draft.owner,
        "plan": plan,
        "attempt_number": attempt_number,
        "amount": plan.price,
        "currency": plan.currency,
        "status": status,
        "external_reference": f"memoverse:draft:{draft.id}:attempt:{attempt_number}",
        "idempotency_key": f"idem-{draft.id}-{attempt_number}",
        "mp_order_id": f"ORD-{draft.id}-{attempt_number}",
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


def make_order_result(*, order_id, external_reference, status="processed", payment_id="PAY-1", **overrides):
    raw = {"id": order_id, "status": status, "external_reference": external_reference}
    raw.update(overrides.pop("raw_overrides", {}))
    defaults = dict(order_id=order_id, status=status, status_detail=None, payment_id=payment_id, raw=raw)
    defaults.update(overrides)
    return MercadoPagoOrderResult(**defaults)


def fake_client(result=None, *, raises=None):
    client = MagicMock()
    if raises is not None:
        client.get_order.side_effect = raises
    else:
        client.get_order.return_value = result
    return client


class PaymentNotFoundTests(TestCase):
    def test_unknown_order_id_raises_payment_not_found(self):
        with self.assertRaises(PaymentNotFound):
            PaymentConfirmationService.confirm_from_order_id(
                mp_order_id="ORD-DOES-NOT-EXIST", mp_client=fake_client()
            )


class OrderMismatchTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")
        self.payment = make_payment(draft=self.draft, plan=self.plan)

    def test_external_reference_mismatch_is_rejected_and_does_not_approve(self):
        result = make_order_result(
            order_id=self.payment.mp_order_id,
            external_reference="memoverse:draft:someone-elses-draft:attempt:1",
            status="processed",
        )
        with self.assertRaises(OrderMismatch):
            PaymentConfirmationService.confirm_from_order_id(
                mp_order_id=self.payment.mp_order_id, mp_client=fake_client(result)
            )

        self.payment.refresh_from_db()
        self.assertNotEqual(self.payment.status, Payment.Status.APPROVED)


class MercadoPagoQueryIsMandatoryTests(TestCase):
    def test_confirmation_always_calls_get_order_before_approving(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        payment = make_payment(draft=draft, plan=plan)

        result = make_order_result(order_id=payment.mp_order_id, external_reference=payment.external_reference)
        client = fake_client(result)

        PaymentConfirmationService.confirm_from_order_id(mp_order_id=payment.mp_order_id, mp_client=client)

        client.get_order.assert_called_once_with(order_id=payment.mp_order_id)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)

    def test_gateway_failure_propagates_and_does_not_change_payment(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        payment = make_payment(draft=draft, plan=plan, status=Payment.Status.PENDING)

        client = fake_client(raises=MercadoPagoGatewayError("falha simulada"))

        with self.assertRaises(MercadoPagoGatewayError):
            PaymentConfirmationService.confirm_from_order_id(mp_order_id=payment.mp_order_id, mp_client=client)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)


class StatusTransitionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")

    def _confirm(self, payment, mp_status):
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status=mp_status
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        payment.refresh_from_db()
        return payment

    def test_pending_order_keeps_payment_pending(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)
        payment = self._confirm(payment, "created")
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_processing_order_moves_payment_to_in_process(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)
        payment = self._confirm(payment, "processing")
        self.assertEqual(payment.status, Payment.Status.IN_PROCESS)

    def test_action_required_order_moves_payment_to_action_required(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)
        payment = self._confirm(payment, "action_required")
        self.assertEqual(payment.status, Payment.Status.ACTION_REQUIRED)

    def test_processed_order_approves_payment(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)
        payment = self._confirm(payment, "processed")
        self.assertEqual(payment.status, Payment.Status.APPROVED)

    def test_failed_order_rejects_payment(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)
        payment = self._confirm(payment, "failed")
        self.assertEqual(payment.status, Payment.Status.REJECTED)

    def test_canceled_order_cancels_payment(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)
        payment = self._confirm(payment, "canceled")
        self.assertEqual(payment.status, Payment.Status.CANCELLED)

    def test_expired_order_expires_payment(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)
        payment = self._confirm(payment, "expired")
        self.assertEqual(payment.status, Payment.Status.EXPIRED)

    def test_refunded_order_refunds_an_approved_payment(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.APPROVED)
        payment = self._confirm(payment, "refunded")
        self.assertEqual(payment.status, Payment.Status.REFUNDED)


class TerminalStateAntiRegressionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")

    def test_approved_payment_does_not_regress_to_rejected_on_stale_webhook(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.APPROVED)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="failed"
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)

    def test_approved_payment_does_not_regress_to_cancelled(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.APPROVED)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="canceled"
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)

    def test_rejected_payment_does_not_flip_to_approved_on_the_same_row(self):
        # Uma tentativa aprovada vive em um Payment NOVO (attempt seguinte),
        # nunca reescrevendo uma tentativa já rejeitada.
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.REJECTED)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REJECTED)

    def test_unrecognized_charged_back_status_leaves_approved_payment_unchanged(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.APPROVED)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="charged_back"
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)


class DraftUpdateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.plan = Plan.objects.get(code="essential")

    def _confirm_approved(self, payment):
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )

    def test_approved_payment_marks_its_own_draft_as_paid(self):
        draft = make_draft(self.user)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        self._confirm_approved(payment)

        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_approved_payment_never_touches_a_different_draft(self):
        target_draft = make_draft(self.user)
        other_draft = make_draft(self.user)
        payment = make_payment(draft=target_draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        self._confirm_approved(payment)

        other_draft.refresh_from_db()
        self.assertEqual(other_draft.status, ExperienceDraft.Status.DRAFT)

    def test_other_users_draft_is_never_altered(self):
        owner = make_user("owner2@example.com")
        stranger = make_user("stranger@example.com")
        owner_draft = make_draft(owner)
        stranger_draft = make_draft(stranger)
        payment = make_payment(draft=owner_draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        self._confirm_approved(payment)

        stranger_draft.refresh_from_db()
        self.assertEqual(stranger_draft.status, ExperienceDraft.Status.DRAFT)

    def test_already_paid_draft_is_not_touched_again_idempotent(self):
        draft = make_draft(self.user)
        draft.status = ExperienceDraft.Status.PAID
        draft.save(update_fields=["status"])
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        self._confirm_approved(payment)

        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_already_published_draft_never_reverts(self):
        draft = make_draft(self.user)
        draft.status = ExperienceDraft.Status.PUBLISHED
        draft.save(update_fields=["status"])
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        self._confirm_approved(payment)

        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PUBLISHED)

    def test_repeated_confirmation_is_idempotent(self):
        draft = make_draft(self.user)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        self._confirm_approved(payment)
        self._confirm_approved(payment)
        self._confirm_approved(payment)

        draft.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)
        self.assertEqual(payment.status, Payment.Status.APPROVED)


class MpPaymentIdPersistenceTests(TestCase):
    def test_mp_payment_id_is_updated_when_present_in_the_order(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        payment = make_payment(draft=draft, plan=plan, status=Payment.Status.PENDING, mp_payment_id=None)

        result = make_order_result(
            order_id=payment.mp_order_id,
            external_reference=payment.external_reference,
            status="action_required",
            payment_id="PAY-CONFIRMED-1",
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )

        payment.refresh_from_db()
        self.assertEqual(payment.mp_payment_id, "PAY-CONFIRMED-1")


class ConfirmFromResultTests(TestCase):
    """confirm_from_result é o método que CheckoutService._create_order chama
    com o `result` já recebido da criação da Order (confirmação síncrona,
    sem GET extra). Testado aqui diretamente, sem passar pela view HTTP de
    checkout, para isolar a decisão de estado da orquestração de request."""

    def setUp(self):
        self.user = make_user()
        self.plan = Plan.objects.get(code="essential")

    def test_approved_result_approves_payment_and_marks_draft_paid(self):
        draft = make_draft(self.user)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        )

        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)

        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_action_required_result_does_not_touch_draft_beyond_awaiting_payment(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="action_required"
        )

        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)

        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.ACTION_REQUIRED)
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)

    def test_rejected_result_does_not_mark_draft_paid(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="failed"
        )

        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)

        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REJECTED)
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PAID)


class SyncThenWebhookIdempotencyTests(TestCase):
    """Os dois pontos de entrada (confirmação síncrona do checkout e webhook)
    convergem para a mesma lógica — não importa a ordem de chegada nem
    quantas vezes cada um roda, o resultado final é o mesmo e sem efeito
    colateral duplicado."""

    def setUp(self):
        self.user = make_user()
        self.plan = Plan.objects.get(code="essential")

    def test_sync_confirmation_followed_by_webhook_is_idempotent(self):
        draft = make_draft(self.user)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        )

        # 1) Confirmação síncrona (o que CheckoutService._create_order faz).
        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)
        paid_at_after_sync = draft.updated_at

        # 2) Webhook chega depois, para a mesma Order, mesmo status aprovado.
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )

        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)
        # _mark_draft_paid não regrava um Draft já PAID: nenhum save() a
        # mais, updated_at não muda no segundo caminho.
        self.assertEqual(draft.updated_at, paid_at_after_sync)

    def test_webhook_followed_by_sync_confirmation_is_idempotent(self):
        draft = make_draft(self.user)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        )

        # 1) Webhook chega primeiro (ordem invertida da esperada, mas o
        # serviço não assume ordem nenhuma).
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)
        paid_at_after_webhook = draft.updated_at

        # 2) A confirmação síncrona roda depois (ex.: corrida improvável em
        # produção, mas o service precisa se comportar bem mesmo assim).
        payment.refresh_from_db()
        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)

        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)
        self.assertEqual(draft.updated_at, paid_at_after_webhook)


class DraftPaymentFailedTests(TestCase):
    """Etapa 9A: AWAITING_PAYMENT -> PAYMENT_FAILED quando um Payment chega
    a um estado terminal desfavorável sem nunca ter sido aprovado."""

    def setUp(self):
        self.user = make_user()
        self.plan = Plan.objects.get(code="essential")

    def _confirm(self, payment, mp_status):
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status=mp_status
        )
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        payment.refresh_from_db()
        return payment

    def test_rejected_payment_moves_draft_to_payment_failed(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        self._confirm(payment, "failed")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)

    def test_cancelled_payment_moves_draft_to_payment_failed(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        self._confirm(payment, "canceled")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)

    def test_expired_payment_moves_draft_to_payment_failed(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)
        self._confirm(payment, "expired")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)

    def test_approved_payment_never_becomes_payment_failed(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)
        self._confirm(payment, "processed")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_pending_payment_keeps_draft_awaiting_payment(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        self._confirm(payment, "created")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)

    def test_action_required_payment_keeps_draft_awaiting_payment(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        self._confirm(payment, "action_required")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)

    def test_already_payment_failed_draft_is_not_touched_again_idempotent(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=self.plan, status=Payment.Status.PENDING)
        self._confirm(payment, "failed")
        draft.refresh_from_db()
        failed_at = draft.updated_at

        # Segunda notificação (duplicada) reconfirmando o MESMO status —
        # _next_status mantém o Payment em REJECTED (current == mapped),
        # não é uma transição nova: não deve haver save() extra no draft.
        self._confirm(payment, "failed")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)
        self.assertEqual(draft.updated_at, failed_at)

    def test_a_paid_draft_is_never_downgraded_to_payment_failed(self):
        # Payment de uma tentativa diferente do MESMO draft (já aprovada por
        # outra tentativa) sendo rejeitado não pode reverter o Draft já PAID.
        draft = make_draft(self.user, status=ExperienceDraft.Status.PAID)
        payment = make_payment(
            draft=draft, plan=self.plan, attempt_number=1, status=Payment.Status.PENDING
        )
        self._confirm(payment, "failed")
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_stale_rejection_of_an_old_attempt_does_not_override_a_newer_active_checkout(self):
        # Corrida identificada na revisão da Etapa 9A: attempt #1 já é
        # REJECTED (o draft já processou essa falha uma vez); attempt #2
        # existe e está ativo, com o draft de volta em AWAITING_PAYMENT
        # (mesmo comportamento incondicional de CheckoutService._create_order).
        # Uma notificação duplicada/atrasada reconfirmando o attempt #1 (já
        # terminal, sem mudança real de status) NUNCA pode sobrescrever o
        # AWAITING_PAYMENT que pertence ao attempt #2 em andamento.
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        old_attempt = make_payment(
            draft=draft, plan=self.plan, attempt_number=1, status=Payment.Status.REJECTED
        )
        make_payment(draft=draft, plan=self.plan, attempt_number=2, status=Payment.Status.ACTION_REQUIRED)

        self._confirm(old_attempt, "failed")

        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)


class SyncThenWebhookPaymentFailedIdempotencyTests(TestCase):
    """Mesmo padrão de SyncThenWebhookIdempotencyTests, mas para o caminho
    de falha em vez de aprovação — confirma que confirm_from_result (síncrono)
    e confirm_from_order_id (webhook) convergem para o mesmo resultado."""

    def test_sync_rejection_followed_by_webhook_is_idempotent(self):
        user = make_user()
        plan = Plan.objects.get(code="essential")
        draft = make_draft(user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="failed"
        )

        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)
        failed_at = draft.updated_at

        payment.refresh_from_db()
        PaymentConfirmationService.confirm_from_order_id(
            mp_order_id=payment.mp_order_id, mp_client=fake_client(result)
        )
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)
        self.assertEqual(draft.updated_at, failed_at)


class ConfirmFromResultPaymentFailedTests(TestCase):
    def test_rejected_result_marks_draft_payment_failed(self):
        user = make_user()
        plan = Plan.objects.get(code="essential")
        draft = make_draft(user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        payment = make_payment(draft=draft, plan=plan, status=Payment.Status.PENDING)
        result = make_order_result(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="failed"
        )

        PaymentConfirmationService.confirm_from_result(payment=payment, result=result)

        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REJECTED)
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)
