import uuid

from django.conf import settings
from django.db import models


class ExperienceDraft(models.Model):
    """A private, editable experience saved before payment and publication."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"
        PAYMENT_FAILED = "payment_failed", "Pagamento falhou"
        PAID = "paid", "Pago"
        PUBLISHED = "published", "Publicado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="experience_drafts",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    # Gerado só na primeira publicação (nunca antes, nunca a partir de
    # título/dado editável) — ver apps.experiences.services.publication_service.
    # null=True: rascunhos não publicados não têm slug; UNIQUE permite
    # múltiplos NULL no Postgres, então isso não exige constraint condicional.
    slug = models.CharField(max_length=32, unique=True, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    experience_type = models.CharField(max_length=100, blank=True)
    theme = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=200, blank=True)
    recipient_name = models.CharField(max_length=200, blank=True)
    creator_name = models.CharField(max_length=200, blank=True)
    event_date = models.DateField(null=True, blank=True)
    letter = models.TextField(blank=True)
    short_message = models.TextField(blank=True)
    music_provider = models.CharField(max_length=32, default="none")
    music_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "experience_drafts"
        ordering = ["-updated_at"]


class Media(models.Model):
    """Metadata for a private media object stored in Cloudflare R2."""

    class Type(models.TextChoices):
        PHOTO = "photo", "Foto"
        VIDEO = "video", "Vídeo"

    class UploadStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        UPLOADED = "uploaded", "Enviado"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(ExperienceDraft, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=10, choices=Type.choices)
    storage_key = models.CharField(max_length=500, unique=True)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()
    duration_seconds = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    upload_status = models.CharField(
        max_length=16, choices=UploadStatus.choices, default=UploadStatus.PENDING
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experience_media"
        ordering = ["media_type", "sort_order", "created_at"]
