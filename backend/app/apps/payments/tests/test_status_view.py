from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan

User = get_user_model()


def make_user(email="user@example.com"):
    return User.objects.create_user(email=email, first_name="Test", last_name="User", password="strong-pass-123")


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, plan, attempt_number=1, status=Payment.Status.APPROVED, **overrides):
    defaults = {
        "draft": draft,
        "owner": draft.owner,
        "plan": plan,
        "attempt_number": attempt_number,
        "amount": plan.price,
        "currency": plan.currency,
        "status": status,
        "external_reference": f"memoverse:draft:{draft.id}:attempt:{attempt_number}",
        "idempotency_key": f"idem-{draft.id}-{attempt_number}",
        "mp_order_id": f"ORD-{draft.id}-{attempt_number}",
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def status_url(draft_id):
    return f"/api/payments/drafts/{draft_id}/status/"


class DraftPaymentStatusOwnershipTests(TestCase):
    def test_owner_can_read_their_own_draft_status(self):
        user = make_user()
        draft = make_draft(user)
        response = auth_client(user).get(status_url(draft.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_user_cannot_read_someone_elses_draft_status(self):
        owner = make_user("owner@example.com")
        stranger = make_user("stranger@example.com")
        draft = make_draft(owner)
        response = auth_client(stranger).get(status_url(draft.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_is_rejected(self):
        user = make_user()
        draft = make_draft(user)
        response = APIClient().get(status_url(draft.id))
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class DraftPaymentStatusContentTests(TestCase):
    def test_returns_confirmed_db_state_for_draft_without_payment(self):
        user = make_user()
        draft = make_draft(user)
        response = auth_client(user).get(status_url(draft.id))
        self.assertEqual(response.data["draft_status"], ExperienceDraft.Status.DRAFT)
        self.assertIsNone(response.data["payment"])

    def test_returns_confirmed_db_state_for_paid_draft(self):
        user = make_user()
        draft = make_draft(user, status=ExperienceDraft.Status.PAID)
        plan = Plan.objects.get(code="stellar")
        payment = make_payment(draft=draft, plan=plan, status=Payment.Status.APPROVED)

        response = auth_client(user).get(status_url(draft.id))

        self.assertEqual(response.data["draft_status"], ExperienceDraft.Status.PAID)
        self.assertEqual(response.data["payment"]["payment_id"], str(payment.id))
        self.assertEqual(response.data["payment"]["status"], Payment.Status.APPROVED)
        self.assertEqual(response.data["payment"]["plan"]["code"], "stellar")

    def test_returns_the_latest_attempt_when_multiple_exist(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        make_payment(draft=draft, plan=plan, attempt_number=1, status=Payment.Status.REJECTED)
        latest = make_payment(draft=draft, plan=plan, attempt_number=2, status=Payment.Status.APPROVED)

        response = auth_client(user).get(status_url(draft.id))

        self.assertEqual(response.data["payment"]["payment_id"], str(latest.id))
        self.assertEqual(response.data["payment"]["attempt_number"], 2)

    def test_status_endpoint_never_calls_mercadopago(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="essential")
        make_payment(draft=draft, plan=plan, status=Payment.Status.ACTION_REQUIRED)

        with patch("apps.payments.services.mercadopago_client.MercadoPagoClient") as mock_cls:
            auth_client(user).get(status_url(draft.id))

        mock_cls.assert_not_called()
