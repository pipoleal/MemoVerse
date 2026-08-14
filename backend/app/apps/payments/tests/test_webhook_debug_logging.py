"""TEMPORARY WEBHOOK DEBUG.

Testes do logging temporário adicionado a apps/payments/views/webhook.py
para diagnosticar se as notificações da Mercado Pago estão chegando ao
MemoVerse. Devem ser removidos junto com esse logging quando o diagnóstico
for concluído.
"""

import hashlib
import hmac
import io
import json
import logging

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan

User = get_user_model()

WEBHOOK_SECRET = "test-webhook-secret"
WEBHOOK_URL = "/api/payments/webhooks/mercadopago/"
WEBHOOK_LOGGER = "apps.payments.views.webhook"


def make_user(email="user@example.com"):
    return User.objects.create_user(email=email, first_name="Test", last_name="User", password="strong-pass-123")


def make_draft(owner):
    return ExperienceDraft.objects.create(owner=owner)


def make_payment(*, draft, plan, status=Payment.Status.ACTION_REQUIRED):
    return Payment.objects.create(
        draft=draft,
        owner=draft.owner,
        plan=plan,
        attempt_number=1,
        amount=plan.price,
        currency=plan.currency,
        status=status,
        external_reference=f"memoverse-draft-{draft.id}-attempt-1",
        idempotency_key=f"mv:{draft.id}:1",
        mp_order_id=f"ORD-{draft.id}",
    )


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
        "data": {"id": resource_id},
    }


def post_webhook(client, *, notification_id, resource_id, topic="order", secret=WEBHOOK_SECRET, omit_signature=False):
    body = webhook_body(notification_id=notification_id, topic=topic, resource_id=resource_id)
    headers = {}
    ts = "1700000000"
    x_request_id = "req-1"
    if not omit_signature:
        v1 = sign(secret=secret, data_id=resource_id, x_request_id=x_request_id, ts=ts)
        headers["HTTP_X_SIGNATURE"] = f"ts={ts},v1={v1}"
    headers["HTTP_X_REQUEST_ID"] = x_request_id
    return client.post(
        f"{WEBHOOK_URL}?data.id={resource_id}",
        data=json.dumps(body),
        content_type="application/json",
        **headers,
    )


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookDebugLoggingSafetyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")
        self.payment = make_payment(draft=self.draft, plan=self.plan)

    def test_valid_request_logs_safe_markers_only(self):
        from unittest.mock import patch

        from ..services.mercadopago_client import MercadoPagoOrderResult

        result = MercadoPagoOrderResult(
            order_id=self.payment.mp_order_id,
            status="processed",
            status_detail=None,
            payment_id="PAY-1",
            raw={"id": self.payment.mp_order_id, "status": "processed", "external_reference": self.payment.external_reference},
        )
        mock_cls_patch = patch("apps.payments.services.payment_confirmation_service.MercadoPagoClient")
        with mock_cls_patch as mock_cls:
            mock_cls.return_value.get_order.return_value = result
            with self.assertLogs(WEBHOOK_LOGGER, level="INFO") as logs:
                response = post_webhook(self.client, notification_id="log-1", resource_id=self.payment.mp_order_id)

        self.assertEqual(response.status_code, 200)
        joined = "\n".join(logs.output)
        self.assertIn("TEMPORARY WEBHOOK DEBUG", joined)
        self.assertIn("has_x_signature=True", joined)
        self.assertIn("signature validation result=valid", joined)
        self.assertIn("returning status=200", joined)

    def test_missing_signature_logs_absence_and_invalid_result(self):
        with self.assertLogs(WEBHOOK_LOGGER, level="INFO") as logs:
            response = post_webhook(
                self.client, notification_id="log-2", resource_id=self.payment.mp_order_id, omit_signature=True
            )

        self.assertEqual(response.status_code, 401)
        joined = "\n".join(logs.output)
        self.assertIn("has_x_signature=False", joined)
        self.assertIn("signature validation result=invalid reason=missing", joined)
        self.assertIn("returning status=401", joined)

    def test_invalid_signature_logs_result_without_leaking_secret_or_signature(self):
        with self.assertLogs(WEBHOOK_LOGGER, level="INFO") as logs:
            response = post_webhook(
                self.client, notification_id="log-3", resource_id=self.payment.mp_order_id, secret="wrong-secret"
            )

        self.assertEqual(response.status_code, 401)
        joined = "\n".join(logs.output)
        self.assertIn("signature validation result=invalid reason=mismatch", joined)
        # O segredo real e a assinatura calculada nunca aparecem em texto.
        self.assertNotIn(WEBHOOK_SECRET, joined)
        self.assertNotIn("wrong-secret", joined)
        real_signature = sign(secret=WEBHOOK_SECRET, data_id=self.payment.mp_order_id, x_request_id="req-1", ts="1700000000")
        self.assertNotIn(real_signature, joined)

    def test_topic_is_logged_but_not_notification_id(self):
        # Mockado (fluxo feliz) de propósito: assim nenhuma linha de log
        # pré-existente e não relacionada a este debug (ex.: o warning de
        # falha ao consultar a MP, que já loga o mp_order_id — não é um
        # segredo, mas não é o que este teste está verificando) entra em
        # cena. O foco aqui é só: as linhas TEMPORARY WEBHOOK DEBUG nunca
        # incluem o notification_id real, só se ele está presente ou não.
        from unittest.mock import patch

        from ..services.mercadopago_client import MercadoPagoOrderResult

        result = MercadoPagoOrderResult(
            order_id=self.payment.mp_order_id,
            status="processed",
            status_detail=None,
            payment_id="PAY-1",
            raw={"id": self.payment.mp_order_id, "status": "processed", "external_reference": self.payment.external_reference},
        )
        with patch("apps.payments.services.payment_confirmation_service.MercadoPagoClient") as mock_cls:
            mock_cls.return_value.get_order.return_value = result
            with self.assertLogs(WEBHOOK_LOGGER, level="INFO") as logs:
                post_webhook(self.client, notification_id="log-4", resource_id=self.payment.mp_order_id)

        debug_lines = [line for line in logs.output if "TEMPORARY WEBHOOK DEBUG" in line]
        joined_debug = "\n".join(debug_lines)
        self.assertIn("topic=order", joined_debug)
        self.assertIn("has_notification_id=True", joined_debug)
        self.assertIn("has_resource_id=True", joined_debug)
        # O notification_id real nunca aparece em nenhuma linha de debug.
        self.assertNotIn("log-4", joined_debug)

    def test_unsupported_topic_logs_status_and_note(self):
        with self.assertLogs(WEBHOOK_LOGGER, level="INFO") as logs:
            response = post_webhook(self.client, notification_id="log-5", resource_id="999999", topic="payment")

        self.assertEqual(response.status_code, 200)
        joined = "\n".join(logs.output)
        self.assertIn("topic=payment", joined)
        self.assertIn("returning status=200 note=unsupported_topic", joined)

    def test_no_log_line_ever_contains_the_webhook_secret(self):
        # Varre TODAS as combinações de teste desta classe de uma vez: uma
        # requisição válida e uma inválida, garantindo que em nenhum dos
        # casos o MP_WEBHOOK_SECRET real aparece em qualquer linha de log.
        with self.assertLogs(WEBHOOK_LOGGER, level="INFO") as logs:
            post_webhook(self.client, notification_id="log-6a", resource_id=self.payment.mp_order_id)
            post_webhook(
                self.client, notification_id="log-6b", resource_id=self.payment.mp_order_id, secret="another-wrong-one"
            )

        for line in logs.output:
            self.assertNotIn(WEBHOOK_SECRET, line)


@override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookDebugLoggingBehaviorUnchangedTests(TestCase):
    """Confirma que o logging é só um observador — não muda nenhum status
    HTTP nem efeito colateral em relação ao comportamento documentado em
    test_webhooks.py."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")

    def test_missing_signature_still_returns_401_and_no_side_effect(self):
        from ..models import WebhookEvent

        payment = make_payment(draft=self.draft, plan=self.plan, status=Payment.Status.PENDING)
        response = post_webhook(self.client, notification_id="beh-1", resource_id=payment.mp_order_id, omit_signature=True)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookEvent.objects.filter(notification_id="beh-1").exists())
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)


class WebhookLoggingConfigurationTests(TestCase):
    """Confirma que a correção mínima de LOGGING (config/settings.py) está
    ativa e é cirurgicamente restrita ao logger do webhook — sem depender de
    assertLogs, que força o nível para baixo durante o teste e mascararia um
    LOGGING mal configurado."""

    def test_webhook_logger_effective_level_is_info(self):
        logger = logging.getLogger(WEBHOOK_LOGGER)
        self.assertEqual(logger.getEffectiveLevel(), logging.INFO)
        self.assertTrue(logger.isEnabledFor(logging.INFO))

    def test_webhook_logger_has_its_own_handler_and_does_not_propagate(self):
        logger = logging.getLogger(WEBHOOK_LOGGER)
        self.assertTrue(logger.handlers, "logger deve ter handler próprio, não depender do lastResort")
        self.assertFalse(logger.propagate)

    def test_info_message_is_actually_emitted_without_assertlogs_forcing_level(self):
        logger = logging.getLogger(WEBHOOK_LOGGER)
        stream = io.StringIO()
        probe = logging.StreamHandler(stream)
        probe.setLevel(logging.INFO)
        logger.addHandler(probe)
        try:
            logger.info("TEMPORARY WEBHOOK DEBUG: config smoke test marker")
        finally:
            logger.removeHandler(probe)
        self.assertIn("TEMPORARY WEBHOOK DEBUG: config smoke test marker", stream.getvalue())

    def test_sibling_payments_logger_is_not_elevated(self):
        # apps.payments.services.mercadopago_client não foi citado no
        # LOGGING — deve continuar no default (WARNING), provando que a
        # elevação para INFO foi escopada só ao logger do webhook.
        sibling = logging.getLogger("apps.payments.services.mercadopago_client")
        self.assertEqual(sibling.getEffectiveLevel(), logging.WARNING)

    def test_root_logger_is_not_elevated(self):
        root = logging.getLogger()
        self.assertEqual(root.getEffectiveLevel(), logging.WARNING)

    def test_no_secret_or_signature_leaks_through_the_new_handler(self):
        logger = logging.getLogger(WEBHOOK_LOGGER)
        stream = io.StringIO()
        probe = logging.StreamHandler(stream)
        probe.setLevel(logging.INFO)
        logger.addHandler(probe)
        try:
            with override_settings(MP_WEBHOOK_SECRET=WEBHOOK_SECRET):
                client = Client()
                user = make_user(email="probe@example.com")
                draft = make_draft(user)
                plan = Plan.objects.get(code="essential")
                payment = make_payment(draft=draft, plan=plan)
                post_webhook(client, notification_id="probe-1", resource_id=payment.mp_order_id, omit_signature=True)
        finally:
            logger.removeHandler(probe)
        output = stream.getvalue()
        self.assertIn("TEMPORARY WEBHOOK DEBUG", output)
        self.assertNotIn(WEBHOOK_SECRET, output)
