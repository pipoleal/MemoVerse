import threading
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import OperationalError, connection
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan
from ..services.checkout_service import CheckoutService, DraftAlreadyPaid, _payer_email_for
from ..services.mercadopago_client import (
    MercadoPagoConfigurationError,
    MercadoPagoGatewayError,
    MercadoPagoOrderResult,
)

User = get_user_model()

SAMPLE_ORDER_RAW = {
    "id": "ORD01TEST",
    "status": "action_required",
    "status_detail": "waiting_transfer",
    "transactions": {
        "payments": [
            {
                "id": "PAY01TEST",
                "status": "action_required",
                "payment_method": {
                    "id": "pix",
                    "type": "bank_transfer",
                    "qr_code": "00020126...",
                    "qr_code_base64": "iVBORw0KGgo=",
                    "ticket_url": "https://www.mercadopago.com.br/sandbox/payments/ticket",
                },
            }
        ]
    },
}


def make_mp_result(**overrides):
    defaults = dict(
        order_id="ORD01TEST",
        status="action_required",
        status_detail="waiting_transfer",
        payment_id="PAY01TEST",
        raw=SAMPLE_ORDER_RAW,
    )
    defaults.update(overrides)
    return MercadoPagoOrderResult(**defaults)


def make_user(email="user@example.com"):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, plan, attempt_number, status=Payment.Status.PENDING, **overrides):
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
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def checkout_url(draft_id):
    return f"/api/payments/drafts/{draft_id}/checkout/"


def patch_mp_client(**create_order_kwargs):
    """Patches the MercadoPagoClient class used inside checkout_service so
    the view never touches the network. Returns the mock CLASS (its
    `.return_value` is the fake client instance)."""

    result = make_mp_result(**create_order_kwargs) if "raise_error" not in create_order_kwargs else None
    mock_cls = MagicMock()
    if create_order_kwargs.get("raise_error"):
        mock_cls.return_value.create_order.side_effect = MercadoPagoGatewayError("falha simulada")
    else:
        mock_cls.return_value.create_order.return_value = result or make_mp_result()
    return patch("apps.payments.services.checkout_service.MercadoPagoClient", mock_cls)


class CheckoutOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.other_user = make_user("other@example.com")
        self.draft = make_draft(self.owner)

    def test_owner_can_create_checkout_for_own_draft(self):
        with patch_mp_client():
            response = auth_client(self.owner).post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_create_checkout_for_other_users_draft(self):
        with patch_mp_client():
            response = auth_client(self.other_user).post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())


class CheckoutPlanResolutionTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_weekly_plan_creates_payment_of_1990(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("19.90"))

    def test_lifetime_galaxy_plan_creates_payment_of_3990(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "lifetime_galaxy"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.90"))

    def test_amount_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "lifetime_galaxy", "amount": "0.01"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.90"))

    def test_price_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "lifetime_galaxy", "price": "0.01"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.90"))

    def test_currency_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(checkout_url(self.draft.id), {"plan_code": "lifetime_galaxy", "currency": "USD"})
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.currency, "BRL")

    def test_draft_id_sent_in_body_is_ignored(self):
        other_draft = make_draft(self.user)
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id), {"plan_code": "weekly", "draft_id": str(other_draft.id)}
            )
        payment = Payment.objects.get(plan__code="weekly")
        self.assertEqual(payment.draft_id, self.draft.id)
        self.assertFalse(Payment.objects.filter(draft=other_draft).exists())

    def test_external_reference_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id),
                {"plan_code": "weekly", "external_reference": "hacked-ref"},
            )
        payment = Payment.objects.get(draft=self.draft)
        self.assertNotEqual(payment.external_reference, "hacked-ref")
        self.assertEqual(payment.external_reference, f"memoverse-draft-{self.draft.id}-attempt-1")

    def test_idempotency_key_sent_by_client_is_ignored(self):
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id),
                {"plan_code": "weekly", "idempotency_key": "hacked-key"},
            )
        payment = Payment.objects.get(draft=self.draft)
        self.assertNotEqual(payment.idempotency_key, "hacked-key")

    def test_status_sent_by_client_is_ignored(self):
        # A serializer nem declara um campo "status" — mas o teste documenta
        # a garantia explicitamente, em vez de depender só da ausência do
        # campo. O mock devolve "action_required" (Pix): se o valor enviado
        # pelo cliente tivesse qualquer efeito, o Payment sairia "approved".
        with patch_mp_client():
            self.client.post(
                checkout_url(self.draft.id),
                {"plan_code": "weekly", "status": "approved"},
            )
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.status, Payment.Status.ACTION_REQUIRED)

    def test_inactive_plan_cannot_be_purchased(self):
        Plan.objects.create(code="inactive-plan", name="Inativo", price=Decimal("9.99"), is_active=False)
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "inactive-plan"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())

    def test_nonexistent_plan_returns_error(self):
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "does-not-exist"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())


class CheckoutRealPriceRegardlessOfEmailTests(TestCase):
    """Etapa 5 — Fase C: o bypass temporário de R$1,00
    (CheckoutService._TEMP_R1_TEST_OWNER_EMAIL) foi removido. Estes testes
    substituem TempR1TestOverrideTests e blindam que nenhum e-mail — nem
    mesmo o que antes recebia o valor especial — altera o preço cobrado."""

    FORMER_OVERRIDE_EMAIL = "felipeleal12345678910@gmail.com"

    def test_former_override_email_now_pays_the_real_plan_price(self):
        user = make_user(self.FORMER_OVERRIDE_EMAIL)
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime_galaxy"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.amount, Decimal("39.90"))

    def test_any_other_account_pays_the_real_plan_price(self):
        other_user = make_user("nao-e-a-conta-de-teste@example.com")
        draft = make_draft(other_user)
        with patch_mp_client():
            auth_client(other_user).post(checkout_url(draft.id), {"plan_code": "lifetime_galaxy"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.amount, Decimal("39.90"))

    def test_client_cannot_spoof_a_special_price_via_request_body(self):
        # draft.owner.email vem sempre do usuário autenticado dono do draft
        # (nunca de um campo do body) — CheckoutRequestSerializer nem
        # declara nada parecido com "email"/"owner_email", então o DRF
        # descarta silenciosamente qualquer tentativa.
        real_user = make_user("outro-usuario@example.com")
        draft = make_draft(real_user)
        with patch_mp_client():
            auth_client(real_user).post(
                checkout_url(draft.id),
                {
                    "plan_code": "lifetime",
                    "email": self.FORMER_OVERRIDE_EMAIL,
                    "owner_email": self.FORMER_OVERRIDE_EMAIL,
                },
            )
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.amount, Decimal("29.90"))


class CheckoutResponsePlanDetailsTests(TestCase):
    """O response de POST /checkout/ passou a incluir price/currency/features
    do plano — para a tela "RESUMO DO PEDIDO" do frontend não precisar
    hardcodar nem recalcular nada. price/currency vêm sempre de
    Payment.amount/currency (congelados), nunca de Plan.price."""

    def test_response_includes_price_currency_and_features_for_weekly(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        # DecimalField serializa como string por padrão no DRF — o contrato
        # da API é "19.90", não 19.90.
        self.assertEqual(response.data["plan"]["price"], "19.90")
        self.assertEqual(response.data["plan"]["currency"], "BRL")
        features = response.data["plan"]["features"]
        self.assertEqual(features["duration_days"], 7)
        self.assertIs(features["is_lifetime"], False)
        self.assertIs(features["galaxy_live_enabled"], False)
        self.assertEqual(
            features["highlights"],
            [
                "Experiência personalizada",
                "Fotos e vídeos",
                "Carta personalizada",
                "Música",
                "Link compartilhável",
                "Disponível por 7 dias",
            ],
        )

    def test_response_includes_galaxy_live_enabled_true_for_lifetime_galaxy(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime_galaxy"})
        self.assertEqual(response.data["plan"]["price"], "39.90")
        self.assertIs(response.data["plan"]["features"]["galaxy_live_enabled"], True)

    def test_response_price_is_unaffected_by_a_later_plan_price_change(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime"})
        self.assertEqual(response.data["plan"]["price"], "29.90")

        plan = Plan.objects.get(code="lifetime")
        plan.price = Decimal("999.00")
        plan.save(update_fields=["price"])

        # Retomar o mesmo checkout (mp_order_id já setado -> short-circuit em
        # start_checkout) tem que continuar reportando o valor congelado.
        with patch_mp_client():
            second_response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime"})
        self.assertEqual(second_response.data["plan"]["price"], "29.90")


class CheckoutPaymentLinkageTests(TestCase):
    def test_payment_linked_to_correct_draft_and_owner(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get()
        self.assertEqual(payment.draft_id, draft.id)
        self.assertEqual(payment.owner_id, user.id)

    def test_payment_amount_is_frozen_after_plan_price_changes(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime_galaxy"})
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, Decimal("39.90"))

        plan = Plan.objects.get(code="lifetime_galaxy")
        plan.price = Decimal("99.99")
        plan.save(update_fields=["price"])

        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("39.90"))


class CheckoutAttemptNumberTests(TestCase):
    def test_first_attempt_gets_number_1(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.attempt_number, 1)

    def test_second_attempt_after_terminal_failure_gets_number_2(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")
        make_payment(draft=draft, plan=plan, attempt_number=1, status=Payment.Status.REJECTED)

        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})

        self.assertTrue(Payment.objects.filter(draft=draft, attempt_number=2).exists())
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 2)


class CheckoutActivePaymentReuseTests(TestCase):
    def test_existing_active_payment_is_reused(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")
        existing = make_payment(
            draft=draft, plan=plan, attempt_number=1, status=Payment.Status.PENDING, mp_order_id="ORD-EXISTING"
        )

        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_id"], str(existing.id))
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)

    def test_no_two_active_payments_for_same_draft_on_repeated_calls(self):
        user = make_user()
        draft = make_draft(user)
        client = auth_client(user)

        with patch_mp_client():
            client.post(checkout_url(draft.id), {"plan_code": "weekly"})
            client.post(checkout_url(draft.id), {"plan_code": "weekly"})
            client.post(checkout_url(draft.id), {"plan_code": "weekly"})

        self.assertEqual(
            Payment.objects.filter(draft=draft, status__in=Payment.ACTIVE_STATUSES).count(), 1
        )
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)

    def test_active_payment_for_different_plan_returns_conflict_and_does_not_alter_it(self):
        user = make_user()
        draft = make_draft(user)
        weekly = Plan.objects.get(code="weekly")
        existing = make_payment(draft=draft, plan=weekly, attempt_number=1, status=Payment.Status.PENDING)

        with patch_mp_client():
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime_galaxy"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        existing.refresh_from_db()
        self.assertEqual(existing.plan.code, "weekly")
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)


class CheckoutConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    # TransactionTestCase faz um flush completo do banco no teardown, o que
    # apaga os Plans semeados pela migration 0002 (dado de migração, não de
    # schema). serialized_rollback restaura esse estado entre testes — sem
    # isso, uma segunda classe TransactionTestCase na mesma suíte (ex.:
    # WebhookConcurrencyTests) encontraria a tabela de Plans vazia.
    serialized_rollback = True

    def test_concurrency_does_not_create_two_active_attempts(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")

        barrier = threading.Barrier(2)
        errors = []

        def worker():
            # Each thread gets its own lazily-opened Django DB connection;
            # against SQLite (this test's original assumption, see comment
            # below) a leaked one is harmless, but against real Postgres
            # (this repo's Docker dev environment) it stays open as a real
            # backend session after the thread exits, blocking the test DB's
            # teardown DROP DATABASE at the end of the full suite. Always
            # close it on the way out, success or failure.
            try:
                fake_client = MagicMock()
                fake_client.create_order.return_value = make_mp_result()
                barrier.wait(timeout=5)
                # SQLite (usado nos testes) não enfileira escritores como o Postgres
                # de produção faz sob select_for_update: sob contenção real ele pode
                # recusar a escrita na hora (OperationalError) em vez de esperar a
                # outra transação. Um cliente real trataria isso como "tente
                # novamente" — simulamos esse retry aqui. O que o teste garante é o
                # resultado final (nunca duas tentativas ativas), não a ausência de
                # contenção no SGBD de teste.
                for attempt in range(5):
                    try:
                        CheckoutService.start_checkout(draft=draft, plan=plan, mp_client=fake_client)
                        return
                    except OperationalError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05 * (attempt + 1))
                    except Exception as exc:  # noqa: BLE001 - surfaced via `errors` for assertions below
                        errors.append(exc)
                        return
            finally:
                connection.close()

        def run_worker():
            try:
                worker()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=run_worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        active_payments = Payment.objects.filter(draft=draft, status__in=Payment.ACTIVE_STATUSES)
        self.assertEqual(active_payments.count(), 1)
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)


class CheckoutReferenceGenerationTests(TestCase):
    def test_external_reference_is_generated_by_backend_with_expected_format(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.external_reference, f"memoverse-draft-{draft.id}-attempt-1")

    def test_external_reference_fits_mercadopago_pattern_and_length(self):
        # A Orders API rejeita external_reference com HTTP 400 se ele tiver
        # caracteres fora de [A-Za-z0-9_-] ou mais de 64 caracteres (causa
        # raiz confirmada via chamada real à API: "does not match pattern").
        import re

        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")

        payment = CheckoutService._create_attempt(draft=draft, plan=plan)

        self.assertLessEqual(len(payment.external_reference), 64)
        self.assertRegex(payment.external_reference, r"^[A-Za-z0-9_-]+$")

        # Estável entre retries da MESMA tentativa (mesma garantia do
        # idempotency_key): nunca regenerado, só lido do banco.
        payment.refresh_from_db()
        self.assertEqual(payment.external_reference, f"memoverse-draft-{draft.id}-attempt-1")

    def test_idempotency_key_is_generated_by_backend_and_is_stable(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")

        payment_a = CheckoutService._create_attempt(draft=draft, plan=plan)
        self.assertTrue(payment_a.idempotency_key)

        # Simula um retry da MESMA tentativa: a idempotency_key não pode mudar.
        payment_a.refresh_from_db()
        self.assertEqual(payment_a.idempotency_key, f"mv:{draft.id}:1")

    def test_idempotency_key_fits_mercadopago_sdk_header_limit(self):
        # O SDK da Mercado Pago rejeita x-idempotency-key acima de 64
        # caracteres. draft.id é um UUID real (36 chars) — o pior caso
        # plausível — e a chave gerada precisa caber com folga.
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")

        payment = CheckoutService._create_attempt(draft=draft, plan=plan)

        self.assertLessEqual(len(payment.idempotency_key), 64)


class PayerEmailForSandboxTests(TestCase):
    """Unidade isolada de _payer_email_for, sem passar pelo checkout inteiro."""

    def test_sandbox_rewrites_domain_to_testuser_com(self):
        self.assertEqual(
            _payer_email_for(email="real.user@example.com", environment="sandbox"),
            "real.user@testuser.com",
        )

    def test_sandbox_preserves_local_part_exactly(self):
        self.assertEqual(
            _payer_email_for(email="first.last+tag@anydomain.com.br", environment="sandbox"),
            "first.last+tag@testuser.com",
        )

    def test_production_keeps_email_unchanged(self):
        self.assertEqual(
            _payer_email_for(email="real.user@example.com", environment="production"),
            "real.user@example.com",
        )

    def test_unknown_environment_value_keeps_email_unchanged(self):
        # Só "sandbox" ativa a reescrita; qualquer outro valor de MP_ENV
        # (incluindo configuração inválida/ausente) preserva o e-mail real
        # em vez de arriscar mascarar produção por engano.
        self.assertEqual(
            _payer_email_for(email="real.user@example.com", environment="staging"),
            "real.user@example.com",
        )


class CheckoutMercadoPagoClientCallTests(TestCase):
    def test_mp_client_receives_amount_external_reference_and_idempotency_key(self):
        user = make_user()
        draft = make_draft(user)

        with patch_mp_client() as mock_cls:
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "lifetime_galaxy"})

        payment = Payment.objects.get(draft=draft)
        mock_cls.return_value.create_order.assert_called_once()
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["amount"], Decimal("39.90"))
        self.assertEqual(call_kwargs["external_reference"], payment.external_reference)
        self.assertEqual(call_kwargs["idempotency_key"], payment.idempotency_key)
        self.assertEqual(call_kwargs["payer"], {"email": user.email})

    def test_payer_email_uses_testuser_domain_in_sandbox(self):
        # Confirmado via chamada real à Orders API: em Sandbox, payer.email
        # que não termina em "@testuser.com" é rejeitado com HTTP 400
        # "invalid_email_for_sandbox".
        user = make_user(email="real.user+tag@example.com")
        draft = make_draft(user)

        with patch_mp_client() as mock_cls:
            mock_cls.return_value.environment = "sandbox"
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})

        payment = Payment.objects.get(draft=draft)
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"], {"email": "real.user+tag@testuser.com"})

        # Nada além do payer muda: mesmo amount/external_reference/idempotency_key
        # que já eram enviados antes desta correção.
        self.assertEqual(call_kwargs["amount"], payment.amount)
        self.assertEqual(call_kwargs["external_reference"], payment.external_reference)
        self.assertEqual(call_kwargs["idempotency_key"], payment.idempotency_key)
        self.assertEqual(
            call_kwargs["payments"],
            [{"amount": f"{payment.amount:.2f}", "payment_method": {"id": "pix", "type": "bank_transfer"}}],
        )

    def test_payer_email_stays_real_in_production(self):
        user = make_user(email="real.user@example.com")
        draft = make_draft(user)

        with patch_mp_client() as mock_cls:
            mock_cls.return_value.environment = "production"
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})

        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"], {"email": "real.user@example.com"})


class SandboxApprovalOptInTests(TestCase):
    """payer_first_name é opt-in explícito de CheckoutService.start_checkout,
    nunca acionado pela view HTTP (DraftCheckoutView nunca passa esse
    argumento) — existe só para disparar sob demanda o mecanismo oficial
    "APRO" de auto-aprovação do Sandbox da Mercado Pago."""

    def test_sandbox_with_explicit_override_sends_apro_first_name(self):
        user = make_user(email="real.user@example.com")
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")
        fake_client = MagicMock()
        fake_client.environment = "sandbox"
        fake_client.create_order.return_value = make_mp_result()

        CheckoutService.start_checkout(draft=draft, plan=plan, mp_client=fake_client, payer_first_name="APRO")

        payment = Payment.objects.get(draft=draft)
        call_kwargs = fake_client.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"], {"email": "real.user@testuser.com", "first_name": "APRO"})

        # Nada além do payer muda com o override presente.
        self.assertEqual(call_kwargs["external_reference"], payment.external_reference)
        self.assertEqual(call_kwargs["idempotency_key"], payment.idempotency_key)
        self.assertEqual(
            call_kwargs["payments"],
            [{"amount": f"{payment.amount:.2f}", "payment_method": {"id": "pix", "type": "bank_transfer"}}],
        )

    def test_production_never_sends_apro_even_if_override_is_passed(self):
        user = make_user(email="real.user@example.com")
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")
        fake_client = MagicMock()
        fake_client.environment = "production"
        fake_client.create_order.return_value = make_mp_result()

        CheckoutService.start_checkout(draft=draft, plan=plan, mp_client=fake_client, payer_first_name="APRO")

        call_kwargs = fake_client.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"], {"email": "real.user@example.com"})
        self.assertNotIn("first_name", call_kwargs["payer"])

    def test_sandbox_without_override_never_sends_first_name(self):
        # Confirma que o checkout Sandbox comum (sem o opt-in) continua
        # exatamente como antes desta mudança.
        user = make_user(email="real.user@example.com")
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")
        fake_client = MagicMock()
        fake_client.environment = "sandbox"
        fake_client.create_order.return_value = make_mp_result()

        CheckoutService.start_checkout(draft=draft, plan=plan, mp_client=fake_client)

        call_kwargs = fake_client.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payer"], {"email": "real.user@testuser.com"})
        self.assertNotIn("first_name", call_kwargs["payer"])


class CheckoutOrderPersistenceTests(TestCase):
    def test_mp_order_id_is_saved(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client(order_id="ORD-XYZ"):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.mp_order_id, "ORD-XYZ")

    def test_mp_payment_id_is_saved_when_available(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client(payment_id="PAY-XYZ"):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.mp_payment_id, "PAY-XYZ")

    def test_mp_payment_id_is_null_when_not_yet_available(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client(payment_id=None, status="processing"):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        payment = Payment.objects.get(draft=draft)
        self.assertIsNone(payment.mp_payment_id)


class CheckoutDraftStatusTests(TestCase):
    def test_draft_becomes_awaiting_payment_after_successful_checkout(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        draft.refresh_from_db()
        self.assertEqual(draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)

    def test_draft_does_not_become_paid_after_successful_checkout(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PAID)

    def test_draft_does_not_become_published_after_successful_checkout(self):
        user = make_user()
        draft = make_draft(user)
        with patch_mp_client():
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PUBLISHED)


SAMPLE_CARD_ORDER_RAW = {
    "id": "ORD01CARD",
    "status": "processed",
    "status_detail": "accredited",
    "transactions": {
        "payments": [
            {
                "id": "PAY01CARD",
                "status": "processed",
                "status_detail": "accredited",
                "payment_method": {"id": "master", "type": "credit_card"},
            }
        ]
    },
}


def make_card_mp_result(**overrides):
    defaults = dict(
        order_id="ORD01CARD",
        status="processed",
        status_detail="accredited",
        payment_id="PAY01CARD",
        raw=SAMPLE_CARD_ORDER_RAW,
    )
    defaults.update(overrides)
    return MercadoPagoOrderResult(**defaults)


def patch_mp_client_for_card(**create_order_kwargs):
    """Same as patch_mp_client, but the fake create_order returns a card-style
    Order response (payment_method.type=credit_card) instead of Pix."""

    mock_cls = MagicMock()
    mock_cls.return_value.create_order.return_value = make_card_mp_result(**create_order_kwargs)
    return patch("apps.payments.services.checkout_service.MercadoPagoClient", mock_cls)


def card_payload(**overrides):
    payload = {
        "plan_code": "weekly",
        "payment_method": "card",
        "token": "card-token-123",
        "payment_method_id": "master",
        "installments": 1,
    }
    payload.update(overrides)
    return payload


class CheckoutCardValidationTests(TestCase):
    """Itens B, C, D, G do checklist: validação de entrada do cartão."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_pix_still_works_without_payment_method_field(self):
        # Item A: nenhum campo novo é obrigatório para o fluxo Pix existente.
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.last_sync_payload["transactions"]["payments"][0]["payment_method"]["id"], "pix")

    def test_card_without_token_returns_400(self):
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), card_payload(token=""))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())

    def test_card_missing_token_field_entirely_returns_400(self):
        payload = card_payload()
        del payload["token"]
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", response.data)

    def test_card_without_payment_method_id_returns_400(self):
        payload = card_payload()
        del payload["payment_method_id"]
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_method_id", response.data)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())

    def test_card_without_installments_returns_400(self):
        payload = card_payload()
        del payload["installments"]
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("installments", response.data)

    def test_card_with_zero_installments_returns_400(self):
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), card_payload(installments=0))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("installments", response.data)

    def test_card_with_negative_installments_returns_400(self):
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), card_payload(installments=-1))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_card_with_non_integer_installments_returns_400(self):
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), card_payload(installments="not-a-number"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CheckoutCardPayloadTests(TestCase):
    """Item E: o payload enviado à Orders API para cartão é montado
    exatamente como confirmado na documentação oficial (id/type/token/
    installments) — e item G: issuer_id nunca é encaminhado, mesmo se o
    frontend enviar."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_card_payload_sent_to_mercadopago_matches_documented_shape(self):
        with patch_mp_client_for_card() as mock_cls:
            self.client.post(
                checkout_url(self.draft.id),
                card_payload(payment_method_id="visa", installments=3),
            )
        payment = Payment.objects.get(draft=self.draft)
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(
            call_kwargs["payments"],
            [
                {
                    "amount": f"{payment.amount:.2f}",
                    "payment_method": {
                        "id": "visa",
                        "type": "credit_card",
                        "token": "card-token-123",
                        "installments": 3,
                    },
                }
            ],
        )

    def test_issuer_id_sent_by_client_never_reaches_orders_api(self):
        with patch_mp_client_for_card() as mock_cls:
            self.client.post(checkout_url(self.draft.id), card_payload(issuer_id="24"))
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        payment_method = call_kwargs["payments"][0]["payment_method"]
        self.assertNotIn("issuer_id", payment_method)

    def test_transaction_amount_sent_by_client_is_ignored_price_comes_from_plan(self):
        # Item F: mesmo que o frontend mande transaction_amount (só para o
        # Brick), o backend continua sendo a única autoridade sobre o preço —
        # esse campo nem é declarado no serializer, então é descartado.
        with patch_mp_client_for_card() as mock_cls:
            self.client.post(
                checkout_url(self.draft.id),
                card_payload(plan_code="lifetime_galaxy", transaction_amount="0.01"),
            )
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.amount, Decimal("39.90"))
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["payments"][0]["amount"], "39.90")

    def test_card_number_or_cvv_like_fields_are_never_accepted(self):
        # O serializer não declara esses campos — mesmo se enviados, o DRF
        # os descarta silenciosamente, e nada no fluxo os lê.
        with patch_mp_client_for_card() as mock_cls:
            self.client.post(
                checkout_url(self.draft.id),
                card_payload(card_number="4509953566233704", cvv="123", expiration_date="11/30"),
            )
        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        payment_method = call_kwargs["payments"][0]["payment_method"]
        self.assertEqual(set(payment_method.keys()), {"id", "type", "token", "installments"})


class CheckoutCardConfirmationFlowTests(TestCase):
    """Itens H e I: o resultado do cartão passa pelo mesmo mapeamento de
    status e pelas mesmas regras de draft.status que o Pix já usa — nenhuma
    lógica nova específica de cartão nessas camadas."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_approved_card_payment_updates_payment_status_via_existing_mapping(self):
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), card_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.mp_order_id, "ORD01CARD")
        self.assertEqual(payment.mp_payment_id, "PAY01CARD")
        # Confirmação síncrona: Draft já sai PAID desta mesma requisição,
        # sem esperar o webhook (nenhum webhook foi chamado neste teste).
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PAID)

    def test_rejected_card_payment_does_not_mark_draft_paid_or_published(self):
        with patch_mp_client_for_card(status="failed", status_detail="cc_rejected_other_reason"):
            response = self.client.post(checkout_url(self.draft.id), card_payload())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment = Payment.objects.get(draft=self.draft)
        self.assertEqual(payment.status, Payment.Status.REJECTED)
        self.draft.refresh_from_db()
        self.assertNotEqual(self.draft.status, ExperienceDraft.Status.PAID)
        self.assertNotEqual(self.draft.status, ExperienceDraft.Status.PUBLISHED)

    def test_card_gateway_failure_returns_502_and_does_not_create_order(self):
        with patch_mp_client(raise_error=True):
            response = self.client.post(checkout_url(self.draft.id), card_payload())
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        payment = Payment.objects.get(draft=self.draft)
        self.assertIsNone(payment.mp_order_id)


class CheckoutMissingConfigurationTests(TestCase):
    """MP_ACCESS_TOKEN ausente/inválido é uma falha de configuração do
    servidor (MercadoPagoClient() levanta MercadoPagoConfigurationError no
    __init__, antes de qualquer chamada de rede) — deve virar 502, o mesmo
    tratamento de uma falha de gateway, nunca um 500 cru vazando detalhe
    interno de configuração para o cliente."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_missing_access_token_returns_502_instead_of_500(self):
        with patch(
            "apps.payments.services.checkout_service.MercadoPagoClient",
            side_effect=MercadoPagoConfigurationError("MP_ACCESS_TOKEN não configurado."),
        ):
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        payment = Payment.objects.get(draft=self.draft)
        self.assertIsNone(payment.mp_order_id)


def publish_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/publish/"


class CheckoutToPublishIntegrationTests(TestCase):
    """Reproduz de ponta a ponta o cenário real encontrado no teste E2E via
    Docker: checkout com cartão aprovado -> Draft PAID -> POST /publish/
    funciona imediatamente, sem qualquer webhook envolvido neste teste."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_card_approval_allows_immediate_publish_without_webhook(self):
        with patch_mp_client_for_card():
            checkout_response = self.client.post(checkout_url(self.draft.id), card_payload())
        self.assertEqual(checkout_response.status_code, status.HTTP_200_OK)

        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PAID)

        publish_response = self.client.post(publish_url(self.draft.id), {})

        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        self.assertTrue(publish_response.data["slug"])
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ExperienceDraft.Status.PUBLISHED)

    def test_rejected_card_payment_still_blocks_publish(self):
        with patch_mp_client_for_card(status="failed", status_detail="cc_rejected_other_reason"):
            checkout_response = self.client.post(checkout_url(self.draft.id), card_payload())
        self.assertEqual(checkout_response.status_code, status.HTTP_200_OK)

        self.draft.refresh_from_db()
        self.assertNotEqual(self.draft.status, ExperienceDraft.Status.PAID)

        publish_response = self.client.post(publish_url(self.draft.id), {})

        self.assertEqual(publish_response.status_code, status.HTTP_409_CONFLICT)
        self.draft.refresh_from_db()
        self.assertIsNone(self.draft.slug)

    def test_pix_checkout_still_requires_webhook_before_publish(self):
        # Pix não aprova sincronamente (action_required) — o comportamento
        # anterior à correção permanece para este método de pagamento.
        with patch_mp_client():
            checkout_response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(checkout_response.status_code, status.HTTP_200_OK)

        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, ExperienceDraft.Status.AWAITING_PAYMENT)

        publish_response = self.client.post(publish_url(self.draft.id), {})
        self.assertEqual(publish_response.status_code, status.HTTP_409_CONFLICT)


class CheckoutResponsePaymentMethodTypeTests(TestCase):
    """A view expõe payment_method_type (derivado do last_sync_payload já
    existente) para o frontend distinguir Pix de cartão ao retomar um
    checkout — sem precisar de nenhuma coluna nova em Payment."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.client = auth_client(self.user)

    def test_pix_response_reports_bank_transfer_type(self):
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.data["checkout"]["payment_method_type"], "bank_transfer")

    def test_card_response_reports_credit_card_type(self):
        with patch_mp_client_for_card():
            response = self.client.post(checkout_url(self.draft.id), card_payload())
        self.assertEqual(response.data["checkout"]["payment_method_type"], "credit_card")


class CheckoutFailureHandlingTests(TestCase):
    def test_mp_failure_returns_gateway_error_and_does_not_publish_or_mark_draft_paid(self):
        user = make_user()
        draft = make_draft(user)

        with patch_mp_client(raise_error=True):
            response = auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        draft.refresh_from_db()
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PAID)
        self.assertNotEqual(draft.status, ExperienceDraft.Status.PUBLISHED)
        self.assertEqual(draft.status, ExperienceDraft.Status.DRAFT)

    def test_mp_failure_leaves_payment_pending_without_order_id(self):
        user = make_user()
        draft = make_draft(user)

        with patch_mp_client(raise_error=True):
            auth_client(user).post(checkout_url(draft.id), {"plan_code": "weekly"})

        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertIsNone(payment.mp_order_id)

    def test_retry_after_transient_failure_does_not_duplicate_the_payment_and_reuses_the_idempotency_key(self):
        user = make_user()
        draft = make_draft(user)
        client = auth_client(user)

        with patch_mp_client(raise_error=True):
            first_response = client.post(checkout_url(draft.id), {"plan_code": "weekly"})
        self.assertEqual(first_response.status_code, status.HTTP_502_BAD_GATEWAY)

        failed_payment = Payment.objects.get(draft=draft)

        with patch_mp_client() as mock_cls:
            second_response = client.post(checkout_url(draft.id), {"plan_code": "weekly"})

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(draft=draft).count(), 1)

        payment = Payment.objects.get(draft=draft)
        self.assertEqual(payment.id, failed_payment.id)
        self.assertEqual(payment.attempt_number, 1)
        self.assertEqual(payment.mp_order_id, "ORD01TEST")

        call_kwargs = mock_cls.return_value.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["idempotency_key"], failed_payment.idempotency_key)
        self.assertEqual(call_kwargs["external_reference"], failed_payment.external_reference)


class CheckoutAlreadyPaidTests(TestCase):
    """Um draft já pago (ou publicado) nunca pode iniciar um novo checkout,
    mesmo que o Payment aprovado seja um estado terminal e por isso não
    colida com uniq_active_payment_per_draft. Ver DraftAlreadyPaid em
    checkout_service.py."""

    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="weekly")
        self.client = auth_client(self.user)

    def test_new_draft_allows_checkout(self):
        # Caso base: nada muda para um draft que nunca foi pago.
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(draft=self.draft).count(), 1)

    def test_draft_with_pending_payment_still_reuses_it(self):
        # Comportamento existente preservado: pending é um estado ativo, não
        # "já pago" — a reutilização continua funcionando exatamente como
        # antes desta correção.
        existing = make_payment(
            draft=self.draft, plan=self.plan, attempt_number=1,
            status=Payment.Status.PENDING, mp_order_id="ORD-PENDING",
        )
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_id"], str(existing.id))
        self.assertEqual(Payment.objects.filter(draft=self.draft).count(), 1)

    def test_draft_with_action_required_payment_still_reuses_it(self):
        existing = make_payment(
            draft=self.draft, plan=self.plan, attempt_number=1,
            status=Payment.Status.ACTION_REQUIRED, mp_order_id="ORD-ACTION-REQUIRED",
        )
        with patch_mp_client():
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_id"], str(existing.id))
        self.assertEqual(Payment.objects.filter(draft=self.draft).count(), 1)

    def test_draft_with_approved_payment_rejects_new_checkout(self):
        make_payment(
            draft=self.draft, plan=self.plan, attempt_number=1,
            status=Payment.Status.APPROVED, mp_order_id="ORD-APPROVED",
        )
        self.draft.status = ExperienceDraft.Status.PAID
        self.draft.save(update_fields=["status"])

        with patch_mp_client() as mock_cls:
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        # Nenhum segundo Payment foi criado, e a Mercado Pago nunca foi chamada.
        self.assertEqual(Payment.objects.filter(draft=self.draft).count(), 1)
        mock_cls.return_value.create_order.assert_not_called()

    def test_paid_draft_rejects_new_checkout_even_without_a_payment_row(self):
        # Checagem é sobre Draft.status, não sobre a existência de um Payment
        # aprovado — cobre o invariante diretamente, sem depender de como o
        # Draft chegou a PAID.
        self.draft.status = ExperienceDraft.Status.PAID
        self.draft.save(update_fields=["status"])

        with patch_mp_client() as mock_cls:
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())
        mock_cls.return_value.create_order.assert_not_called()

    def test_published_draft_rejects_new_checkout(self):
        self.draft.status = ExperienceDraft.Status.PUBLISHED
        self.draft.slug = "already-public"
        self.draft.save(update_fields=["status", "slug"])

        with patch_mp_client() as mock_cls:
            response = self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())
        mock_cls.return_value.create_order.assert_not_called()

    def test_no_mercadopago_call_when_draft_already_paid(self):
        # Item 9 explícito: a exceção é levantada antes de qualquer
        # construção de MercadoPagoClient em start_checkout.
        self.draft.status = ExperienceDraft.Status.PAID
        self.draft.save(update_fields=["status"])

        with patch_mp_client() as mock_cls:
            self.client.post(checkout_url(self.draft.id), {"plan_code": "weekly"})

        mock_cls.assert_not_called()

    def test_other_user_still_gets_404_even_if_draft_is_already_paid(self):
        # A checagem de ownership na view acontece antes de qualquer lógica
        # de checkout — o status PAID do draft de B não muda o 404 para A.
        other_user = make_user("other-paid-owner@example.com")
        self.draft.status = ExperienceDraft.Status.PAID
        self.draft.save(update_fields=["status"])

        with patch_mp_client():
            response = auth_client(other_user).post(checkout_url(self.draft.id), {"plan_code": "weekly"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Payment.objects.filter(draft=self.draft).exists())

    def test_service_level_raises_draft_already_paid_directly(self):
        # Confirma o tipo de exceção exato na camada de serviço, não só o
        # HTTP status mapeado pela view.
        self.draft.status = ExperienceDraft.Status.PAID
        self.draft.save(update_fields=["status"])

        fake_client = MagicMock()
        with self.assertRaises(DraftAlreadyPaid):
            CheckoutService.start_checkout(draft=self.draft, plan=self.plan, mp_client=fake_client)
        fake_client.create_order.assert_not_called()


class CheckoutAlreadyPaidConcurrencyTests(TransactionTestCase):
    """Duas requisições simultâneas contra um draft já pago: nenhuma delas
    pode criar um novo Payment, e ambas devem ser recusadas — o lock via
    select_for_update no Draft (mesmo usado para serializar a criação de
    tentativas) também serializa esta checagem."""

    reset_sequences = False
    serialized_rollback = True

    def test_concurrent_checkout_attempts_on_paid_draft_are_both_rejected(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="weekly")
        draft.status = ExperienceDraft.Status.PAID
        draft.save(update_fields=["status"])

        barrier = threading.Barrier(2)
        errors = []
        rejections = []

        def worker():
            try:
                fake_client = MagicMock()
                barrier.wait(timeout=5)
                try:
                    CheckoutService.start_checkout(draft=draft, plan=plan, mp_client=fake_client)
                    errors.append(AssertionError("start_checkout deveria ter recusado o draft já pago"))
                except DraftAlreadyPaid:
                    rejections.append(True)
                except OperationalError:
                    # Mesma tolerância a contenção do SQLite de teste já usada
                    # em CheckoutConcurrencyTests — o que importa é que nenhuma
                    # das duas threads cria um Payment novo.
                    rejections.append(True)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(len(rejections), 2)
        self.assertFalse(Payment.objects.filter(draft=draft).exists())
