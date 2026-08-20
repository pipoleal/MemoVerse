from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers

from .models import ExperienceDraft, Media, Theme
from .storage import generate_presigned_read_url


class ThemeSerializer(serializers.Serializer):
    """Catálogo público de temas ativos — GET /api/experiences/themes/.
    Nunca expõe id/is_active/sort_order/created_at/updated_at: o queryset já
    vem filtrado por is_active e ordenado por sort_order (Theme.Meta.ordering),
    então o frontend não precisa desses campos para montar o seletor."""

    code = serializers.CharField()
    name = serializers.CharField()
    features = serializers.DictField()


class MediaSerializer(serializers.ModelSerializer):
    # A readable URL for the OWNER's own media (used by the wizard to resume
    # a draft and show already-uploaded photos/videos). generate_presigned_read_url
    # signs the URL locally (no network round-trip to R2, no extra query per
    # item) — the exact same function PublicExperienceView already uses, just
    # scoped here to the draft's own owner via the normal IsAuthenticated +
    # get_owned_draft_or_404 chain in views.py. None (not an error) when R2
    # isn't configured or the object hasn't finished uploading yet, matching
    # the graceful-degradation pattern already used elsewhere in this app.
    url = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = (
            "id", "media_type", "original_filename", "mime_type", "size_bytes",
            "duration_seconds", "sort_order", "upload_status", "uploaded_at", "created_at", "url",
        )
        read_only_fields = fields

    def get_url(self, media: Media) -> str | None:
        if media.upload_status != Media.UploadStatus.UPLOADED:
            return None
        try:
            return generate_presigned_read_url(media.storage_key)
        except ImproperlyConfigured:
            return None


class ExperienceDraftSerializer(serializers.ModelSerializer):
    media = MediaSerializer(many=True, read_only=True)

    class Meta:
        model = ExperienceDraft
        fields = (
            "id", "status", "slug", "experience_type", "theme", "title", "recipient_name",
            "creator_name", "event_date", "letter", "short_message", "music_provider",
            "music_url", "media", "created_at", "updated_at",
        )
        # slug is only ever set by PublicationService on first publish (see
        # models.ExperienceDraft.slug) — never client-writable, same as status.
        read_only_fields = ("id", "status", "slug", "media", "created_at", "updated_at")

    def validate_theme(self, value):
        # Só valida quando um valor é de fato enviado — "" continua permitido
        # (mesmo comportamento de sempre, ex. um draft ainda na Etapa 1 do
        # wizard, antes de StyleStep). Este método só roda em is_valid()/
        # create()/update() (escrita) — NUNCA na serialização de leitura
        # (GET), então um draft já existente com um theme fora do catálogo
        # atual (ou removido dele) continua sendo lido e devolvido
        # normalmente; só uma nova tentativa de GRAVAR um theme inválido é
        # rejeitada.
        if not value:
            return value
        if not Theme.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError("Tema inválido ou indisponível.")
        return value


class PublishResponseSerializer(serializers.Serializer):
    """Somente os dados que o frontend precisa após publicar. Nunca inclui
    owner, payment ou qualquer outro dado interno do draft."""

    slug = serializers.CharField()
    status = serializers.CharField()
    published_at = serializers.DateTimeField()


class PublicMediaSerializer(serializers.Serializer):
    """Uma mídia pública: só o suficiente para renderizar. `url` é sempre
    uma presigned GET temporária (ver storage.generate_presigned_read_url)
    — storage_key nunca aparece aqui."""

    id = serializers.UUIDField()
    media_type = serializers.CharField()
    url = serializers.CharField()
    original_filename = serializers.CharField()
    sort_order = serializers.IntegerField()


class PublicMusicSerializer(serializers.Serializer):
    provider = serializers.CharField()
    url = serializers.CharField()


class PublicExperienceSerializer(serializers.Serializer):
    """Resposta de GET /api/public/experiences/<slug>/ — sem autenticação.

    Deliberadamente NUNCA inclui: id interno do draft, owner/dados do
    usuário, status de pagamento, Payment, mp_order_id/mp_payment_id,
    storage_key ou qualquer outro dado interno. Só o necessário para
    renderizar a experiência para quem recebeu o link."""

    slug = serializers.CharField()
    title = serializers.CharField()
    experience_type = serializers.CharField()
    theme = serializers.CharField()
    recipient_name = serializers.CharField()
    creator_name = serializers.CharField()
    event_date = serializers.DateField(allow_null=True)
    letter = serializers.CharField()
    short_message = serializers.CharField()
    music = PublicMusicSerializer()
    media = PublicMediaSerializer(many=True)
    published_at = serializers.DateTimeField()


class UploadIntentSerializer(serializers.Serializer):
    media_type = serializers.ChoiceField(choices=Media.Type.choices)
    filename = serializers.CharField(max_length=255)
    mime_type = serializers.CharField(max_length=100)
    size_bytes = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        allowed_types = {
            Media.Type.PHOTO: {"image/jpeg", "image/png", "image/webp"},
            Media.Type.VIDEO: {"video/mp4", "video/webm", "video/quicktime"},
        }
        maximum_sizes = {
            Media.Type.PHOTO: 20 * 1024 * 1024,
            Media.Type.VIDEO: 500 * 1024 * 1024,
        }
        media_type = attrs["media_type"]
        if attrs["mime_type"] not in allowed_types[media_type]:
            raise serializers.ValidationError({"mime_type": "Tipo de arquivo não permitido."})
        if attrs["size_bytes"] > maximum_sizes[media_type]:
            raise serializers.ValidationError({"size_bytes": "Arquivo excede o tamanho permitido."})
        return attrs
