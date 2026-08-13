import uuid
from pathlib import PurePath

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExperienceDraft, Media
from .serializers import ExperienceDraftSerializer, UploadIntentSerializer
from .storage import get_r2_client


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


class MediaUploadIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id):
        draft = get_owned_draft_or_404(request, draft_id)
        serializer = UploadIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        media_type = data["media_type"]
        limits = {Media.Type.PHOTO: 10, Media.Type.VIDEO: 3}
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
