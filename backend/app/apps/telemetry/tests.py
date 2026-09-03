"""Instrumentação anônima do funil de conversão (POST /api/events/).

Cobre: criação válida, rejeição de nome de evento fora do enum, nunca
persiste um payload de metadata grande/aninhado demais, e a listagem do
painel admin (apps.ops) exige IsAuthenticated + IsProductionAdmin, igual às
outras listagens daquele app.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import FunnelEvent

User = get_user_model()

EVENTS_URL = "/api/events/"
ADMIN_FUNNEL_EVENTS_URL = "/api/ops/9b4/funnel-events/"


class FunnelEventCreateViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_creates_event_anonymously(self):
        response = self.client.post(
            EVENTS_URL,
            {"name": "preview_completed", "session_id": "abc123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FunnelEvent.objects.count(), 1)
        event = FunnelEvent.objects.get()
        self.assertEqual(event.name, "preview_completed")
        self.assertEqual(event.session_id, "abc123")

    def test_rejects_unknown_event_name(self):
        response = self.client.post(EVENTS_URL, {"name": "totally_made_up"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FunnelEvent.objects.count(), 0)

    def test_accepts_small_metadata(self):
        response = self.client.post(
            EVENTS_URL,
            {"name": "payment_started", "metadata": {"plan_code": "weekly"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FunnelEvent.objects.get().metadata, {"plan_code": "weekly"})

    def test_rejects_oversized_metadata_value(self):
        response = self.client.post(
            EVENTS_URL,
            {"name": "payment_started", "metadata": {"note": "x" * 500}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FunnelEvent.objects.count(), 0)

    def test_rejects_nested_metadata_value(self):
        response = self.client.post(
            EVENTS_URL,
            {"name": "payment_started", "metadata": {"nested": {"a": 1}}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FunnelEvent.objects.count(), 0)


class FunnelEventAdminListViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        FunnelEvent.objects.create(name="preview_completed", session_id="s1")
        FunnelEvent.objects.create(name="payment_approved", session_id="s2")

    def _auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_requires_authentication(self):
        response = self.client.get(ADMIN_FUNNEL_EVENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_requires_production_admin(self):
        regular_user = User.objects.create_user(email="regular@example.com", password="Str0ngPass!123")
        self._auth(regular_user)
        response = self.client.get(ADMIN_FUNNEL_EVENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_events(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="Str0ngPass!123", is_staff=True, is_superuser=True
        )
        self._auth(admin)
        response = self.client.get(ADMIN_FUNNEL_EVENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_admin_filters_by_name(self):
        admin = User.objects.create_user(
            email="admin2@example.com", password="Str0ngPass!123", is_staff=True, is_superuser=True
        )
        self._auth(admin)
        response = self.client.get(ADMIN_FUNNEL_EVENTS_URL, {"name": "payment_approved"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["session_id"], "s2")
