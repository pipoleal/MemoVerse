"""Validação estrita dos query params aceitos pelas 3 operações da 9B.4.

Cada campo aqui é um valor tipado e limitado (inteiro com min/max, ou
booleano) — nenhum deles é usado como nome de model/método/função em
lugar nenhum do código (ver apps.ops.views: os valores validados só viram
argumentos nomeados de Command.build_report(), nunca um getattr/lookup
dinâmico). Qualquer query param que não esteja declarado aqui é
silenciosamente ignorado pelo DRF (comportamento padrão de Serializer,
nunca lido em código algum) — não existe caminho para um cliente
influenciar QUAL função roda, só os limites numéricos de uma execução já
fixa.
"""

from rest_framework import serializers

from apps.experiences.models import ExperienceDraft
from apps.payments.models import Payment, WebhookEvent

# Mesmo teto pensado para os --limit/--*-limit dos management commands:
# protege contra um cliente (mesmo autenticado como admin) disparando uma
# rajada de chamadas de rede reais (Mercado Pago / R2) num único GET.
MAX_MINUTES = 10_080  # 7 dias
MAX_HOURS = 8_760  # 1 ano
MAX_DAYS = 3_650  # 10 anos
MAX_PAYMENT_RECONCILE_LIMIT = 200
MAX_R2_SAMPLE_LIMIT = 2_000
MAX_R2_LIST_LIMIT = 20_000

# Paginação das listagens administrativas (painel /admin) — limit/offset
# simples, no mesmo estilo dos outros campos deste módulo, em vez de
# adotar as classes de paginação do DRF (nunca usadas em outro lugar do
# projeto). MAX_ADMIN_LIST_LIMIT protege contra uma página gigante num
# único GET; MAX_ADMIN_LIST_OFFSET é só uma rede de segurança contra um
# offset absurdo, não uma garantia de segurança por si só.
MAX_ADMIN_LIST_LIMIT = 200
MAX_ADMIN_LIST_OFFSET = 1_000_000


class AdminListQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_ADMIN_LIST_LIMIT, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, max_value=MAX_ADMIN_LIST_OFFSET, default=0)


class AdminUserListQuerySerializer(AdminListQuerySerializer):
    # icontains sobre User.email — nunca usado como lookup dinâmico (ver
    # apps.ops.views.UserListView: sempre email__icontains, hardcoded, o
    # valor do cliente é só o texto buscado, nunca o nome do campo).
    email = serializers.CharField(required=False, allow_blank=True, max_length=254)


class AdminExperienceListQuerySerializer(AdminListQuerySerializer):
    status = serializers.ChoiceField(choices=ExperienceDraft.Status.choices, required=False)
    owner_email = serializers.CharField(required=False, allow_blank=True, max_length=254)


class AdminPaymentListQuerySerializer(AdminListQuerySerializer):
    status = serializers.ChoiceField(choices=Payment.Status.choices, required=False)
    owner_email = serializers.CharField(required=False, allow_blank=True, max_length=254)


class AdminWebhookEventListQuerySerializer(AdminListQuerySerializer):
    status = serializers.ChoiceField(choices=WebhookEvent.Status.choices, required=False)


class LifecycleInventoryQuerySerializer(serializers.Serializer):
    stale_media_minutes = serializers.IntegerField(required=False, min_value=1, max_value=MAX_MINUTES)
    check_r2 = serializers.BooleanField(required=False, default=False)
    r2_sample_limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_R2_SAMPLE_LIMIT, default=200)
    r2_list_limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_R2_LIST_LIMIT, default=5000)


class PaymentReconcileQuerySerializer(serializers.Serializer):
    stale_minutes = serializers.IntegerField(required=False, min_value=1, max_value=MAX_MINUTES, default=60)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_PAYMENT_RECONCILE_LIMIT, default=50)


class LifecycleCleanupPreviewQuerySerializer(serializers.Serializer):
    draft_abandoned_days = serializers.IntegerField(required=False, min_value=0, max_value=MAX_DAYS, default=30)
    draft_anonymous_unclaimed_hours = serializers.IntegerField(
        required=False, min_value=0, max_value=MAX_HOURS, default=48
    )
    payment_failed_days = serializers.IntegerField(required=False, min_value=0, max_value=MAX_DAYS, default=30)
    media_failed_days = serializers.IntegerField(required=False, min_value=0, max_value=MAX_DAYS, default=7)
    r2_orphan_grace_days = serializers.IntegerField(required=False, min_value=0, max_value=MAX_DAYS, default=30)
    stale_media_minutes = serializers.IntegerField(required=False, min_value=1, max_value=MAX_MINUTES)
    check_r2 = serializers.BooleanField(required=False, default=False)
    r2_list_limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_R2_LIST_LIMIT, default=5000)
