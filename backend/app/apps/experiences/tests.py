import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.contrib.admin import site
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.models import Payment, Plan

from . import storage
from .models import ExperienceDraft, Media, Theme
from .services.draft_deletion import DraftDeletionService, DraftNotDeletable
from .services.media_cleanup import cleanup_abandoned_media
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


def media_delete_url(draft_id, media_id):
    return f"/api/experiences/drafts/{draft_id}/media/{media_id}/"


def draft_detail_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/"


def public_url(slug):
    return f"/api/public/experiences/{slug}/"


def expire_media(media, *, minutes_ago):
    # Media.created_at usa auto_now_add — só dá para "envelhecer" um
    # registro existente via update() na queryset, nunca atribuindo
    # created_at diretamente na instância antes de save().
    Media.objects.filter(id=media.id).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
    media.refresh_from_db()


THEMES_URL = "/api/experiences/themes/"
DRAFT_LIST_URL = "/api/experiences/drafts/"


class ThemeListViewTests(TestCase):
    """GET /api/experiences/themes/ — catálogo público (AllowAny) dos temas
    ativos. Ver ThemeListView/ThemeSerializer."""

    def test_no_authentication_required(self):
        response = APIClient().get(THEMES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_returns_the_six_existing_themes(self):
        response = self.client.get(THEMES_URL)
        codes = {item["code"] for item in response.data}
        self.assertEqual(codes, {"universe", "cinema", "beach", "flowers", "night", "minimal"})

    def test_an_inactive_theme_never_appears(self):
        Theme.objects.create(code="discontinued", name="Descontinuado", is_active=False)
        response = self.client.get(THEMES_URL)
        codes = {item["code"] for item in response.data}
        self.assertNotIn("discontinued", codes)

    def test_results_are_ordered_by_sort_order(self):
        response = self.client.get(THEMES_URL)
        codes_in_order = [item["code"] for item in response.data]
        self.assertEqual(codes_in_order, ["universe", "cinema", "beach", "flowers", "night", "minimal"])

    def test_theme_shape_and_names(self):
        response = self.client.get(THEMES_URL)
        by_code = {item["code"]: item for item in response.data}
        self.assertEqual(by_code["universe"]["name"], "Universo")
        self.assertEqual(by_code["cinema"]["name"], "Cinema")
        self.assertEqual(by_code["beach"]["name"], "Praia")
        self.assertEqual(by_code["flowers"]["name"], "Flores")
        self.assertEqual(by_code["night"]["name"], "Noite")
        self.assertEqual(by_code["minimal"]["name"], "Minimalista")

    def test_response_items_never_expose_internal_fields(self):
        response = self.client.get(THEMES_URL)
        for item in response.data:
            self.assertEqual(set(item.keys()), {"code", "name", "features"})
            self.assertNotIn("id", item)
            self.assertNotIn("is_active", item)
            self.assertNotIn("sort_order", item)
            self.assertNotIn("created_at", item)
            self.assertNotIn("updated_at", item)


class ExperienceDraftThemeValidationTests(TestCase):
    """ExperienceDraftSerializer.validate_theme — a validação só roda na
    ESCRITA (POST/PATCH). Drafts/experiências já existentes com um theme
    fora do catálogo atual continuam sendo lidos normalmente (nunca
    revalidados) — ver os testes de compatibilidade no final desta classe."""

    def setUp(self):
        self.user = make_user()
        self.client = auth_client(self.user)

    def test_creating_draft_with_active_theme_is_accepted(self):
        response = self.client.post(DRAFT_LIST_URL, {"theme": "beach"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["theme"], "beach")

    def test_creating_draft_with_empty_theme_is_accepted(self):
        # Comportamento inalterado: um draft ainda na Etapa 1 do wizard
        # (antes de StyleStep) nunca deve falhar por causa disso.
        response = self.client.post(DRAFT_LIST_URL, {"theme": ""})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["theme"], "")

    def test_creating_draft_without_theme_field_is_accepted(self):
        response = self.client.post(DRAFT_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["theme"], "")

    def test_creating_draft_with_nonexistent_theme_is_rejected(self):
        response = self.client.post(DRAFT_LIST_URL, {"theme": "does-not-exist"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("theme", response.data)

    def test_creating_draft_with_inactive_theme_is_rejected(self):
        Theme.objects.create(code="discontinued", name="Descontinuado", is_active=False)
        response = self.client.post(DRAFT_LIST_URL, {"theme": "discontinued"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("theme", response.data)

    def test_patching_draft_to_a_valid_theme_is_accepted(self):
        draft = make_draft(self.user, theme="universe")
        response = self.client.patch(draft_detail_url(draft.id), {"theme": "night"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertEqual(draft.theme, "night")

    def test_patching_draft_to_an_invalid_theme_is_rejected_and_leaves_it_unchanged(self):
        draft = make_draft(self.user, theme="universe")
        response = self.client.patch(draft_detail_url(draft.id), {"theme": "does-not-exist"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        draft.refresh_from_db()
        self.assertEqual(draft.theme, "universe")

    # --- Compatibilidade com drafts/experiências legadas ---

    def test_reading_a_draft_with_a_legacy_unknown_theme_still_works(self):
        # Simula um draft antigo com um valor que nunca existiu (ou não
        # existe mais) no catálogo — criado direto no banco, sem passar
        # pelo serializer, exatamente como um registro histórico real.
        draft = make_draft(self.user, theme="stellar")
        response = self.client.get(draft_detail_url(draft.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["theme"], "stellar")

    def test_patching_unrelated_field_on_legacy_theme_draft_does_not_revalidate_theme(self):
        draft = make_draft(self.user, theme="stellar")
        response = self.client.patch(draft_detail_url(draft.id), {"title": "Novo título"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertEqual(draft.theme, "stellar")
        self.assertEqual(draft.title, "Novo título")


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


class PublicationServiceExpiresAtTests(TestCase):
    """expires_at só é calculado no momento da publicação (nunca antes — ver
    ExpiresAtNotSetBeforePublicationTests) e depende exclusivamente do Plan
    do Payment aprovado do draft. Ver
    PublicationService._compute_expires_at."""

    def test_weekly_plan_expires_seven_days_after_publication(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, plan=Plan.objects.get(code="weekly"), status=Payment.Status.APPROVED)

        published = PublicationService.publish(draft)

        self.assertIsNotNone(published.expires_at)
        self.assertEqual(published.expires_at, published.published_at + timedelta(days=7))

    def test_lifetime_plan_never_expires(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, plan=Plan.objects.get(code="lifetime"), status=Payment.Status.APPROVED)

        published = PublicationService.publish(draft)

        self.assertIsNone(published.expires_at)

    def test_lifetime_galaxy_plan_never_expires(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        make_payment(
            draft=draft, plan=Plan.objects.get(code="lifetime_galaxy"), status=Payment.Status.APPROVED
        )

        published = PublicationService.publish(draft)

        self.assertIsNone(published.expires_at)

    def test_legacy_essential_plan_never_expires(self):
        # Planos antigos (essential/stellar) não têm is_lifetime/duration_days
        # em features — o default seguro (is_lifetime=True) preserva o
        # comportamento histórico de "nunca expira" para pagamentos já
        # existentes antes desta feature.
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, plan=Plan.objects.get(code="essential"), status=Payment.Status.APPROVED)

        published = PublicationService.publish(draft)

        self.assertIsNone(published.expires_at)

    def test_republishing_does_not_recompute_expires_at(self):
        # Mesma filosofia de idempotência já usada para slug/published_at:
        # publicar de novo um draft já PUBLISHED nunca altera nada.
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, plan=Plan.objects.get(code="weekly"), status=Payment.Status.APPROVED)

        first = PublicationService.publish(draft)
        original_expires_at = first.expires_at

        second = PublicationService.publish(draft)

        self.assertEqual(second.expires_at, original_expires_at)

    def test_publish_without_any_approved_payment_defaults_to_never_expires(self):
        # Caso defensivo (não deveria acontecer em produção, ver o warning
        # em _compute_expires_at): sem Payment aprovado, o fallback seguro é
        # nunca expirar, nunca levantar erro e travar a publicação.
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        published = PublicationService.publish(draft)

        self.assertIsNone(published.expires_at)


class ExpiresAtNotSetBeforePublicationTests(TestCase):
    """A contagem de expires_at só começa depois de pagamento aprovado E
    publicação — criar o draft ou iniciar o checkout nunca a inicia."""

    def test_freshly_created_draft_has_no_expires_at(self):
        user = make_user()
        draft = make_draft(user)
        self.assertIsNone(draft.expires_at)

    def test_awaiting_payment_draft_has_no_expires_at(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        make_payment(draft=draft, plan=Plan.objects.get(code="weekly"), status=Payment.Status.PENDING)
        draft.refresh_from_db()
        self.assertIsNone(draft.expires_at)

    def test_paid_but_not_yet_published_draft_has_no_expires_at(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, plan=Plan.objects.get(code="weekly"), status=Payment.Status.APPROVED)
        draft.refresh_from_db()
        self.assertIsNone(draft.expires_at)


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
        # Simula explicitamente R2 não configurado, mockando get_r2_client
        # para levantar — não depende de o ambiente de teste ter ou não
        # credenciais reais (o .env de dev pode ter R2 configurado).
        with patch(
            "apps.experiences.storage.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            with self.assertRaises(ImproperlyConfigured):
                storage.generate_presigned_read_url("some-key")


class MediaUploadIntentRegressionTests(TestCase):
    """Cobertura do fluxo de upload EXISTENTE (upload-intents). A view agora
    também chama cleanup_abandoned_media(draft) antes de contar a quota (ver
    MediaUploadIntentCleanupTests) — nenhum destes testes cria mídia
    PENDING expirada, então a chamada é sempre um no-op aqui, e o
    comportamento documentado nesta classe permanece válido."""

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

    def test_sequential_uploads_receive_strictly_increasing_sort_order(self):
        # Não-concorrente, de propósito: cobre o caminho normal (fotos
        # enviadas uma de cada vez) que já funcionava antes da correção da
        # race condition — ver ConcurrentUploadIntentSortOrderTests em
        # test_anonymous_draft.py para o caso concorrente.
        orders = []
        for i in range(3):
            with self._patch_r2():
                response = auth_client(self.owner).post(
                    upload_intent_url(self.draft.id),
                    {"media_type": "photo", "filename": f"foto-{i}.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            orders.append(Media.objects.get(id=response.data["media_id"]).sort_order)
        self.assertEqual(orders, [0, 1, 2])

    def test_r2_not_configured_returns_503_and_cleans_up_media_row(self):
        # Simula explicitamente R2 não configurado (não depende de o
        # ambiente de teste ter ou não credenciais reais — o .env de dev
        # pode ter R2 configurado, e o teste precisa continuar valendo).
        with patch(
            "apps.experiences.views.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
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


class PublicExperienceViewTests(TestCase):
    """GET /api/public/experiences/<slug>/ — sem autenticação (AllowAny),
    nunca exige/aceita JWT."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="test-slug-123",
            published_at=timezone.now(),
            title="Feliz Aniversário",
            experience_type="aniversario",
            theme="stellar",
            recipient_name="Fulano",
            creator_name="Ciclano",
            event_date="2026-12-25",
            letter="Uma carta bonita.",
            short_message="Com carinho.",
            context_answer="Nos conhecemos na faculdade.",
            music_provider="youtube",
            music_url="https://www.youtube.com/watch?v=abc123",
        )

    def _patch_presigned_url(self, url="https://r2.example/signed-read"):
        return patch("apps.experiences.views.generate_presigned_read_url", return_value=url)

    def test_published_experience_returns_200_with_expected_fields(self):
        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "test-slug-123")
        self.assertEqual(response.data["title"], "Feliz Aniversário")
        self.assertEqual(response.data["experience_type"], "aniversario")
        self.assertEqual(response.data["theme"], "stellar")
        self.assertEqual(response.data["recipient_name"], "Fulano")
        self.assertEqual(response.data["creator_name"], "Ciclano")
        self.assertEqual(str(response.data["event_date"]), "2026-12-25")
        self.assertEqual(response.data["letter"], "Uma carta bonita.")
        self.assertEqual(response.data["short_message"], "Com carinho.")
        self.assertEqual(response.data["context_answer"], "Nos conhecemos na faculdade.")
        self.assertEqual(response.data["music"], {"provider": "youtube", "url": "https://www.youtube.com/watch?v=abc123"})
        self.assertIn("published_at", response.data)
        self.assertEqual(response.data["media"], [])

    def test_request_requires_no_authentication_at_all(self):
        # Cliente sem NENHUM header de Authorization — nem token inválido,
        # simplesmente ausente.
        with self._patch_presigned_url():
            response = APIClient().get(public_url(self.draft.slug))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_slug_returns_404(self):
        response = self.client.get(public_url("does-not-exist"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_paid_but_not_published_draft_returns_404(self):
        # PublicationService só atribui slug na publicação — para simular
        # "existe, tem algo parecido com slug, mas não está published",
        # setamos um slug manualmente sem publicar (cenário defensivo).
        paid_draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID, slug="paid-not-published")
        response = self.client.get(public_url(paid_draft.slug))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_404_response_is_identical_whether_slug_exists_or_not(self):
        paid_draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID, slug="paid-not-published-2")

        response_existing_unpublished = self.client.get(public_url(paid_draft.slug))
        response_nonexistent = self.client.get(public_url("totally-made-up-slug"))

        self.assertEqual(response_existing_unpublished.status_code, response_nonexistent.status_code)
        self.assertEqual(response_existing_unpublished.data, response_nonexistent.data)

    def test_uploaded_media_appears_in_response(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED, sort_order=0)

        with self._patch_presigned_url(url="https://r2.example/photo-signed"):
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(len(response.data["media"]), 1)
        item = response.data["media"][0]
        self.assertEqual(item["id"], str(media.id))
        self.assertEqual(item["media_type"], "photo")
        self.assertEqual(item["url"], "https://r2.example/photo-signed")
        self.assertEqual(item["original_filename"], media.original_filename)
        self.assertEqual(item["sort_order"], 0)

    def test_pending_media_does_not_appear(self):
        make_media(self.draft, upload_status=Media.UploadStatus.PENDING)

        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(response.data["media"], [])

    def test_failed_media_does_not_appear(self):
        make_media(self.draft, upload_status=Media.UploadStatus.FAILED)

        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(response.data["media"], [])

    def test_only_uploaded_media_is_returned_among_a_mix_of_statuses(self):
        uploaded = make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED, sort_order=0)
        make_media(self.draft, upload_status=Media.UploadStatus.PENDING, sort_order=1)
        make_media(self.draft, upload_status=Media.UploadStatus.FAILED, sort_order=2)

        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(len(response.data["media"]), 1)
        self.assertEqual(response.data["media"][0]["id"], str(uploaded.id))

    def test_another_experiences_media_is_never_mixed_in(self):
        other_owner = make_user("other-owner@example.com")
        other_draft = make_draft(
            other_owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="other-experience-slug",
            published_at=timezone.now(),
        )
        make_media(other_draft, upload_status=Media.UploadStatus.UPLOADED)
        make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)

        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(len(response.data["media"]), 1)
        self.assertEqual(Media.objects.filter(draft=self.draft).count(), 1)
        self.assertEqual(Media.objects.filter(draft=other_draft).count(), 1)

    def test_r2_not_configured_returns_503(self):
        make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)
        # Simula explicitamente R2 não configurado (mesmo padrão de
        # _patch_presigned_url, mas levantando) — não depende de o ambiente
        # de teste ter ou não credenciais reais (o .env de dev pode ter R2
        # configurado, e este teste precisa continuar valendo mesmo assim).
        with patch(
            "apps.experiences.views.generate_presigned_read_url",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            response = self.client.get(public_url(self.draft.slug))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_presigned_url_is_generated_with_the_correct_storage_key(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)

        with self._patch_presigned_url() as mock_fn:
            self.client.get(public_url(self.draft.slug))

        mock_fn.assert_called_once_with(media.storage_key)

    def test_storage_key_never_appears_anywhere_in_the_response(self):
        media = make_media(
            self.draft,
            upload_status=Media.UploadStatus.UPLOADED,
            storage_key=f"drafts/{self.draft.id}/photos/very-secret-internal-key.jpg",
        )

        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        serialized = str(response.data)
        self.assertNotIn(media.storage_key, serialized)
        self.assertNotIn("very-secret-internal-key", serialized)

    def test_response_never_exposes_owner_or_payment_data(self):
        make_payment(draft=self.draft, status=Payment.Status.APPROVED)

        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        serialized_keys = str(response.data)
        for forbidden in (
            "owner",
            "owner_id",
            "payment",
            "payment_id",
            "mp_order_id",
            "mp_payment_id",
            self.owner.email,
            str(self.owner.id),
            str(self.draft.id),
        ):
            self.assertNotIn(forbidden, serialized_keys)

    def test_response_top_level_keys_are_exactly_the_public_contract(self):
        with self._patch_presigned_url():
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(
            set(response.data.keys()),
            {
                "slug", "title", "experience_type", "theme", "recipient_name",
                "creator_name", "event_date", "letter", "short_message",
                "music", "media", "published_at", "viewer_can_manage", "context_answer",
            },
        )

    def test_anonymous_viewer_can_manage_is_false(self):
        with self._patch_presigned_url():
            response = APIClient().get(public_url(self.draft.slug))
        self.assertFalse(response.data["viewer_can_manage"])

    def test_owner_viewer_can_manage_is_true(self):
        with self._patch_presigned_url():
            response = auth_client(self.owner).get(public_url(self.draft.slug))
        self.assertTrue(response.data["viewer_can_manage"])

    def test_other_authenticated_user_viewer_can_manage_is_false(self):
        other_user = make_user("other-viewer@example.com")
        with self._patch_presigned_url():
            response = auth_client(other_user).get(public_url(self.draft.slug))
        self.assertFalse(response.data["viewer_can_manage"])


class PublicExperienceViewExpirationTests(TestCase):
    """Draft.expires_at=None (planos vitalícios, ou publicações antigas de
    antes desta feature) nunca expira — só um expires_at no passado bloqueia
    o acesso. Mesmo tratamento de "nunca revelar existência" do resto desta
    view: expirado vira o mesmíssimo 404 de slug inexistente."""

    def setUp(self):
        self.owner = make_user("owner@example.com")

    def test_draft_with_no_expires_at_is_always_reachable(self):
        draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="lifetime-slug",
            published_at=timezone.now(),
            expires_at=None,
        )
        response = self.client.get(public_url(draft.slug))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_draft_with_future_expires_at_is_reachable(self):
        draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="not-yet-expired-slug",
            published_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(public_url(draft.slug))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_draft_with_past_expires_at_returns_404(self):
        draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="expired-slug",
            published_at=timezone.now() - timedelta(days=8),
            expires_at=timezone.now() - timedelta(days=1),
        )
        response = self.client.get(public_url(draft.slug))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_expired_response_is_identical_to_nonexistent_slug(self):
        draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="expired-slug-2",
            published_at=timezone.now() - timedelta(days=8),
            expires_at=timezone.now() - timedelta(days=1),
        )
        response_expired = self.client.get(public_url(draft.slug))
        response_nonexistent = self.client.get(public_url("totally-made-up-slug-2"))
        self.assertEqual(response_expired.status_code, response_nonexistent.status_code)
        self.assertEqual(response_expired.data, response_nonexistent.data)


class DeleteObjectTests(TestCase):
    """storage.delete_object é infraestrutura pura, mesmo contrato de
    generate_presigned_read_url — nenhuma dessas chamadas alcança a rede."""

    def test_calls_delete_object_with_configured_bucket_and_exact_key(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client, \
             patch("apps.experiences.storage.settings.R2_BUCKET_NAME", "test-bucket"):
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            storage.delete_object("drafts/abc/photos/1-a.jpg")

            mock_client.delete_object.assert_called_once_with(
                Bucket="test-bucket", Key="drafts/abc/photos/1-a.jpg"
            )

    def test_raises_when_r2_is_not_configured(self):
        with patch(
            "apps.experiences.storage.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            with self.assertRaises(ImproperlyConfigured):
                storage.delete_object("some-key")

    def test_propagates_client_error(self):
        with patch("apps.experiences.storage.get_r2_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.delete_object.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Internal Error"}}, "DeleteObject"
            )
            mock_get_client.return_value = mock_client

            with self.assertRaises(ClientError):
                storage.delete_object("some-key")


class MediaDeleteViewTests(TestCase):
    """DELETE /api/experiences/drafts/<id>/media/<id>/ — ver
    views.MediaDeleteView e storage.delete_object."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)
        self.media = make_media(self.draft)

    def _patch_r2(self, delete_object_side_effect=None):
        mock_client = MagicMock()
        if delete_object_side_effect is not None:
            mock_client.delete_object.side_effect = delete_object_side_effect
        return patch("apps.experiences.storage.get_r2_client", return_value=mock_client)

    def test_owner_deletes_own_media(self):
        with self._patch_r2():
            response = auth_client(self.owner).delete(media_delete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id=self.media.id).exists())

    def test_deletion_calls_r2_delete_object_with_exact_storage_key(self):
        with patch("apps.experiences.views.delete_object") as mock_delete_object:
            auth_client(self.owner).delete(media_delete_url(self.draft.id, self.media.id))
            mock_delete_object.assert_called_once_with(self.media.storage_key)

    def test_other_user_cannot_delete_someone_elses_media(self):
        with self._patch_r2():
            response = auth_client(self.other_user).delete(media_delete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Media.objects.filter(id=self.media.id).exists())

    def test_anonymous_user_cannot_delete(self):
        # Etapa 10: MediaDeleteView agora é AllowAny (para permitir drafts
        # anônimos com X-Draft-Claim-Token) — uma requisição anônima sem esse
        # header, contra um draft que tem owner, cai em
        # get_accessible_draft_or_404 e resulta em 404 (não mais 401/403),
        # igual a qualquer outra combinação não autorizada (ver
        # test_anonymous_draft.py).
        response = APIClient().delete(media_delete_url(self.draft.id, self.media.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Media.objects.filter(id=self.media.id).exists())

    def test_nonexistent_media_id_returns_404(self):
        with self._patch_r2():
            response = auth_client(self.owner).delete(media_delete_url(self.draft.id, uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_media_belonging_to_a_different_draft_returns_404(self):
        # media_id existe, mas não pertence ao draft_id da URL — mesmo
        # padrão de "nunca revelar existência" usado no resto do app.
        other_draft = make_draft(self.owner)
        with self._patch_r2():
            response = auth_client(self.owner).delete(media_delete_url(other_draft.id, self.media.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Media.objects.filter(id=self.media.id).exists())

    def test_r2_client_error_does_not_block_record_deletion(self):
        error = ClientError({"Error": {"Code": "500", "Message": "Internal Error"}}, "DeleteObject")
        with self._patch_r2(delete_object_side_effect=error):
            response = auth_client(self.owner).delete(media_delete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id=self.media.id).exists())

    def test_r2_not_configured_does_not_block_record_deletion(self):
        with patch(
            "apps.experiences.storage.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            response = auth_client(self.owner).delete(media_delete_url(self.draft.id, self.media.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id=self.media.id).exists())

    def test_can_delete_media_in_any_upload_status(self):
        for upload_status in (Media.UploadStatus.PENDING, Media.UploadStatus.UPLOADED, Media.UploadStatus.FAILED):
            media = make_media(self.draft, upload_status=upload_status)
            with self._patch_r2():
                response = auth_client(self.owner).delete(media_delete_url(self.draft.id, media.id))
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertFalse(Media.objects.filter(id=media.id).exists())

    def test_deleted_media_does_not_reappear_on_draft_resume(self):
        # Etapa 9A: fecha o loop "mídia removida não reaparece no resume" —
        # o frontend passou a chamar este DELETE de verdade; aqui provamos
        # que, uma vez chamado, um GET subsequente do draft (o que o wizard
        # usa para retomar) já não inclui mais a mídia removida.
        media = make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)
        client = auth_client(self.owner)
        with self._patch_r2():
            delete_response = client.delete(media_delete_url(self.draft.id, media.id))
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        get_response = client.get(draft_detail_url(self.draft.id))
        media_ids = [item["id"] for item in get_response.data["media"]]
        self.assertNotIn(str(media.id), media_ids)


class MediaCaptionUpdateTests(TestCase):
    """PATCH /api/experiences/drafts/<id>/media/<id>/ (legenda) — Fase 2.2.
    Mesma view/URL/autorização de MediaDeleteViewTests, só um verbo a mais."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)
        self.media = make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)

    def test_owner_updates_caption(self):
        response = auth_client(self.owner).patch(
            media_delete_url(self.draft.id, self.media.id),
            {"caption": "Nosso primeiro passeio juntos."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.media.refresh_from_db()
        self.assertEqual(self.media.caption, "Nosso primeiro passeio juntos.")

    def test_blank_caption_is_valid_and_means_no_caption(self):
        self.media.caption = "Uma legenda qualquer"
        self.media.save(update_fields=["caption"])

        response = auth_client(self.owner).patch(
            media_delete_url(self.draft.id, self.media.id), {"caption": ""}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.media.refresh_from_db()
        self.assertEqual(self.media.caption, "")

    def test_legacy_media_without_caption_reads_as_empty_string(self):
        # make_media() nunca passa caption -- simula mídia criada antes
        # deste campo existir.
        response = auth_client(self.owner).get(draft_detail_url(self.draft.id))
        media_item = next(item for item in response.data["media"] if item["id"] == str(self.media.id))
        self.assertEqual(media_item["caption"], "")

    def test_other_user_cannot_update_someone_elses_media_caption(self):
        response = auth_client(self.other_user).patch(
            media_delete_url(self.draft.id, self.media.id), {"caption": "Tentativa indevida"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.media.refresh_from_db()
        self.assertEqual(self.media.caption, "")

    def test_anonymous_user_without_token_cannot_update_caption(self):
        response = APIClient().patch(
            media_delete_url(self.draft.id, self.media.id), {"caption": "Tentativa indevida"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_caption_at_max_length_is_accepted(self):
        caption = "x" * 140
        response = auth_client(self.owner).patch(
            media_delete_url(self.draft.id, self.media.id), {"caption": caption}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.media.refresh_from_db()
        self.assertEqual(self.media.caption, caption)

    def test_caption_over_max_length_is_rejected(self):
        response = auth_client(self.owner).patch(
            media_delete_url(self.draft.id, self.media.id), {"caption": "x" * 141}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.media.refresh_from_db()
        self.assertEqual(self.media.caption, "")

    def test_caption_update_does_not_change_other_media_fields(self):
        original_upload_status = self.media.upload_status
        original_sort_order = self.media.sort_order
        original_storage_key = self.media.storage_key

        response = auth_client(self.owner).patch(
            media_delete_url(self.draft.id, self.media.id), {"caption": "Só a legenda muda"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.media.refresh_from_db()
        self.assertEqual(self.media.upload_status, original_upload_status)
        self.assertEqual(self.media.sort_order, original_sort_order)
        self.assertEqual(self.media.storage_key, original_storage_key)

    def test_caption_appears_in_public_experience(self):
        self.media.caption = "Nosso primeiro passeio juntos."
        self.media.save(update_fields=["caption"])
        self.draft.status = ExperienceDraft.Status.PUBLISHED
        self.draft.slug = "caption-public-test"
        self.draft.published_at = timezone.now()
        self.draft.save(update_fields=["status", "slug", "published_at"])

        with patch("apps.experiences.views.generate_presigned_read_url", return_value="https://r2.example/signed"):
            response = self.client.get(public_url(self.draft.slug))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        media_item = next(item for item in response.data["media"] if item["id"] == str(self.media.id))
        self.assertEqual(media_item["caption"], "Nosso primeiro passeio juntos.")


class MediaCleanupServiceTests(TestCase):
    """services.media_cleanup.cleanup_abandoned_media — ver docstring do
    módulo para a motivação (uploads nunca confirmados não podem prender a
    quota de mídia de um draft indefinidamente)."""

    def setUp(self):
        self.owner = make_user()
        self.draft = make_draft(self.owner)

    def _patch_r2(self, delete_object_side_effect=None):
        mock_client = MagicMock()
        if delete_object_side_effect is not None:
            mock_client.delete_object.side_effect = delete_object_side_effect
        return patch("apps.experiences.storage.get_r2_client", return_value=mock_client)

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_pending_media_older_than_expiration_is_removed(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(media, minutes_ago=61)

        with self._patch_r2():
            cleanup_abandoned_media(self.draft)

        self.assertFalse(Media.objects.filter(id=media.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_pending_media_within_expiration_window_is_kept(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(media, minutes_ago=59)

        with self._patch_r2():
            cleanup_abandoned_media(self.draft)

        self.assertTrue(Media.objects.filter(id=media.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_uploaded_media_is_never_touched_regardless_of_age(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)
        expire_media(media, minutes_ago=999)

        with self._patch_r2():
            cleanup_abandoned_media(self.draft)

        self.assertTrue(Media.objects.filter(id=media.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_failed_media_is_never_touched_regardless_of_age(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.FAILED)
        expire_media(media, minutes_ago=999)

        with self._patch_r2():
            cleanup_abandoned_media(self.draft)

        self.assertTrue(Media.objects.filter(id=media.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_r2_failure_does_not_block_removal_of_the_record(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(media, minutes_ago=61)
        error = ClientError({"Error": {"Code": "500", "Message": "Internal Error"}}, "DeleteObject")

        with self._patch_r2(delete_object_side_effect=error):
            cleanup_abandoned_media(self.draft)

        self.assertFalse(Media.objects.filter(id=media.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_r2_not_configured_does_not_block_removal_of_the_record(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(media, minutes_ago=61)

        with patch(
            "apps.experiences.storage.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            cleanup_abandoned_media(self.draft)

        self.assertFalse(Media.objects.filter(id=media.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_only_touches_media_of_the_given_draft(self):
        other_draft = make_draft(self.owner)
        own_expired = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(own_expired, minutes_ago=61)
        other_expired = make_media(other_draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(other_expired, minutes_ago=61)

        with self._patch_r2():
            cleanup_abandoned_media(self.draft)

        self.assertFalse(Media.objects.filter(id=own_expired.id).exists())
        self.assertTrue(Media.objects.filter(id=other_expired.id).exists())

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_deletion_calls_r2_delete_object_with_exact_storage_key(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        expire_media(media, minutes_ago=61)

        with patch("apps.experiences.services.media_cleanup.delete_object") as mock_delete_object:
            cleanup_abandoned_media(self.draft)

        mock_delete_object.assert_called_once_with(media.storage_key)


class MediaUploadIntentCleanupTests(TestCase):
    """MediaUploadIntentView chama cleanup_abandoned_media(draft) antes de
    contar a quota — mídias PENDING abandonadas nunca devem prender a
    quota de um draft indefinidamente."""

    def setUp(self):
        self.owner = make_user()
        self.draft = make_draft(self.owner)

    def _patch_r2(self, upload_url="https://r2.example/upload-signed"):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = upload_url
        return patch("apps.experiences.views.get_r2_client", return_value=mock_client)

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_expired_pending_media_is_cleaned_up_and_frees_quota(self):
        # 10 fotos PENDING expiradas ocupam o limite de 10 — sem a limpeza,
        # a próxima tentativa de upload seria recusada por engano.
        for _ in range(10):
            media = make_media(self.draft, media_type=Media.Type.PHOTO, upload_status=Media.UploadStatus.PENDING)
            expire_media(media, minutes_ago=61)

        with self._patch_r2():
            response = auth_client(self.owner).post(
                upload_intent_url(self.draft.id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Media.objects.filter(draft=self.draft, upload_status=Media.UploadStatus.PENDING).count(), 1)

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_recent_pending_media_still_counts_toward_quota(self):
        # Sem expiração (criada agora, dentro da janela), a pending continua
        # valendo como mídia ativa — a limpeza não é retroativamente
        # agressiva, só remove o que já passou do prazo.
        for _ in range(10):
            make_media(self.draft, media_type=Media.Type.PHOTO, upload_status=Media.UploadStatus.PENDING)

        with self._patch_r2():
            response = auth_client(self.owner).post(
                upload_intent_url(self.draft.id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Media.objects.filter(draft=self.draft).count(), 10)


class DraftDeleteViewTests(TestCase):
    """DELETE /api/experiences/drafts/<id>/ — ver views.DraftDetailView.delete
    e services.draft_deletion.DraftDeletionService.

    Regra central testada aqui: só um draft sem slug, sem Payment associado
    e com status exatamente 'draft' pode ser excluído — nunca
    awaiting_payment/payment_failed/paid/published, e nunca um draft de
    outro usuário (sempre 404, nunca 403, mesmo padrão do resto do app)."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)

    def _patch_r2(self, delete_object_side_effect=None):
        mock_client = MagicMock()
        if delete_object_side_effect is not None:
            mock_client.delete_object.side_effect = delete_object_side_effect
        return patch("apps.experiences.storage.get_r2_client", return_value=mock_client)

    # 1. Exclusão do próprio draft --------------------------------------

    def test_owner_can_delete_own_draft(self):
        with self._patch_r2():
            response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExperienceDraft.objects.filter(id=self.draft.id).exists())

    def test_response_body_is_empty_on_success(self):
        with self._patch_r2():
            response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))
        self.assertEqual(response.content, b"")

    # 2. Ownership --------------------------------------------------------

    def test_other_user_cannot_delete_someone_elses_draft(self):
        with self._patch_r2():
            response = auth_client(self.other_user).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ExperienceDraft.objects.filter(id=self.draft.id).exists())

    # 3-6. Guarda de status ------------------------------------------------

    def test_awaiting_payment_draft_cannot_be_deleted(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        response = auth_client(self.owner).delete(draft_detail_url(draft.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft.id).exists())

    def test_payment_failed_draft_cannot_be_deleted(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.PAYMENT_FAILED)
        response = auth_client(self.owner).delete(draft_detail_url(draft.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft.id).exists())

    def test_paid_draft_cannot_be_deleted(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID)
        response = auth_client(self.owner).delete(draft_detail_url(draft.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft.id).exists())

    def test_published_draft_cannot_be_deleted(self):
        draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            slug="test-slug-1",
            published_at=timezone.now(),
        )
        response = auth_client(self.owner).delete(draft_detail_url(draft.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft.id).exists())

    # 7. Payment associado, mesmo com status draft -------------------------

    def test_draft_with_payment_cannot_be_deleted_even_if_status_is_draft(self):
        # Cenário defensivo: mesmo que o status ainda esteja como "draft" no
        # banco, a existência de QUALQUER Payment associado bloqueia a
        # exclusão — nunca confiamos só no status.
        make_payment(draft=self.draft, status=Payment.Status.PENDING)

        response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(ExperienceDraft.objects.filter(id=self.draft.id).exists())

    # 8-9. Mídia + R2 -------------------------------------------------------

    def test_deleting_draft_removes_its_media_records(self):
        media_a = make_media(self.draft)
        media_b = make_media(self.draft, media_type=Media.Type.VIDEO)

        with self._patch_r2():
            response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id__in=[media_a.id, media_b.id]).exists())

    def test_deletion_calls_r2_delete_object_for_each_media(self):
        media_a = make_media(self.draft)
        media_b = make_media(self.draft, media_type=Media.Type.VIDEO)

        with patch("apps.experiences.services.draft_deletion.delete_object") as mock_delete_object:
            auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        mock_delete_object.assert_any_call(media_a.storage_key)
        mock_delete_object.assert_any_call(media_b.storage_key)
        self.assertEqual(mock_delete_object.call_count, 2)

    def test_other_drafts_media_is_never_touched(self):
        other_draft = make_draft(self.owner)
        other_media = make_media(other_draft)
        own_media = make_media(self.draft)

        with self._patch_r2():
            response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id=own_media.id).exists())
        self.assertTrue(Media.objects.filter(id=other_media.id).exists())
        self.assertTrue(ExperienceDraft.objects.filter(id=other_draft.id).exists())

    def test_r2_client_error_does_not_block_draft_deletion(self):
        media = make_media(self.draft)
        error = ClientError({"Error": {"Code": "500", "Message": "Internal Error"}}, "DeleteObject")

        with self._patch_r2(delete_object_side_effect=error):
            response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExperienceDraft.objects.filter(id=self.draft.id).exists())
        self.assertFalse(Media.objects.filter(id=media.id).exists())

    def test_r2_not_configured_does_not_block_draft_deletion(self):
        make_media(self.draft)
        with patch(
            "apps.experiences.storage.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            response = auth_client(self.owner).delete(draft_detail_url(self.draft.id))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExperienceDraft.objects.filter(id=self.draft.id).exists())

    # 10-11. Inexistência / idempotência do lado do cliente -----------------

    def test_nonexistent_draft_returns_404(self):
        response = auth_client(self.owner).delete(draft_detail_url(uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_repeating_delete_after_success_returns_404(self):
        with self._patch_r2():
            first = auth_client(self.owner).delete(draft_detail_url(self.draft.id))
        self.assertEqual(first.status_code, status.HTTP_204_NO_CONTENT)

        second = auth_client(self.owner).delete(draft_detail_url(self.draft.id))
        self.assertEqual(second.status_code, status.HTTP_404_NOT_FOUND)

    # 12. Autenticação ------------------------------------------------------

    def test_anonymous_user_receives_401(self):
        response = APIClient().delete(draft_detail_url(self.draft.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(ExperienceDraft.objects.filter(id=self.draft.id).exists())

    # Segurança: body do request nunca é lido para decidir nada -------------

    def test_body_owner_and_status_fields_are_ignored(self):
        # DELETE nunca lê request.data: owner vem só de request.user, status
        # vem só do banco. Um body tentando forjar outro dono/status não
        # tem nenhum efeito.
        with self._patch_r2():
            response = auth_client(self.owner).delete(
                draft_detail_url(self.draft.id),
                data={"owner": str(self.other_user.id), "status": "published", "id": str(uuid.uuid4())},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExperienceDraft.objects.filter(id=self.draft.id).exists())


class DraftDeletionServiceUnitTests(TestCase):
    """services.draft_deletion.DraftDeletionService — testes diretos no
    service, sem passar pela view/HTTP."""

    def _patch_r2(self):
        mock_client = MagicMock()
        return patch("apps.experiences.storage.get_r2_client", return_value=mock_client)

    def test_delete_raises_draft_not_deletable_for_non_draft_status(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)

        with self.assertRaises(DraftNotDeletable):
            DraftDeletionService.delete(draft)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft.id).exists())

    def test_delete_raises_draft_not_deletable_when_payment_exists(self):
        user = make_user()
        draft = make_draft(user)
        make_payment(draft=draft, status=Payment.Status.APPROVED)

        with self.assertRaises(DraftNotDeletable):
            DraftDeletionService.delete(draft)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft.id).exists())

    def test_delete_removes_draft_and_cascades_media(self):
        user = make_user()
        draft = make_draft(user)
        media = make_media(draft)

        with self._patch_r2():
            DraftDeletionService.delete(draft)

        self.assertFalse(ExperienceDraft.objects.filter(id=draft.id).exists())
        self.assertFalse(Media.objects.filter(id=media.id).exists())


class ExperiencesAdminReadOnlyTests(TestCase):
    """Etapa 6 — Fase C: ExperienceDraft/Media/Theme aparecem no Django
    Admin, com busca/filtro, e SOMENTE leitura (sem Adicionar/Salvar/
    Excluir) — nenhuma action destrutiva ou de mudança de negócio."""

    def setUp(self):
        self.staff = User.objects.create_superuser(
            email="admin@example.com", password="strong-pass-123"
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_experience_draft_list_page_loads_with_data(self):
        draft = make_draft(make_user("owner1@example.com"), title="Aniversário da Ana")
        response = self.client.get("/admin/experiences/experiencedraft/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aniversário da Ana")
        self.assertContains(response, str(draft.status))

    def test_media_list_page_loads_with_data(self):
        draft = make_draft(make_user("owner2@example.com"))
        make_media(draft, original_filename="foto-especial.jpg")
        response = self.client.get("/admin/experiences/media/")
        self.assertEqual(response.status_code, 200)

    def test_theme_list_page_loads_with_data(self):
        response = self.client.get("/admin/experiences/theme/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "universe")

    def test_status_filter_narrows_the_experience_draft_list(self):
        make_draft(make_user("owner3@example.com"), status=ExperienceDraft.Status.DRAFT)
        make_draft(make_user("owner4@example.com"), status=ExperienceDraft.Status.PUBLISHED)
        response = self.client.get(
            "/admin/experiences/experiencedraft/", {"status__exact": ExperienceDraft.Status.PUBLISHED}
        )
        self.assertEqual(response.status_code, 200)

    def test_add_change_and_delete_permissions_are_all_denied(self):
        request = _FakeRequest(self.staff)
        for model in (ExperienceDraft, Media, Theme):
            model_admin = site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))

    def test_add_view_is_not_reachable(self):
        response = self.client.get("/admin/experiences/experiencedraft/add/")
        self.assertEqual(response.status_code, 403)

    def test_delete_view_is_not_reachable(self):
        draft = make_draft(make_user("owner5@example.com"))
        response = self.client.get(f"/admin/experiences/experiencedraft/{draft.id}/delete/")
        self.assertEqual(response.status_code, 403)


class _FakeRequest:
    """Objeto mínimo com o único atributo que has_*_permission consulta."""

    def __init__(self, user):
        self.user = user


class DraftCreationAndPatchTests(TestCase):
    """Etapa 7 — Fase D: cobertura dos gaps identificados na auditoria —
    criação minimalista genérica (não só tema), round-trip completo de
    todos os campos, PATCH multi-campo simultâneo, e ownership dedicado de
    GET/PATCH em DraftDetailView (antes só coberto para publish/media/delete)."""

    def test_creating_a_draft_with_an_empty_payload_succeeds(self):
        user = make_user()
        response = auth_client(user).post(DRAFT_LIST_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], ExperienceDraft.Status.DRAFT)
        self.assertEqual(response.data["title"], "")

    def test_creating_a_draft_with_only_one_non_theme_field_succeeds(self):
        user = make_user()
        response = auth_client(user).post(DRAFT_LIST_URL, {"title": "Aniversário"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Aniversário")
        self.assertEqual(response.data["theme"], "")

    def test_legacy_draft_without_context_answer_reads_as_empty_string(self):
        # Fase 2.1: um draft criado antes deste campo existir (aqui,
        # simulado por não passar context_answer no create) nunca deveria
        # quebrar ao ser lido — mesma garantia que short_message/letter já
        # davam antes.
        user = make_user()
        draft = make_draft(user)
        response = auth_client(user).get(draft_detail_url(draft.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["context_answer"], "")

    def test_created_draft_round_trips_every_field_on_get(self):
        user = make_user()
        payload = {
            "experience_type": "birthday",
            "theme": "beach",
            "title": "Feliz Aniversário",
            "recipient_name": "Ana",
            "creator_name": "Bruno",
            "event_date": "2026-12-25",
            "letter": "Uma carta especial.",
            "short_message": "Com carinho",
            "context_answer": "Nos conhecemos há 5 anos.",
            "music_provider": "youtube",
            "music_url": "https://youtube.com/watch?v=abc123",
        }
        client = auth_client(user)
        create_response = client.post(DRAFT_LIST_URL, payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        draft_id = create_response.data["id"]

        get_response = client.get(draft_detail_url(draft_id))
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        for field, value in payload.items():
            self.assertEqual(get_response.data[field], value, f"campo {field} não bateu no round-trip")

    def test_patch_updates_multiple_non_theme_fields_simultaneously(self):
        user = make_user()
        draft = make_draft(user)
        response = auth_client(user).patch(
            draft_detail_url(draft.id),
            {
                "letter": "Nova carta",
                "short_message": "Nova mensagem",
                "context_answer": "Nova resposta de contexto",
                "recipient_name": "Carla",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertEqual(draft.letter, "Nova carta")
        self.assertEqual(draft.short_message, "Nova mensagem")
        self.assertEqual(draft.context_answer, "Nova resposta de contexto")
        self.assertEqual(draft.recipient_name, "Carla")

    def test_get_draft_of_another_user_returns_404(self):
        owner = make_user("owner-a@example.com")
        other = make_user("owner-b@example.com")
        draft = make_draft(owner)
        response = auth_client(other).get(draft_detail_url(draft.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_draft_of_another_user_returns_404_and_does_not_modify_it(self):
        owner = make_user("owner-c@example.com")
        other = make_user("owner-d@example.com")
        draft = make_draft(owner, title="Original")
        response = auth_client(other).patch(
            draft_detail_url(draft.id), {"title": "Hackeado"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        draft.refresh_from_db()
        self.assertEqual(draft.title, "Original")


class DraftCreateAndPatchLoggingTests(TestCase):
    """Etapa 7 — Fase C: eventos de criação/PATCH de draft logados sem PII
    (sem carta, mensagem, título ou qualquer conteúdo do usuário no log)."""

    def _assert_no_pii_leaked(self, log_output, *, forbidden_values):
        joined = "\n".join(log_output)
        for value in forbidden_values:
            self.assertNotIn(value, joined)

    def test_create_success_logs_event_without_pii(self):
        user = make_user()
        payload = {"title": "Segredo íntimo", "letter": "Conteúdo sensível da carta"}
        with self.assertLogs("apps.experiences.views", level="INFO") as captured:
            response = auth_client(user).post(DRAFT_LIST_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("draft.create.success", captured.output[0])
        self._assert_no_pii_leaked(captured.output, forbidden_values=[payload["title"], payload["letter"]])

    def test_create_failure_logs_event_without_pii(self):
        user = make_user()
        payload = {"theme": "tema-que-nao-existe", "letter": "Carta que não deveria vazar"}
        with self.assertLogs("apps.experiences.views", level="WARNING") as captured:
            response = auth_client(user).post(DRAFT_LIST_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("draft.create.failure", captured.output[0])
        self._assert_no_pii_leaked(captured.output, forbidden_values=[payload["letter"]])

    def test_patch_success_logs_event_without_pii(self):
        user = make_user()
        draft = make_draft(user)
        payload = {"letter": "Carta nova super privada"}
        with self.assertLogs("apps.experiences.views", level="INFO") as captured:
            response = auth_client(user).patch(draft_detail_url(draft.id), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("draft.patch.success", captured.output[0])
        self._assert_no_pii_leaked(captured.output, forbidden_values=[payload["letter"]])

    def test_patch_failure_logs_event_without_pii(self):
        user = make_user()
        draft = make_draft(user)
        payload = {"theme": "tema-invalido-xyz", "letter": "Outra carta privada"}
        with self.assertLogs("apps.experiences.views", level="WARNING") as captured:
            response = auth_client(user).patch(draft_detail_url(draft.id), payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("draft.patch.failure", captured.output[0])
        self._assert_no_pii_leaked(captured.output, forbidden_values=[payload["letter"]])
