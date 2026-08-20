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


class AuthLoggingTests(TestCase):
    """
    Etapa 6 — Fase D: eventos de login/registro logados sem PII (sem
    e-mail, senha ou token no log) — a resposta da API não muda.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _assert_no_pii_leaked(self, log_output, *, forbidden_values):
        joined = "\n".join(log_output)
        for value in forbidden_values:
            self.assertNotIn(value, joined)

    def test_login_success_logs_event_without_pii(self):
        email = "logging-login-ok@example.com"
        password = "super-secret-123"
        User.objects.create_user(
            email=email, first_name="Ana", last_name="Silva", password=password
        )

        with self.assertLogs("apps.accounts.views.login", level="INFO") as captured:
            response = self.client.post(
                LOGIN_URL, {"email": email, "password": password}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auth.login.success", captured.output[0])
        self._assert_no_pii_leaked(
            captured.output,
            forbidden_values=[email, password, response.data["access"], response.data["refresh"]],
        )

    def test_login_failure_logs_event_without_pii(self):
        email = "logging-login-fail@example.com"

        with self.assertLogs("apps.accounts.views.login", level="WARNING") as captured:
            response = self.client.post(
                LOGIN_URL, {"email": email, "password": "wrong-password"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("auth.login.failure", captured.output[0])
        self._assert_no_pii_leaked(
            captured.output, forbidden_values=[email, "wrong-password"]
        )

    def test_register_success_logs_event_without_pii(self):
        email = "logging-register-ok@example.com"
        payload = {
            "email": email,
            "first_name": "Ana",
            "last_name": "Silva",
            "password": "super-secret-123",
        }

        with self.assertLogs("apps.accounts.views.register", level="INFO") as captured:
            response = self.client.post(REGISTER_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("auth.register.success", captured.output[0])
        self._assert_no_pii_leaked(
            captured.output, forbidden_values=[email, payload["password"]]
        )

    def test_register_failure_logs_event_without_pii(self):
        email = "logging-register-dup@example.com"
        User.objects.create_user(
            email=email, first_name="Ana", last_name="Silva", password="super-secret-123"
        )
        payload = {
            "email": email,
            "first_name": "Ana",
            "last_name": "Silva",
            "password": "another-secret-456",
        }

        with self.assertLogs("apps.accounts.views.register", level="WARNING") as captured:
            response = self.client.post(REGISTER_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("auth.register.failure", captured.output[0])
        self._assert_no_pii_leaked(
            captured.output, forbidden_values=[email, payload["password"]]
        )
