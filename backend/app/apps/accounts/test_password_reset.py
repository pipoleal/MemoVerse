"""Recuperação de senha ("Esqueci minha senha") — código de 6 dígitos por
e-mail, hash no banco, expiração de 10 minutos, uso único, limite de
tentativas por código e rate limit por IP nos dois endpoints que aceitam um
código.

A cache local (LocMemCache) é limpa antes de cada teste, mesmo padrão já
usado em tests.py (AuthThrottlingTests) — sem isso a contagem de throttle
vazaria entre testes.
"""

from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import MAX_PASSWORD_RESET_ATTEMPTS, PasswordResetCode, User

REQUEST_URL = "/api/auth/password-reset/request/"
VERIFY_URL = "/api/auth/password-reset/verify/"
CONFIRM_URL = "/api/auth/password-reset/confirm/"
LOGIN_URL = "/api/auth/login/"

GENERIC_REQUEST_MESSAGE = (
    "Se existir uma conta associada a este e-mail, enviaremos um código de recuperação."
)
INVALID_CODE_MESSAGE = "Código inválido ou expirado."


def make_user(email="user@example.com", password="super-secret-123", **overrides):
    defaults = {"first_name": "Ana", "last_name": "Silva"}
    defaults.update(overrides)
    return User.objects.create_user(email=email, password=password, **defaults)


def latest_code_for(user):
    return PasswordResetCode.objects.filter(user=user).order_by("-created_at").first()


def extract_code_from_outbox(index=-1):
    body = mail.outbox[index].body
    # O e-mail (services.email_service) sempre traz "Código de recuperação: NNNNNN".
    for line in body.splitlines():
        if "Código de recuperação:" in line:
            return line.split(":")[-1].strip()
    raise AssertionError("Nenhum código encontrado no corpo do e-mail de teste.")


class PasswordResetRequestTests(TestCase):
    """Cenários 1-3: solicitação para e-mail existente/inexistente, resposta
    pública equivalente nos dois casos."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()

    def test_existing_email_sends_one_email_and_creates_a_code(self):
        user = make_user("existing@example.com")

        response = self.client.post(REQUEST_URL, {"email": user.email}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], GENERIC_REQUEST_MESSAGE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertEqual(PasswordResetCode.objects.filter(user=user).count(), 1)

    def test_nonexistent_email_sends_no_email_but_same_response(self):
        response = self.client.post(
            REQUEST_URL, {"email": "ghost@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], GENERIC_REQUEST_MESSAGE)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(PasswordResetCode.objects.exists())

    def test_existing_and_nonexistent_email_responses_are_identical(self):
        make_user("real@example.com")

        real_response = self.client.post(
            REQUEST_URL, {"email": "real@example.com"}, format="json"
        )
        ghost_response = self.client.post(
            REQUEST_URL, {"email": "ghost2@example.com"}, format="json"
        )

        self.assertEqual(real_response.status_code, ghost_response.status_code)
        self.assertEqual(real_response.data, ghost_response.data)

    def test_requesting_again_invalidates_the_previous_code(self):
        user = make_user("resend@example.com")
        self.client.post(REQUEST_URL, {"email": user.email}, format="json")
        first_code = extract_code_from_outbox()

        self.client.post(REQUEST_URL, {"email": user.email}, format="json")
        second_code = extract_code_from_outbox()

        self.assertEqual(PasswordResetCode.objects.filter(user=user).count(), 2)

        # O código antigo não deve mais servir para nada.
        verify_old = self.client.post(
            VERIFY_URL, {"email": user.email, "code": first_code}, format="json"
        )
        self.assertEqual(verify_old.status_code, status.HTTP_400_BAD_REQUEST)

        # O novo continua válido.
        verify_new = self.client.post(
            VERIFY_URL, {"email": user.email, "code": second_code}, format="json"
        )
        self.assertEqual(verify_new.status_code, status.HTTP_200_OK)

    def test_request_response_never_contains_the_code(self):
        user = make_user("noleak@example.com")

        response = self.client.post(REQUEST_URL, {"email": user.email}, format="json")

        real_code = extract_code_from_outbox()
        self.assertNotIn(real_code, str(response.data))
        self.assertNotIn(real_code, response.content.decode())

    def test_request_throttles_after_too_many_attempts(self):
        # DEFAULT_THROTTLE_RATES["password_reset_request"] = "5/hour"
        for _ in range(5):
            response = self.client.post(
                REQUEST_URL, {"email": "throttle@example.com"}, format="json"
            )
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(
            REQUEST_URL, {"email": "throttle@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class PasswordResetVerifyTests(TestCase):
    """Cenários 4-8: código correto/incorreto/expirado/reutilizado, e que
    verify NUNCA consome o código (só confirm consome)."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()
        self.user = make_user("verify@example.com")
        self.client.post(REQUEST_URL, {"email": self.user.email}, format="json")
        self.code = extract_code_from_outbox()

    def test_correct_code_is_valid(self):
        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verify_does_not_consume_the_code(self):
        first = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )
        second = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)

    def test_incorrect_code_is_rejected(self):
        wrong_code = "000000" if self.code != "000000" else "111111"

        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": wrong_code}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], INVALID_CODE_MESSAGE)

    def test_expired_code_is_rejected(self):
        reset_code = latest_code_for(self.user)
        reset_code.expires_at = timezone.now() - timedelta(seconds=1)
        reset_code.save(update_fields=["expires_at"])

        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_used_code_is_rejected(self):
        reset_code = latest_code_for(self.user)
        reset_code.used_at = timezone.now()
        reset_code.save(update_fields=["used_at"])

        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_format_code_is_rejected_without_hitting_the_database_logic(self):
        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": "abc"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_wrong_attempts_burns_the_code_even_for_the_right_one_later(self):
        wrong_code = "000000" if self.code != "000000" else "111111"

        for _ in range(MAX_PASSWORD_RESET_ATTEMPTS):
            self.client.post(
                VERIFY_URL, {"email": self.user.email, "code": wrong_code}, format="json"
            )

        # Mesmo com o código CERTO, o código já foi queimado pelo limite de
        # tentativas — precisa pedir um novo.
        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_response_never_contains_the_code(self):
        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": self.code}, format="json"
        )
        self.assertNotIn(self.code, response.content.decode())


class PasswordResetConfirmTests(TestCase):
    """Cenários 11-13, 16: senha nova salva, senha antiga para de funcionar,
    login com a senha nova funciona, ninguém troca a senha de outra conta."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()
        self.old_password = "super-secret-123"
        self.new_password = "brand-new-secret-456"
        self.user = make_user("confirm@example.com", password=self.old_password)
        self.client.post(REQUEST_URL, {"email": self.user.email}, format="json")
        self.code = extract_code_from_outbox()

    def _confirm(self, *, email=None, code=None, new_password=None):
        return self.client.post(
            CONFIRM_URL,
            {
                "email": email if email is not None else self.user.email,
                "code": code if code is not None else self.code,
                "new_password": new_password if new_password is not None else self.new_password,
            },
            format="json",
        )

    def test_confirm_with_correct_code_changes_the_password(self):
        response = self._confirm()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

    def test_old_password_stops_working_after_reset(self):
        self._confirm()

        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.old_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_new_password_works_at_login_after_reset(self):
        self._confirm()

        response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.new_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_confirm_does_not_return_tokens_no_automatic_login(self):
        response = self._confirm()
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_code_cannot_be_reused_after_a_successful_confirm(self):
        first = self._confirm()
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self._confirm(new_password="yet-another-secret-789")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

        # A senha da PRIMEIRA troca continua sendo a válida — a segunda
        # tentativa (código reaproveitado) nunca chegou a aplicar nada.
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

    def test_cannot_use_another_users_code_to_reset_own_email(self):
        other_user = make_user("victim@example.com", password="victim-secret-123")
        self.client.post(REQUEST_URL, {"email": other_user.email}, format="json")
        other_code = extract_code_from_outbox(index=-1)

        # Ataque: e-mail da vítima, mas com o código pego para OUTRA conta.
        response = self._confirm(email=other_user.email, code=self.code)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        other_user.refresh_from_db()
        self.assertTrue(other_user.check_password("victim-secret-123"))

        # Controle: o código certo da vítima, para a conta dela, continua
        # funcionando — prova que o teste acima falhou pelo motivo certo.
        control = self._confirm(
            email=other_user.email, code=other_code, new_password="new-victim-secret-000"
        )
        self.assertEqual(control.status_code, status.HTTP_200_OK)

    def test_weak_password_is_rejected_by_the_same_validators_as_register(self):
        response = self._confirm(new_password="1234567")  # menor que 8 e comum

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_confirm_invalidates_all_outstanding_refresh_tokens(self):
        login_response = self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": self.old_password},
            format="json",
        )
        old_refresh = login_response.data["refresh"]
        self.assertEqual(
            OutstandingToken.objects.filter(user=self.user).count(), 1
        )
        self.assertFalse(BlacklistedToken.objects.filter(token__user=self.user).exists())

        self._confirm()

        self.assertTrue(BlacklistedToken.objects.filter(token__user=self.user).exists())

        refresh_attempt = self.client.post(
            "/api/auth/refresh/", {"refresh": old_refresh}, format="json"
        )
        self.assertEqual(refresh_attempt.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_confirm_response_never_contains_the_code(self):
        response = self._confirm()
        self.assertNotIn(self.code, response.content.decode())

    def test_verify_throttles_after_too_many_attempts(self):
        # DEFAULT_THROTTLE_RATES["password_reset_verify"] = "10/hour"
        # (scope compartilhado por verify/ e confirm/, ver settings.py)
        for _ in range(10):
            response = self.client.post(
                VERIFY_URL, {"email": self.user.email, "code": "000000"}, format="json"
            )
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(
            VERIFY_URL, {"email": self.user.email, "code": "000000"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class PasswordResetLoggingTests(TestCase):
    """Cenário 15: nem e-mail nem código aparecem em nenhum log."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()

    def _assert_not_leaked(self, log_output, *values):
        joined = "\n".join(log_output)
        for value in values:
            self.assertNotIn(value, joined)

    def test_request_logs_event_without_email(self):
        user = make_user("logging-request@example.com")

        with self.assertLogs(
            "apps.accounts.services.password_reset_service", level="INFO"
        ) as captured:
            self.client.post(REQUEST_URL, {"email": user.email}, format="json")

        self.assertIn("auth.password_reset.request.sent", captured.output[0])
        self._assert_not_leaked(captured.output, user.email)

    def test_request_for_unknown_email_logs_event_without_email(self):
        with self.assertLogs(
            "apps.accounts.services.password_reset_service", level="INFO"
        ) as captured:
            self.client.post(
                REQUEST_URL, {"email": "unknown-log@example.com"}, format="json"
            )

        self.assertIn("auth.password_reset.request.unknown_email", captured.output[0])
        self._assert_not_leaked(captured.output, "unknown-log@example.com")

    def test_verify_and_confirm_never_log_the_code(self):
        user = make_user("logging-code@example.com")
        self.client.post(REQUEST_URL, {"email": user.email}, format="json")
        code = extract_code_from_outbox()

        with self.assertLogs(
            "apps.accounts.services.password_reset_service", level="INFO"
        ) as captured:
            self.client.post(
                VERIFY_URL, {"email": user.email, "code": code}, format="json"
            )
            self.client.post(
                CONFIRM_URL,
                {"email": user.email, "code": code, "new_password": "another-strong-pass-1"},
                format="json",
            )

        self._assert_not_leaked(captured.output, code, user.email)

    def test_email_body_is_the_only_place_the_code_appears(self):
        user = make_user("logging-outbox@example.com")

        with self.assertLogs(
            "apps.accounts.services.password_reset_service", level="INFO"
        ) as captured:
            self.client.post(REQUEST_URL, {"email": user.email}, format="json")

        code = extract_code_from_outbox()
        # O código está no e-mail (canal esperado)...
        self.assertIn(code, mail.outbox[0].body)
        # ...mas não vazou para o log do mesmo evento.
        self._assert_not_leaked(captured.output, code)


class PasswordResetFullFlowIntegrationTests(TestCase):
    """Cenário 17 (nível de API): request → verify → confirm → login,
    ponta a ponta, como o frontend realmente encadeia as chamadas."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()

    def test_full_reset_flow(self):
        user = make_user("fullflow@example.com", password="original-secret-123")

        request_response = self.client.post(
            REQUEST_URL, {"email": user.email}, format="json"
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)

        code = extract_code_from_outbox()

        verify_response = self.client.post(
            VERIFY_URL, {"email": user.email, "code": code}, format="json"
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        confirm_response = self.client.post(
            CONFIRM_URL,
            {"email": user.email, "code": code, "new_password": "brand-new-secret-999"},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        login_response = self.client.post(
            LOGIN_URL,
            {"email": user.email, "password": "brand-new-secret-999"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
