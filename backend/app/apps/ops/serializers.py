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
from apps.payments.models import Payment, Plan, WebhookEvent
from apps.recovery.models import CartRecoveryMessage
from apps.telemetry.models import FunnelEvent

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


class AdminFunnelEventListQuerySerializer(AdminListQuerySerializer):
    name = serializers.ChoiceField(choices=FunnelEvent.Name.choices, required=False)
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=64)


class AdminCartRecoveryMessageListQuerySerializer(AdminListQuerySerializer):
    stage = serializers.ChoiceField(choices=CartRecoveryMessage.Stage.choices, required=False)
    channel = serializers.ChoiceField(choices=CartRecoveryMessage.Channel.choices, required=False)
    status = serializers.ChoiceField(choices=CartRecoveryMessage.Status.choices, required=False)
    owner_email = serializers.CharField(required=False, allow_blank=True, max_length=254)


class _OptionalBooleanField(serializers.BooleanField):
    """serializers.BooleanField comum, mas sem o comportamento especial do
    DRF para input "estilo HTML form" (e é exatamente isso que um
    QueryDict de query params é, na visão do DRF): por padrão,
    BooleanField.default_empty_html = False faz um campo AUSENTE do
    querystring virar False dentro de validated_data — nunca omitido —
    tornando impossível distinguir "não filtrei por is_active" de
    "filtrei por is_active=false" (ambos ficariam com data["is_active"]
    == False). Aqui default_empty_html = empty restaura o comportamento
    padrão de qualquer outro campo required=False: ausente do querystring
    -> ausente de validated_data (SkipField), só True/False quando o
    cliente realmente envia ?is_active=true|false."""

    default_empty_html = serializers.empty


class AdminPlanDiscountListQuerySerializer(AdminListQuerySerializer):
    email = serializers.CharField(required=False, allow_blank=True, max_length=254)
    plan_code = serializers.CharField(required=False, allow_blank=True, max_length=50)
    is_active = _OptionalBooleanField(required=False)


class AdminPlanDiscountCreateSerializer(serializers.Serializer):
    """Cria um PlanDiscount — a única forma de dar um preço combinado a um
    e-mail específico. price é sempre um valor absoluto em BRL (o que o
    e-mail vai pagar), nunca um percentual: mais simples de auditar e é
    literalmente o que o painel pede ("plano mais barato pra esse
    amigo")."""

    email = serializers.EmailField()
    plan_code = serializers.CharField(max_length=50)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate_email(self, value):
        # Mesma normalização usada pelo matching em
        # CheckoutService._create_attempt (email__iexact) — aqui é só
        # cosmético, para a listagem do painel nunca mostrar o mesmo e-mail
        # com capitalizações diferentes.
        return value.strip().lower()

    def validate_plan_code(self, value):
        # Mesmo padrão de CheckoutRequestSerializer.validate_plan_code —
        # nunca um plano inativo/inexistente vira desconto.
        try:
            return Plan.objects.get(code=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plano inválido ou indisponível.")


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
