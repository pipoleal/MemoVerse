from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.models import Payment, Plan

from .models import ExperienceDraft
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


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def publish_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/publish/"


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
