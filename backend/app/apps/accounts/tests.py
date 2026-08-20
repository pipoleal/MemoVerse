from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"


class AuthThrottlingTests(TestCase):
    """
    Etapa 5 — Fase B: rate limiting nos endpoints de autenticação.

    A cache local (LocMemCache, padrão do Django em ausência de CACHES
    configurado) é limpa antes de cada teste para que a contagem de uma
    tentativa de throttle não vaze entre testes.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _register_payload(self, email="user@example.com"):
        return {
            "email": email,
            "first_name": "Ana",
            "last_name": "Silva",
            "password": "super-secret-123",
        }

    def test_register_normal_flow_still_works(self):
        response = self.client.post(
            REGISTER_URL, self._register_payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_throttles_after_too_many_attempts(self):
        # DEFAULT_THROTTLE_RATES["register"] = "10/hour"
        payload = self._register_payload()
        for _ in range(10):
            response = self.client.post(REGISTER_URL, payload, format="json")
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_login_normal_flow_still_works(self):
        User.objects.create_user(
            email="login-ok@example.com",
            first_name="Ana",
            last_name="Silva",
            password="super-secret-123",
        )

        response = self.client.post(
            LOGIN_URL,
            {"email": "login-ok@example.com", "password": "super-secret-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_throttles_after_too_many_attempts(self):
        # DEFAULT_THROTTLE_RATES["login"] = "10/min"
        payload = {"email": "nobody@example.com", "password": "wrong-password"}
        for _ in range(10):
            response = self.client.post(LOGIN_URL, payload, format="json")
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(LOGIN_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_refresh_normal_flow_still_works(self):
        User.objects.create_user(
            email="refresh-ok@example.com",
            first_name="Ana",
            last_name="Silva",
            password="super-secret-123",
        )
        login_response = self.client.post(
            LOGIN_URL,
            {"email": "refresh-ok@example.com", "password": "super-secret-123"},
            format="json",
        )
        refresh_token = login_response.data["refresh"]

        response = self.client.post(
            REFRESH_URL, {"refresh": refresh_token}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_throttles_after_too_many_attempts(self):
        # DEFAULT_THROTTLE_RATES["token_refresh"] = "30/min"
        payload = {"refresh": "not-a-real-token"}
        for _ in range(30):
            response = self.client.post(REFRESH_URL, payload, format="json")
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(REFRESH_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
