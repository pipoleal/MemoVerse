import hashlib
import hmac
import json
import threading
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import Client, TestCase, TransactionTestCase, override_settings

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan, WebhookEvent
from ..services.mercadopago_client import (
    MercadoPagoGatewayError,
    MercadoPagoOrderResult,
    MercadoPagoResponseError,
)

User = get_user_model()

WEBHOOK_SECRET = "test-webhook-secret"
WEBHOOK_URL = "/api/payments/webhooks/mercadopago/"


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


def make_order_result(*, order_id, external_reference, status="processed", payment_id="PAY-1"):
    raw = {"id": order_id, "status": status, "external_reference": external_reference}
    return MercadoPagoOrderResult(order_id=order_id, status=status, status_detail=None, payment_id=payment_id, raw=raw)


def sign(*, secret, data_id, x_request_id, ts):
    manifest = ""
    if data_id:
        manifest += f"id:{data_id.lower()};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    return hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()


def webhook_body(*, notification_id, topic, resource_id):
    return {
        "id": notification_id,
        "live_mode": False,
        "type": topic,
        "date_created": "2026-08-13T00:00:00.000-03:00",
        "user_id": 12345,
        "api_version": "v1",
        "action": f"{topic}.updated",
        "data": {"id": resource_id},
    }


def post_webhook(
    client,
    *,
    notification_id,
    resource_id,
    topic="order",
    secret=WEBHOOK_SECRET,
    x_request_id="req-1",
    ts="1700000000",
    signature_override=None,
    omit_signature=False,
):
    body = webhook_body(notification_id=notification_id, topic=topic, resource_id=resource_id)
    headers = {}
    if not omit_signature:
        if signature_override is not None:
            x_signature = signature_override
        else:
            v1 = sign(secret=secret, data_id=resource_id, x_request_id=x_request_id, ts=ts)
            x_signature = f"ts={ts},v1={v1}"
        headers["HTTP_X_SIGNATURE"] = x_signature
    headers["HTTP_X_REQUEST_ID"] = x_request_id
    return client.post(
        f"{WEBHOOK_URL}?data.id={resource_id}",
        data=json.dumps(body),
        content_type="application/json",
        **headers,
    )


def patch_confirmation_mp_client(**create_result_kwargs):
    """Patcheia MercadoPagoClient no módulo do PaymentConfirmationService,
    para que o webhook nunca toque a rede de verdade."""

    mock_cls = MagicMock()
    if create_result_kwargs.get("raise_error"):
        mock_cls.return_value.get_order.side_effect = create_result_kwargs["raise_error"]
    else:
        mock_cls.return_value.get_order.return_value = make_order_result(**create_result_kwargs)
    return patch("apps.payments.services.payment_confirmation_service.MercadoPagoClient", mock_cls)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookSignatureEnforcementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")
        self.payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)

    def test_valid_signature_is_processed(self):
        with patch_confirmation_mp_client(
            order_id=self.payment.mp_order_id, external_reference=self.payment.external_reference, status="created"
        ):
            response = post_webhook(self.client, notification_id="1", resource_id=self.payment.mp_order_id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(WebhookEvent.objects.filter(notification_id="1").exists())

    def test_missing_signature_is_rejected(self):
        response = post_webhook(
            self.client, notification_id="2", resource_id=self.payment.mp_order_id, omit_signature=True
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookEvent.objects.filter(notification_id="2").exists())

    def test_invalid_signature_is_rejected(self):
        response = post_webhook(
            self.client, notification_id="3", resource_id=self.payment.mp_order_id, secret="wrong-secret"
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookEvent.objects.filter(notification_id="3").exists())

    def test_tampered_signature_is_rejected(self):
        response = post_webhook(
            self.client,
            notification_id="4",
            resource_id=self.payment.mp_order_id,
            signature_override="ts=1700000000,v1=" + "0" * 64,
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookEvent.objects.filter(notification_id="4").exists())

    def test_malformed_signature_header_is_rejected(self):
        response = post_webhook(
            self.client,
            notification_id="5",
            resource_id=self.payment.mp_order_id,
            signature_override="not-a-valid-header",
        )
        self.assertEqual(response.status_code, 400)

    def test_signature_never_produces_a_payment_side_effect_when_rejected(self):
        post_webhook(self.client, notification_id="6", resource_id=self.payment.mp_order_id, omit_signature=True)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")
        self.payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

    def test_duplicate_notification_id_is_processed_only_once(self):
        with patch_confirmation_mp_client(
            order_id=self.payment.mp_order_id, external_reference=self.payment.external_reference, status="processed"
        ) as mock_cls:
            post_webhook(self.client, notification_id="dup-1", resource_id=self.payment.mp_order_id)
            post_webhook(self.client, notification_id="dup-1", resource_id=self.payment.mp_order_id)
            post_webhook(self.client, notification_id="dup-1", resource_id=self.payment.mp_order_id)

        mock_cls.return_value.get_order.assert_called_once()
        self.assertEqual(WebhookEvent.objects.filter(notification_id="dup-1").count(), 1)

    def test_duplicate_notification_returns_200_without_reprocessing(self):
        with patch_confirmation_mp_client(
            order_id=self.payment.mp_order_id, external_reference=self.payment.external_reference, status="processed"
        ):
            first = post_webhook(self.client, notification_id="dup-2", resource_id=self.payment.mp_order_id)
            second = post_webhook(self.client, notification_id="dup-2", resource_id=self.payment.mp_order_id)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

    def test_different_notification_ids_for_the_same_resource_are_both_processed(self):
        # Duas notificações genuinamente diferentes (ex.: action_required
        # depois processed) sobre a MESMA Order não são "duplicadas" —
        # idempotência é por notification_id, não por resource_id.
        with patch_confirmation_mp_client(
            order_id=self.payment.mp_order_id, external_reference=self.payment.external_reference, status="processed"
        ) as mock_cls:
            post_webhook(self.client, notification_id="evt-1", resource_id=self.payment.mp_order_id)
            post_webhook(self.client, notification_id="evt-2", resource_id=self.payment.mp_order_id)

        self.assertEqual(mock_cls.return_value.get_order.call_count, 2)
        self.assertEqual(WebhookEvent.objects.count(), 2)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookResourceCorrelationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")

    def test_order_with_no_matching_local_payment_returns_200_without_approving(self):
        response = post_webhook(self.client, notification_id="7", resource_id="ORD-NEVER-CREATED-LOCALLY")

        self.assertEqual(response.status_code, 200)
        event = WebhookEvent.objects.get(notification_id="7")
        self.assertEqual(event.status, WebhookEvent.Status.FAILED)

    def test_external_reference_mismatch_returns_200_without_approving(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)
        with patch_confirmation_mp_client(
            order_id=payment.mp_order_id, external_reference="memoverse:draft:not-this-one:attempt:1", status="processed"
        ):
            response = post_webhook(self.client, notification_id="8", resource_id=payment.mp_order_id)

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertNotEqual(payment.status, Payment.Status.APPROVED)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookMercadoPagoQueryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")
        self.payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)

    def test_confirmation_requires_a_real_mercadopago_query(self):
        with patch_confirmation_mp_client(
            order_id=self.payment.mp_order_id, external_reference=self.payment.external_reference, status="processed"
        ) as mock_cls:
            post_webhook(self.client, notification_id="9", resource_id=self.payment.mp_order_id)

        mock_cls.return_value.get_order.assert_called_once_with(order_id=self.payment.mp_order_id)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.APPROVED)

    def test_gateway_failure_returns_502_and_keeps_event_retryable(self):
        with patch_confirmation_mp_client(raise_error=MercadoPagoGatewayError("falha de rede simulada")):
            response = post_webhook(self.client, notification_id="10", resource_id=self.payment.mp_order_id)

        self.assertEqual(response.status_code, 502)
        event = WebhookEvent.objects.get(notification_id="10")
        self.assertEqual(event.status, WebhookEvent.Status.FAILED)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)

    def test_timeout_is_treated_as_gateway_failure_returns_502(self):
        with patch_confirmation_mp_client(raise_error=MercadoPagoGatewayError("Falha de comunicação com a Mercado Pago.")):
            response = post_webhook(self.client, notification_id="11", resource_id=self.payment.mp_order_id)
        self.assertEqual(response.status_code, 502)

    def test_invalid_mercadopago_response_returns_502(self):
        with patch_confirmation_mp_client(raise_error=MercadoPagoResponseError("sem id na resposta")):
            response = post_webhook(self.client, notification_id="12", resource_id=self.payment.mp_order_id)
        self.assertEqual(response.status_code, 502)

    def test_retry_after_gateway_failure_reprocesses_the_same_notification(self):
        with patch_confirmation_mp_client(raise_error=MercadoPagoGatewayError("falha de rede simulada")):
            first = post_webhook(self.client, notification_id="13", resource_id=self.payment.mp_order_id)
        self.assertEqual(first.status_code, 502)

        with patch_confirmation_mp_client(
            order_id=self.payment.mp_order_id, external_reference=self.payment.external_reference, status="processed"
        ):
            second = post_webhook(self.client, notification_id="13", resource_id=self.payment.mp_order_id)

        self.assertEqual(second.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.APPROVED)
        self.assertEqual(WebhookEvent.objects.filter(notification_id="13").count(), 1)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookStatusAndDraftEndToEndTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")

    def test_approved_webhook_marks_draft_as_paid(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)
        with patch_confirmation_mp_client(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        ):
            post_webhook(self.client, notification_id="20", resource_id=payment.mp_order_id)

        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PAID)

    def test_other_users_draft_is_never_altered_by_this_webhook(self):
        stranger = make_user("stranger@example.com")
        stranger_draft = make_draft(stranger)
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        with patch_confirmation_mp_client(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        ):
            post_webhook(self.client, notification_id="21", resource_id=payment.mp_order_id)

        stranger_draft.refresh_from_db()
        self.assertEqual(stranger_draft.status, ExperienceDraft.Status.DRAFT)

    def test_approved_payment_does_not_publish_or_alter_a_different_draft(self):
        other_draft = make_draft(self.user)
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        with patch_confirmation_mp_client(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        ):
            post_webhook(self.client, notification_id="22", resource_id=payment.mp_order_id)

        other_draft.refresh_from_db()
        self.assertEqual(other_draft.status, ExperienceDraft.Status.DRAFT)

    def test_old_rejected_webhook_replay_cannot_regress_an_approved_payment(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.APPROVED)
        self.draft.status = ExperienceDraft.Status.PAID
        self.draft.save(update_fields=["status"])

        with patch_confirmation_mp_client(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="failed"
        ):
            post_webhook(self.client, notification_id="23", resource_id=payment.mp_order_id)

        payment.refresh_from_db()
        self.draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PAID)

    def test_repeated_processing_of_the_same_webhook_stays_idempotent(self):
        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.ACTION_REQUIRED)

        with patch_confirmation_mp_client(
            order_id=payment.mp_order_id, external_reference=payment.external_reference, status="processed"
        ):
            for _ in range(3):
                post_webhook(self.client, notification_id="24", resource_id=payment.mp_order_id)

        payment.refresh_from_db()
        self.draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PAID)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookUnsupportedTopicTests(TestCase):
    def test_unsupported_topic_is_acknowledged_without_processing(self):
        client = Client()
        with patch_confirmation_mp_client(order_id="ORD-X", external_reference="whatever") as mock_cls:
            response = post_webhook(client, notification_id="30", resource_id="123456789", topic="payment")

        self.assertEqual(response.status_code, 200)
        mock_cls.return_value.get_order.assert_not_called()
        event = WebhookEvent.objects.get(notification_id="30")
        self.assertEqual(event.status, WebhookEvent.Status.PROCESSED)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookConcurrencyTests(TransactionTestCase):
    # Ver comentário equivalente em test_checkout.py::CheckoutConcurrencyTests
    # — TransactionTestCase faz flush completo do banco, o que apaga os
    # Plans semeados pela migration; serialized_rollback restaura o estado.
    serialized_rollback = True

    def test_two_simultaneous_webhooks_for_the_same_notification_apply_effects_once(self):
        user = User.objects.create_user(
            email="concurrent@example.com", first_name="T", last_name="U", password="strong-pass-123"
        )
        draft = ExperienceDraft.objects.create(owner=user)
        plan = Plan.objects.get(code="essential")
        payment = make_payment(draft=draft, plan=plan, status=Payment.Status.ACTION_REQUIRED)

        barrier = threading.Barrier(2)
        errors = []

        def worker():
            client = Client()
            barrier.wait(timeout=5)
            # SQLite (usado nos testes) pode recusar a escrita na hora
            # (OperationalError) em vez de enfileirar o escritor como o
            # Postgres de produção faz. Um cliente real trataria isso como
            # "tente novamente" — simulamos esse retry aqui, sem re-sincronizar
            # no barrier (só a primeira investida precisa ser simultânea).
            for attempt in range(5):
                try:
                    with patch_confirmation_mp_client(
                        order_id=payment.mp_order_id,
                        external_reference=payment.external_reference,
                        status="processed",
                    ):
                        post_webhook(client, notification_id="concurrent-1", resource_id=payment.mp_order_id)
                    return
                except OperationalError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))

        def run_worker():
            try:
                worker()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run_worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(errors, [])
        self.assertEqual(WebhookEvent.objects.filter(notification_id="concurrent-1").count(), 1)
        payment.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(draft.status, ExperienceDraft.Status.PAID)
