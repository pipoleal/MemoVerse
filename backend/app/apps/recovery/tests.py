"""Fluxo de recuperação de carrinho abandonado (ver management/commands/
cart_recovery.py para o desenho completo). Cobre: idempotência sob
concorrência real (threads), retry de falha transitória, isolamento de
falha por draft, elegibilidade de draft, o link mágico (criação + resgate),
que nenhuma mensagem jamais oferece desconto, que o WhatsApp nunca finge um
envio sem telefone/credenciais, e que abrir um draft pelo link de
recuperação preserva tema/mídia intactos.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.experiences.models import ExperienceDraft, Media
from apps.payments.models import PlanDiscount

from .content import build_email, build_whatsapp
from .management.commands.cart_recovery import Command as CartRecoveryCommand
from .models import CartRecoveryMessage, RecoveryLoginToken
from .services.recovery_link import create_recovery_link
from .services.whatsapp_service import (
    WhatsAppNotConfiguredError,
    is_whatsapp_configured,
    send_whatsapp_template,
)

User = get_user_model()

Stage = CartRecoveryMessage.Stage
Channel = CartRecoveryMessage.Channel
Status = CartRecoveryMessage.Status


def make_user(email="anna@example.com", **overrides):
    defaults = {"first_name": "Anna", "last_name": "Magalhães", "password": "strong-pass-123"}
    defaults.update(overrides)
    return User.objects.create_user(email=email, **defaults)


def make_abandoned_draft(owner, *, age: timedelta, **overrides):
    defaults = {
        "owner": owner,
        "status": ExperienceDraft.Status.DRAFT,
        "title": "Nosso aniversário",
        "recipient_name": "Meu amor",
    }
    defaults.update(overrides)
    draft = ExperienceDraft.objects.create(**defaults)
    backdated = timezone.now() - age
    ExperienceDraft.objects.filter(pk=draft.pk).update(updated_at=backdated)
    draft.refresh_from_db()
    return draft


def run_command(*, dry_run=False, only_email="", only_draft_id=""):
    CartRecoveryCommand().handle(dry_run=dry_run, only_email=only_email, only_draft_id=only_draft_id)


class ContentTests(TestCase):
    def test_email_never_mentions_discount_or_bonus(self):
        for stage in (Stage.ONE_HOUR, Stage.ONE_DAY, Stage.THREE_DAYS):
            content = build_email(stage, first_name="Anna", recovery_url="https://x.test/r/abc")
            lowered = (content.subject + " " + content.body).lower()
            for forbidden in ("desconto", "bônus", "bonus", "%", "moldura", "grátis", "gratis"):
                self.assertNotIn(forbidden, lowered, f"stage={stage} contém '{forbidden}'")

    def test_whatsapp_never_mentions_discount_or_bonus(self):
        for stage in (Stage.ONE_HOUR, Stage.ONE_DAY, Stage.THREE_DAYS):
            content = build_whatsapp(stage, first_name="Anna", recovery_url="https://x.test/r/abc")
            lowered = content.body.lower()
            for forbidden in ("desconto", "bônus", "bonus", "%", "moldura", "grátis", "gratis"):
                self.assertNotIn(forbidden, lowered, f"stage={stage} contém '{forbidden}'")

    def test_whatsapp_body_includes_recovery_link(self):
        content = build_whatsapp(Stage.ONE_HOUR, first_name="Anna", recovery_url="https://x.test/r/abc")
        self.assertIn("https://x.test/r/abc", content.body)


class CartRecoveryMessageModelTests(TestCase):
    def test_uniqueness_prevents_double_send_record(self):
        user = make_user()
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))
        CartRecoveryMessage.objects.create(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL, status=Status.SENT)
        with self.assertRaises(IntegrityError):
            CartRecoveryMessage.objects.create(
                draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL, status=Status.SENT
            )


class RecoveryLinkTests(TestCase):
    def test_raises_for_anonymous_draft(self):
        draft = ExperienceDraft.objects.create(owner=None, claim_token="tok123")
        with self.assertRaises(ValueError):
            create_recovery_link(draft)

    def test_creates_a_working_link(self):
        user = make_user()
        draft = make_abandoned_draft(user, age=timedelta(hours=1))
        url = create_recovery_link(draft)
        self.assertIn("/r/", url)
        token = url.rsplit("/r/", 1)[1]
        record = RecoveryLoginToken.objects.get(token=token)
        self.assertEqual(record.user_id, user.id)
        self.assertEqual(record.draft_id, draft.id)
        self.assertIsNone(record.used_at)


class RecoveryRedeemViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_redeems_a_valid_token(self):
        user = make_user()
        draft = make_abandoned_draft(user, age=timedelta(hours=1))
        url = create_recovery_link(draft)
        token = url.rsplit("/r/", 1)[1]

        response = self.client.post("/api/recovery/redeem/", {"token": token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["draft_id"], str(draft.id))
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_is_single_use(self):
        user = make_user()
        draft = make_abandoned_draft(user, age=timedelta(hours=1))
        url = create_recovery_link(draft)
        token = url.rsplit("/r/", 1)[1]

        first = self.client.post("/api/recovery/redeem/", {"token": token}, format="json")
        second = self.client.post("/api/recovery/redeem/", {"token": token}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_token_is_rejected(self):
        user = make_user()
        draft = make_abandoned_draft(user, age=timedelta(hours=1))
        record = RecoveryLoginToken.objects.create(
            token="expired-token-abc",
            user=user,
            draft=draft,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        response = self.client.post("/api/recovery/redeem/", {"token": record.token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_token_is_rejected(self):
        response = self.client.post("/api/recovery/redeem/", {"token": "does-not-exist"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RecoveryPreservesMediaEndToEndTests(TestCase):
    """Ponto 9/10 da auditoria: abrir um draft pelo link de recuperação
    nunca perde tema/fotos/vídeos — reusa 100% o endpoint de detalhe de
    draft já existente (get_accessible_draft_or_404), então não há nenhum
    caminho de código NOVO que possa reintroduzir o bug de CORS já
    corrigido anteriormente (aquele era especificamente sobre o header
    X-Draft-Claim-Token em preflight de draft anônimo — não existe aqui,
    porque o resgate sempre autentica de verdade antes)."""

    def test_redeemed_session_reads_theme_and_media_back_intact(self):
        user = make_user()
        draft = make_abandoned_draft(
            user,
            age=timedelta(hours=1, minutes=5),
            theme="universe",
            letter="Carta completa com fotos.",
        )
        Media.objects.create(
            draft=draft,
            media_type=Media.Type.PHOTO,
            storage_key=f"drafts/{draft.id}/photos/one.jpg",
            original_filename="one.jpg",
            mime_type="image/jpeg",
            size_bytes=1234,
            upload_status=Media.UploadStatus.UPLOADED,
            caption="Nosso primeiro encontro",
        )
        Media.objects.create(
            draft=draft,
            media_type=Media.Type.VIDEO,
            storage_key=f"drafts/{draft.id}/videos/one.mp4",
            original_filename="one.mp4",
            mime_type="video/mp4",
            size_bytes=5678,
            upload_status=Media.UploadStatus.UPLOADED,
        )

        recovery_url = create_recovery_link(draft)
        token = recovery_url.rsplit("/r/", 1)[1]

        client = APIClient()
        redeem_response = client.post("/api/recovery/redeem/", {"token": token}, format="json")
        self.assertEqual(redeem_response.status_code, status.HTTP_200_OK)

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {redeem_response.data['access']}")
        draft_response = client.get(f"/api/experiences/drafts/{draft.id}/")

        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)
        self.assertEqual(draft_response.data["theme"], "universe")
        self.assertEqual(draft_response.data["letter"], "Carta completa com fotos.")
        media = draft_response.data["media"]
        self.assertEqual(len(media), 2)
        self.assertEqual({item["media_type"] for item in media}, {"photo", "video"})
        self.assertEqual({item["upload_status"] for item in media}, {"uploaded"})


class WhatsAppServiceTests(TestCase):
    def test_not_configured_by_default(self):
        self.assertFalse(is_whatsapp_configured())

    def test_raises_without_credentials(self):
        with self.assertRaises(WhatsAppNotConfiguredError):
            send_whatsapp_template(to_phone="5511999999999", template_name="cart_1h", body_params=["Anna"])

    @override_settings(WHATSAPP_API_TOKEN="token", WHATSAPP_PHONE_NUMBER_ID="123")
    def test_raises_without_template_name(self):
        with self.assertRaises(WhatsAppNotConfiguredError):
            send_whatsapp_template(to_phone="5511999999999", template_name="", body_params=["Anna"])


class CartRecoveryCommandTests(TestCase):
    def test_sends_email_and_skips_whatsapp_without_phone_at_1h(self):
        user = make_user("anna@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        run_command()

        email_msg = CartRecoveryMessage.objects.get(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL)
        whatsapp_msg = CartRecoveryMessage.objects.get(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.WHATSAPP)

        self.assertEqual(email_msg.status, Status.SENT)
        self.assertEqual(whatsapp_msg.status, Status.SKIPPED_NO_CONTACT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("presente", mail.outbox[0].subject.lower())

    def test_sends_whatsapp_when_phone_and_template_are_configured(self):
        user = make_user("anna2@example.com", phone="5511999999999")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        with override_settings(
            WHATSAPP_API_TOKEN="token",
            WHATSAPP_PHONE_NUMBER_ID="123",
            WHATSAPP_TEMPLATES={"1h": "cart_1h", "24h": "", "72h": ""},
        ), patch("apps.recovery.management.commands.cart_recovery.send_whatsapp_template") as mocked_send:
            run_command()

        whatsapp_msg = CartRecoveryMessage.objects.get(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.WHATSAPP)
        self.assertEqual(whatsapp_msg.status, Status.SENT)
        mocked_send.assert_called_once()
        self.assertEqual(mocked_send.call_args.kwargs["to_phone"], "5511999999999")

    def test_never_sends_twice_for_the_same_stage(self):
        user = make_user("anna3@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        run_command()
        run_command()

        self.assertEqual(
            CartRecoveryMessage.objects.filter(draft=draft, stage=Stage.ONE_HOUR).count(), 2  # email + whatsapp
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_draft_still_too_fresh_is_never_touched(self):
        user = make_user("anna4@example.com")
        draft = make_abandoned_draft(user, age=timedelta(minutes=10))

        run_command()

        self.assertFalse(CartRecoveryMessage.objects.filter(draft=draft).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_empty_draft_is_never_considered_abandoned(self):
        user = make_user("anna5@example.com")
        draft = make_abandoned_draft(
            user, age=timedelta(hours=1, minutes=5), title="", recipient_name="", letter="", short_message=""
        )

        run_command()

        self.assertFalse(CartRecoveryMessage.objects.filter(draft=draft).exists())

    def test_anonymous_draft_is_never_considered(self):
        draft = ExperienceDraft.objects.create(
            owner=None, claim_token="tok-abc", title="Presente", status=ExperienceDraft.Status.DRAFT
        )
        ExperienceDraft.objects.filter(pk=draft.pk).update(updated_at=timezone.now() - timedelta(hours=1, minutes=5))

        run_command()

        self.assertFalse(CartRecoveryMessage.objects.filter(draft=draft).exists())

    def test_awaiting_payment_draft_is_out_of_scope(self):
        user = make_user("anna6@example.com")
        draft = make_abandoned_draft(
            user, age=timedelta(hours=1, minutes=5), status=ExperienceDraft.Status.AWAITING_PAYMENT
        )

        run_command()

        self.assertFalse(CartRecoveryMessage.objects.filter(draft=draft).exists())

    def test_only_email_filters_to_a_single_owner(self):
        target = make_user("anna7@example.com")
        other = make_user("someone-else@example.com")
        target_draft = make_abandoned_draft(target, age=timedelta(hours=1, minutes=5))
        other_draft = make_abandoned_draft(other, age=timedelta(hours=1, minutes=5))

        run_command(only_email="anna7@example.com")

        self.assertTrue(CartRecoveryMessage.objects.filter(draft=target_draft).exists())
        self.assertFalse(CartRecoveryMessage.objects.filter(draft=other_draft).exists())

    def test_only_draft_id_filters_to_a_single_draft(self):
        user = make_user("anna7b@example.com")
        target_draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))
        other_draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        run_command(only_draft_id=str(target_draft.id))

        self.assertTrue(CartRecoveryMessage.objects.filter(draft=target_draft).exists())
        self.assertFalse(CartRecoveryMessage.objects.filter(draft=other_draft).exists())

    def test_dry_run_never_writes_or_sends(self):
        user = make_user("anna8@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        run_command(dry_run=True)

        self.assertFalse(CartRecoveryMessage.objects.filter(draft=draft).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_never_creates_a_plan_discount_at_any_stage(self):
        user = make_user("anna9@example.com")
        make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))
        make_abandoned_draft(user, age=timedelta(hours=24, minutes=5))
        make_abandoned_draft(user, age=timedelta(hours=72, minutes=5))

        run_command()

        self.assertFalse(PlanDiscount.objects.filter(email__iexact=user.email).exists())

    def test_retries_after_a_transient_email_failure(self):
        user = make_user("anna10@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        with patch(
            "apps.recovery.management.commands.cart_recovery.send_recovery_email",
            side_effect=RuntimeError("resend indisponível"),
        ):
            run_command()

        failed = CartRecoveryMessage.objects.get(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL)
        self.assertEqual(failed.status, Status.FAILED)
        self.assertEqual(len(mail.outbox), 0)

        # Provedor volta a funcionar na próxima execução — o FAILED anterior
        # é retentado, nunca tratado como "já cuidei disso".
        run_command()

        failed.refresh_from_db()
        self.assertEqual(failed.status, Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_stale_in_progress_claim_is_reclaimed_and_retried(self):
        # Simula um processo anterior que morreu logo depois de reservar a
        # linha (nunca chegou a enviar nem a atualizar o status) — a
        # próxima execução precisa reconhecer isso como retentável, nunca
        # como "alguém já está cuidando disso".
        user = make_user("stale@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))
        stuck = CartRecoveryMessage.objects.create(
            draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL, status=Status.IN_PROGRESS
        )
        CartRecoveryMessage.objects.filter(pk=stuck.pk).update(updated_at=timezone.now() - timedelta(minutes=30))

        run_command(only_draft_id=str(draft.id))

        stuck.refresh_from_db()
        self.assertEqual(stuck.status, Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_fresh_in_progress_claim_is_never_touched_by_another_run(self):
        # Um IN_PROGRESS recente é presumido como "outro processo enviando
        # agora, de verdade" — nunca reaproveitado nem reenviado por cima.
        user = make_user("fresh-lock@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))
        CartRecoveryMessage.objects.create(
            draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL, status=Status.IN_PROGRESS
        )

        run_command(only_draft_id=str(draft.id))

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            CartRecoveryMessage.objects.filter(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL).count(), 1
        )

    def test_terminal_status_is_never_retried(self):
        user = make_user("anna11@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))
        # SKIPPED_NO_CONTACT é terminal — mesmo rodando de novo (e mesmo que
        # o usuário ganhe um telefone depois), o WhatsApp desta etapa nunca
        # é retentado automaticamente.
        run_command()
        whatsapp_msg = CartRecoveryMessage.objects.get(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.WHATSAPP)
        self.assertEqual(whatsapp_msg.status, Status.SKIPPED_NO_CONTACT)

        user.phone = "5511999999999"
        user.save(update_fields=["phone"])
        run_command()

        whatsapp_msg.refresh_from_db()
        self.assertEqual(whatsapp_msg.status, Status.SKIPPED_NO_CONTACT)

    def test_one_bad_draft_never_blocks_the_others(self):
        user1 = make_user("anna12@example.com")
        user2 = make_user("anna13@example.com")
        bad_draft = make_abandoned_draft(user1, age=timedelta(hours=1, minutes=5))
        good_draft = make_abandoned_draft(user2, age=timedelta(hours=1, minutes=5))

        real_create_link = create_recovery_link

        def boom(draft):
            if draft.id == bad_draft.id:
                raise RuntimeError("erro inesperado só neste draft")
            return real_create_link(draft)

        with patch("apps.recovery.management.commands.cart_recovery.create_recovery_link", side_effect=boom):
            run_command()

        # O draft com erro fica registrado como FAILED (retentável na
        # próxima execução, ver test_retries_after_a_transient_email_failure)
        # — nunca perdido silenciosamente, e principalmente nunca impede o
        # OUTRO draft de ser processado normalmente na mesma execução.
        bad_email_message = CartRecoveryMessage.objects.get(draft=bad_draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL)
        self.assertEqual(bad_email_message.status, Status.FAILED)
        self.assertTrue(CartRecoveryMessage.objects.filter(draft=good_draft, status=Status.SENT).exists())

    def test_batch_never_does_one_query_per_draft_for_existing_messages(self):
        user = make_user("anna14@example.com")
        for i in range(5):
            make_abandoned_draft(user, age=timedelta(hours=1, minutes=5), title=f"Presente {i}")

        with CaptureQueriesContext(connection) as ctx:
            run_command()

        existing_message_queries = [q for q in ctx.captured_queries if "cart_recovery_messages" in q["sql"] and "SELECT" in q["sql"].upper()]
        # Uma consulta de prefetch no início + no máximo uma leitura por
        # claim que precisou reconsultar a linha (nunca uma por draft só
        # para descobrir o que já existe) — bem abaixo de 5 (o número de
        # drafts) x 2 (canais) se fosse N+1 de verdade.
        self.assertLessEqual(len(existing_message_queries), 3)


class CartRecoveryConcurrencyTests(TransactionTestCase):
    """TransactionTestCase (não TestCase): as threads abaixo precisam de
    conexões de banco de verdade, cada uma com sua própria transação — um
    TestCase comum embrulha o teste inteiro numa única transação e as
    threads nunca veriam o commit umas das outras. Mesmo padrão já usado em
    apps.experiences.test_anonymous_draft para testar a corrida do claim de
    draft anônimo."""

    def test_two_concurrent_runs_never_send_the_same_stage_twice(self):
        user = make_user("concurrent@example.com")
        draft = make_abandoned_draft(user, age=timedelta(hours=1, minutes=5))

        barrier = threading.Barrier(2)
        original_claim = CartRecoveryCommand._claim

        def synced_claim(self, **kwargs):
            barrier.wait(timeout=5)
            return original_claim(self, **kwargs)

        errors = []

        def worker():
            try:
                run_command(only_draft_id=str(draft.id))
            except Exception as exc:  # pragma: no cover - só para não perder o erro da thread
                errors.append(exc)
            finally:
                connection.close()

        # Patch aplicado UMA vez, fora das threads: as duas threads chamam
        # a MESMA função synced_claim (que já fecha sobre original_claim) —
        # nunca duas threads mexendo ao mesmo tempo no bookkeeping de
        # patch/unpatch do mock, que não é garantidamente thread-safe.
        with patch.object(CartRecoveryCommand, "_claim", synced_claim):
            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(
            CartRecoveryMessage.objects.filter(draft=draft, stage=Stage.ONE_HOUR, channel=Channel.EMAIL).count(), 1
        )
        self.assertEqual(len(mail.outbox), 1)

