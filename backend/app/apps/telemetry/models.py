import uuid

from django.db import models


class FunnelEvent(models.Model):
    """Registro mínimo de instrumentação do funil de conversão (criação da
    experiência -> preview -> preço -> cadastro -> checkout -> pagamento ->
    publicação). Anônimo por design, mesmo princípio já usado em
    apps.accounts (logs de auth.register.success/auth.login.success nunca
    carregam e-mail/payload): nenhuma linha aqui guarda e-mail, nome ou IP —
    só o necessário para reconstruir, depois do fato, em qual etapa um
    visitante parou.

    Existe porque, até esta etapa, /admin (apps.ops) só mostrava o ESTADO
    final de um draft/pagamento, nunca a JORNADA (quantas vezes abriu o
    checkout, se chegou a ver o preço antes de cadastrar, etc.) — ver
    investigação de conversão que motivou esta tabela.
    """

    class Name(models.TextChoices):
        PREVIEW_COMPLETED = "preview_completed", "Preview concluído"
        PRICING_VIEWED = "pricing_viewed", "Preço visualizado"
        SIGNUP_STARTED = "signup_started", "Cadastro iniciado"
        SIGNUP_COMPLETED = "signup_completed", "Cadastro concluído"
        CHECKOUT_VIEWED = "checkout_viewed", "Checkout visualizado"
        PAYMENT_STARTED = "payment_started", "Pagamento iniciado"
        PAYMENT_FAILED = "payment_failed", "Pagamento falhou"
        PAYMENT_APPROVED = "payment_approved", "Pagamento aprovado"
        PUBLICATION_COMPLETED = "publication_completed", "Publicação concluída"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=40, choices=Name.choices)
    # Correlaciona eventos da MESMA aba/navegador ao longo de uma sessão
    # (gerado e persistido em localStorage pelo frontend, ver
    # frontend/lib/analytics.ts) — nunca um identificador de usuário nem
    # deriva de e-mail/IP. Opcional: um evento ainda é útil para contagens
    # agregadas por etapa mesmo sem esse valor (ex.: localStorage
    # indisponível em modo privado).
    session_id = models.CharField(max_length=64, blank=True)
    # Id do ExperienceDraft envolvido, quando existe um nesse momento.
    # Deliberadamente uma string solta, nunca uma ForeignKey: o draft pode
    # já ter sido apagado (lifecycle_cleanup) por quando alguém for ler
    # este registro, e telemetria nunca deve travar nem ser travada por
    # essa exclusão.
    draft_id = models.CharField(max_length=64, blank=True)
    # Só o suficiente para diferenciar uma ocorrência do mesmo evento (ex.:
    # {"plan_code": "weekly"} em payment_started) — nunca um payload livre
    # grande/aninhado (ver FunnelEventCreateSerializer.validate_metadata).
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "funnel_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name", "created_at"]),
            models.Index(fields=["session_id"]),
        ]

    def __str__(self):
        return f"{self.name} @ {self.created_at:%Y-%m-%d %H:%M}"
