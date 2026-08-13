import threading
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan
from ..services.checkout_service import CheckoutService
from ..services.mercadopago_client import MercadoPagoGatewayError, MercadoPagoOrderResult

User = get_user_model()

SAMPLE_ORDER_RAW = {
    "id": "ORD01TEST",
    "status": "action_required",
    "status_detail": "waiting_transfer",
    "transactions": {
        "payments": [
            {
                "id": "PAY01TEST",
                "status": "action_required",
                "payment_method": {
                    "id": "pix",
                    "type": "bank_transfer",
                    "qr_code": "00020126...",
                    "qr_code_base64": "iVBORw0KGgo=",
                    "ticket_url": "https://www.mercadopago.com.br/sandbox/payments/ticket",
                },
            }
        ]
    },
}


def make_mp_result(**overrides):
    defaults = dict(
        order_id="ORD01TEST",
        status="action_required",
        status_detail="waiting_transfer",
        payment_id="PAY01TEST",
        raw=SAMPLE_ORDER_RAW,
    )
    defaults.update(overrides)
    return MercadoPagoOrderResult(**defaults)


def make_user(email="user@example.com"):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, plan, attempt_number, status=Payment.Status.PENDING, **overrides):
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
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def checkout_url(draft_id):
    return f"/api/payments/drafts/{draft_id}/checkout/"


def patch_mp_client(**create_order_kwargs):
    """Patches the MercadoPagoClient class used inside checkout_service so
    the view never touches the network. Returns the mock CLASS (its
    `.return_value` is the fake client instance)."""

    result = make_mp_result(**create_order_kwargs) if "raise_error" not in create_order_kwargs else None
    mock_cls = MagicMock()
    if create_order_kwargs.get("raise_error"):
        mock_cls.return_value.create_order.side_effect = MercadoPagoGatewayError("falha simulada")
    else:
        mock_cls.return_value.create_order.return_value = result or make_mp_result()
    return patch("apps.payments.services.checkout_service.MercadoPagoClient", mock_cls)


class CheckoutOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)

    def test_owner_can_create_checkout_for_own_draft(self):
        with patch_mp_client():
            response = auth_client(self.owner).post(checkout_url(self.draft.id), {"plan_code": "essential"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_create_checkout_for_other_users_draft(self):
        with patch_mp_client():
            response = auth_client(self.other_user).post(checkout_url(self.draft.id), {"plan_code": "essential"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())


class CheckoutPlanResolutionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_essential_plan_creates_payment_of_2999(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("29.99"))

    def test_stellar_plan_creates_payment_of_3999(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "stellar"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.99"))

    def test_amount_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "stellar", "amount": "0.01"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.99"))

    def test_price_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "stellar", "price": "0.01"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.99"))

    def test_currency_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "stellar", "currency": "USD"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.currency, "BRL")

    def test_draft_id_sent_in_body_is_ignored(self):
        other_draft = make_draft(self.user)
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id), {"plan_code": "essential", "draft_id": str(other_draft.id)}
            )
        payment = Payment.objects.get(plan__code="essential")
        self.assertEqual(payment.draft_id, self.draft.id)
        self.assertFalse(Payment.objects.filter(draft=other_draft).exists())

    def test_external_reference_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id),
                {"plan_code": "essential", "external_reference": "hacked-ref"},
            )
        payment = Payment.objects.get(draft=self.draft)
        self.assertNotEqual(payment.external_reference, "hacked-ref")
        self.assertEqual(payment.external_reference, f"memoverse:draft:{self.draft.id}:attempt:1")

    def test_idempotency_key_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id),
                {"plan_code": "essential", "idempotency_key": "hacked-key"},
            )
        payment = Payment.objects.get(draft=self.draft)
        self.assertNotEqual(payment.idempotency_key, "hacked-key")

    def test_inactive_plan_cannot_be_purchased(self):
        Plan.objects.create(code="inactive-plan", name="Inativo", price=Decimal("9.99"), is_active=False)
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "inactive-plan"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())

    def test_nonexistent_plan_returns_error(self):
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "does-not-exist"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())


class CheckoutPaymentLinkageTests(TestCase):
    def test_payment_linked_to_correct_draft_and_owner(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get()
        self.assertEqual(payment.draft_id, draft.id)
        self.assertEqual(payment.owner_id, user.id)

    def test_payment_amount_is_frozen_after_plan_price_changes(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "stellar"})
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal("39.99"))

        plan = Plan.objects.get(code="stellar")
        plan.price = Decimal("99.99")
        plan.save(update_fields=["price"])

        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("39.99"))


class CheckoutAttemptNumberTests(TestCase):
    def test_first_attempt_gets_number_1(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.attempt_number, 1)

    def test_second_attempt_after_terminal_failure_gets_number_2(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        make_payment(draft=draft, plan=plan, attempt_number=1, status=Payment.Status.REJECTED)

        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})

        self.assertTrue(Payment.objects.filter(draft=draft, attempt_number=2).exists())
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 2)


class CheckoutActivePaymentReuseTests(TestCase):
    def test_existing_active_payment_is_reused(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        existing = make_payment(
            draft=draft, plan=plan, attempt_number=1, status=Payment.Status.PENDING, mp_order_id="ORD-EXISTING"
        )

        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_id"], str(existing.id))
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)

    def test_no_two_active_payments_for_same_draft_on_repeated_calls(self):
        user = make_user()
        draft = make_draft(user)
        client = auth_client(user)

        with patch_mp_client():
            client.post(checkout_url(draft.id), {"plan_code": "essential"})
            client.post(checkout_url(draft.id), {"plan_code": "essential"})
            client.post(checkout_url(draft.id), {"plan_code": "essential"})

        self.assertEqual(
            Payment.objects.filter(draft=draft, status__in=Payment.ACTIVE_STATUSES).count(), 1
        )
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)

    def test_active_payment_for_different_plan_returns_conflict_and_does_not_alter_it(self):
        user = make_user()
        draft = make_draft(user)
        essential = Plan.objects.get(code="essential")
        existing = make_payment(draft=draft, plan=essential, attempt_number=1, status=Payment.Status.PENDING)

        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "stellar"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        existing.refresh_from_db()
        self.assertEqual(existing.plan.code, "essential")
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)


class CheckoutConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    # TransactionTestCase faz um flush completo do banco no teardown, o que
    # apaga os Plans semeados pela migration 0002 (dado de migração, não de
    # schema). serialized_rollback restaura esse estado entre testes — sem
    # isso, uma segunda classe TransactionTestCase na mesma suíte (ex.:
    # WebhookConcurrencyTests) encontraria a tabela de Plans vazia.
    serialized_rollback = True

    def test_concurrency_does_not_create_two_active_attempts(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")

        barrier = threading.Barrier(2)
        errors = []

        def worker():
            fake_client = MagicMock()
            fake_client.create_order.return_value = make_mp_result()
            barrier.wait(timeout=5)
            # SQLite (usado nos testes) não enfileira escritores como o Postgres
            # de produção faz sob select_for_update: sob contenção real ele pode
            # recusar a escrita na hora (OperationalError) em vez de esperar a
            # outra transação. Um cliente real trataria isso como "tente
            # novamente" — simulamos esse retry aqui. O que o teste garante é o
            # resultado final (nunca duas tentativas ativas), não a ausência de
            # contenção no SGBD de teste.
            for attempt in range(5):
                try:
                    CheckoutService.start_checkout(draft=draft, plan=plan, mp_client=fake_client)
                    return
                except OperationalError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
                except Exception as exc:  # noqa: BLE001 - surfaced via `errors` for assertions below
                    errors.append(exc)
                    return

        def run_worker():
            try:
                worker()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run_worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        active_payments = Payment.objects.filter(draft=draft, status__in=Payment.ACTIVE_STATUSES)
        self.assertEqual(active_payments.count(), 1)
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)


class CheckoutReferenceGenerationTests(TestCase):
    def test_external_reference_is_generated_by_backend_with_expected_format(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.external_reference, f"memoverse:draft:{draft.id}:attempt:1")

    def test_idempotency_key_is_generated_by_backend_and_is_stable(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")

        payment_a = CheckoutService._create_attempt(draft=draft, plan=plan)
        self.assertTrue(payment_a.idempotency_key)

        # Simula um retry da MESMA tentativa: a idempotency_key não pode mudar.
        payment_a.refresh_from_db()
        self.assertEqual(payment_a.idempotency_key, f"memoverse:idem:draft-{draft.id}-attempt-1")


class CheckoutMercadoPagoClientCallTests(TestCase):
    def test_mp_client_receives_amount_external_reference_and_idempotency_key(self):
        user = make_user()
        draft = make_draft(user)

        with patch_mp_client() as mock_cls:
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "stellar"})

        payment = Payment.objects.get(draft=draft)
        mock_cls.return_value.create_order.assert_called_once()
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], Decimal("39.99"))
        self.assertEqual(call_kwargs["external_reference"], payment.external_reference)
        self.assertEqual(call_kwargs["idempotency_key"], payment.idempotency_key)
        self.assertEqual(call_kwargs["payer"], {"email": user.email})


class CheckoutOrderPersistenceTests(TestCase):
    def test_mp_order_id_is_saved(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client(order_id="ORD-XYZ"):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.mp_order_id, "ORD-XYZ")

    def test_mp_payment_id_is_saved_when_available(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client(payment_id="PAY-XYZ"):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.mp_payment_id, "PAY-XYZ")

    def test_mp_payment_id_is_null_when_not_yet_available(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client(payment_id=None, status="processing"):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        payment = Payment.objects.get(draft=draft)
        self.assertIsNone(payment.mp_payment_id)


class CheckoutDraftStatusTests(TestCase):
    def test_draft_becomes_awaiting_payment_after_successful_checkout(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)

    def test_draft_does_not_become_paid_after_successful_checkout(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_draft_does_not_become_published_after_successful_checkout(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PUBLISHED)


class CheckoutFailureHandlingTests(TestCase):
    def test_mp_failure_returns_gateway_error_and_does_not_publish_or_mark_draft_paid(self):
        user = make_user()
        draft = make_draft(user)

        with patch_mp_client(raise_error=True):
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PAID)
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PUBLISHED)
        self.assertEqual(draft.status, ExperienceDraft.Status.DRAFT)

    def test_mp_failure_leaves_payment_pending_without_order_id(self):
        user = make_user()
        draft = make_draft(user)

        with patch_mp_client(raise_error=True):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "essential"})

        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIsNone(payment.mp_order_id)

    def test_retry_after_transient_failure_does_not_duplicate_the_payment_and_reuses_the_idempotency_key(self):
        user = make_user()
        draft = make_draft(user)
        client = auth_client(user)

        with patch_mp_client(raise_error=True):
            first_response = client.post(checkout_url(draft.id), {"plan_code": "essential"})
        self.assertEqual(first_response.status_code, status.HTTP_502_BAD_GATEWAY)

        failed_payment = Payment.objects.get(draft=draft)

        with patch_mp_client() as mock_cls:
            second_response = client.post(checkout_url(draft.id), {"plan_code": "essential"})

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)

        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.id, failed_payment.id)
        self.assertEqual(payment.attempt_number, 1)
        self.assertEqual(payment.mp_order_id, "ORD01TEST")

        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["idempotency_key"], failed_payment.idempotency_key)
        self.assertEqual(call_kwargs["external_reference"], failed_payment.external_reference)
