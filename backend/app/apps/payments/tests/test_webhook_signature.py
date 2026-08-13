import hashlib
import hmac

from django.test import TestCase

from ..services.webhook_signature import (
    InvalidSignatureError,
    MalformedSignatureError,
    MissingSignatureError,
    WebhookSecretNotConfiguredError,
    validate_webhook_signature,
)

SECRET = "test-webhook-secret"


def reference_signature(*, secret, data_id, x_request_id, ts):
    """Implementação de referência do algoritmo oficial, escrita de forma
    independente do módulo testado (não importa `build_manifest`), para que
    um bug no manifest do módulo real não "confirme a si mesmo"."""

    manifest = ""
    if data_id:
        manifest += f"id:{data_id.lower()};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    return hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()


def make_header(*, secret=SECRET, data_id="ORD123", x_request_id="req-1", ts="1700000000"):
    v1 = reference_signature(secret=secret, data_id=data_id, x_request_id=x_request_id, ts=ts)
    return f"ts={ts},v1={v1}"


class ValidWebhookSignatureTests(TestCase):
    def test_valid_signature_does_not_raise(self):
        header = make_header()
        # Não deve levantar exceção.
        validate_webhook_signature(
            x_signature=header, x_request_id="req-1", data_id="ORD123", secret=SECRET
        )

    def test_valid_signature_lowercases_uppercase_data_id(self):
        # Assinado com o data_id já em minúsculas (regra oficial), mas
        # recebido em maiúsculas na notificação real.
        header = make_header(data_id="ord123")
        validate_webhook_signature(
            x_signature=header, x_request_id="req-1", data_id="ORD123", secret=SECRET
        )

    def test_valid_signature_when_x_request_id_absent(self):
        header = make_header(x_request_id=None)
        validate_webhook_signature(x_signature=header, x_request_id=None, data_id="ORD123", secret=SECRET)

    def test_valid_signature_when_data_id_absent(self):
        header = make_header(data_id=None)
        validate_webhook_signature(x_signature=header, x_request_id="req-1", data_id=None, secret=SECRET)


class MissingOrMalformedSignatureTests(TestCase):
    def test_missing_signature_header_is_rejected(self):
        with self.assertRaises(MissingSignatureError):
            validate_webhook_signature(x_signature=None, x_request_id="req-1", data_id="ORD123", secret=SECRET)

    def test_empty_signature_header_is_rejected(self):
        with self.assertRaises(MissingSignatureError):
            validate_webhook_signature(x_signature="", x_request_id="req-1", data_id="ORD123", secret=SECRET)

    def test_signature_without_v1_is_malformed(self):
        with self.assertRaises(MalformedSignatureError):
            validate_webhook_signature(
                x_signature="ts=1700000000", x_request_id="req-1", data_id="ORD123", secret=SECRET
            )

    def test_signature_without_ts_is_malformed(self):
        with self.assertRaises(MalformedSignatureError):
            validate_webhook_signature(
                x_signature="v1=deadbeef", x_request_id="req-1", data_id="ORD123", secret=SECRET
            )

    def test_signature_with_garbage_format_is_malformed(self):
        with self.assertRaises(MalformedSignatureError):
            validate_webhook_signature(
                x_signature="not-a-valid-header", x_request_id="req-1", data_id="ORD123", secret=SECRET
            )


class InvalidWebhookSignatureTests(TestCase):
    def test_signature_computed_with_wrong_secret_is_rejected(self):
        header = make_header(secret="a-completely-different-secret")
        with self.assertRaises(InvalidSignatureError):
            validate_webhook_signature(
                x_signature=header, x_request_id="req-1", data_id="ORD123", secret=SECRET
            )

    def test_tampered_v1_value_is_rejected(self):
        header = make_header()
        ts, v1 = header.split(",")
        tampered = f"{ts},v1=deadbeef{v1[-10:]}"
        with self.assertRaises(InvalidSignatureError):
            validate_webhook_signature(
                x_signature=tampered, x_request_id="req-1", data_id="ORD123", secret=SECRET
            )

    def test_signature_for_a_different_data_id_is_rejected(self):
        header = make_header(data_id="ORD123")
        with self.assertRaises(InvalidSignatureError):
            validate_webhook_signature(
                x_signature=header, x_request_id="req-1", data_id="ORD999", secret=SECRET
            )

    def test_signature_for_a_different_request_id_is_rejected(self):
        header = make_header(x_request_id="req-1")
        with self.assertRaises(InvalidSignatureError):
            validate_webhook_signature(
                x_signature=header, x_request_id="req-2", data_id="ORD123", secret=SECRET
            )

    def test_signature_for_a_different_ts_is_rejected(self):
        header = make_header(ts="1700000000")
        tampered = header.replace("ts=1700000000", "ts=1799999999")
        with self.assertRaises(InvalidSignatureError):
            validate_webhook_signature(
                x_signature=tampered, x_request_id="req-1", data_id="ORD123", secret=SECRET
            )


class WebhookSecretConfigurationTests(TestCase):
    def test_missing_server_secret_raises_configuration_error(self):
        header = make_header()
        with self.assertRaises(WebhookSecretNotConfiguredError):
            validate_webhook_signature(x_signature=header, x_request_id="req-1", data_id="ORD123", secret="")
