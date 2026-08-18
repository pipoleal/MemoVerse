import uuid
from pathlib import PurePath

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Max, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExperienceDraft, Media
from .serializers import (
    ExperienceDraftSerializer,
    PublicExperienceSerializer,
    PublishResponseSerializer,
    UploadIntentSerializer,
)
from .services.media_cleanup import cleanup_abandoned_media
from .services.publication_service import DraftNotPayable, PublicationService
from .storage import delete_object, generate_presigned_read_url, get_r2_client


def get_owned_draft_or_404(request, draft_id):
    return get_object_or_404(ExperienceDraft, id=draft_id, owner=request.user)


class DraftListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        drafts = ExperienceDraft.objects.filter(owner=request.user).prefetch_related("media")
        return Response(ExperienceDraftSerializer(drafts, many=True).data)

    def post(self, request):
        serializer = ExperienceDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        draft = serializer.save(owner=request.user)
        return Response(ExperienceDraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class DraftDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, draft_id):
        draft = get_owned_draft_or_404(request, draft_id)
        return Response(ExperienceDraftSerializer(draft).data)

    def patch(self, request, draft_id):
        draft = get_owned_draft_or_404(request, draft_id)
        serializer = ExperienceDraftSerializer(draft, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DraftPublishView(APIView):
    """POST /api/experiences/drafts/<uuid:draft_id>/publish/

    Publica um ExperienceDraft já pago (status=paid), gerando um slug
    público via PublicationService. Idempotente: publicar um draft já
    publicado retorna o mesmo slug, sem efeito colateral adicional.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id):
        # Mesmo padrão do resto do app: draft de outro usuário -> 404,
        # nunca revelando que existe.
        draft = get_owned_draft_or_404(request, draft_id)

        try:
            published = PublicationService.publish(draft)
        except DraftNotPayable:
            return Response(
                {"detail": "Este draft ainda não foi pago."},
                status=status.HTTP_409_CONFLICT,
            )

        response_data = {
            "slug": published.slug,
            "status": published.status,
            "published_at": published.published_at,
        }
        return Response(PublishResponseSerializer(response_data).data, status=status.HTTP_200_OK)


class PublicExperienceView(APIView):
    """GET /api/public/experiences/<slug:slug>/

    Único endpoint deste app sem autenticação — quem recebeu o link de uma
    experiência publicada não tem (nem deveria precisar de) conta no
    MemoVerse. Só retorna o necessário para renderizar a experiência.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug):
        # slug inexistente E draft existente-mas-não-publicado caem no MESMO
        # Http404 (a query exige as duas condições ao mesmo tempo) — nunca
        # diferencia os dois casos, mesmo padrão de "nunca revelar
        # existência" já usado em get_owned_draft_or_404.
        draft = get_object_or_404(
            ExperienceDraft.objects.prefetch_related(
                Prefetch("media", queryset=Media.objects.filter(upload_status=Media.UploadStatus.UPLOADED))
            ),
            slug=slug,
            status=ExperienceDraft.Status.PUBLISHED,
        )

        media_items = []
        for media in draft.media.all():
            try:
                url = generate_presigned_read_url(media.storage_key)
            except ImproperlyConfigured:
                # Mesmo tratamento de infraestrutura indisponível já usado em
                # MediaUploadIntentView — nunca deixa o traceback chegar ao
                # cliente.
                return Response(
                    {"detail": "Mídia temporariamente indisponível."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            media_items.append(
                {
                    "id": media.id,
                    "media_type": media.media_type,
                    "url": url,
                    "original_filename": media.original_filename,
                    "sort_order": media.sort_order,
                }
            )

        response_data = {
            "slug": draft.slug,
            "title": draft.title,
            "experience_type": draft.experience_type,
            "theme": draft.theme,
            "recipient_name": draft.recipient_name,
            "creator_name": draft.creator_name,
            "event_date": draft.event_date,
            "letter": draft.letter,
            "short_message": draft.short_message,
            "music": {"provider": draft.music_provider, "url": draft.music_url},
            "media": media_items,
            "published_at": draft.published_at,
        }
        return Response(PublicExperienceSerializer(response_data).data)


class MediaUploadIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id):
        draft = get_owned_draft_or_404(request, draft_id)
        serializer = UploadIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        media_type = data["media_type"]
        limits = {Media.Type.PHOTO: 10, Media.Type.VIDEO: 3}
        # Antes de contar a quota: descarta pendências abandonadas (upload
        # nunca confirmado via .../complete/) para que elas nunca prendam a
        # quota do usuário indefinidamente — ver services.media_cleanup.
        cleanup_abandoned_media(draft)
        active_media = draft.media.exclude(upload_status=Media.UploadStatus.FAILED)
        if active_media.filter(media_type=media_type).count() >= limits[media_type]:
            return Response({"detail": "Limite de mídias atingido."}, status=status.HTTP_400_BAD_REQUEST)

        filename = PurePath(data["filename"]).name
        stem = slugify(PurePath(filename).stem) or "media"
        extension = PurePath(filename).suffix.lower()[:12]
        next_order = (active_media.filter(media_type=media_type).aggregate(max_order=Max("sort_order"))["max_order"] or -1) + 1
        media_id = uuid.uuid4()
        media = Media.objects.create(
            id=media_id,
            draft=draft,
            media_type=media_type,
            storage_key=f"drafts/{draft.id}/{media_type}s/{media_id}-{stem}{extension}",
            original_filename=filename,
            mime_type=data["mime_type"],
            size_bytes=data["size_bytes"],
            sort_order=next_order,
        )
        try:
            upload_url = get_r2_client().generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.R2_BUCKET_NAME,
                    "Key": media.storage_key,
                    "ContentType": media.mime_type,
                },
                ExpiresIn=settings.R2_PRESIGNED_URL_TTL_SECONDS,
            )
        except ImproperlyConfigured:
            media.delete()
            return Response({"detail": "Cloudflare R2 ainda não está configurado."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "media_id": str(media.id),
                "upload_url": upload_url,
                "method": "PUT",
                "headers": {"Content-Type": media.mime_type},
                "expires_in": settings.R2_PRESIGNED_URL_TTL_SECONDS,
            },
            status=status.HTTP_201_CREATED,
        )


class MediaUploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id, media_id):
        draft = get_owned_draft_or_404(request, draft_id)
        media = get_object_or_404(Media, id=media_id, draft=draft)
        try:
            metadata = get_r2_client().head_object(Bucket=settings.R2_BUCKET_NAME, Key=media.storage_key)
        except (ImproperlyConfigured, ClientError):
            return Response({"detail": "Não foi possível confirmar o upload."}, status=status.HTTP_400_BAD_REQUEST)
        if metadata.get("ContentLength", 0) > media.size_bytes or metadata.get("ContentType") != media.mime_type:
            media.upload_status = Media.UploadStatus.FAILED
            media.save(update_fields=["upload_status"])
            return Response({"detail": "O arquivo enviado não confere com a solicitação."}, status=status.HTTP_400_BAD_REQUEST)
        media.upload_status = Media.UploadStatus.UPLOADED
        media.uploaded_at = timezone.now()
        media.save(update_fields=["upload_status", "uploaded_at"])
        return Response({"id": str(media.id), "upload_status": media.upload_status})


class MediaDeleteView(APIView):
    """DELETE /api/experiences/drafts/<uuid:draft_id>/media/<uuid:media_id>/

    Remove uma mídia (em qualquer upload_status) do draft do usuário.

    Best-effort quanto ao R2 (ver storage.delete_object): uma falha ao
    remover o objeto do bucket nunca impede a remoção do registro — o
    usuário pediu para a mídia sumir da experiência, e é isso que o
    registro no banco representa. Um objeto órfão no R2, se isso acontecer,
    nunca é servido a ninguém: generate_presigned_read_url só é chamado
    para mídia com upload_status=UPLOADED referenciada por um draft
    PUBLISHED.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, draft_id, media_id):
        draft = get_owned_draft_or_404(request, draft_id)
        media = get_object_or_404(Media, id=media_id, draft=draft)
        try:
            delete_object(media.storage_key)
        except (ImproperlyConfigured, ClientError):
            pass
        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
