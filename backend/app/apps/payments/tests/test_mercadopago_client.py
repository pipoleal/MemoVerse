from decimal import Decimal

from django.test import TestCase
from mercadopago.errors.response import MPResponse

from ..services.mercadopago_client import (
    MercadoPagoClient,
    MercadoPagoConfigurationError,
    MercadoPagoGatewayError,
    MercadoPagoOrderResult,
    MercadoPagoResponseError,
)

SAMPLE_ORDER_RESPONSE = {
    "id": "ORD01TEST",
    "status": "action_required",
    "status_detail": "waiting_transfer",
    "transactions": {"payments": [{"id": "PAY01TEST", "status": "action_required"}]},
}

SAMPLE_PAYER = {"email": "buyer@example.com"}
SAMPLE_PAYMENTS = [{"amount": "39.99", "payment_method": {"id": "pix", "type": "bank_transfer"}}]
SAMPLE_ITEMS = [{"id": "stellar", "title": "MemoVerse Estelar", "quantity": 1, "unit_price": "39.99"}]


class _FakeOrderResource:
    """Stand-in for mercadopago.resources.order.Order — never touches the network."""

    def __init__(self, response_body=None, status=201):
        self.response_body = response_body
        self.status = status
        self.calls = []

    def create(self, order_payload, request_options):
        self.calls.append({"order_payload": order_payload, "request_options": request_options})
        return MPResponse({"status": self.status, "response": self.response_body})

    def get(self, order_id, request_options):
        self.calls.append({"order_id": order_id, "request_options": request_options})
        return MPResponse({"status": self.status, "response": self.response_body})

    @property
    def last_call(self):
        return self.calls[-1]


class _FakeSDK:
    """Stand-in for mercadopago.SDK — hands back a pre-built fake Order resource."""

    def __init__(self, order_resource):
        self._order_resource = order_resource

    def order(self, request_options=None):
        return self._order_resource


def make_client(order_resource, *, access_token="TEST-ACCESS-TOKEN"):
    return MercadoPagoClient(access_token=access_token, environment="sandbox", sdk=_FakeSDK(order_resource))


def call_create_order(client, **overrides):
    kwargs = {
        "amount": Decimal("39.99"),
        "currency": "BRL",
        "external_reference": "memoverse:draft:abc123:attempt:1",
        "idempotency_key": "idem-abc123-1",
        "payer": SAMPLE_PAYER,
        "payments": SAMPLE_PAYMENTS,
        "items": SAMPLE_ITEMS,
    }
    kwargs.update(overrides)
    return client.create_order(**kwargs)


class MercadoPagoClientInitializationTests(TestCase):
    def test_initializes_with_valid_configuration(self):
        client = make_client(_FakeOrderResource())
        self.assertEqual(client.environment, "sandbox")

    def test_missing_access_token_raises_configuration_error(self):
        with self.assertRaises(MercadoPagoConfigurationError):
            MercadoPagoClient(access_token="", sdk=_FakeOrderResource())


class MercadoPagoClientCreateOrderPayloadTests(TestCase):
    def setUp(self):
        self.order_resource = _FakeOrderResource(response_body=SAMPLE_ORDER_RESPONSE)
        self.client = make_client(self.order_resource)

    def test_sends_total_amount_as_fixed_two_decimal_string(self):
        call_create_order(self.client, amount=Decimal("39.9"))
        payload = self.order_resource.last_call["order_payload"]
        self.assertEqual(payload["total_amount"], "39.90")

    def test_sends_external_reference(self):
        call_create_order(self.client, external_reference="memoverse:draft:xyz:attempt:2")
        payload = self.order_resource.last_call["order_payload"]
        self.assertEqual(payload["external_reference"], "memoverse:draft:xyz:attempt:2")

    def test_forwards_idempotency_key_via_request_options_custom_header(self):
        call_create_order(self.client, idempotency_key="my-unique-key")
        request_options = self.order_resource.last_call["request_options"]
        self.assertEqual(request_options.custom_headers.get("x-idempotency-key"), "my-unique-key")

    def test_sends_payer(self):
        call_create_order(self.client, payer={"email": "someone@example.com"})
        payload = self.order_resource.last_call["order_payload"]
        self.assertEqual(payload["payer"], {"email": "someone@example.com"})

    def test_forwards_items_when_provided(self):
        call_create_order(self.client, items=SAMPLE_ITEMS)
        payload = self.order_resource.last_call["order_payload"]
        self.assertEqual(payload["items"], SAMPLE_ITEMS)

    def test_omits_items_when_not_provided(self):
        call_create_order(self.client, items=None)
        payload = self.order_resource.last_call["order_payload"]
        self.assertNotIn("items", payload)

    def test_does_not_send_currency_field(self):
        # Confirmed real Orders API payloads (Pix and card) have no currency
        # field — Mercado Pago infers it from the seller account.
        call_create_order(self.client, currency="BRL")
        payload = self.order_resource.last_call["order_payload"]
        self.assertNotIn("currency", payload)
        self.assertNotIn("currency_id", payload)

    def test_sends_transactions_payments(self):
        call_create_order(self.client, payments=SAMPLE_PAYMENTS)
        payload = self.order_resource.last_call["order_payload"]
        self.assertEqual(payload["transactions"], {"payments": SAMPLE_PAYMENTS})


class MercadoPagoClientResponseNormalizationTests(TestCase):
    def test_valid_response_is_normalized_and_returned(self):
        order_resource = _FakeOrderResource(response_body=SAMPLE_ORDER_RESPONSE)
        client = make_client(order_resource)

        result = call_create_order(client)

        self.assertIsInstance(result, MercadoPagoOrderResult)
        self.assertEqual(result.order_id, "ORD01TEST")
        self.assertEqual(result.status, "action_required")
        self.assertEqual(result.status_detail, "waiting_transfer")
        self.assertEqual(result.payment_id, "PAY01TEST")
        self.assertEqual(result.raw, SAMPLE_ORDER_RESPONSE)

    def test_response_without_nested_payment_yields_none_payment_id(self):
        body = {**SAMPLE_ORDER_RESPONSE, "transactions": {"payments": []}}
        order_resource = _FakeOrderResource(response_body=body)
        client = make_client(order_resource)

        result = call_create_order(client)

        self.assertIsNone(result.payment_id)

    def test_response_without_order_id_raises_response_error(self):
        order_resource = _FakeOrderResource(response_body={"status": "created"})
        client = make_client(order_resource)

        with self.assertRaises(MercadoPagoResponseError):
            call_create_order(client)


class MercadoPagoClientErrorHandlingTests(TestCase):
    def test_sdk_error_is_converted_to_gateway_error(self):
        order_resource = _FakeOrderResource(
            response_body={"message": "external_reference já utilizada", "error": "bad_request"},
            status=400,
        )
        client = make_client(order_resource)

        with self.assertRaises(MercadoPagoGatewayError) as ctx:
            call_create_order(client)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.mp_error_code, "bad_request")

    def test_access_token_never_appears_in_logs_or_error_message(self):
        secret_token = "APP_USR-SECRET-VALUE-DO-NOT-LEAK"
        order_resource = _FakeOrderResource(
            response_body={"message": "erro interno", "error": "server_error"}, status=500
        )
        client = make_client(order_resource, access_token=secret_token)

        with self.assertLogs("apps.payments.services.mercadopago_client", level="WARNING") as captured:
            with self.assertRaises(MercadoPagoGatewayError) as ctx:
                call_create_order(client)

        self.assertNotIn(secret_token, str(ctx.exception))
        for record in captured.records:
            self.assertNotIn(secret_token, record.getMessage())
            self.assertNotIn(secret_token, str(record.__dict__))


class MercadoPagoClientGetOrderTests(TestCase):
    """Fase 4: consulta real da Order, usada pela confirmação server-side —
    nunca decidimos um Payment aprovado a partir só do payload do webhook."""

    def test_requests_the_given_order_id(self):
        order_resource = _FakeOrderResource(response_body=SAMPLE_ORDER_RESPONSE, status=200)
        client = make_client(order_resource)

        client.get_order(order_id="ORD01TEST")

        self.assertEqual(order_resource.last_call["order_id"], "ORD01TEST")

    def test_returns_normalized_result(self):
        order_resource = _FakeOrderResource(response_body=SAMPLE_ORDER_RESPONSE, status=200)
        client = make_client(order_resource)

        result = client.get_order(order_id="ORD01TEST")

        self.assertIsInstance(result, MercadoPagoOrderResult)
        self.assertEqual(result.order_id, "ORD01TEST")
        self.assertEqual(result.status, "action_required")
        self.assertEqual(result.status_detail, "waiting_transfer")
        self.assertEqual(result.payment_id, "PAY01TEST")
        self.assertEqual(result.raw, SAMPLE_ORDER_RESPONSE)

    def test_order_not_found_raises_gateway_error(self):
        order_resource = _FakeOrderResource(
            response_body={"message": "Order not found", "error": "not_found"}, status=404
        )
        client = make_client(order_resource)

        with self.assertRaises(MercadoPagoGatewayError) as ctx:
            client.get_order(order_id="ORD-DOES-NOT-EXIST")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_response_without_order_id_raises_response_error(self):
        order_resource = _FakeOrderResource(response_body={"status": "created"}, status=200)
        client = make_client(order_resource)

        with self.assertRaises(MercadoPagoResponseError):
            client.get_order(order_id="ORD01TEST")

    def test_access_token_never_appears_in_logs_on_get_order_failure(self):
        secret_token = "APP_USR-SECRET-VALUE-DO-NOT-LEAK"
        order_resource = _FakeOrderResource(
            response_body={"message": "erro interno", "error": "server_error"}, status=500
        )
        client = make_client(order_resource, access_token=secret_token)

        with self.assertLogs("apps.payments.services.mercadopago_client", level="WARNING") as captured:
            with self.assertRaises(MercadoPagoGatewayError):
                client.get_order(order_id="ORD01TEST")

        for record in captured.records:
            self.assertNotIn(secret_token, record.getMessage())
