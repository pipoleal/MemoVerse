"""Isolated client for all backend communication with the Mercado Pago Orders API.

    MemoVerse -> MercadoPagoClient -> mercadopago SDK -> Mercado Pago API

Nothing outside this module should import the `mercadopago` package directly.
MercadoPagoClient does not decide price, does not look up Plan/ExperienceDraft,
and does not write to Payment - it only receives data already validated by the
domain and talks to Mercado Pago.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

import mercadopago
import requests
from django.conf import settings
from mercadopago.config import RequestOptions
from mercadopago.errors.exceptions import MercadoPagoError as MercadoPagoSDKError

logger = logging.getLogger(__name__)


class MercadoPagoClientError(Exception):
    """Base class for every error raised by MercadoPagoClient."""


class MercadoPagoConfigurationError(MercadoPagoClientError):
    """Missing or invalid client configuration (e.g. no access token)."""


class MercadoPagoGatewayError(MercadoPagoClientError):
    """Communication with Mercado Pago failed.

    Covers both HTTP-level API errors (4xx/5xx, wrapping the SDK's own
    exception) and transport-level failures (timeouts, connection errors).
    """

    def __init__(self, message, *, status_code=None, mp_error_code=None):
        super().__init__(message)
        self.status_code = status_code
        self.mp_error_code = mp_error_code


class MercadoPagoResponseError(MercadoPagoClientError):
    """Mercado Pago returned a successful (2xx) response missing fields
    MemoVerse depends on (e.g. no order id)."""


@dataclass(frozen=True)
class MercadoPagoOrderResult:
    """Normalised result of a successful Order creation."""

    order_id: str
    status: Optional[str]
    status_detail: Optional[str]
    payment_id: Optional[str]
    raw: dict


def _format_amount(amount) -> str:
    """Mercado Pago expects amounts as fixed 2-decimal strings (e.g. "39.99")."""
    return f"{Decimal(amount):.2f}"


def _sanitize_for_log(*, status_code, mp_error_code, detail) -> dict:
    """Only ever includes status/error-code/detail. Never headers, tokens,
    or raw request/response payloads.

    Uses `mp_status_code`/`mp_error_code`/`mp_detail` as keys (not
    `status_code`/`message`) because `logging.LogRecord` reserves several
    attribute names (`message` among them) - passing a colliding key via
    `extra=` raises `KeyError` from the logging module itself.
    """
    return {"mp_status_code": status_code, "mp_error_code": mp_error_code, "mp_detail": detail}


class MercadoPagoClient:
    """Encapsulates every interaction with the Mercado Pago Orders API."""

    def __init__(self, *, access_token: Optional[str] = None, environment: Optional[str] = None, sdk=None):
        self._access_token = access_token if access_token is not None else getattr(settings, "MP_ACCESS_TOKEN", "")
        if not self._access_token:
            raise MercadoPagoConfigurationError(
                "MP_ACCESS_TOKEN não está configurado. Defina a variável de ambiente "
                "correspondente antes de usar o MercadoPagoClient."
            )
        self._environment = environment if environment is not None else getattr(settings, "MP_ENV", "sandbox")
        self._sdk = sdk if sdk is not None else mercadopago.SDK(self._access_token)

    @property
    def environment(self) -> str:
        return self._environment

    def create_order(
        self,
        *,
        amount: Decimal,
        currency: str,
        external_reference: str,
        idempotency_key: str,
        payer: dict,
        payments: list,
        items: Optional[list] = None,
        processing_mode: str = "automatic",
    ) -> MercadoPagoOrderResult:
        """Creates an Order in Mercado Pago (`POST /v1/orders`).

        `amount`, `external_reference`, `idempotency_key`, `payer` and
        `payments` must already be fully resolved by the caller. This client
        does not compute price, does not look up a Plan/ExperienceDraft, and
        does not decide anything about the business shape of the order.

        `currency` is accepted for the caller's own bookkeeping/logging but is
        NOT sent to Mercado Pago: the confirmed real Orders API payloads (Pix
        and card, verified directly against the official docs and the SDK
        source) carry no currency field - Mercado Pago infers it from the
        seller account.

        `items` is optional and forwarded verbatim if provided: the confirmed
        real Orders API payloads do not include a top-level `items` array
        (that field belongs to the older Preference/Checkout Pro API), so
        this client does not fabricate one.
        """

        order_payload: dict[str, Any] = {
            "type": "online",
            "total_amount": _format_amount(amount),
            "external_reference": external_reference,
            "processing_mode": processing_mode,
            "payer": payer,
            "transactions": {"payments": payments},
        }
        if items:
            order_payload["items"] = items

        # The idempotency key always comes from the caller (Payment.idempotency_key).
        # RequestOptions would otherwise generate a random one on every call,
        # which would defeat idempotency on retries - never rely on that default.
        request_options = RequestOptions(
            access_token=self._access_token,
            custom_headers={"x-idempotency-key": idempotency_key},
        )

        try:
            result = self._sdk.order().create(order_payload, request_options)
            result.raise_for_status()
        except MercadoPagoSDKError as exc:
            logger.warning(
                "Mercado Pago rejeitou a criação da Order",
                extra=_sanitize_for_log(
                    status_code=getattr(exc, "status_code", None),
                    mp_error_code=getattr(exc, "error", None),
                    detail=getattr(exc, "message", None),
                ),
            )
            raise MercadoPagoGatewayError(
                f"Mercado Pago recusou a criação da Order (status={getattr(exc, 'status_code', None)}).",
                status_code=getattr(exc, "status_code", None),
                mp_error_code=getattr(exc, "error", None),
            ) from exc
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Falha de transporte ao comunicar com a Mercado Pago",
                extra=_sanitize_for_log(status_code=None, mp_error_code=None, detail=type(exc).__name__),
            )
            raise MercadoPagoGatewayError("Falha de comunicação com a Mercado Pago.") from exc

        body = result["response"] or {}
        order_id = body.get("id")
        if not order_id:
            raise MercadoPagoResponseError("Resposta da Mercado Pago não contém o id da Order.")

        order_payments = (body.get("transactions") or {}).get("payments") or []
        payment_id = order_payments[0].get("id") if order_payments else None

        return MercadoPagoOrderResult(
            order_id=order_id,
            status=body.get("status"),
            status_detail=body.get("status_detail"),
            payment_id=payment_id,
            raw=body,
        )
