"""Testes da Etapa 9B.1 — management command lifecycle_inventory.

O comando é deliberadamente só-leitura (ver docstring do próprio comando em
management/commands/lifecycle_inventory.py). Estes testes existem para
provar isso, não só para checar as contagens:

- toda fixture (users/drafts/payments/media) é criada ANTES de qualquer
  bloco que afirme "nenhuma escrita" — senão a própria fixture dispararia
  os mocks de escrita;
- `assert_no_writes()` troca Model.save/Model.delete/QuerySet.update/
  QuerySet.delete/QuerySet.bulk_create/QuerySet.bulk_update por mocks e
  confirma, no fim do bloco (mesmo se uma exceção subir), que nenhum foi
  chamado — isto cobre qualquer subclasse de Model, não só as três usadas
  aqui;
- comparações de snapshot antes/depois (valores de campo, não só count())
  fecham o caso para qualquer mutação in-place que escapasse dos mocks.
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

from apps.payments.models import Payment, Plan

from .models import ExperienceDraft, Media

User = get_user_model()

COMMAND_NAME = "lifecycle_inventory"
COMMAND_MODULE = "apps.experiences.management.commands.lifecycle_inventory"


# ---------------------------------------------------------------------------
# Fixtures (mesmo padrão de apps/payments/tests/test_models.py e
# apps/experiences/tests.py — cada arquivo de teste define suas próprias
# factories locais em vez de importar de tests.py).
# ---------------------------------------------------------------------------


def make_user(email):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, attempt_number=1, status=Payment.Status.APPROVED, **overrides):
    plan = Plan.objects.get(code="essential")
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


def run_command(*args):
    out = StringIO()
    call_command(COMMAND_NAME, *args, stdout=out)
    return out.getvalue()


def run_json(*args):
    return json.loads(run_command(*args, "--format=json"))


def snapshot():
    """Estado observável de cada linha (não só count()) para provar que
    nada mudou — pega os campos que o próprio comando poderia, em tese,
    tocar (status, timestamps, chaves)."""

    drafts = list(
        ExperienceDraft.objects.order_by("id").values_list(
            "id", "status", "slug", "published_at", "expires_at", "updated_at"
        )
    )
    payments = list(
        Payment.objects.order_by("id").values_list(
            "id", "status", "mp_order_id", "mp_payment_id", "updated_at"
        )
    )
    media = list(
        Media.objects.order_by("id").values_list(
            "id", "upload_status", "uploaded_at", "storage_key"
        )
    )
    return drafts, payments, media


@contextmanager
def assert_no_writes():
    """Troca todo caminho de escrita do ORM por um MagicMock e garante, ao
    sair do bloco (mesmo em exceção), que nenhum foi chamado."""

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


# ---------------------------------------------------------------------------


class DryRunRequiredTests(TestCase):
    def test_missing_dry_run_raises_command_error(self):
        with assert_no_writes():
            with self.assertRaises(CommandError):
                call_command(COMMAND_NAME)

    def test_missing_dry_run_does_not_touch_database(self):
        owner = make_user("owner@example.com")
        make_draft(owner)
        before = snapshot()

        with self.assertRaises(CommandError):
            call_command(COMMAND_NAME)

        self.assertEqual(snapshot(), before)

    def test_dry_run_flag_is_accepted(self):
        # Não deve levantar CommandError quando --dry-run é passado.
        run_command("--dry-run")


class DraftInventoryTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")

    def test_counts_by_status(self):
        make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        make_draft(self.owner, status=ExperienceDraft.Status.PAYMENT_FAILED)
        make_draft(self.owner, status=ExperienceDraft.Status.PAID)
        make_draft(self.owner, status=ExperienceDraft.Status.PUBLISHED, expires_at=None)

        report = run_json("--dry-run")["drafts"]

        self.assertEqual(report["total"], 6)
        self.assertEqual(report["by_status"]["draft"]["count"], 2)
        self.assertEqual(report["by_status"]["awaiting_payment"]["count"], 1)
        self.assertEqual(report["by_status"]["payment_failed"]["count"], 1)
        self.assertEqual(report["by_status"]["paid"]["count"], 1)
        self.assertEqual(report["by_status"]["published"]["count"], 1)

    def test_status_with_zero_rows_reports_zero_and_no_oldest(self):
        report = run_json("--dry-run")["drafts"]
        for status_value, data in report["by_status"].items():
            self.assertEqual(data["count"], 0)
            self.assertIsNone(data["oldest_created_at"])
            self.assertIsNone(data["oldest_age_days"])

    def test_oldest_created_at_is_reported_for_populated_status(self):
        draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        report = run_json("--dry-run")["drafts"]
        entry = report["by_status"]["draft"]
        self.assertEqual(entry["oldest_created_at"], draft.created_at.isoformat())
        self.assertIsNotNone(entry["oldest_age_days"])

    def test_published_expiration_buckets(self):
        now = timezone.now()
        make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            expires_at=now - timedelta(days=1),
        )
        make_draft(
            self.owner,
            status=ExperienceDraft.Status.PUBLISHED,
            expires_at=now + timedelta(days=30),
        )
        make_draft(self.owner, status=ExperienceDraft.Status.PUBLISHED, expires_at=None)

        report = run_json("--dry-run")["drafts"]

        self.assertEqual(report["published_expired"], 1)
        self.assertEqual(report["published_not_yet_expired"], 1)
        self.assertEqual(report["published_never_expires"], 1)


class PaymentInventoryTests(TestCase):
    def test_counts_by_status_and_without_mp_order_id(self):
        for status_value in Payment.Status.values:
            owner = make_user(f"owner-{status_value}@example.com")
            draft = make_draft(
                owner,
                status=(
                    ExperienceDraft.Status.AWAITING_PAYMENT
                    if status_value in Payment.ACTIVE_STATUSES
                    else ExperienceDraft.Status.PAID
                ),
            )
            make_payment(draft=draft, status=status_value)

        report = run_json("--dry-run")["payments"]

        self.assertEqual(report["total"], len(Payment.Status.values))
        for status_value in Payment.Status.values:
            self.assertEqual(report["by_status"][status_value]["count"], 1)
        # Nenhum payment de teste recebeu mp_order_id.
        self.assertEqual(report["without_mp_order_id"], len(Payment.Status.values))
        # Baseline consistente: toda payment ativa aqui está com o draft em
        # AWAITING_PAYMENT, então o invariante não deve disparar.
        self.assertEqual(report["active_payment_with_inconsistent_draft_status"], 0)

    def test_with_mp_order_id_is_excluded_from_without_mp_order_id(self):
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.PAID)
        make_payment(draft=draft, status=Payment.Status.APPROVED, mp_order_id="order-123")

        report = run_json("--dry-run")["payments"]

        self.assertEqual(report["total"], 1)
        self.assertEqual(report["without_mp_order_id"], 0)

    def test_active_payment_with_inconsistent_draft_status_is_flagged(self):
        consistent_owner = make_user("consistent@example.com")
        consistent_draft = make_draft(
            consistent_owner, status=ExperienceDraft.Status.AWAITING_PAYMENT
        )
        make_payment(draft=consistent_draft, status=Payment.Status.IN_PROCESS)

        inconsistent_owner = make_user("inconsistent@example.com")
        inconsistent_draft = make_draft(inconsistent_owner, status=ExperienceDraft.Status.DRAFT)
        make_payment(draft=inconsistent_draft, status=Payment.Status.PENDING)

        report = run_json("--dry-run")["payments"]

        self.assertEqual(report["active_payment_with_inconsistent_draft_status"], 1)


class MediaInventoryTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@example.com")
        self.draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)

    def test_counts_by_upload_status(self):
        make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        make_media(self.draft, upload_status=Media.UploadStatus.UPLOADED)
        make_media(self.draft, upload_status=Media.UploadStatus.FAILED)

        report = run_json("--dry-run")["media"]

        self.assertEqual(report["total"], 4)
        self.assertEqual(report["by_upload_status"]["pending"], 2)
        self.assertEqual(report["by_upload_status"]["uploaded"], 1)
        self.assertEqual(report["by_upload_status"]["failed"], 1)

    def test_without_draft_is_always_zero(self):
        # Media.draft é FK obrigatória (NOT NULL) — sem fixture especial
        # aqui, só confirmando o valor factual reportado.
        make_media(self.draft)
        report = run_json("--dry-run")["media"]
        self.assertEqual(report["without_draft"], 0)

    @override_settings(PENDING_MEDIA_EXPIRATION_MINUTES=45)
    def test_stale_pending_uses_setting_by_default(self):
        old_media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        Media.objects.filter(pk=old_media.pk).update(
            created_at=timezone.now() - timedelta(minutes=60)
        )
        recent_media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        Media.objects.filter(pk=recent_media.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )

        report = run_json("--dry-run")["media"]

        self.assertEqual(report["stale_media_minutes_used"], 45)
        self.assertEqual(report["pending_older_than_threshold"], 1)

    def test_stale_pending_minutes_can_be_overridden(self):
        media = make_media(self.draft, upload_status=Media.UploadStatus.PENDING)
        Media.objects.filter(pk=media.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )

        report_strict = run_json("--dry-run", "--stale-media-minutes=5")["media"]
        self.assertEqual(report_strict["stale_media_minutes_used"], 5)
        self.assertEqual(report_strict["pending_older_than_threshold"], 1)

        report_lenient = run_json("--dry-run", "--stale-media-minutes=1440")["media"]
        self.assertEqual(report_lenient["stale_media_minutes_used"], 1440)
        self.assertEqual(report_lenient["pending_older_than_threshold"], 0)

    def test_media_on_never_advanced_drafts(self):
        never_advanced_draft = make_draft(self.owner, status=ExperienceDraft.Status.DRAFT)
        advanced_draft = make_draft(self.owner, status=ExperienceDraft.Status.PAID)
        make_media(never_advanced_draft)
        make_media(advanced_draft)

        report = run_json("--dry-run")["media"]

        # self.draft (setUp) também está em DRAFT e não recebeu media aqui,
        # então a contagem esperada é só a media do never_advanced_draft.
        self.assertEqual(report["media_on_never_advanced_drafts"], 1)


class OutputFormatTests(TestCase):
    def setUp(self):
        owner = make_user("owner@example.com")
        draft = make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        make_media(draft)

    def test_text_output_contains_expected_sections(self):
        output = run_command("--dry-run")
        self.assertIn("DRAFTS", output)
        self.assertIn("PAYMENTS", output)
        self.assertIn("MEDIA", output)
        self.assertIn("R2", output)
        self.assertIn("não verificado", output)
        self.assertIn("dry-run", output)

    def test_json_output_is_valid_json_with_expected_top_level_keys(self):
        report = run_json("--dry-run")
        self.assertEqual(
            set(report.keys()),
            {"generated_at", "mode", "drafts", "payments", "media", "r2"},
        )
        self.assertFalse(report["r2"]["checked"])

    def test_default_format_is_text_not_json(self):
        output = run_command("--dry-run")
        with self.assertRaises(json.JSONDecodeError):
            json.loads(output)


class CheckR2Tests(TestCase):
    def setUp(self):
        owner = make_user("owner@example.com")
        self.draft = make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        self.media = make_media(self.draft, storage_key="drafts/known/1-a.jpg")

    def test_check_r2_off_by_default_never_touches_client(self):
        with patch(f"{COMMAND_MODULE}.get_r2_client") as mock_get_client:
            report = run_json("--dry-run")["r2"]

        mock_get_client.assert_not_called()
        self.assertFalse(report["checked"])
        self.assertIn("--check-r2", report["reason"])

    def test_check_r2_without_configuration_reports_not_checked(self):
        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=False), patch(
            f"{COMMAND_MODULE}.get_r2_client"
        ) as mock_get_client:
            report = run_json("--dry-run", "--check-r2")["r2"]

        mock_get_client.assert_not_called()
        self.assertFalse(report["checked"])
        self.assertIn("não configurado", report["reason"])

    def test_check_r2_uses_mocked_client_and_never_calls_write_methods(self):
        mock_client = MagicMock()

        def head_object(*, Bucket, Key):
            if Key == self.media.storage_key:
                return {}
            raise AssertionError(f"unexpected head_object key: {Key}")

        mock_client.head_object.side_effect = head_object
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": self.media.storage_key},
                {"Key": "drafts/orphan/2-b.jpg"},
            ],
            "IsTruncated": False,
        }

        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True), patch(
            f"{COMMAND_MODULE}.get_r2_client", return_value=mock_client
        ), patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"):
            report = run_json("--dry-run", "--check-r2")["r2"]

        self.assertTrue(report["checked"])
        self.assertEqual(report["bucket"], "test-bucket")
        self.assertEqual(report["db_references_missing_object_count"], 0)
        self.assertEqual(report["objects_without_db_reference_count"], 1)
        self.assertEqual(report["objects_without_db_reference_sample"], ["drafts/orphan/2-b.jpg"])

        mock_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key=self.media.storage_key
        )
        mock_client.list_objects_v2.assert_called_once()
        for write_method in (
            "put_object",
            "delete_object",
            "delete_objects",
            "upload_fileobj",
            "complete_multipart_upload",
            "create_bucket",
            "delete_bucket",
        ):
            getattr(mock_client, write_method).assert_not_called()

    def test_check_r2_classifies_404_as_missing_object_not_error(self):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        mock_client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}

        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True), patch(
            f"{COMMAND_MODULE}.get_r2_client", return_value=mock_client
        ), patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"):
            report = run_json("--dry-run", "--check-r2")["r2"]

        self.assertEqual(report["db_references_missing_object_count"], 1)
        self.assertEqual(report["db_references_missing_object_sample"], [self.media.storage_key])
        self.assertEqual(report["head_object_check_errors"], 0)

    def test_check_r2_classifies_non_404_error_separately(self):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}}, "HeadObject"
        )
        mock_client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}

        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True), patch(
            f"{COMMAND_MODULE}.get_r2_client", return_value=mock_client
        ), patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"):
            report = run_json("--dry-run", "--check-r2")["r2"]

        self.assertEqual(report["db_references_missing_object_count"], 0)
        self.assertEqual(report["head_object_check_errors"], 1)

    def test_r2_sample_and_list_limits_are_respected(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}
        mock_client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}

        with patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True), patch(
            f"{COMMAND_MODULE}.get_r2_client", return_value=mock_client
        ), patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"):
            report = run_json(
                "--dry-run", "--check-r2", "--r2-sample-limit=1", "--r2-list-limit=10"
            )["r2"]

        self.assertEqual(report["media_rows_checked"], 1)
        self.assertTrue(report["media_rows_checked_capped"])
        mock_client.list_objects_v2.assert_called_once()
        _, kwargs = mock_client.list_objects_v2.call_args
        self.assertEqual(kwargs["MaxKeys"], 10)


class NoDatabaseMutationTests(TestCase):
    """Prova, de duas formas independentes, que o comando não escreve:

    1) o estado observável do banco (não só count()) é idêntico antes e
       depois de rodar o comando, em text, json e com --check-r2 mockado;
    2) nenhum método de escrita do ORM (Model.save/delete, QuerySet.update/
       delete/bulk_create/bulk_update) é sequer chamado durante a execução.
    """

    def setUp(self):
        self.owner = make_user("owner@example.com")

        self.drafts = [
            make_draft(self.owner, status=ExperienceDraft.Status.DRAFT),
            make_draft(self.owner, status=ExperienceDraft.Status.AWAITING_PAYMENT),
            make_draft(self.owner, status=ExperienceDraft.Status.PAID),
            make_draft(
                self.owner,
                status=ExperienceDraft.Status.PUBLISHED,
                expires_at=timezone.now() - timedelta(days=1),
            ),
        ]
        make_payment(draft=self.drafts[1], status=Payment.Status.PENDING)
        make_payment(draft=self.drafts[2], status=Payment.Status.APPROVED)

        old_media = make_media(self.drafts[0], upload_status=Media.UploadStatus.PENDING)
        Media.objects.filter(pk=old_media.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        make_media(self.drafts[2], upload_status=Media.UploadStatus.UPLOADED)

        self.mock_r2_client = MagicMock()
        self.mock_r2_client.head_object.return_value = {}
        self.mock_r2_client.list_objects_v2.return_value = {
            "Contents": [],
            "IsTruncated": False,
        }

    def _r2_patches(self):
        return (
            patch(f"{COMMAND_MODULE}.r2_is_configured", return_value=True),
            patch(f"{COMMAND_MODULE}.get_r2_client", return_value=self.mock_r2_client),
            patch(f"{COMMAND_MODULE}.settings.R2_BUCKET_NAME", "test-bucket"),
        )

    def test_snapshot_is_identical_before_and_after_text_run(self):
        before = snapshot()
        run_command("--dry-run")
        self.assertEqual(snapshot(), before)

    def test_snapshot_is_identical_before_and_after_json_run(self):
        before = snapshot()
        run_json("--dry-run")
        self.assertEqual(snapshot(), before)

    def test_snapshot_is_identical_before_and_after_check_r2_run(self):
        before = snapshot()
        p1, p2, p3 = self._r2_patches()
        with p1, p2, p3:
            run_json("--dry-run", "--check-r2")
        self.assertEqual(snapshot(), before)

    def test_no_orm_write_methods_are_called_during_full_run(self):
        p1, p2, p3 = self._r2_patches()
        with p1, p2, p3:
            with assert_no_writes():
                run_json("--dry-run", "--check-r2")

    def test_no_orm_write_methods_are_called_without_check_r2(self):
        with assert_no_writes():
            run_command("--dry-run")
