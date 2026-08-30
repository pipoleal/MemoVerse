import uuid

from django.conf import settings
from django.db import models


class Plan(models.Model):
    """A purchasable MemoVerse plan and the commercial features it unlocks."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="BRL")
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_plans"
        ordering = ["price"]

    def __str__(self):
        return self.code

    def get_feature(self, key, default=None):
        """
        Único ponto de leitura de diferenciais comerciais do plano.
        Evita espalhar `if plan.code == "stellar"` pelo código.
        """

        return self.features.get(key, default)


class Payment(models.Model):
    """A single payment attempt for an ExperienceDraft against a Plan."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        IN_PROCESS = "in_process", "Em processamento"
        ACTION_REQUIRED = "action_required", "Aguardando ação (Pix)"
        APPROVED = "approved", "Aprovado"
        REJECTED = "rejected", "Recusado"
        CANCELLED = "cancelled", "Cancelado"
        EXPIRED = "expired", "Expirado"
        REFUNDED = "refunded", "Reembolsado"

    # Status considerados "em aberto" para fins da constraint de tentativa ativa.
    # Mantido como strings literais (e não Status.PENDING etc.) porque uma classe
    # aninhada em Meta não enxerga nomes definidos no corpo da classe externa.
    ACTIVE_STATUSES = ("pending", "in_process", "action_required")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        "experiences.ExperienceDraft",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    attempt_number = models.PositiveSmallIntegerField()

    # Congelados a partir de plan.price / plan.currency no momento da criação.
    # Nunca recalculados a partir do preço atual do Plan.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    external_reference = models.CharField(max_length=128, unique=True)
    idempotency_key = models.CharField(max_length=128, unique=True)
    mp_order_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    mp_payment_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    last_sync_payload = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "attempt_number"],
                name="uniq_draft_attempt",
            ),
            models.UniqueConstraint(
                fields=["draft"],
                condition=models.Q(status__in=["pending", "in_process", "action_required"]),
                name="uniq_active_payment_per_draft",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["draft", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.draft_id} attempt #{self.attempt_number} ({self.status})"


class PlanDiscount(models.Model):
    """Um preço combinado manualmente no /admin: este e-mail paga `price`
    (em vez de Plan.price) na próxima vez que comprar `plan`. Criado por um
    admin (ver apps.ops), consumido automaticamente por
    CheckoutService._create_attempt.

    Uso único por design: no momento em que vira o preço de um Payment,
    is_active passa a False e redeemed_at/redeemed_payment são gravados —
    nunca mais se aplica sozinho a uma segunda compra do mesmo e-mail. Para
    dar outro desconto ao mesmo e-mail/plano depois, o admin cria uma nova
    linha (a UniqueConstraint abaixo só proíbe DUAS linhas ativas ao mesmo
    tempo para o mesmo par email+plan, nunca o histórico de linhas já
    consumidas)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="discounts")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_plan_discounts"
        ordering = ["-created_at"]
        constraints = [
            # Mesmo padrão de Payment.uniq_active_payment_per_draft: só
            # bloqueia DUAS linhas ativas simultâneas para o mesmo par
            # email+plan — linhas já consumidas (is_active=False) nunca
            # colidem, então o histórico completo de descontos já usados
            # fica preservado.
            models.UniqueConstraint(
                fields=["email", "plan"],
                condition=models.Q(is_active=True),
                name="uniq_active_discount_per_email_plan",
            ),
        ]
        indexes = [
            models.Index(fields=["email", "plan", "is_active"]),
        ]

    def __str__(self):
        return f"{self.email} -> {self.plan.code} @ {self.price}"


class WebhookEvent(models.Model):
    """Registro de idempotência das notificações Webhook da Mercado Pago.

    A garantia de "nunca processar a mesma notificação duas vezes" vive no
    banco (constraint UNIQUE em notification_id) e não em memória/cache —
    sobrevive a reinícios do processo e é segura sob múltiplos workers.
    """

    class Status(models.TextChoices):
        RECEIVED = "received", "Recebido"
        PROCESSED = "processed", "Processado"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # ID de notificação da Mercado Pago (campo `id` do corpo do webhook).
    notification_id = models.CharField(max_length=64, unique=True)
    # Campo `type` do corpo do webhook (ex.: "order", "payment").
    topic = models.CharField(max_length=50)
    # `data.id` do webhook: o recurso a consultar na Mercado Pago.
    resource_id = models.CharField(max_length=64)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    error_detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_webhook_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["topic", "resource_id"]),
        ]

    def __str__(self):
        return f"{self.topic}:{self.resource_id} ({self.notification_id})"
