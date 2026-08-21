"""Testes da Etapa 9B.3 — management command payment_reconcile.

Mesma filosofia de teste de apps.experiences.test_lifecycle_inventory: o
comando é deliberadamente só-leitura em relação ao BANCO (a única escrita de
rede real que ele faz é um GET — get_order — contra a Mercado Pago, nunca
uma chamada de escrita). Os testes aqui prêem isso com:

- fixtures criadas ANTES de qualquer bloco `assert_no_writes()`;
- `assert_no_writes()` (mesmo helper de test_lifecycle_inventory, reaplicado
  aqui) provando que nenhum Model.save/delete nem QuerySet.update/delete/
  bulk_create/bulk_update roda durante a execução — em particular, que
  PaymentConfirmationService.confirm_from_result NUNCA é chamado por este
  comando, mesmo quando o relatório recomenda essa ação;
- MercadoPagoClient sempre mockado — nenhum teste depende de rede real nem
  de MP_ACCESS_TOKEN configurado.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Model
from django.db.models.query import QuerySet
from django.test import TestCase
from django.utils import timezone

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan
from ..services.mercadopago_client import (
    MercadoPagoClientError,
    MercadoPagoConfigurationError,
    MercadoPagoGatewayError,
    MercadoPagoOrderResult,
)

User = get_user_model()

COMMAND_NAME = "payment_reconcile"
COMMAND_MODULE = "apps.payments.management.commands.payment_reconcile"


def make_user(email):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, attempt_number=1, status=Payment.Status.PENDING, **overrides):
    plan = Plan.objects.get(code="weekly")
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


def age_payment(payment, *, minutes):
    Payment.objects.filter(pk=payment.pk).update(updated_at=timezone.now() - timedelta(minutes=minutes))


def run_command(*args):
    out = StringIO()
    call_command(COMMAND_NAME, *args, stdout=out)
    return out.getvalue()


def run_json(*args):
    return json.loads(run_command(*args, "--format=json"))


@contextmanager
def assert_no_writes():
    with patch.object(Model, "save") as mock_save, patch.object(
        Model, "delete"
    ) as mock_model_delete, patch.object(QuerySet, "update") as mock_qs_update, patch.object(
        QuerySet, "delete"
    ) as mock_qs_delete, patch.object(
        QuerySet, "bulk_create"
    ) as mock_bulk_create, patch.object(
        QuerySet, "bulk_update"
    ) as mock_bulk_update:
        try:
            yield
        finally:
            mock_save.assert_not_called()
            mock_model_delete.assert_not_called()
            mock_qs_update.assert_not_called()
            mock_qs_delete.assert_not_called()
            mock_bulk_create.assert_not_called()
            mock_bulk_update.assert_not_called()


class DryRunRequiredTests(TestCase):
    def test_missing_dry_run_raises_command_error(self):
        with assert_no_writes():
            with self.assertRaises(CommandError):
                call_command(COMMAND_NAME)

    def test_dry_run_flag_is_accepted_and_makes_no_network_call_when_no_candidates(self):
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient") as mock_client_cls:
            run_command("--dry-run")
        mock_client_cls.assert_not_called()


class StalenessFilterTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)

    def test_recent_active_payment_is_not_a_candidate(self):
        make_payment(draft=self.draft, status=Payment.Status.PENDING, mp_order_id="ORD-1")
        # updated_at é auto_now — acabou de ser criado, dentro do default de 60min.
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient") as mock_client_cls:
            report = run_json("--dry-run")
        self.assertEqual(report["active_payments_matching_staleness"], 0)
        mock_client_cls.assert_not_called()

    def test_stale_active_payment_is_a_candidate(self):
        payment = make_payment(draft=self.draft, status=Payment.Status.PENDING, mp_order_id="ORD-1")
        age_payment(payment, minutes=90)

        mock_client = MagicMock()
        mock_client.get_order.return_value = MercadoPagoOrderResult(
            order_id="ORD-1", status="created", status_detail=None, payment_id=None, raw={}
        )
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client):
            report = run_json("--dry-run")

        self.assertEqual(report["active_payments_matching_staleness"], 1)
        mock_client.get_order.assert_called_once_with(order_id="ORD-1")

    def test_terminal_payment_is_never_a_candidate_regardless_of_age(self):
        payment = make_payment(draft=self.draft, status=Payment.Status.APPROVED, mp_order_id="ORD-1")
        age_payment(payment, minutes=999999)

        with patch(f"{COMMAND_MODULE}.MercadoPagoClient") as mock_client_cls:
            report = run_json("--dry-run")

        self.assertEqual(report["active_payments_matching_staleness"], 0)
        mock_client_cls.assert_not_called()

    def test_stale_minutes_can_be_overridden(self):
        payment = make_payment(draft=self.draft, status=Payment.Status.PENDING, mp_order_id="ORD-1")
        age_payment(payment, minutes=10)

        with patch(f"{COMMAND_MODULE}.MercadoPagoClient") as mock_client_cls:
            report = run_json("--dry-run", "--stale-minutes=5")
        self.assertEqual(report["active_payments_matching_staleness"], 1)
        mock_client_cls.return_value.get_order.assert_called_once()

    def test_limit_caps_candidates_and_network_calls(self):
        for i in range(3):
            draft = make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
            p = make_payment(draft=draft, status=Payment.Status.PENDING, mp_order_id=f"ORD-{i}")
            age_payment(p, minutes=90)

        mock_client = MagicMock()
        mock_client.get_order.return_value = MercadoPagoOrderResult(
            order_id="ORD-0", status="created", status_detail=None, payment_id=None, raw={}
        )
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client):
            report = run_json("--dry-run", "--limit=2")

        self.assertEqual(report["active_payments_matching_staleness"], 2)
        self.assertTrue(report["candidates_capped"])
        self.assertEqual(mock_client.get_order.call_count, 2)


class WithoutMpOrderIdTests(TestCase):
    def test_payment_without_mp_order_id_is_reported_separately_and_never_queried(self):
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        payment = make_payment(draft=draft, status=Payment.Status.PENDING, mp_order_id=None)
        age_payment(payment, minutes=90)

        with patch(f"{COMMAND_MODULE}.MercadoPagoClient") as mock_client_cls:
            report = run_json("--dry-run")

        mock_client_cls.assert_not_called()
        self.assertEqual(len(report["without_mp_order_id"]), 1)
        row = report["without_mp_order_id"][0]
        self.assertEqual(row["payment_id"], str(payment.id))
        self.assertFalse(row["draft_status_consistent"])
        self.assertIn("Sem mp_order_id", row["recommended_action"])
        self.assertEqual(report["queried"], [])


class ReconciliationClassificationTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        self.payment = make_payment(draft=self.draft, status=Payment.Status.PENDING, mp_order_id="ORD-1")
        age_payment(self.payment, minutes=90)

    def _run_with_mp_status(self, mp_status):
        mock_client = MagicMock()
        mock_client.get_order.return_value = MercadoPagoOrderResult(
            order_id="ORD-1", status=mp_status, status_detail=None, payment_id=None, raw={}
        )
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client):
            return run_json("--dry-run")

    def test_mp_still_pending_reports_no_change(self):
        report = self._run_with_mp_status("created")
        row = report["queried"][0]
        self.assertIsNone(row["would_transition_to"])
        self.assertIn("Nenhuma mudança", row["recommended_action"])

    def test_mp_processed_recommends_approve_and_mark_draft_paid(self):
        report = self._run_with_mp_status("processed")
        row = report["queried"][0]
        self.assertEqual(row["would_transition_to"], Payment.Status.APPROVED)
        self.assertIn("Payment -> approved", row["recommended_action"])
        self.assertIn("Draft -> paid", row["recommended_action"])

    def test_mp_canceled_recommends_reject_and_mark_draft_payment_failed(self):
        report = self._run_with_mp_status("canceled")
        row = report["queried"][0]
        self.assertEqual(row["would_transition_to"], Payment.Status.CANCELLED)
        self.assertIn("Draft -> payment_failed", row["recommended_action"])

    def test_mp_canceled_with_inconsistent_draft_does_not_claim_draft_transition(self):
        # Draft já fora de AWAITING_PAYMENT (o próprio invariante da 9B.2) —
        # PaymentConfirmationService._mark_draft_payment_failed seria no-op
        # sobre o Draft nesse caso; o relatório não pode prometer algo que
        # não aconteceria.
        ExperienceDraft.objects.filter(pk=self.draft.pk).update(status=ExperienceDraft.Status.DRAFT)
        report = self._run_with_mp_status("canceled")
        row = report["queried"][0]
        self.assertFalse(row["draft_status_consistent"])
        self.assertIn("no-op sobre o Draft", row["recommended_action"])

    def test_query_error_is_reported_and_counted_without_raising(self):
        mock_client = MagicMock()
        mock_client.get_order.side_effect = MercadoPagoGatewayError("timeout")
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client):
            report = run_json("--dry-run")

        self.assertEqual(report["query_errors"], 1)
        row = report["queried"][0]
        self.assertIn("query_error", row)

    def test_client_not_configured_is_reported_per_row_without_raising(self):
        with patch(
            f"{COMMAND_MODULE}.MercadoPagoClient",
            side_effect=MercadoPagoConfigurationError("MP_ACCESS_TOKEN não configurado."),
        ):
            report = run_json("--dry-run")

        self.assertEqual(report["query_errors"], 1)
        row = report["queried"][0]
        self.assertIn("query_error", row)


class OutputFormatTests(TestCase):
    def test_text_output_contains_expected_sections(self):
        output = run_command("--dry-run")
        self.assertIn("Reconciliação de Payment", output)
        self.assertIn("SEM mp_order_id", output)
        self.assertIn("CONSULTADOS", output)
        self.assertIn("dry-run", output)

    def test_json_output_has_expected_top_level_keys(self):
        report = run_json("--dry-run")
        self.assertEqual(
            set(report.keys()),
            {
                "generated_at", "mode", "stale_minutes_used", "limit_used",
                "active_payments_matching_staleness", "candidates_capped",
                "without_mp_order_id", "queried", "query_errors",
            },
        )


class NoDatabaseWriteTests(TestCase):
    """Prova central da 9B.3 para este comando: mesmo quando o relatório
    recomenda 'aplicaria confirm_from_result', nada é de fato aplicado."""

    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        self.payment = make_payment(draft=self.draft, status=Payment.Status.PENDING, mp_order_id="ORD-1")
        age_payment(self.payment, minutes=90)

    def test_no_orm_write_methods_are_called_even_when_mp_reports_approved(self):
        mock_client = MagicMock()
        mock_client.get_order.return_value = MercadoPagoOrderResult(
            order_id="ORD-1", status="processed", status_detail=None, payment_id="PAY-1", raw={}
        )
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client):
            with assert_no_writes():
                run_json("--dry-run")

    def test_payment_confirmation_service_apply_is_never_invoked(self):
        mock_client = MagicMock()
        mock_client.get_order.return_value = MercadoPagoOrderResult(
            order_id="ORD-1", status="processed", status_detail=None, payment_id="PAY-1", raw={}
        )
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client), patch(
            f"{COMMAND_MODULE}.PaymentConfirmationService.confirm_from_result"
        ) as mock_confirm:
            run_json("--dry-run")
        mock_confirm.assert_not_called()

    def test_snapshot_is_identical_before_and_after_run(self):
        before_payment = Payment.objects.get(pk=self.payment.pk)
        before = (before_payment.status, before_payment.updated_at, self.draft.status)

        mock_client = MagicMock()
        mock_client.get_order.return_value = MercadoPagoOrderResult(
            order_id="ORD-1", status="processed", status_detail=None, payment_id="PAY-1", raw={}
        )
        with patch(f"{COMMAND_MODULE}.MercadoPagoClient", return_value=mock_client):
            run_json("--dry-run")

        after_payment = Payment.objects.get(pk=self.payment.pk)
        after_draft = ExperienceDraft.objects.get(pk=self.draft.pk)
        after = (after_payment.status, after_payment.updated_at, after_draft.status)
        self.assertEqual(before, after)
