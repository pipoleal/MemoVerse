"""Validação de assinatura HMAC dos webhooks da Mercado Pago.

Implementa exatamente o algoritmo documentado oficialmente (consultado via
MCP): o header `x-signature` chega no formato `ts=<epoch_ms>,v1=<hmac_hex>`;
a mensagem assinada ("manifest") é

    id:[data.id];request-id:[x-request-id];ts:[ts];

onde `data.id` é o valor da query string (nunca do corpo) e, se contiver
letras maiúsculas, é usado em minúsculas. Qualquer um dos três segmentos cujo
valor não esteja presente na notificação é omitido do manifest (não vira
`id:;`). A assinatura esperada é HMAC-SHA256(secret, manifest) em hex,
comparada ao `v1` recebido.

Não inventamos formato nem algoritmo aqui — nenhuma peça deste módulo deve
divergir da documentação oficial sem uma nova consulta a ela.
"""

from __future__ import annotations

import hashlib
import hmac


class WebhookSignatureError(Exception):
    """Base para toda falha de validação da assinatura do webhook."""


class WebhookSecretNotConfiguredError(WebhookSignatureError):
    """MP_WEBHOOK_SECRET não está configurado no servidor.

    Falha de configuração nossa, não do chamador — tratada separadamente
    das demais para que a view responda 500 (e não 401) nesse caso.
    """


class MissingSignatureError(WebhookSignatureError):
    """Header x-signature ausente na requisição."""


class MalformedSignatureError(WebhookSignatureError):
    """Header x-signature presente mas sem os campos `ts`/`v1` esperados."""


class InvalidSignatureError(WebhookSignatureError):
    """A assinatura calculada não corresponde à recebida no header."""


def parse_x_signature(header_value: str) -> tuple[str, str]:
    """Extrai (ts, v1) de um header `x-signature: ts=...,v1=...`."""

    parts: dict[str, str] = {}
    for chunk in header_value.split(","):
        if "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        parts[key.strip()] = value.strip()

    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        raise MalformedSignatureError("Header x-signature não contém os campos ts e v1.")
    return ts, v1


def build_manifest(*, data_id: str | None, x_request_id: str | None, ts: str) -> str:
    """Monta o manifest exatamente na ordem documentada: id, request-id, ts."""

    manifest = ""
    if data_id:
        manifest += f"id:{data_id.lower()};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    return manifest


def validate_webhook_signature(
    *,
    x_signature: str | None,
    x_request_id: str | None,
    data_id: str | None,
    secret: str,
) -> None:
    """Levanta uma subclasse de WebhookSignatureError quando a notificação
    não pode ser autenticada. Não retorna nada em caso de sucesso.

    Deve ser chamada antes de qualquer efeito colateral (leitura de Payment,
    gravação de WebhookEvent, etc.) — validar a origem vem sempre primeiro.
    """

    if not secret:
        raise WebhookSecretNotConfiguredError("MP_WEBHOOK_SECRET não configurado no servidor.")

    if not x_signature:
        raise MissingSignatureError("Header x-signature ausente.")

    ts, v1 = parse_x_signature(x_signature)

    manifest = build_manifest(data_id=data_id, x_request_id=x_request_id, ts=ts)
    expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, v1):
        raise InvalidSignatureError("Assinatura x-signature não corresponde à notificação recebida.")
