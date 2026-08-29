"""Etapa 9B.4 — 3 endpoints GET-only, administrativos, read-only.

Cada view abaixo é uma casca fina em volta de UM Command já existente e já
testado (lifecycle_inventory/payment_reconcile/lifecycle_cleanup): valida
os query params (apps.ops.serializers, tipados e limitados — nunca um nome
de model/método/função), instancia a MESMA classe Command usada pelo CLI, e
chama Command.build_report(**kwargs) — o mesmo método que o CLI chama, sem
nenhuma lógica duplicada.

Não existe nenhum quarto caminho: só estas 3 operações, cada uma com sua
própria URL fixa (ver urls.py) e sua própria classe de view. Nenhuma delas
aceita um parâmetro que selecione QUAL função roda — a função é sempre a
mesma, hardcoded no import no topo deste módulo.

Cada view define só `get()`. DRF (APIView.dispatch) responde 405 Method Not
Allowed sozinho para POST/PUT/PATCH/DELETE — não há necessidade (nem
intenção) de tratá-los aqui.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsProductionAdmin, is_production_admin
from apps.experiences.management.commands.lifecycle_cleanup import Command as LifecycleCleanupCommand
from apps.experiences.management.commands.lifecycle_inventory import Command as LifecycleInventoryCommand
from apps.experiences.models import ExperienceDraft
from apps.experiences.storage import r2_is_configured
from apps.payments.management.commands.payment_reconcile import Command as PaymentReconcileCommand
from apps.payments.models import Payment, WebhookEvent

from .serializers import (
    AdminExperienceListQuerySerializer,
    AdminListQuerySerializer,
    AdminPaymentListQuerySerializer,
    AdminWebhookEventListQuerySerializer,
    LifecycleCleanupPreviewQuerySerializer,
    LifecycleInventoryQuerySerializer,
    PaymentReconcileQuerySerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class _BaseOpsReportView(APIView):
    """Só GET (nada mais é definido), só admin real — IsAuthenticated vem
    antes de IsProductionAdmin de propósito, para que um pedido sem token
    volte 401 (não autenticado) em vez de 403 (autenticado mas sem
    permissão), mesma distinção HTTP que o resto da API já usa."""

    permission_classes = [IsAuthenticated, IsProductionAdmin]


class LifecycleInventoryReportView(_BaseOpsReportView):
    """GET /api/ops/9b4/lifecycle-inventory/

    Mesmo relatório de `python manage.py lifecycle_inventory --dry-run`,
    acrescido de `users.total` (Etapa 9B.5 — o painel administrativo
    precisa de uma contagem total de usuários que nenhum dos 3 management
    commands expõe; é uma única query trivial, montada aqui, nunca dentro
    de Command.build_report() — o CLI e seu contrato/testes continuam
    exatamente como estavam)."""

    def get(self, request):
        query = LifecycleInventoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        logger.info("ops.lifecycle_inventory.accessed")
        report = LifecycleInventoryCommand().build_report(
            stale_media_minutes=data.get("stale_media_minutes"),
            check_r2=data.get("check_r2", False),
            r2_sample_limit=data.get("r2_sample_limit", 200),
            r2_list_limit=data.get("r2_list_limit", 5000),
        )
        report["users"] = {"total": User.objects.count()}
        return Response(report)


class PaymentReconcileReportView(_BaseOpsReportView):
    """GET /api/ops/9b4/payment-reconcile/

    Mesmo relatório de `python manage.py payment_reconcile --dry-run`.
    Faz chamadas de rede reais, só leitura (GET /v1/orders/{id}), contra a
    Mercado Pago — nunca escreve lá nem aqui."""

    def get(self, request):
        query = PaymentReconcileQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        logger.info("ops.payment_reconcile.accessed")
        report = PaymentReconcileCommand().build_report(
            stale_minutes=data.get("stale_minutes", 60),
            limit=data.get("limit", 50),
        )
        return Response(report)


class LifecycleCleanupPreviewView(_BaseOpsReportView):
    """GET /api/ops/9b4/lifecycle-cleanup-preview/

    Mesmo relatório de `python manage.py lifecycle_cleanup --dry-run`
    (com `--check-r2` opcional). Nunca implementa `--apply` — esse modo
    não existe em nenhuma classe Command reutilizada aqui."""

    def get(self, request):
        query = LifecycleCleanupPreviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        logger.info("ops.lifecycle_cleanup_preview.accessed")
        report = LifecycleCleanupCommand().build_report(
            draft_abandoned_days=data.get("draft_abandoned_days", 30),
            draft_anonymous_unclaimed_hours=data.get("draft_anonymous_unclaimed_hours", 48),
            payment_failed_days=data.get("payment_failed_days", 30),
            media_failed_days=data.get("media_failed_days", 7),
            r2_orphan_grace_days=data.get("r2_orphan_grace_days", 30),
            stale_media_minutes=data.get("stale_media_minutes"),
            check_r2=data.get("check_r2", False),
            r2_list_limit=data.get("r2_list_limit", 5000),
        )
        return Response(report)


# ----------------------------------------------------------------------
# Listagens administrativas do painel /admin (seções Usuários, Experiências,
# Pagamentos, Logs, Configurações). Mesmo gate das 3 views acima
# (IsAuthenticated + IsProductionAdmin), mesmo princípio de só leitura —
# nenhuma delas define POST/PUT/PATCH/DELETE. Paginação via limit/offset
# (ver apps.ops.serializers) em vez das classes de paginação do DRF, para
# ficar no mesmo estilo do resto deste módulo.
# ----------------------------------------------------------------------


class UserListView(_BaseOpsReportView):
    """GET /api/ops/9b4/users/

    Nunca inclui password/hash — só os campos que o painel administrativo
    precisa para listar contas. is_admin é sempre calculado chamando
    is_production_admin(user) na instância real (nunca uma segunda cópia
    da regra), exatamente como MeView e IsProductionAdmin já fazem."""

    def get(self, request):
        query = AdminListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        limit = query.validated_data["limit"]
        offset = query.validated_data["offset"]

        qs = User.objects.all().order_by("-created_at")
        total = qs.count()
        page = list(qs[offset : offset + limit])

        results = [
            {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "is_admin": is_production_admin(user),
                "stars_count": user.stars_count,
                "created_at": user.created_at.isoformat(),
            }
            for user in page
        ]

        logger.info("ops.admin_users.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": results,
            }
        )


class ExperienceListView(_BaseOpsReportView):
    """GET /api/ops/9b4/experiences/

    Só metadados operacionais (status/datas/tema) — deliberadamente NUNCA
    inclui title/recipient_name/creator_name/letter/short_message/
    context_answer nem qualquer URL de mídia: são o conteúdo privado da
    experiência de um usuário, sem nenhuma relação com operar a
    plataforma. Filtro opcional por status (mesmo enum do model, nunca uma
    string livre)."""

    def get(self, request):
        query = AdminExperienceListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        limit, offset = data["limit"], data["offset"]

        qs = ExperienceDraft.objects.select_related("owner").order_by("-updated_at")
        status_filter = data.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        page = list(qs[offset : offset + limit])

        results = [
            {
                "id": str(draft.id),
                "owner_email": draft.owner.email if draft.owner_id else None,
                "status": draft.status,
                "slug": draft.slug,
                "experience_type": draft.experience_type,
                "theme": draft.theme,
                "created_at": draft.created_at.isoformat(),
                "updated_at": draft.updated_at.isoformat(),
                "published_at": draft.published_at.isoformat() if draft.published_at else None,
                "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
            }
            for draft in page
        ]

        logger.info("ops.admin_experiences.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": results,
            }
        )


class PaymentListView(_BaseOpsReportView):
    """GET /api/ops/9b4/payments/

    Nunca inclui last_sync_payload (resposta bruta da Mercado Pago) nem
    qualquer dado de cartão — este model nunca armazena PAN/CVV (a
    tokenização acontece inteiramente do lado da Mercado Pago), mas mesmo
    o payload bruto fica de fora por princípio de minimização. Filtro
    opcional por status (mesmo enum do model)."""

    def get(self, request):
        query = AdminPaymentListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        limit, offset = data["limit"], data["offset"]

        qs = Payment.objects.select_related("owner", "plan").order_by("-created_at")
        status_filter = data.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        page = list(qs[offset : offset + limit])

        results = [
            {
                "id": str(payment.id),
                "draft_id": str(payment.draft_id),
                "owner_email": payment.owner.email,
                "plan_code": payment.plan.code,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": payment.status,
                "attempt_number": payment.attempt_number,
                "mp_order_id": payment.mp_order_id,
                "created_at": payment.created_at.isoformat(),
                "updated_at": payment.updated_at.isoformat(),
            }
            for payment in page
        ]

        logger.info("ops.admin_payments.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": results,
            }
        )


class WebhookEventListView(_BaseOpsReportView):
    """GET /api/ops/9b4/webhook-events/

    Alimenta a seção "Logs" do painel — registro de idempotência dos
    webhooks da Mercado Pago (ver apps.payments.models.WebhookEvent).
    Nunca inclui `payload` (corpo bruto da notificação): status/
    error_detail já bastam para diagnosticar uma falha, sem replicar o
    payload inteiro da Mercado Pago num painel de leitura."""

    def get(self, request):
        query = AdminWebhookEventListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        limit, offset = data["limit"], data["offset"]

        qs = WebhookEvent.objects.all().order_by("-created_at")
        status_filter = data.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        page = list(qs[offset : offset + limit])

        results = [
            {
                "id": str(event.id),
                "notification_id": event.notification_id,
                "topic": event.topic,
                "resource_id": event.resource_id,
                "status": event.status,
                "error_detail": event.error_detail,
                "created_at": event.created_at.isoformat(),
            }
            for event in page
        ]

        logger.info("ops.admin_webhook_events.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": results,
            }
        )


class SettingsSnapshotView(_BaseOpsReportView):
    """GET /api/ops/9b4/settings-snapshot/

    Alimenta a seção "Configurações" do painel — só flags/valores
    operacionais não-secretos. NUNCA inclui SECRET_KEY, MP_ACCESS_TOKEN,
    MP_WEBHOOK_SECRET, R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY, DATABASE_URL
    nem RESEND_API_KEY — nenhum deles é lido aqui. MEMOVERSE_ADMIN_EMAIL é
    incluído (não é uma credencial, é só o e-mail que já habilita o
    próprio admin que está vendo esta tela)."""

    def get(self, request):
        logger.info("ops.admin_settings_snapshot.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "debug": settings.DEBUG,
                "mercado_pago_environment": settings.MP_ENV,
                "r2_configured": r2_is_configured(),
                "r2_bucket_name": settings.R2_BUCKET_NAME or None,
                "email_backend": settings.EMAIL_BACKEND,
                "pending_media_expiration_minutes": settings.PENDING_MEDIA_EXPIRATION_MINUTES,
                "memoverse_admin_email": settings.MEMOVERSE_ADMIN_EMAIL or None,
                "allowed_hosts": list(settings.ALLOWED_HOSTS),
            }
        )
