from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
LOGOUT_URL = "/api/auth/logout/"


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

    def test_logout_throttles_after_too_many_attempts(self):
        # DEFAULT_THROTTLE_RATES["logout"] = "30/min"
        payload = {"refresh": "not-a-real-token"}
        for _ in range(30):
            response = self.client.post(LOGOUT_URL, payload, format="json")
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(LOGOUT_URL, payload, format="json")
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

    def test_logout_success_logs_event_without_pii(self):
        email = "logging-logout-ok@example.com"
        password = "super-secret-123"
        User.objects.create_user(
            email=email, first_name="Ana", last_name="Silva", password=password
        )
        login_response = self.client.post(
            LOGIN_URL, {"email": email, "password": password}, format="json"
        )
        refresh_token = login_response.data["refresh"]

        with self.assertLogs("apps.accounts.views.logout", level="INFO") as captured:
            response = self.client.post(LOGOUT_URL, {"refresh": refresh_token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auth.logout.success", captured.output[0])
        self._assert_no_pii_leaked(
            captured.output, forbidden_values=[email, password, refresh_token]
        )

    def test_logout_failure_logs_event_without_pii(self):
        with self.assertLogs("apps.accounts.views.logout", level="WARNING") as captured:
            response = self.client.post(
                LOGOUT_URL, {"refresh": "not-a-real-token"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("auth.logout.failure", captured.output[0])
        self._assert_no_pii_leaked(captured.output, forbidden_values=["not-a-real-token"])


class RegisterEmailEnumerationTests(TestCase):
    """
    Etapa 8 — Fase C: a mensagem de e-mail duplicado não confirma mais a
    existência da conta no texto. Mitigação parcial e deliberada — ver
    comentário em RegisterSerializer.validate_email para o porquê o status
    HTTP em si ainda é um sinal residual, fora do escopo desta etapa.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_duplicate_email_message_does_not_confirm_account_exists(self):
        email = "already-registered@example.com"
        User.objects.create_user(
            email=email, first_name="Ana", last_name="Silva", password="super-secret-123"
        )

        response = self.client.post(
            REGISTER_URL,
            {"email": email, "first_name": "Bruno", "last_name": "Costa", "password": "another-secret-456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        message = response.data["email"][0]
        self.assertNotIn("cadastrado", message.lower())
        self.assertNotIn("existe", message.lower())

    def test_normal_registration_still_returns_201(self):
        response = self.client.post(
            REGISTER_URL,
            {"email": "brand-new@example.com", "first_name": "Ana", "last_name": "Silva", "password": "super-secret-123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class RegisterPasswordValidationTests(TestCase):
    """
    Etapa 8 — Fase D: AUTH_PASSWORD_VALIDATORS (já configurado em
    settings.py) agora é de fato executado no registro, via
    RegisterSerializer.validate().
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _payload(self, **overrides):
        payload = {
            "email": "password-validation@example.com",
            "first_name": "Ana",
            "last_name": "Silva",
            "password": "super-secret-123",
        }
        payload.update(overrides)
        return payload

    def test_common_password_is_rejected(self):
        response = self.client.post(
            REGISTER_URL, self._payload(password="password123"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_entirely_numeric_password_is_rejected(self):
        response = self.client.post(
            REGISTER_URL, self._payload(password="19283746"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_password_too_similar_to_email_is_rejected(self):
        response = self.client.post(
            REGISTER_URL,
            self._payload(email="carlossilva2026@example.com", password="carlossilva2026"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_a_reasonable_password_still_passes(self):
        response = self.client.post(
            REGISTER_URL, self._payload(password="super-secret-123"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LogoutTests(TestCase):
    """
    Etapa 8 — Fase B: logout revoga de verdade o refresh token (blacklist),
    e a rotação (Etapa 8 — Fase A, BLACKLIST_AFTER_ROTATION) impede que um
    refresh token pré-rotação continue utilizável.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _register_and_login(self, email="logout-user@example.com", password="super-secret-123"):
        User.objects.create_user(
            email=email, first_name="Ana", last_name="Silva", password=password
        )
        response = self.client.post(
            LOGIN_URL, {"email": email, "password": password}, format="json"
        )
        return response.data["access"], response.data["refresh"]

    def test_logout_returns_200_for_a_valid_refresh_token(self):
        _, refresh = self._register_and_login()
        response = self.client.post(LOGOUT_URL, {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_token_is_rejected_after_logout(self):
        _, refresh = self._register_and_login()

        self.client.post(LOGOUT_URL, {"refresh": refresh}, format="json")

        response = self.client.post(REFRESH_URL, {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_still_works_after_logout(self):
        # Comportamento documentado do SimpleJWT: logout blacklista só o
        # refresh token. O access token em uso continua válido até expirar
        # naturalmente — este teste prova exatamente isso, não é uma
        # limitação a corrigir.
        access, refresh = self._register_and_login()
        self.client.post(LOGOUT_URL, {"refresh": refresh}, format="json")

        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = authed_client.get("/api/experiences/drafts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_without_a_refresh_token_returns_400(self):
        response = self.client.post(LOGOUT_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_with_an_invalid_token_returns_401(self):
        response = self.client.post(
            LOGOUT_URL, {"refresh": "not-a-real-token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pre_rotation_refresh_token_is_rejected_after_rotation(self):
        # Etapa 8 — Fase A: BLACKLIST_AFTER_ROTATION=True fecha exatamente
        # este gap — sem ele, o token abaixo continuaria válido por até 7
        # dias mesmo após a rotação legítima.
        _, original_refresh = self._register_and_login()

        rotate_response = self.client.post(
            REFRESH_URL, {"refresh": original_refresh}, format="json"
        )
        self.assertEqual(rotate_response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", rotate_response.data)
        self.assertNotEqual(rotate_response.data["refresh"], original_refresh)

        reuse_response = self.client.post(
            REFRESH_URL, {"refresh": original_refresh}, format="json"
        )
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_new_refresh_token_from_rotation_still_works(self):
        # Regressão: a correção do gap acima não pode quebrar o uso normal
        # do token novo emitido pela própria rotação.
        _, original_refresh = self._register_and_login()

        rotate_response = self.client.post(
            REFRESH_URL, {"refresh": original_refresh}, format="json"
        )
        new_refresh = rotate_response.data["refresh"]

        second_rotation = self.client.post(
            REFRESH_URL, {"refresh": new_refresh}, format="json"
        )
        self.assertEqual(second_rotation.status_code, status.HTTP_200_OK)


ME_URL = "/api/auth/me/"


class MeViewTests(TestCase):
    """Etapa 9B.5: /api/auth/me/ é a única fonte de verdade para o
    frontend saber se o usuário logado é admin (is_superuser) — o token
    JWT em si nunca carrega isso (LoginSerializer/RefreshView são os
    padrões do SimpleJWT, sem custom claims)."""

    def setUp(self):
        self.client = APIClient()

    def _authed_client_for(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        token = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def test_anonymous_gets_401(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_sees_own_profile_with_is_superuser_false(self):
        user = User.objects.create_user(
            email="user@example.com", first_name="Ana", last_name="Silva", password="strong-pass-123"
        )
        response = self._authed_client_for(user).get(ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(user.id))
        self.assertEqual(response.data["email"], "user@example.com")
        self.assertEqual(response.data["first_name"], "Ana")
        self.assertEqual(response.data["last_name"], "Silva")
        self.assertIs(response.data["is_superuser"], False)

    def test_superuser_sees_is_superuser_true(self):
        admin = User.objects.create_user(
            email="admin@example.com", first_name="Admin", last_name="User",
            password="strong-pass-123", is_staff=True, is_superuser=True,
        )
        response = self._authed_client_for(admin).get(ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIs(response.data["is_superuser"], True)

    def test_staff_without_superuser_still_sees_is_superuser_false(self):
        # Mesmo perfil de conta técnica usado pelo sandbox-apro-runner —
        # is_staff=True sozinho nunca deve aparecer como admin aqui.
        staff = User.objects.create_user(
            email="staff@example.com", first_name="Staff", last_name="User",
            password="strong-pass-123", is_staff=True, is_superuser=False,
        )
        response = self._authed_client_for(staff).get(ME_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIs(response.data["is_superuser"], False)

    def test_never_reveals_another_users_data(self):
        User.objects.create_user(
            email="other@example.com", first_name="Other", last_name="Person", password="strong-pass-123"
        )
        me = User.objects.create_user(
            email="me@example.com", first_name="Me", last_name="Myself", password="strong-pass-123"
        )
        response = self._authed_client_for(me).get(ME_URL)

        self.assertEqual(response.data["email"], "me@example.com")
        self.assertNotEqual(response.data["email"], "other@example.com")
