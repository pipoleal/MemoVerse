"""Backend do painel administrativo — Etapa 9B.4 (3 relatórios read-only) +
listagens (usuários/experiências/pagamentos/logs/configurações/descontos) +
ações de escrita explicitamente autorizadas pelo dono do produto: excluir um
usuário sem histórico de pagamentos, cancelar localmente um Payment ainda
ativo, criar/apagar um PlanDiscount (preço combinado por e-mail+plano, ver
apps.payments.models.PlanDiscount), e o detalhe de uma experiência (conteúdo
privado, só para moderação). Ver o docstring de cada view de escrita para as
salvaguardas específicas — a regra geral: histórico financeiro (qualquer
Payment, mesmo terminal) nunca é apagado, e nada aqui chama a Mercado Pago
para escrever.

Os 3 relatórios são uma casca fina em volta de UM Command já existente e já
testado (lifecycle_inventory/payment_reconcile/lifecycle_cleanup): valida
os query params (apps.ops.serializers, tipados e limitados — nunca um nome
de model/método/função), instancia a MESMA classe Command usada pelo CLI, e
chama Command.build_report(**kwargs) — o mesmo método que o CLI chama, sem
nenhuma lógica duplicada.

Nenhuma view aceita um parâmetro que selecione QUAL função roda — a função é
sempre a mesma, hardcoded no import no topo deste módulo. Toda view exige
IsAuthenticated + IsProductionAdmin (ver _BaseOpsReportView), sem exceção.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsProductionAdmin, is_production_admin
from apps.experiences.management.commands.lifecycle_cleanup import Command as LifecycleCleanupCommand
from apps.experiences.management.commands.lifecycle_inventory import Command as LifecycleInventoryCommand
from apps.experiences.models import ExperienceDraft, Media
from apps.experiences.services.draft_deletion import DraftDeletionService, DraftNotDeletable
from apps.experiences.storage import generate_presigned_read_url, r2_is_configured
from apps.payments.management.commands.payment_reconcile import Command as PaymentReconcileCommand
from apps.payments.models import Payment, PlanDiscount, WebhookEvent
from apps.payments.services.payment_confirmation_service import PaymentConfirmationService
from apps.telemetry.models import FunnelEvent

from .serializers import (
    AdminExperienceListQuerySerializer,
    AdminFunnelEventListQuerySerializer,
    AdminPaymentListQuerySerializer,
    AdminPlanDiscountCreateSerializer,
    AdminPlanDiscountListQuerySerializer,
    AdminUserListQuerySerializer,
    AdminWebhookEventListQuerySerializer,
    LifecycleCleanupPreviewQuerySerializer,
    LifecycleInventoryQuerySerializer,
    PaymentReconcileQuerySerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class _BaseOpsReportView(APIView):
    """Gate comum de todas as views deste módulo (read-only ou não) — só
    admin real. IsAuthenticated vem antes de IsProductionAdmin de
    propósito, para que um pedido sem token volte 401 (não autenticado)
    em vez de 403 (autenticado mas sem permissão), mesma distinção HTTP
    que o resto da API já usa. A maioria das subclasses só define `get()`
    (DRF responde 405 sozinho para o resto); as 2 exceções que escrevem
    (UserDeleteView, PaymentCancelView) documentam suas próprias
    salvaguardas."""

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
    da regra), exatamente como MeView e IsProductionAdmin já fazem.
    Filtro opcional ?email=<texto> (icontains, case-insensitive) — busca
    de suporte ao cliente, nunca um lookup dinâmico (o campo é sempre
    email, hardcoded; o valor do cliente é só o texto buscado)."""

    def get(self, request):
        query = AdminUserListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        limit, offset = data["limit"], data["offset"]

        qs = User.objects.all().order_by("-created_at")
        email_filter = data.get("email")
        if email_filter:
            qs = qs.filter(email__icontains=email_filter)

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
        owner_email_filter = data.get("owner_email")
        if owner_email_filter:
            qs = qs.filter(owner__email__icontains=owner_email_filter)

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
        owner_email_filter = data.get("owner_email")
        if owner_email_filter:
            qs = qs.filter(owner__email__icontains=owner_email_filter)

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


class FunnelEventListView(_BaseOpsReportView):
    """GET /api/ops/9b4/funnel-events/

    Alimenta a seção "Logs" do painel, ao lado dos webhooks — instrumentação
    do funil de conversão (ver apps.telemetry.models.FunnelEvent), a única
    forma hoje de ver a JORNADA de um visitante (não só o estado final de um
    draft/pagamento). Filtros opcionais por nome do evento e por
    session_id (para reconstruir a linha do tempo de UMA sessão de
    navegador)."""

    def get(self, request):
        query = AdminFunnelEventListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        limit, offset = data["limit"], data["offset"]

        qs = FunnelEvent.objects.all().order_by("-created_at")
        name_filter = data.get("name")
        if name_filter:
            qs = qs.filter(name=name_filter)
        session_id_filter = data.get("session_id")
        if session_id_filter:
            qs = qs.filter(session_id=session_id_filter)

        total = qs.count()
        page = list(qs[offset : offset + limit])

        results = [
            {
                "id": str(event.id),
                "name": event.name,
                "session_id": event.session_id,
                "draft_id": event.draft_id,
                "metadata": event.metadata,
                "created_at": event.created_at.isoformat(),
            }
            for event in page
        ]

        logger.info("ops.admin_funnel_events.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": results,
            }
        )


class PlanDiscountListView(_BaseOpsReportView):
    """GET/POST /api/ops/9b4/discounts/

    Alimenta a seção "Descontos" do painel — a forma de dar a um amigo um
    preço combinado num plano específico. GET lista os PlanDiscount
    cadastrados (mais recentes primeiro), com filtros opcionais de
    e-mail/plano/ativo. POST cria um novo: <email> paga <price> na próxima
    vez que comprar <plan_code> — uso único, ver PlanDiscount.__doc__ e
    CheckoutService._create_attempt (é lá que o valor é de fato aplicado,
    nunca aqui — esta view só cadastra a intenção).

    Nunca edita uma linha existente: se já existir um desconto ATIVO para
    o mesmo par email+plano, a UniqueConstraint do banco rejeita a
    segunda, traduzido aqui para 409 — apague o antigo (DELETE
    /discounts/<id>/) antes de cadastrar um novo valor para o mesmo par."""

    def get(self, request):
        query = AdminPlanDiscountListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        limit, offset = data["limit"], data["offset"]

        qs = PlanDiscount.objects.select_related("plan", "created_by")
        email_filter = data.get("email")
        if email_filter:
            qs = qs.filter(email__icontains=email_filter)
        plan_code_filter = data.get("plan_code")
        if plan_code_filter:
            qs = qs.filter(plan__code=plan_code_filter)
        if "is_active" in data:
            qs = qs.filter(is_active=data["is_active"])

        total = qs.count()
        page = list(qs[offset : offset + limit])

        results = [
            {
                "id": str(discount.id),
                "email": discount.email,
                "plan_code": discount.plan.code,
                "price": str(discount.price),
                "currency": discount.plan.currency,
                "note": discount.note,
                "is_active": discount.is_active,
                "created_by_email": discount.created_by.email if discount.created_by_id else None,
                "redeemed_at": discount.redeemed_at.isoformat() if discount.redeemed_at else None,
                "created_at": discount.created_at.isoformat(),
            }
            for discount in page
        ]

        logger.info("ops.admin_discounts_list.accessed")
        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": results,
            }
        )

    def post(self, request):
        serializer = AdminPlanDiscountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            # transaction.atomic() aqui cria um savepoint: sem ele, o
            # IntegrityError da UniqueConstraint deixaria a transação da
            # requisição inteira "quebrada" (Postgres/SQLite recusam
            # qualquer outra query até um ROLLBACK), mesmo já tendo sido
            # capturado pelo except abaixo — nunca um problema visível em
            # SQLite fora de testes (cada request tem sua própria conexão
            # em produção), mas quebra o próximo assert dentro do MESMO
            # teste (TestCase reaproveita uma única transação/conexão).
            with transaction.atomic():
                discount = PlanDiscount.objects.create(
                    email=data["email"],
                    plan=data["plan_code"],
                    price=data["price"],
                    note=data.get("note", ""),
                    created_by=request.user,
                )
        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "Já existe um desconto ativo para este e-mail neste plano. "
                        "Apague-o antes de cadastrar outro valor."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        logger.warning(
            "ops.admin_discount_create email=%s plan=%s price=%s by=%s",
            discount.email,
            discount.plan.code,
            discount.price,
            request.user.email,
        )
        return Response(
            {
                "id": str(discount.id),
                "email": discount.email,
                "plan_code": discount.plan.code,
                "price": str(discount.price),
                "currency": discount.plan.currency,
                "note": discount.note,
                "is_active": discount.is_active,
                "created_at": discount.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class PlanDiscountDeleteView(_BaseOpsReportView):
    """DELETE /api/ops/9b4/discounts/<uuid:discount_id>/

    Apaga um desconto — ativo (o admin mudou de ideia antes de o amigo
    usar) ou já consumido (limpeza de histórico). Sempre exclusão real:
    diferente de UserDeleteView (que preserva histórico financeiro por
    regra do produto), aqui não há PROTECT algum a respeitar —
    Payment.amount já está congelado independentemente de o PlanDiscount
    que o originou continuar existindo (Payment.redeemed_payment é a FK
    de PlanDiscount para Payment, on_delete=SET_NULL; apagar o desconto
    nunca apaga nem afeta o Payment)."""

    def delete(self, request, discount_id):
        discount = get_object_or_404(PlanDiscount, pk=discount_id)
        discount_email = discount.email
        discount_plan_code = discount.plan.code
        discount.delete()

        logger.warning(
            "ops.admin_discount_delete email=%s plan=%s by=%s",
            discount_email,
            discount_plan_code,
            request.user.email,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


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


# ----------------------------------------------------------------------
# Detalhe de experiência (moderação) e ações de escrita explicitamente
# autorizadas pelo dono do produto. Ver docstring do módulo para o
# resumo — cada view abaixo repete suas próprias salvaguardas.
# ----------------------------------------------------------------------


class ExperienceDetailView(_BaseOpsReportView):
    """GET /api/ops/9b4/experiences/<uuid:draft_id>/

    ÚNICA rota deste módulo que expõe conteúdo privado de uma experiência
    (título, nomes, carta, fotos/vídeos) — a listagem (ExperienceListView)
    nunca inclui nada disso. Existe para moderação de conteúdo (checar
    denúncia/abuso), não para uso rotineiro — por isso cada acesso é
    logado com o e-mail do admin, em nível WARNING (mais visível que o
    INFO usado pelas views só de metadados).

    URL de mídia gerada com a MESMA generate_presigned_read_url usada
    pelo resto do produto (PublicExperienceView etc.) — nunca uma cópia;
    só para Media com upload_status=UPLOADED (mídia pending/failed não
    tem objeto para ler no R2)."""

    def get(self, request, draft_id):
        draft = get_object_or_404(ExperienceDraft.objects.select_related("owner"), pk=draft_id)

        media_items = [
            {
                "id": str(media.id),
                "media_type": media.media_type,
                "upload_status": media.upload_status,
                "caption": media.caption,
                "sort_order": media.sort_order,
                "url": (
                    generate_presigned_read_url(media.storage_key)
                    if media.upload_status == Media.UploadStatus.UPLOADED
                    else None
                ),
            }
            for media in Media.objects.filter(draft=draft).order_by("media_type", "sort_order", "created_at")
        ]

        logger.warning("ops.admin_experience_detail_accessed draft_id=%s by=%s", draft_id, request.user.email)
        return Response(
            {
                "id": str(draft.id),
                "owner_email": draft.owner.email if draft.owner_id else None,
                "status": draft.status,
                "slug": draft.slug,
                "experience_type": draft.experience_type,
                "theme": draft.theme,
                "title": draft.title,
                "recipient_name": draft.recipient_name,
                "creator_name": draft.creator_name,
                "event_date": draft.event_date.isoformat() if draft.event_date else None,
                "letter": draft.letter,
                "short_message": draft.short_message,
                "context_answer": draft.context_answer,
                "created_at": draft.created_at.isoformat(),
                "updated_at": draft.updated_at.isoformat(),
                "published_at": draft.published_at.isoformat() if draft.published_at else None,
                "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
                "media": media_items,
            }
        )


class UserDeleteView(_BaseOpsReportView):
    """DELETE /api/ops/9b4/users/<uuid:user_id>/

    Salvaguardas, nesta ordem — cada uma um 400/409 explícito, nunca uma
    exclusão parcial silenciosa:

    1. nunca a própria conta autenticada (evita o admin se auto-bloquear
       do próprio painel);
    2. nunca outra conta que também seja admin (is_production_admin) —
       protege a própria arquitetura de autorização;
    3. nunca um usuário com QUALQUER Payment, em qualquer status, mesmo
       terminal — histórico financeiro nunca é apagado neste projeto (ver
       REGRA DE OURO em apps.experiences.management.commands.
       lifecycle_cleanup); Payment.owner é on_delete=PROTECT, então mesmo
       que este check fosse burlado, o Django recusaria com
       ProtectedError em vez de apagar silenciosamente;
    4. cada ExperienceDraft do usuário é excluído via
       DraftDeletionService.delete() — a MESMA lógica que já protege
       exclusão de draft em qualquer outro lugar do produto (nunca uma
       segunda cópia): só aceita status=DRAFT sem slug e sem Payment (já
       garantido pelo passo 3), e limpa o objeto correspondente no R2
       antes de apagar a linha (best-effort, mesmo contrato do service).

    Tudo dentro de uma transação — se qualquer draft não puder ser
    excluído (não deveria acontecer, dado o passo 3, mas nunca presumido),
    a transação inteira é revertida via transaction.set_rollback(True) e
    nada é excluído."""

    def delete(self, request, user_id):
        if str(request.user.id) == str(user_id):
            return Response(
                {"detail": "Você não pode excluir a própria conta administrativa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = get_object_or_404(User, pk=user_id)

        if is_production_admin(target):
            return Response(
                {"detail": "Esta conta tem acesso administrativo e não pode ser excluída por aqui."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Payment.objects.filter(owner=target).exists():
            return Response(
                {
                    "detail": (
                        "Este usuário tem histórico de pagamentos — nunca excluído automaticamente. "
                        "Histórico financeiro é preservado mesmo ao excluir a conta."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        target_email = target.email

        with transaction.atomic():
            try:
                for draft in list(ExperienceDraft.objects.filter(owner=target)):
                    DraftDeletionService.delete(draft)
            except DraftNotDeletable:
                transaction.set_rollback(True)
                return Response(
                    {"detail": "Não foi possível excluir todas as experiências deste usuário."},
                    status=status.HTTP_409_CONFLICT,
                )

            target.delete()

        logger.warning("ops.admin_user_delete deleted_email=%s by=%s", target_email, request.user.email)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentCancelView(_BaseOpsReportView):
    """POST /api/ops/9b4/payments/<uuid:payment_id>/cancel/

    Cancela LOCALMENTE um Payment ainda ativo (pending/in_process/
    action_required) — NUNCA chama a Mercado Pago para cancelar a Order
    do lado deles (MercadoPagoClient só tem get_order, leitura; não existe
    operação de escrita nesta ferramenta). Se o cliente ainda tiver a
    página de checkout aberta, a Order pode, em teoria, ainda ser paga do
    lado da Mercado Pago mesmo depois deste cancelamento local — usar para
    limpar tentativas abandonadas na sua base, nunca como garantia de que
    a cobrança foi interrompida do lado deles.

    Reaproveita PaymentConfirmationService._mark_draft_payment_failed para
    a transição do Draft (mesma lógica idempotente/guardada já usada pelo
    fluxo real de confirmação — nunca uma segunda cópia), e a mesma ordem
    de lock (Draft antes de Payment) de
    PaymentConfirmationService._apply_result, para evitar deadlock contra
    uma confirmação real (webhook) acontecendo ao mesmo tempo."""

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id)

        if payment.status not in Payment.ACTIVE_STATUSES:
            return Response(
                {"detail": f"Só pagamentos ativos podem ser cancelados (status atual: {payment.status})."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            draft = ExperienceDraft.objects.select_for_update().get(pk=payment.draft_id)
            locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)

            if locked_payment.status not in Payment.ACTIVE_STATUSES:
                return Response(
                    {
                        "detail": (
                            f"Só pagamentos ativos podem ser cancelados "
                            f"(status atual: {locked_payment.status})."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            locked_payment.status = Payment.Status.CANCELLED
            locked_payment.save(update_fields=["status", "updated_at"])
            PaymentConfirmationService._mark_draft_payment_failed(draft)

        logger.warning("ops.admin_payment_cancel payment_id=%s by=%s", payment_id, request.user.email)
        return Response(
            {
                "id": str(locked_payment.id),
                "status": locked_payment.status,
                "draft_status": draft.status,
            }
        )
