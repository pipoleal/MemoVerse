"""
Fail-closed SECRET_KEY resolution tests (Etapa 5 — Fase A) and LOGGING
configuration tests (Etapa 6 — Fase A).

`_resolve_secret_key` is tested directly with a fake `get_config` that
mirrors decouple's real contract (raise when the value is absent and no
default was passed, otherwise return the value/default) so these tests
never touch real environment variables or the local .env file.
"""

import logging
from unittest.mock import patch

from decouple import UndefinedValueError
from django.conf import settings
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from config.settings import _resolve_secret_key

HEALTH_CHECK_URL = "/api/health/"

_INSECURE_DEV_FALLBACK = "django-insecure-**f5&8s#wb(__j1n#cqpv^s2k-ft)o&b7ee37mbk98$ja&b+dp"


def _fake_config_unset(key, default=None):
    if default is None:
        raise UndefinedValueError(f"{key} not found")
    return default


def _fake_config_set(value):
    def get_config(key, default=None):
        return value

    return get_config


class ResolveSecretKeyTests(SimpleTestCase):
    def test_debug_true_falls_back_to_insecure_dev_default_when_unset(self):
        # Comportamento esperado em desenvolvimento: `manage.py runserver`
        # continua funcionando sem exigir SECRET_KEY no ambiente.
        result = _resolve_secret_key(True, get_config=_fake_config_unset)
        self.assertEqual(result, _INSECURE_DEV_FALLBACK)

    def test_debug_false_raises_when_unset(self):
        # Fail-closed em produção: ausência de SECRET_KEY impede o boot com
        # um erro explícito, em vez de reutilizar o fallback inseguro.
        with self.assertRaises(UndefinedValueError):
            _resolve_secret_key(False, get_config=_fake_config_unset)

    def test_debug_false_never_returns_the_insecure_dev_default(self):
        # Ausência de configuração insegura: mesmo se alguém tentasse, o
        # branch DEBUG=False nunca consulta o valor hardcoded de fallback.
        with self.assertRaises(UndefinedValueError):
            _resolve_secret_key(False, get_config=_fake_config_unset)

    def test_debug_false_uses_the_explicitly_configured_value(self):
        real_key = "a-real-secret-key-set-by-the-deployment"
        result = _resolve_secret_key(False, get_config=_fake_config_set(real_key))
        self.assertEqual(result, real_key)

    def test_debug_true_prefers_an_explicitly_configured_value_over_the_fallback(self):
        real_key = "a-real-secret-key-set-locally"
        result = _resolve_secret_key(True, get_config=_fake_config_set(real_key))
        self.assertEqual(result, real_key)


class LoggingConfigurationTests(SimpleTestCase):
    """Etapa 6 — Fase A: LOGGING precisa ter timestamp/nível/logger/mensagem,
    manter bibliotecas de terceiros silenciosas por padrão, e realmente
    entregar logs de apps.* e erros 5xx (django.request) ao handler console."""

    def test_formatter_includes_timestamp_level_logger_and_message(self):
        format_string = settings.LOGGING["formatters"]["standard"]["format"]
        self.assertIn("%(asctime)s", format_string)
        self.assertIn("%(levelname)s", format_string)
        self.assertIn("%(name)s", format_string)
        self.assertIn("%(message)s", format_string)

    def test_console_handler_uses_the_standard_formatter(self):
        handler = settings.LOGGING["handlers"]["console"]
        self.assertEqual(handler["class"], "logging.StreamHandler")
        self.assertEqual(handler["formatter"], "standard")

    def test_third_party_libraries_stay_quiet_by_default(self):
        # Nenhum logger de terceiros (boto3, botocore, urllib3, mercadopago)
        # tem entrada própria — todos herdam o nível WARNING da raiz.
        self.assertEqual(settings.LOGGING["root"]["level"], "WARNING")
        self.assertNotIn("boto3", settings.LOGGING["loggers"])
        self.assertNotIn("botocore", settings.LOGGING["loggers"])

    def test_django_request_logs_5xx_errors_with_a_handler(self):
        request_logger = settings.LOGGING["loggers"]["django.request"]
        self.assertEqual(request_logger["level"], "ERROR")
        self.assertIn("console", request_logger["handlers"])

    def test_app_loggers_actually_emit_at_info_level(self):
        # Prova funcional (não só a forma do dict): um logger nomeado como
        # os de apps/*.py (logging.getLogger(__name__)) realmente propaga
        # através da entrada "apps" configurada em LOGGING.
        logger = logging.getLogger("apps.some.module.for.testing")
        with self.assertLogs("apps.some.module.for.testing", level="INFO") as captured:
            logger.info("a-test-event")
        self.assertIn("a-test-event", captured.output[0])


class HealthCheckViewTests(TestCase):
    """Etapa 6 — Fase B: GET /api/health/ — público, barato, sem detalhe
    interno, refletindo de verdade a disponibilidade do banco."""

    def setUp(self):
        self.client = APIClient()

    def test_returns_200_and_ok_when_database_is_healthy(self):
        response = self.client.get(HEALTH_CHECK_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

    def test_returns_503_and_unavailable_when_database_is_down(self):
        with patch(
            "django.db.backends.utils.CursorWrapper.execute",
            side_effect=OperationalError("simulated connection failure"),
        ):
            response = self.client.get(HEALTH_CHECK_URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"status": "unavailable"})

    def test_does_not_require_authentication(self):
        # Nenhum header de autenticação enviado — já é o comportamento do
        # self.client "cru" acima, este teste só deixa a intenção explícita.
        anonymous_client = APIClient()
        response = anonymous_client.get(HEALTH_CHECK_URL)
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)

    def test_failure_response_reveals_no_internal_detail(self):
        with patch(
            "django.db.backends.utils.CursorWrapper.execute",
            side_effect=OperationalError("simulated connection failure"),
        ):
            response = self.client.get(HEALTH_CHECK_URL)
        # Resposta é só {"status": "unavailable"} — sem traceback, sem
        # mensagem de exceção, sem nome de host/porta do banco.
        self.assertEqual(set(response.data.keys()), {"status"})
        self.assertNotIn("simulated connection failure", str(response.data))
