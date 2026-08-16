import uuid
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.models import Payment, Plan

from . import storage
from .models import ExperienceDraft, Media
from .services.publication_service import DraftNotPayable, PublicationService

User = get_user_model()


def make_user(email="user@example.com"):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, attempt_number=1, status=Payment.Status.APPROVED, **overrides):
    plan = Plan.objects.get(code="essential")
    defaults = {
        "draft": draft,
        "owner": draft.owner,
        "plan": plan,
        "attempt_number": attempt_number,
        "amount": plan.price,
        "currency": plan.currency,
        "status": status,
        "external_reference": f"memoverse-draft-{draft.id}-attempt-{attempt_number}",
        "idempotency_key": f"mv:{draft.id}:{attempt_number}",
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


def make_media(draft, **overrides):
    media_id = overrides.pop("id", uuid.uuid4())
    defaults = {
        "id": media_id,
        "draft": draft,
        "media_type": Media.Type.PHOTO,
        "storage_key": f"drafts/{draft.id}/photos/{media_id}-test.jpg",
        "original_filename": "test.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
    }
    defaults.update(overrides)
    return Media.objects.create(**defaults)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def publish_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/publish/"


def upload_intent_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/media/upload-intents/"


def upload_complete_url(draft_id, media_id):
    return f"/api/experiences/drafts/{draft_id}/media/{media_id}/complete/"


class PublishOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID)

    def test_owner_can_publish_own_paid_draft(self):
        response = auth_client(self.owner).post(publish_url(self.draft.id), {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_user_cannot_publish_someone_elses_draft(self):
        response = auth_client(self.other_user).post(publish_url(self.draft.id), {})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PAID)
        self.assertIsNone(self.draft.slug)

    def test_anonymous_user_cannot_publish(self):
        response = APIClient().post(publish_url(self.draft.id), {})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class PublishStatusGuardTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = auth_client(self.user)

    def test_draft_status_cannot_be_published(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.DRAFT)
        response = self.client.post(publish_url(draft.id), {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.DRAFT)
        self.assertIsNone(draft.slug)

    def test_awaiting_payment_draft_cannot_be_published(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        response = self.client.post(publish_url(draft.id), {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)
        self.assertIsNone(draft.slug)

    def test_payment_failed_draft_cannot_be_published(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.PAYMENT_FAILED)
        response = self.client.post(publish_url(draft.id), {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PAYMENT_FAILED)
        self.assertIsNone(draft.slug)

    def test_paid_draft_can_be_published(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.PAID)
        response = self.client.post(publish_url(draft.id), {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.PUBLISHED)

    def test_empty_body_is_accepted(self):
        draft = make_draft(self.user, status=ExperienceDraft.Status.PAID)
        response = self.client.post(publish_url(draft.id), {}, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PublishResponseShapeTests(TestCase):
    def test_response_contains_only_slug_status_published_at(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        response = auth_client(user).post(publish_url(draft.id), {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.keys()), {"slug", "status", "published_at"})
        self.assertEqual(response.data["status"], "published")
        self.assertTrue(response.data["slug"])
        self.assertIsNotNone(response.data["published_at"])
        # Nunca deve vazar owner, payment ou qualquer outro dado interno.
        self.assertNotIn("owner", response.data)
        self.assertNotIn("payment", response.data)


class PublishIdempotencyTests(TestCase):
    def test_publishing_twice_keeps_the_same_slug(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        client = auth_client(user)

        first = client.post(publish_url(draft.id), {})
        second = client.post(publish_url(draft.id), {})

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["slug"], second.data["slug"])

    def test_publishing_twice_does_not_change_published_at(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        client = auth_client(user)

        client.post(publish_url(draft.id), {})
        draft.refresh_from_db()
        first_published_at = draft.published_at

        client.post(publish_url(draft.id), {})
        draft.refresh_from_db()

        self.assertEqual(draft.published_at, first_published_at)

    def test_publishing_an_already_published_draft_via_service_is_a_noop(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        first = PublicationService.publish(draft)
        second = PublicationService.publish(first)

        self.assertEqual(first.slug, second.slug)
        self.assertEqual(first.published_at, second.published_at)


class PublishSlugTests(TestCase):
    def test_slug_is_persisted_and_url_safe(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        PublicationService.publish(draft)
        draft.refresh_from_db()

        self.assertTrue(draft.slug)
        self.assertRegex(draft.slug, r"^[A-Za-z0-9_-]+$")
        self.assertLessEqual(len(draft.slug), 32)

    def test_two_different_drafts_get_different_slugs(self):
        user = make_user()
        draft_a = make_draft(user, status=ExperienceDraft.Status.PAID)
        draft_b = make_draft(user, status=ExperienceDraft.Status.PAID)

        PublicationService.publish(draft_a)
        PublicationService.publish(draft_b)
        draft_a.refresh_from_db()
        draft_b.refresh_from_db()

        self.assertNotEqual(draft_a.slug, draft_b.slug)

    def test_slug_collision_is_retried_and_resolved(self):
        user = make_user()
        taken = make_draft(user, status=ExperienceDraft.Status.PAID)
        PublicationService.publish(taken)
        taken.refresh_from_db()

        colliding_draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        with patch(
            "apps.experiences.services.publication_service._generate_slug",
            side_effect=[taken.slug, taken.slug, "fresh-unique-slug"],
        ):
            published = PublicationService.publish(colliding_draft)

        self.assertEqual(published.slug, "fresh-unique-slug")
        self.assertEqual(published.status, ExperienceDraft.Status.PUBLISHED)

    def test_exhausting_all_retry_attempts_raises_integrity_error(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        with patch(
            "apps.experiences.services.publication_service._generate_slug",
            return_value="always-the-same-slug",
        ):
            # Primeira chamada "consome" o slug fixo com sucesso.
            other_draft = make_draft(user, status=ExperienceDraft.Status.PAID)
            PublicationService.publish(other_draft)

            # Toda tentativa subsequente colide com o mesmo slug fixo e
            # esgota as tentativas.
            with self.assertRaises(IntegrityError):
                PublicationService.publish(draft)


class PublishPaymentIsolationTests(TestCase):
    def test_publishing_does_not_create_or_modify_any_payment(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        payment = make_payment(draft=draft, status=Payment.Status.APPROVED)
        payment.refresh_from_db()
        payment_updated_at_before = payment.updated_at

        auth_client(user).post(publish_url(draft.id), {})

        self.assertEqual(Payment.objects.count(), 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.updated_at, payment_updated_at_before)

    def test_publishing_a_paid_draft_with_no_payment_at_all_still_works(self):
        # PublicationService só olha para ExperienceDraft.status — não exige
        # nem consulta nenhum Payment.
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        self.assertFalse(Payment.objects.filter(draft=draft).exists())

        response = auth_client(user).post(publish_url(draft.id), {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Payment.objects.filter(draft=draft).exists())


class PublicationServiceUnitTests(TestCase):
    def test_publish_raises_draft_not_payable_for_non_paid_status(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.DRAFT)

        with self.assertRaises(DraftNotPayable):
            PublicationService.publish(draft)

    def test_published_at_is_close_to_now(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        before = timezone.now()
        published = PublicationService.publish(draft)
        after = timezone.now()

        self.assertGreaterEqual(published.published_at, before)
        self.assertLessEqual(published.published_at, after)


class PresignedReadUrlTests(TestCase):
    """storage.generate_presigned_read_url é infraestrutura pura: não sabe o
    que é Media/ExperienceDraft, não decide autorização. Todas essas
    chamadas mockam o cliente R2 — nenhuma delas alcança a rede."""

    def test_calls_get_object_for_get_semantics(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://r2.example/signed"
            mock_get_client.return_value = mock_client

            storage.generate_presigned_read_url("drafts/abc/photos/1-a.jpg")

            call_args = mock_client.generate_presigned_url.call_args
            self.assertEqual(call_args.args[0], "get_object")

    def test_uses_configured_bucket_and_exact_storage_key(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client, \
             patch("apps.experiences.storage.settings.R2_BUCKET_NAME", "test-bucket"):
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://r2.example/signed"
            mock_get_client.return_value = mock_client

            storage.generate_presigned_read_url("drafts/abc/photos/1-a.jpg")

            params = mock_client.generate_presigned_url.call_args.kwargs["Params"]
            self.assertEqual(params["Bucket"], "test-bucket")
            self.assertEqual(params["Key"], "drafts/abc/photos/1-a.jpg")
            # Só Bucket/Key — nunca credenciais nos Params assinados.
            self.assertEqual(set(params.keys()), {"Bucket", "Key"})

    def test_default_expiration_uses_existing_r2_ttl_setting(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client, \
             patch("apps.experiences.storage.settings.R2_PRESIGNED_URL_TTL_SECONDS", 1234):
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://r2.example/signed"
            mock_get_client.return_value = mock_client

            storage.generate_presigned_read_url("some-key")

            self.assertEqual(mock_client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 1234)

    def test_explicit_expires_in_overrides_default(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://r2.example/signed"
            mock_get_client.return_value = mock_client

            storage.generate_presigned_read_url("some-key", expires_in=60)

            self.assertEqual(mock_client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 60)

    def test_returns_exactly_what_the_client_returns(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://r2.example/signed?X-Amz-Signature=abc"
            mock_get_client.return_value = mock_client

            url = storage.generate_presigned_read_url("some-key")

            self.assertEqual(url, "https://r2.example/signed?X-Amz-Signature=abc")

    def test_no_credentials_appear_in_call_arguments(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client, \
             patch("apps.experiences.storage.settings.R2_ACCESS_KEY_ID", "super-secret-access-key"), \
             patch("apps.experiences.storage.settings.R2_SECRET_ACCESS_KEY", "super-secret-key"):
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = "https://r2.example/signed"
            mock_get_client.return_value = mock_client

            storage.generate_presigned_read_url("some-key")

            call = mock_client.generate_presigned_url.call_args
            serialized_call = f"{call.args}{call.kwargs}"
            self.assertNotIn("super-secret-access-key", serialized_call)
            self.assertNotIn("super-secret-key", serialized_call)

    def test_raises_when_r2_is_not_configured(self):
        # Ambiente de teste não define nenhuma credencial R2 por padrão
        # (settings.py: default=""), então get_r2_client() real (não
        # mockado) levanta antes de qualquer tentativa de rede.
        with self.assertRaises(ImproperlyConfigured):
            storage.generate_presigned_read_url("some-key")


class MediaUploadIntentRegressionTests(TestCase):
    """Cobertura do fluxo de upload EXISTENTE (upload-intents) — nenhuma
    linha desta view foi alterada nesta tarefa; estes testes só documentam o
    comportamento atual para provar ausência de regressão."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)

    def _patch_r2(self, upload_url="https://r2.example/upload-signed"):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = upload_url
        return patch("apps.experiences.views.get_r2_client", return_value=mock_client)

    def test_owner_creates_upload_intent_for_own_draft(self):
        with self._patch_r2():
            response = auth_client(self.owner).post(
                upload_intent_url(self.draft.id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["method"], "PUT")
        self.assertIn("media_id", response.data)
        self.assertIn("upload_url", response.data)

    def test_other_user_cannot_create_upload_intent_for_someone_elses_draft(self):
        with self._patch_r2():
            response = auth_client(self.other_user).post(
                upload_intent_url(self.draft.id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.count(), 0)

    def test_invalid_mime_type_is_rejected(self):
        with self._patch_r2():
            response = auth_client(self.owner).post(
                upload_intent_url(self.draft.id),
                {"media_type": "photo", "filename": "foto.gif", "mime_type": "image/gif", "size_bytes": 1000},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Media.objects.count(), 0)

    def test_photo_limit_of_ten_is_enforced(self):
        for _ in range(10):
            make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)

        with self._patch_r2():
            response = auth_client(self.owner).post(
                upload_intent_url(self.draft.id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Media.objects.filter(draft=self.draft).count(), 10)

    def test_r2_not_configured_returns_503_and_cleans_up_media_row(self):
        # Sem mock: ambiente de teste não tem credenciais R2 configuradas.
        response = auth_client(self.owner).post(
            upload_intent_url(self.draft.id),
            {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Media.objects.count(), 0)


class MediaUploadCompleteRegressionTests(TestCase):
    """Cobertura do fluxo de upload EXISTENTE (complete) — nenhuma linha
    desta view foi alterada nesta tarefa."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)
        self.media = make_media(self.draft, size_bytes=1000, mime_type="image/jpeg")

    def _patch_r2(self, head_object_return=None, head_object_side_effect=None):
        mock_client = MagicMock()
        if head_object_side_effect is not None:
            mock_client.head_object.side_effect = head_object_side_effect
        else:
            mock_client.head_object.return_value = head_object_return
        return patch("apps.experiences.views.get_r2_client", return_value=mock_client)

    def test_matching_upload_marks_media_as_uploaded(self):
        with self._patch_r2(head_object_return={"ContentLength": 1000, "ContentType": "image/jpeg"}):
            response = auth_client(self.owner).post(upload_complete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.media.refresh_from_db()
        self.assertEqual(self.media.upload_status, Media.UploadStatus.UPLOADED)
        self.assertIsNotNone(self.media.uploaded_at)

    def test_content_mismatch_marks_media_as_failed(self):
        with self._patch_r2(head_object_return={"ContentLength": 999999, "ContentType": "image/jpeg"}):
            response = auth_client(self.owner).post(upload_complete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.media.refresh_from_db()
        self.assertEqual(self.media.upload_status, Media.UploadStatus.FAILED)

    def test_object_not_found_in_r2_returns_400(self):
        error = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        with self._patch_r2(head_object_side_effect=error):
            response = auth_client(self.owner).post(upload_complete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.media.refresh_from_db()
        # Comportamento atual (pré-existente, não alterado nesta tarefa):
        # o branch de ClientError não marca FAILED, só o de conteúdo
        # divergente marca. Fica registrado aqui como característica
        # conhecida, não como algo que esta tarefa corrigiu.
        self.assertEqual(self.media.upload_status, Media.UploadStatus.PENDING)

    def test_other_user_cannot_complete_upload_for_someone_elses_draft(self):
        with self._patch_r2(head_object_return={"ContentLength": 1000, "ContentType": "image/jpeg"}):
            response = auth_client(self.other_user).post(upload_complete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.media.refresh_from_db()
        self.assertEqual(self.media.upload_status, Media.UploadStatus.PENDING)
