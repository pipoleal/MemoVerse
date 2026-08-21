"""Testes da Etapa 9B.3 — management command lifecycle_cleanup.

Mesmo contrato de test_lifecycle_inventory.py: o comando é só-leitura, então
os testes provam isso de duas formas (assert_no_writes + snapshot antes/
depois), além de verificar a CLASSIFICAÇÃO em si (candidatos vs.
never_removed) contra a política aprovada na Etapa 9B.2.

Um ponto específico deste comando: mesmo quando um item aparece na lista de
"candidatos", nenhuma exclusão pode acontecer — não existe --apply no
código desta fase. Os testes de escrita aqui cobrem justamente o caso mais
arriscado de auditar (contagens grandes, muitos candidatos) para provar que
mesmo assim nada é tocado.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Model
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.payments.models import Payment, Plan, WebhookEvent

from .models import ExperienceDraft, Media

User = get_user_model()

COMMAND_NAME = "lifecycle_cleanup"
COMMAND_MODULE = "apps.experiences.management.commands.lifecycle_cleanup"


def make_user(email):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def age_draft(draft, *, days):
    ExperienceDraft.objects.filter(pk=draft.pk).update(updated_at=timezone.now() - timedelta(days=days))


def age_draft_created_at(draft, *, hours):
    ExperienceDraft.objects.filter(pk=draft.pk).update(created_at=timezone.now() - timedelta(hours=hours))


def make_payment(*, draft, attempt_number=1, status=Payment.Status.APPROVED, **overrides):
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


def make_media(draft, **overrides):
    media_id = overrides.pop("id", uuid.uuid4())
    defaults = {
        "id": media_id,
        "draft": draft,
        "media_type": Media.Type.PHOTO,
        "storage_key": f"drafts/{draft.id}/photos/{media_id}-test.jpg",
        "original_filename": "test.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
    }
    defaults.update(overrides)
    return Media.objects.create(**defaults)


def age_media(media, *, minutes=None, days=None):
    delta = timedelta(minutes=minutes) if minutes is not None else timedelta(days=days)
    Media.objects.filter(pk=media.pk).update(created_at=timezone.now() - delta)


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


class DryRunAndApplyTests(TestCase):
    def test_missing_dry_run_raises_command_error(self):
        with assert_no_writes():
            with self.assertRaises(CommandError):
                call_command(COMMAND_NAME)

    def test_apply_flag_does_not_exist_in_this_phase(self):
        # --apply não existe no parser nesta fase — CommandError de
        # argumento desconhecido, nunca uma exclusão real.
        with self.assertRaises(CommandError):
            call_command(COMMAND_NAME, "--dry-run", "--apply")


class DraftAbandonedCandidateTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")

    def test_old_draft_without_payment_is_a_candidate(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        age_draft(draft, days=31)

        report = run_json("--dry-run")["candidates"]["draft_abandoned"]
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["sample_ids"], [str(draft.id)])

    def test_recent_draft_is_not_a_candidate(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        age_draft(draft, days=10)

        report = run_json("--dry-run")["candidates"]["draft_abandoned"]
        self.assertEqual(report["count"], 0)

    def test_draft_with_unexpected_payment_is_excluded_and_flagged(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        age_draft(draft, days=31)
        make_payment(draft=draft, status=Payment.Status.REJECTED)

        report = run_json("--dry-run")["candidates"]["draft_abandoned"]
        self.assertEqual(report["count"], 0)
        self.assertEqual(report["excluded_unexpectedly_has_payment"], 1)

    def test_days_threshold_is_overridable(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        age_draft(draft, days=10)

        report = run_json("--dry-run", "--draft-abandoned-days=5")["candidates"]["draft_abandoned"]
        self.assertEqual(report["count"], 1)


class DraftAnonymousUnclaimedCandidateTests(TestCase):
    """Etapa 10: draft anônimo (owner IS NULL) nunca reivindicado, criado
    há mais de 48h por padrão."""

    def test_old_unclaimed_anonymous_draft_is_a_candidate(self):
        draft = make_draft(None, status=ExperienceDraft.Status.DRAFT, claim_token="tok-1")
        age_draft_created_at(draft, hours=49)

        report = run_json("--dry-run")["candidates"]["draft_anonymous_unclaimed"]
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["sample_ids"], [str(draft.id)])

    def test_recent_unclaimed_anonymous_draft_is_not_a_candidate(self):
        draft = make_draft(None, status=ExperienceDraft.Status.DRAFT, claim_token="tok-2")
        age_draft_created_at(draft, hours=1)

        report = run_json("--dry-run")["candidates"]["draft_anonymous_unclaimed"]
        self.assertEqual(report["count"], 0)

    def test_claimed_draft_is_never_a_candidate_even_if_old(self):
        # owner preenchido = já foi reivindicado — nunca cai nesta
        # categoria, mesmo muito antigo (cairia, quando muito, em
        # draft_abandoned, categoria separada e com seu próprio corte).
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        age_draft_created_at(draft, hours=200)
        age_draft(draft, days=1)  # updated_at recente o bastante pra não cair em draft_abandoned também

        report = run_json("--dry-run")["candidates"]["draft_anonymous_unclaimed"]
        self.assertEqual(report["count"], 0)

    def test_unclaimed_draft_with_unexpected_payment_is_excluded_and_flagged(self):
        # Estruturalmente não deveria existir (checkout exige owner), mas a
        # checagem defensiva deve continuar excluindo se acontecer mesmo
        # assim — nunca remove um draft com Payment associado.
        draft = make_draft(None, status=ExperienceDraft.Status.DRAFT, claim_token="tok-3")
        age_draft_created_at(draft, hours=49)
        temp_owner = make_user("temp-owner@example.com")
        make_payment(draft=draft, owner=temp_owner, status=Payment.Status.REJECTED)

        report = run_json("--dry-run")["candidates"]["draft_anonymous_unclaimed"]
        self.assertEqual(report["count"], 0)
        self.assertEqual(report["excluded_unexpectedly_has_payment"], 1)

    def test_hours_threshold_is_overridable(self):
        draft = make_draft(None, status=ExperienceDraft.Status.DRAFT, claim_token="tok-4")
        age_draft_created_at(draft, hours=10)

        report = run_json("--dry-run", "--draft-anonymous-unclaimed-hours=5")["candidates"][
            "draft_anonymous_unclaimed"
        ]
        self.assertEqual(report["count"], 1)


class DraftPaymentFailedCandidateTests(TestCase):
    def test_old_payment_failed_draft_is_a_candidate_but_flagged_blocked(self):
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.PAYMENT_FAILED)
        age_draft(draft, days=31)
        make_payment(draft=draft, status=Payment.Status.REJECTED)

        report = run_json("--dry-run")["candidates"]["draft_payment_failed"]
        self.assertEqual(report["count"], 1)
        self.assertTrue(report["blocked_by_protect_constraint"])
        self.assertIn("PROTECT", report["warning"])

    def test_recent_payment_failed_draft_is_not_a_candidate(self):
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.PAYMENT_FAILED)
        age_draft(draft, days=5)

        report = run_json("--dry-run")["candidates"]["draft_payment_failed"]
        self.assertEqual(report["count"], 0)

    def test_payment_failed_draft_with_still_active_payment_is_excluded_not_listed_as_candidate(self):
        # Cenário do invariante da 9B.2: um Draft payment_failed que ainda
        # tem um Payment ativo (dado legado anterior à correção da 9B.3 em
        # checkout_service) nunca pode ser tratado como "abandonado" — idade
        # nenhuma justifica isso, precisa passar por payment_reconcile
        # primeiro. Regressão direta: sem esta exclusão, o relatório
        # prometeria remover um Draft com pagamento ainda em andamento.
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.PAYMENT_FAILED)
        age_draft(draft, days=31)
        make_payment(draft=draft, status=Payment.Status.PENDING)

        report = run_json("--dry-run")["candidates"]["draft_payment_failed"]
        self.assertEqual(report["count"], 0)
        self.assertEqual(report["excluded_has_active_payment_requires_reconcile_first"], 1)


class MediaCandidateTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=60)
    def test_stale_pending_media_is_a_candidate(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        age_media(media, minutes=90)

        report = run_json("--dry-run")["candidates"]["media_pending_stale"]
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["sample_ids"], [str(media.id)])

    def test_old_failed_media_is_a_candidate(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.FAILED)
        age_media(media, days=8)

        report = run_json("--dry-run")["candidates"]["media_failed_stale"]
        self.assertEqual(report["count"], 1)

    def test_recent_failed_media_is_not_a_candidate(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.FAILED)
        age_media(media, days=1)

        report = run_json("--dry-run")["candidates"]["media_failed_stale"]
        self.assertEqual(report["count"], 0)


class NeverRemovedTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")

    def test_paid_unpublished_draft_is_never_a_candidate_even_when_very_old(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID)
        age_draft(draft, days=9999)

        report = run_json("--dry-run")
        self.assertNotIn("draft_paid", report["candidates"])
        never = report["never_removed"]["draft_paid_unpublished"]
        self.assertEqual(never["count"], 1)
        self.assertIn("REGRA DE OURO", never["reason"])

    def test_expired_published_draft_is_never_a_candidate(self):
        draft = make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            expires_at=timezone.now() - timedelta(days=100),
        )
        report = run_json("--dry-run")
        never = report["never_removed"]["draft_published_expired"]
        self.assertEqual(never["count"], 1)
        self.assertEqual(never["sample_ids"], [str(draft.id)])

    def test_approved_payment_is_never_a_candidate(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, status=Payment.Status.APPROVED)

        report = run_json("--dry-run")
        never = report["never_removed"]["payment_financial_terminal"]
        self.assertEqual(never["by_status"]["approved"], 1)
        self.assertIn("REGRA DE OURO", never["reason"])

    def test_active_payment_is_excluded_from_financial_terminal_bucket(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        make_payment(draft=draft, status=Payment.Status.PENDING)

        report = run_json("--dry-run")
        never = report["never_removed"]["payment_financial_terminal"]
        self.assertEqual(never["count"], 0)

    def test_invariant_inconsistent_payment_is_reported_but_never_a_cleanup_candidate(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        make_payment(draft=draft, status=Payment.Status.PENDING, mp_order_id=None)

        report = run_json("--dry-run")
        never = report["never_removed"]["payment_invariant_inconsistent"]
        self.assertEqual(never["count"], 1)
        self.assertIn("payment_reconcile", never["reason"])

    def test_webhook_events_are_inventoried_with_no_candidates(self):
        WebhookEvent.objects.create(
            notification_id="evt-1", topic="order", resource_id="ORD-1",
            payload={}, status=WebhookEvent.Status.FAILED,
        )
        report = run_json("--dry-run")
        never = report["never_removed"]["webhook_events"]
        self.assertEqual(never["count"], 1)
        self.assertEqual(never["by_status"]["failed"], 1)
        self.assertIn("ainda não foi definida", never["reason"])


class CheckR2Tests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        self.media = make_media(self.draft, storage_key="drafts/known/1-a.jpg")

    def test_off_by_default_never_touches_client(self):
        with patch(f"{COMMAND_MODULE}.get_r2_client") as mock_get_client:
            report = run_json("--dry-run")

        mock_get_client.assert_not_called()
        self.assertFalse(report["candidates"]["r2_orphans_past_grace"]["checked"])
        self.assertFalse(report["never_removed"]["r2_missing_but_referenced"]["checked"])

    def test_orphan_past_grace_is_a_candidate_orphan_within_grace_is_excluded(self):
        now = timezone.now()
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": self.media.storage_key, "LastModified": now},
                {"Key": "drafts/orphan/old.jpg", "LastModified": now - timedelta(days=40)},
                {"Key": "drafts/orphan/recent.jpg", "LastModified": now - timedelta(days=2)},
            ],
            "IsTruncated": False,
        }
        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True), patch(
            f"{COMMAND_MODULE}.get_r2_client", return_value=mock_client
        ), patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"):
            report = run_json("--dry-run", "--check-r2")

        candidates = report["candidates"]["r2_orphans_past_grace"]
        self.assertEqual(candidates["count"], 1)
        self.assertEqual(candidates["sample_keys"], ["drafts/orphan/old.jpg"])
        self.assertEqual(candidates["orphans_within_grace_period_excluded"], 1)

        for write_method in ("delete_object", "delete_objects", "put_object"):
            getattr(mock_client, write_method).assert_not_called()

    def test_missing_but_referenced_is_reported_and_never_a_candidate(self):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        mock_client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}

        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True), patch(
            f"{COMMAND_MODULE}.get_r2_client", return_value=mock_client
        ), patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"):
            report = run_json("--dry-run", "--check-r2")

        never = report["never_removed"]["r2_missing_but_referenced"]
        self.assertEqual(never["count"], 1)
        self.assertEqual(never["sample_keys"], [self.media.storage_key])
        self.assertNotIn("r2_missing_but_referenced", report["candidates"])


class OutputFormatTests(TestCase):
    def test_text_output_contains_expected_sections(self):
        output = run_command("--dry-run")
        self.assertIn("CANDIDATOS", output)
        self.assertIn("NUNCA REMOVIDOS", output)
        self.assertIn("dry-run", output)

    def test_json_output_has_candidates_and_never_removed_top_level_keys(self):
        report = run_json("--dry-run")
        self.assertIn("candidates", report)
        self.assertIn("never_removed", report)
        self.assertEqual(
            set(report["candidates"].keys()),
            {
                "draft_abandoned", "draft_anonymous_unclaimed", "draft_payment_failed",
                "media_pending_stale", "media_failed_stale", "r2_orphans_past_grace",
            },
        )
        self.assertEqual(
            set(report["never_removed"].keys()),
            {
                "draft_paid_unpublished", "draft_published_expired",
                "payment_financial_terminal", "payment_invariant_inconsistent",
                "webhook_events", "r2_missing_but_referenced",
            },
        )


class NoDatabaseMutationTests(TestCase):
    """Prova central da 9B.3 para este comando: mesmo com candidatos reais
    em toda categoria (inclusive R2 mockado), nada é escrito — não existe
    --apply, e nenhuma chamada de escrita do ORM acontece."""

    def setUp(self):
        owner = make_user("owner@example.com")

        abandoned = make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        age_draft(abandoned, days=40)

        failed = make_draft(owner, status=ExperienceDraft.Status.PAYMENT_FAILED)
        age_draft(failed, days=40)
        make_payment(draft=failed, status=Payment.Status.REJECTED)

        paid = make_draft(owner, status=ExperienceDraft.Status.PAID)
        age_draft(paid, days=9999)

        media_draft = make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        pending = make_media(media_draft, upload_status=Media.UploadStatus.PENDING)
        age_media(pending, minutes=120)
        failed_media = make_media(media_draft, upload_status=Media.UploadStatus.FAILED)
        age_media(failed_media, days=10)

        self.mock_r2_client = MagicMock()
        self.mock_r2_client.head_object.return_value = {}
        self.mock_r2_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "drafts/orphan/old.jpg", "LastModified": timezone.now() - timedelta(days=40)}],
            "IsTruncated": False,
        }

    def _r2_patches(self):
        return (
            patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True),
            patch(f"{COMMAND_MODULE}.get_r2_client", return_value=self.mock_r2_client),
            patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"),
        )

    def test_no_orm_write_methods_are_called_with_real_candidates_in_every_category(self):
        p1, p2, p3 = self._r2_patches()
        with p1, p2, p3:
            with assert_no_writes():
                report = run_json("--dry-run", "--check-r2")

        # Confere que os candidatos realmente existiam (não é um teste vazio).
        self.assertGreaterEqual(report["candidates"]["draft_abandoned"]["count"], 1)
        self.assertGreaterEqual(report["candidates"]["draft_payment_failed"]["count"], 1)
        self.assertGreaterEqual(report["candidates"]["media_pending_stale"]["count"], 1)
        self.assertGreaterEqual(report["candidates"]["media_failed_stale"]["count"], 1)
        self.assertGreaterEqual(report["candidates"]["r2_orphans_past_grace"]["count"], 1)

    def test_snapshot_is_identical_before_and_after_run(self):
        def snapshot():
            return (
                list(ExperienceDraft.objects.order_by("id").values_list("id", "status", "updated_at")),
                list(Payment.objects.order_by("id").values_list("id", "status", "updated_at")),
                list(Media.objects.order_by("id").values_list("id", "upload_status")),
            )

        before = snapshot()
        p1, p2, p3 = self._r2_patches()
        with p1, p2, p3:
            run_json("--dry-run", "--check-r2")
        self.assertEqual(snapshot(), before)
