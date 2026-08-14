"""TEST-ONLY / TEMPORARY.

Testes de apps/payments/views/sandbox_apro_test.py. Deve ser removido junto
com a view, a rota e a migration accounts/0002_sandbox_apro_test_runner.py
quando o teste manual do APRO em Sandbox for concluído.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import Payment
from ..services.mercadopago_client import MercadoPagoGatewayError, MercadoPagoOrderResult

User = get_user_model()

TEST_APRO_URL = "/api/payments/sandbox-apro-test/"

SAMPLE_ORDER_RAW = {
    "id": "ORD01APRO",
    "status": "action_required",
    "status_detail": "waiting_transfer",
    "transactions": {"payments": [{"id": "PAY01APRO", "status": "action_required"}]},
}


def make_mp_result(**overrides):
    defaults = dict(
        order_id="ORD01APRO",
        status="action_required",
        status_detail="waiting_transfer",
        payment_id="PAY01APRO",
        raw=SAMPLE_ORDER_RAW,
    )
    defaults.update(overrides)
    return MercadoPagoOrderResult(**defaults)


def make_user(email="user@example.com", is_staff=False):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123", is_staff=is_staff
    )


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def patch_mp_client(environment="sandbox", raise_error=False):
    mock_cls = MagicMock()
    mock_cls.return_value.environment = environment
    if raise_error:
        mock_cls.return_value.create_order.side_effect = MercadoPagoGatewayError("falha simulada")
    else:
        mock_cls.return_value.create_order.return_value = make_mp_result()
    return patch("apps.payments.services.checkout_service.MercadoPagoClient", mock_cls)


class SandboxAproTestAuthorizationTests(TestCase):
    def test_unauthenticated_user_is_rejected(self):
        response = APIClient().post(TEST_APRO_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_non_staff_user_is_rejected(self):
        user = make_user(is_staff=False)
        with patch_mp_client() as mock_cls:
            response = auth_client(user).post(TEST_APRO_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_cls.return_value.create_order.assert_not_called()
        self.assertFalse(Payment.objects.filter(owner=user).exists())

    def test_staff_user_can_access(self):
        user = make_user(is_staff=True)
        with patch_mp_client() as mock_cls:
            response = auth_client(user).post(TEST_APRO_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_cls.return_value.create_order.assert_called_once()


class SandboxAproEnvironmentGuardTests(TestCase):
    def test_sandbox_sends_apro_first_name(self):
        user = make_user(is_staff=True)
        with patch_mp_client(environment="sandbox") as mock_cls:
            auth_client(user).post(TEST_APRO_URL)
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"]["first_name"], "APRO")
        self.assertTrue(call_kwargs["payer"]["email"].endswith("@testuser.com"))

    @override_settings(MP_ENV="production")
    def test_production_is_blocked_entirely(self):
        # A view checa settings.MP_ENV diretamente, antes até de construir
        # um MercadoPagoClient — por isso o override é em settings, não no
        # client mockado (que só controla o gate interno do CheckoutService).
        user = make_user(is_staff=True)
        with patch_mp_client(environment="production") as mock_cls:
            response = auth_client(user).post(TEST_APRO_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_cls.return_value.create_order.assert_not_called()
        self.assertFalse(Payment.objects.filter(owner=user).exists())


class SandboxAproPayloadIntegrityTests(TestCase):
    def test_external_reference_and_idempotency_key_use_normal_format(self):
        user = make_user(is_staff=True)
        with patch_mp_client() as mock_cls:
            auth_client(user).post(TEST_APRO_URL)
        payment = Payment.objects.get(owner=user)
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["external_reference"], payment.external_reference)
        self.assertEqual(call_kwargs["idempotency_key"], payment.idempotency_key)
        self.assertTrue(payment.external_reference.startswith("memoverse-draft-"))
        self.assertTrue(payment.idempotency_key.startswith("mv:"))

    def test_payment_method_is_still_pix(self):
        user = make_user(is_staff=True)
        with patch_mp_client() as mock_cls:
            auth_client(user).post(TEST_APRO_URL)
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(
            call_kwargs["payments"],
            [{"amount": "29.99", "payment_method": {"id": "pix", "type": "bank_transfer"}}],
        )

    def test_client_cannot_override_payer_first_name(self):
        user = make_user(is_staff=True)
        with patch_mp_client() as mock_cls:
            auth_client(user).post(TEST_APRO_URL, {"payer_first_name": "HACKED"})
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"]["first_name"], "APRO")

    def test_response_never_contains_secrets(self):
        user = make_user(is_staff=True)
        with patch_mp_client():
            response = auth_client(user).post(TEST_APRO_URL)
        self.assertEqual(
            set(response.json().keys()),
            {"draft_id", "payment_id", "mp_order_id", "mp_payment_id", "payment_status", "draft_status"},
        )


class SandboxAproIdempotencyTests(TestCase):
    def test_second_execution_does_not_create_a_second_order(self):
        user = make_user(is_staff=True)
        with patch_mp_client() as mock_cls:
            first = auth_client(user).post(TEST_APRO_URL)
            second = auth_client(user).post(TEST_APRO_URL)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        mock_cls.return_value.create_order.assert_called_once()
        self.assertEqual(Payment.objects.filter(owner=user).count(), 1)
        self.assertEqual(first.json()["mp_order_id"], second.json()["mp_order_id"])
