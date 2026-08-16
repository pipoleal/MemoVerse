from rest_framework import serializers

from .models import ExperienceDraft, Media


class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = (
            "id", "media_type", "original_filename", "mime_type", "size_bytes",
            "duration_seconds", "sort_order", "upload_status", "uploaded_at", "created_at",
        )
        read_only_fields = fields


class ExperienceDraftSerializer(serializers.ModelSerializer):
    media = MediaSerializer(many=True, read_only=True)

    class Meta:
        model = ExperienceDraft
        fields = (
            "id", "status", "experience_type", "theme", "title", "recipient_name",
            "creator_name", "event_date", "letter", "short_message", "music_provider",
            "music_url", "media", "created_at", "updated_at",
        )
        read_only_fields = ("id", "status", "media", "created_at", "updated_at")


class PublishResponseSerializer(serializers.Serializer):
    """Somente os dados que o frontend precisa após publicar. Nunca inclui
    owner, payment ou qualquer outro dado interno do draft."""

    slug = serializers.CharField()
    status = serializers.CharField()
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
