import json
import logging

from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import WebhookEvent
from ..services.mercadopago_client import MercadoPagoClientError
from ..services.payment_confirmation_service import (
    OrderMismatch,
    PaymentConfirmationError,
    PaymentConfirmationService,
    PaymentNotFound,
)
from ..services.webhook_signature import (
    InvalidSignatureError,
    MalformedSignatureError,
    MissingSignatureError,
    WebhookSecretNotConfiguredError,
    validate_webhook_signature,
)

logger = logging.getLogger(__name__)

# Único tópico que este MVP sabe processar: Orders API (Pix). Qualquer outro
# tópico configurado na aplicação (ex.: "payment", de integrações antigas)
# é reconhecido (200, para não gerar retries inúteis) mas não processado —
# nossa correlação é toda baseada em mp_order_id.
SUPPORTED_TOPICS = {"order"}


# ============================================================================
# TEMPORARY WEBHOOK DEBUG — diagnóstico de entrega de notificação.
# Remover esta função e todas as chamadas a ela assim que confirmarmos se a
# Mercado Pago está (ou não) alcançando este endpoint. Só loga presença/
# ausência de headers, o tópico, o resultado (válido/inválido) e o status
# HTTP retornado — nunca valores de header, secret, assinatura ou payload.
# ============================================================================
def _debug_return(response, note):
    logger.info("TEMPORARY WEBHOOK DEBUG: returning status=%s note=%s", response.status_code, note)
    return response


@method_decorator(csrf_exempt, name="dispatch")
class MercadoPagoWebhookView(APIView):
    """POST /api/payments/webhooks/mercadopago/

    Endpoint público (sem JWT) chamado pelos servidores da Mercado Pago.

    Este endpoint NUNCA decide um Payment como aprovado a partir do próprio
    payload — ele só valida a origem da notificação (x-signature) e aponta
    qual Order consultar. A fonte da verdade é sempre
    PaymentConfirmationService, que consulta a Mercado Pago diretamente com
    o Access Token do servidor antes de qualquer mudança de status.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data_id = request.query_params.get("data.id")
        x_request_id = request.headers.get("x-request-id")
        x_signature = request.headers.get("x-signature")

        # TEMPORARY WEBHOOK DEBUG — só presença/ausência, nunca o valor.
        logger.info(
            "TEMPORARY WEBHOOK DEBUG: incoming request method=%s "
            "has_x_signature=%s has_x_request_id=%s has_data_id=%s",
            request.method,
            bool(x_signature),
            bool(x_request_id),
            bool(data_id),
        )

        try:
            validate_webhook_signature(
                x_signature=x_signature,
                x_request_id=x_request_id,
                data_id=data_id,
                secret=settings.MP_WEBHOOK_SECRET,
            )
        except WebhookSecretNotConfiguredError:
            # Falha de configuração nossa, não do chamador.
            logger.error("MP_WEBHOOK_SECRET não configurado — webhook rejeitado.")
            logger.info("TEMPORARY WEBHOOK DEBUG: signature validation result=not_configured")
            return _debug_return(
                Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR), "secret_not_configured"
            )
        except MissingSignatureError:
            logger.info("TEMPORARY WEBHOOK DEBUG: signature validation result=invalid reason=missing")
            return _debug_return(
                Response({"detail": "x-signature ausente."}, status=status.HTTP_401_UNAUTHORIZED),
                "missing_signature",
            )
        except MalformedSignatureError:
            logger.info("TEMPORARY WEBHOOK DEBUG: signature validation result=invalid reason=malformed")
            return _debug_return(
                Response({"detail": "x-signature em formato inválido."}, status=status.HTTP_400_BAD_REQUEST),
                "malformed_signature",
            )
        except InvalidSignatureError:
            logger.info("TEMPORARY WEBHOOK DEBUG: signature validation result=invalid reason=mismatch")
            return _debug_return(
                Response({"detail": "Assinatura inválida."}, status=status.HTTP_401_UNAUTHORIZED),
                "invalid_signature",
            )

        logger.info("TEMPORARY WEBHOOK DEBUG: signature validation result=valid")

        try:
            body = json.loads(request.body or b"{}")
        except ValueError:
            return _debug_return(
                Response({"detail": "Payload inválido."}, status=status.HTTP_400_BAD_REQUEST), "invalid_json"
            )

        if not isinstance(body, dict):
            return _debug_return(
                Response({"detail": "Payload inválido."}, status=status.HTTP_400_BAD_REQUEST), "non_dict_payload"
            )

        notification_id = body.get("id")
        topic = body.get("type") or body.get("topic")
        resource_id = str((body.get("data") or {}).get("id") or data_id or "")

        # TEMPORARY WEBHOOK DEBUG — o tópico não é sensível; ids não são
        # logados, só se estão presentes ou não.
        logger.info(
            "TEMPORARY WEBHOOK DEBUG: topic=%s has_notification_id=%s has_resource_id=%s",
            topic,
            bool(notification_id),
            bool(resource_id),
        )

        if not notification_id or not topic or not resource_id:
            return _debug_return(
                Response({"detail": "Notificação incompleta."}, status=status.HTTP_400_BAD_REQUEST),
                "incomplete_notification",
            )

        # get_or_create é a garantia de idempotência: a constraint UNIQUE em
        # notification_id vive no banco, não em memória/cache, e o próprio
        # Django resolve a corrida de duas requisições concorrentes criando
        # a MESMA linha (uma delas ganha o create, a outra recebe created=False).
        event, created = WebhookEvent.objects.get_or_create(
            notification_id=str(notification_id),
            defaults={
                "topic": topic,
                "resource_id": resource_id,
                "payload": body,
                "status": WebhookEvent.Status.RECEIVED,
            },
        )

        if not created and event.status == WebhookEvent.Status.PROCESSED:
            # Notificação duplicada já processada com sucesso: reconhece sem
            # repetir nenhum efeito colateral.
            return _debug_return(Response(status=status.HTTP_200_OK), "duplicate_already_processed")

        if topic not in SUPPORTED_TOPICS:
            event.status = WebhookEvent.Status.PROCESSED
            event.error_detail = f"topic '{topic}' fora de escopo nesta fase; ignorado sem efeito."
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_detail", "processed_at"])
            return _debug_return(Response(status=status.HTTP_200_OK), "unsupported_topic")

        try:
            PaymentConfirmationService.confirm_from_order_id(mp_order_id=event.resource_id)
        except PaymentNotFound:
            # Não é transiente: nenhum retry vai fazer esse Payment existir.
            event.status = WebhookEvent.Status.FAILED
            event.error_detail = "Nenhum Payment local corresponde a esta Order."
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_detail", "processed_at"])
            logger.info("TEMPORARY WEBHOOK DEBUG: exception=PaymentNotFound")
            return _debug_return(Response(status=status.HTTP_200_OK), "payment_not_found")
        except OrderMismatch as exc:
            event.status = WebhookEvent.Status.FAILED
            event.error_detail = str(exc)[:255]
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_detail", "processed_at"])
            logger.info("TEMPORARY WEBHOOK DEBUG: exception=OrderMismatch")
            return _debug_return(Response(status=status.HTTP_200_OK), "order_mismatch")
        except PaymentConfirmationError as exc:
            # Rede de segurança para futuras subclasses de erro de negócio
            # que este view ainda não conheça explicitamente — mesmo
            # tratamento: não é transiente, não aprova, registra e reconhece.
            event.status = WebhookEvent.Status.FAILED
            event.error_detail = str(exc)[:255]
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_detail", "processed_at"])
            logger.info("TEMPORARY WEBHOOK DEBUG: exception=%s", type(exc).__name__)
            return _debug_return(Response(status=status.HTTP_200_OK), "payment_confirmation_error")
        except MercadoPagoClientError:
            # Falha transiente (rede/timeout/gateway) — não marca como
            # PROCESSED, para permitir reprocessar no reenvio da Mercado
            # Pago (mesmo notification_id, mesma linha, nova tentativa).
            event.status = WebhookEvent.Status.FAILED
            event.error_detail = "Falha ao consultar a Mercado Pago."
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_detail", "processed_at"])
            logger.warning("Falha ao consultar a Order %s na Mercado Pago.", event.resource_id)
            logger.info("TEMPORARY WEBHOOK DEBUG: exception=MercadoPagoClientError")
            return _debug_return(Response(status=status.HTTP_502_BAD_GATEWAY), "mercadopago_client_error")

        event.status = WebhookEvent.Status.PROCESSED
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])
        return _debug_return(Response(status=status.HTTP_200_OK), "processed_ok")
