"""
Fail-closed SECRET_KEY resolution tests (Etapa 5 — Fase A).

`_resolve_secret_key` is tested directly with a fake `get_config` that
mirrors decouple's real contract (raise when the value is absent and no
default was passed, otherwise return the value/default) so these tests
never touch real environment variables or the local .env file.
"""

from decouple import UndefinedValueError
from django.test import SimpleTestCase

from config.settings import _resolve_secret_key

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
