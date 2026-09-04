"""Fluxo de recuperação de carrinho abandonado — dispara e-mail/WhatsApp em
3 etapas (1h / 24h / 72h desde a última edição) para quem criou uma
experiência (ExperienceDraft) mas ainda não publicou.

Regra de negócio: este fluxo NUNCA oferece desconto, bônus ou qualquer
benefício além do que o produto já entrega — só um lembrete carinhoso (ver
apps.recovery.content). Não é um detalhe de copy: nenhum código aqui lê ou
grava PlanDiscount.

Uso pretendido: agendado (cron) rodando a cada 15-30 minutos. Não depende de
Celery/Redis (nenhum dos dois está configurado neste projeto ainda — ver
docs/ai/PROJECT_CONTEXT.md) — só precisa de QUALQUER agendador externo
chamando `python manage.py cart_recovery` (cron do próprio Render, por
exemplo), no mesmo espírito de lifecycle_cleanup e payment_reconcile.

Segurança contra concorrência (2 crons rodando ao mesmo tempo, um cron
atrasado sobrepondo o próximo, ou um processo que morreu no meio de um
envio): ver Command._claim — cada (draft, stage, channel) só é enviado por
QUEM CONSEGUIR RESERVAR a linha correspondente em CartRecoveryMessage
primeiro (UniqueConstraint + status=IN_PROGRESS como reserva), nunca por
"eu chequei antes de enviar" (isso teria uma janela de corrida real entre o
check e o send). Um FAILED (falha transitória do provedor) ou um
IN_PROGRESS mais velho que STALE_CLAIM_AFTER (processo anterior morreu no
meio) são elegíveis a nova tentativa; SENT/SKIPPED_* nunca são.

Elegibilidade de um draft para entrar no fluxo:
- status=draft (nunca chegou a abrir checkout — ver docstring de
  ExperienceDraft.Status). Um draft em awaiting_payment/payment_failed já
  decidiu comprar; é um problema de checkout/pagamento, não de "esqueceu
  que criou", e fica fora deste fluxo de propósito.
- owner IS NOT NULL (draft anônimo nunca reivindicado não tem para quem
  mandar e-mail — isso já é limpo separadamente por lifecycle_cleanup).
- pelo menos um campo de conteúdo preenchido (título, destinatário, carta
  ou mensagem curta) — um draft vazio (só o tipo/tema escolhidos) nunca é
  "abandono de um presente", é só alguém testando o fluxo.
- `updated_at` (não `created_at`) é o relógio de abandono: cada PATCH do
  wizard atualiza esse campo, então alguém ainda editando ativamente nunca
  entra numa janela por engano.

Uma exceção inesperada processando UM draft (bug específico daquele
registro, erro de rede não previsto) nunca aborta o resto da execução —
ver o try/except por draft dentro de handle().

Uso:
    python manage.py cart_recovery --dry-run
    python manage.py cart_recovery --dry-run --only-email cliente@example.com
    python manage.py cart_recovery --only-draft-id <uuid>
    python manage.py cart_recovery
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.experiences.models import ExperienceDraft
from apps.recovery.content import build_email, build_whatsapp
from apps.recovery.models import CartRecoveryMessage
from apps.recovery.services.email_sender import send_recovery_email
from apps.recovery.services.recovery_link import create_recovery_link
from apps.recovery.services.whatsapp_service import (
    WhatsAppNotConfiguredError,
    WhatsAppSendError,
    is_whatsapp_configured,
    send_whatsapp_template,
    template_name_for_stage,
)

logger = logging.getLogger(__name__)

Stage = CartRecoveryMessage.Stage
Channel = CartRecoveryMessage.Channel
Status = CartRecoveryMessage.Status

# Nunca retentados — um envio de verdade (ou uma ausência definitiva de
# canal) não é reconsiderado nas próximas execuções.
TERMINAL_STATUSES = (Status.SENT, Status.SKIPPED_NO_CONTACT, Status.SKIPPED_NOT_CONFIGURED)

# Acima disso, um IN_PROGRESS é tratado como "o processo que reservou isso
# morreu no meio do envio" — nunca fica preso para sempre. Bem acima do
# tempo real de uma chamada de e-mail/WhatsApp (segundos), para nunca
# competir com um envio genuinamente em andamento.
STALE_CLAIM_AFTER = timedelta(minutes=10)

# (idade mínima, idade máxima) desde updated_at para cada etapa entrar na
# janela de disparo. A folga de +6h sobre o alvo (1h/24h/72h) é só
# tolerância a atraso do agendador — a reserva via CartRecoveryMessage é
# quem de fato impede reenvio; essa janela só evita reconsiderar um draft
# muito antigo para sempre a cada execução.
STAGE_WINDOWS: dict[str, tuple[timedelta, timedelta]] = {
    Stage.ONE_HOUR: (timedelta(hours=1), timedelta(hours=7)),
    Stage.ONE_DAY: (timedelta(hours=24), timedelta(hours=30)),
    Stage.THREE_DAYS: (timedelta(hours=72), timedelta(hours=78)),
}

HAS_CONTENT = Q(title__gt="") | Q(recipient_name__gt="") | Q(letter__gt="") | Q(short_message__gt="")


@dataclass
class SendOutcome:
    status: str
    detail: str = ""


class Command(BaseCommand):
    help = "Dispara e-mail/WhatsApp de recuperação de carrinho abandonado (etapas 1h/24h/72h). Nunca oferece desconto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só mostra o que seria enviado — nunca envia, nunca escreve no banco.",
        )
        parser.add_argument(
            "--only-email",
            default="",
            help="Restringe a um único e-mail de dono (case-insensitive) — para testar com segurança.",
        )
        parser.add_argument(
            "--only-draft-id",
            default="",
            help="Restringe a um único draft por id — para reenviar/testar manualmente um caso pontual.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        only_email: str = options["only_email"].strip()
        only_draft_id: str = options["only_draft_id"].strip()

        candidates = (
            ExperienceDraft.objects.filter(status=ExperienceDraft.Status.DRAFT, owner__isnull=False)
            .filter(HAS_CONTENT)
            .select_related("owner")
        )
        if only_email:
            candidates = candidates.filter(owner__email__iexact=only_email)
        if only_draft_id:
            candidates = candidates.filter(id=only_draft_id)
        candidates = list(candidates)

        # UMA consulta para todo o lote, nunca uma por (draft, stage) — ver
        # docstring do módulo. Só uma otimização: a decisão de verdade
        # (quem pode enviar agora) continua sendo _claim(), que sempre
        # relê o estado atual da linha antes de reservar.
        existing_lookup: dict[tuple[str, str, str], CartRecoveryMessage] = {
            (str(message.draft_id), message.stage, message.channel): message
            for message in CartRecoveryMessage.objects.filter(draft_id__in=[draft.id for draft in candidates])
        }

        now = timezone.now()
        total_sent = 0
        total_skipped = 0

        for draft in candidates:
            try:
                sent, skipped = self._process_draft(
                    draft=draft, now=now, existing_lookup=existing_lookup, dry_run=dry_run
                )
                total_sent += sent
                total_skipped += skipped
            except Exception:
                # Um bug/erro específico deste draft nunca pode impedir os
                # outros de serem processados nesta mesma execução.
                logger.exception("cart_recovery.draft_processing_failed draft=%s", draft.id)

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"cart_recovery: {total_sent} enviadas, {total_skipped} puladas."))

    def _process_draft(self, *, draft, now, existing_lookup, dry_run: bool) -> tuple[int, int]:
        sent = 0
        skipped = 0
        elapsed = now - draft.updated_at

        for stage, (min_age, max_age) in STAGE_WINDOWS.items():
            if not (min_age <= elapsed <= max_age):
                continue

            for channel in (Channel.EMAIL, Channel.WHATSAPP):
                existing = existing_lookup.get((str(draft.id), stage, channel))
                if existing is not None and existing.status in TERMINAL_STATUSES:
                    continue
                if (
                    existing is not None
                    and existing.status == Status.IN_PROGRESS
                    and now - existing.updated_at < STALE_CLAIM_AFTER
                ):
                    continue  # outro processo está enviando isso agora

                if dry_run:
                    outcome = self._send_one(draft=draft, stage=stage, channel=channel, dry_run=True)
                    self._print_dry_run(draft=draft, stage=stage, channel=channel, outcome=outcome)
                    continue

                claimed = self._claim(draft=draft, stage=stage, channel=channel)
                if claimed is None:
                    continue  # perdeu a corrida para outro processo entre o prefetch e agora

                outcome = self._send_one(draft=draft, stage=stage, channel=channel, dry_run=False)
                claimed.status = outcome.status
                claimed.error_detail = outcome.detail
                claimed.save(update_fields=["status", "error_detail", "updated_at"])

                if outcome.status == Status.SENT:
                    sent += 1
                    logger.info("cart_recovery.sent stage=%s channel=%s", stage, channel)
                else:
                    skipped += 1
                    logger.info("cart_recovery.skipped stage=%s channel=%s status=%s", stage, channel, outcome.status)

        return sent, skipped

    def _claim(self, *, draft, stage, channel) -> CartRecoveryMessage | None:
        """Reserva (draft, stage, channel) para ESTE processo enviar agora.
        Devolve a linha reservada (status=IN_PROGRESS) se ganhou a corrida,
        ou None se não deve enviar (outro processo já reservou/enviou
        agora, ou já é um estado terminal). Ver docstring do módulo."""

        try:
            with transaction.atomic():
                return CartRecoveryMessage.objects.create(
                    draft=draft, stage=stage, channel=channel, status=Status.IN_PROGRESS
                )
        except IntegrityError:
            pass  # já existe uma linha — decide abaixo se pode reaproveitar

        with transaction.atomic():
            existing = CartRecoveryMessage.objects.select_for_update().get(draft=draft, stage=stage, channel=channel)

            if existing.status in TERMINAL_STATUSES:
                return None
            if existing.status == Status.IN_PROGRESS and timezone.now() - existing.updated_at < STALE_CLAIM_AFTER:
                return None

            # FAILED (retry legítimo) ou IN_PROGRESS velho (processo
            # anterior morreu no meio do envio): reaproveita a MESMA linha
            # em vez de tentar criar outra (a UniqueConstraint nunca
            # permitiria uma segunda).
            existing.status = Status.IN_PROGRESS
            existing.error_detail = ""
            existing.save(update_fields=["status", "error_detail", "updated_at"])
            return existing

    def _print_dry_run(self, *, draft, stage, channel, outcome: SendOutcome) -> None:
        # backslashreplace: o console do Windows (cp1252) não imprime os
        # emojis do corpo do e-mail (ver outcome.detail com o assunto) —
        # isso já é só a prévia de terminal, nunca o conteúdo de verdade
        # enviado; sem isso, --dry-run derruba com UnicodeEncodeError em
        # vez de mostrar a prévia.
        line = (
            f"[dry-run] draft={draft.id} owner={draft.owner.email} "
            f"stage={stage} channel={channel} -> {outcome.status} {outcome.detail}"
        )
        self.stdout.write(line.encode("ascii", "backslashreplace").decode("ascii"))

    def _send_one(self, *, draft: ExperienceDraft, stage: str, channel: str, dry_run: bool) -> SendOutcome:
        owner = draft.owner

        if channel == Channel.WHATSAPP and not owner.phone:
            return SendOutcome(status=Status.SKIPPED_NO_CONTACT)

        if channel == Channel.WHATSAPP and not dry_run and not is_whatsapp_configured():
            return SendOutcome(status=Status.SKIPPED_NOT_CONFIGURED)

        # Um único try/except cobrindo TUDO (inclusive create_recovery_link
        # e a construção do conteúdo) — não só a chamada final de
        # envio: uma falha em QUALQUER ponto daqui vira FAILED (retentável
        # na próxima execução, ver Command._claim), nunca deixa a linha
        # travada em IN_PROGRESS esperando o timeout de
        # STALE_CLAIM_AFTER para se recuperar sozinha.
        try:
            recovery_url = "https://memoverse.com.br/r/<preview-only>" if dry_run else create_recovery_link(draft)

            if channel == Channel.EMAIL:
                content = build_email(stage, first_name=owner.first_name, recovery_url=recovery_url)
                if dry_run:
                    return SendOutcome(status=Status.SENT, detail=content.subject)
                send_recovery_email(to_email=owner.email, subject=content.subject, body=content.body)
                return SendOutcome(status=Status.SENT)

            content = build_whatsapp(stage, first_name=owner.first_name, recovery_url=recovery_url)
            if dry_run:
                template_name = template_name_for_stage(stage) or "(nenhum template configurado ainda)"
                return SendOutcome(status=Status.SENT, detail=f"template={template_name}")

            template_name = template_name_for_stage(stage)
            if not template_name:
                return SendOutcome(status=Status.SKIPPED_NOT_CONFIGURED)

            send_whatsapp_template(
                to_phone=owner.phone,
                template_name=template_name,
                body_params=[owner.first_name or "Olá", recovery_url],
            )
            return SendOutcome(status=Status.SENT)
        except (WhatsAppNotConfiguredError, WhatsAppSendError) as exc:
            logger.warning("cart_recovery.whatsapp_failed stage=%s", stage)
            return SendOutcome(status=Status.FAILED, detail=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001 - qualquer outra falha (provedor de e-mail, link de recuperação, etc.) vira um registro FAILED, nunca derruba o comando inteiro
            logger.warning("cart_recovery.send_failed stage=%s channel=%s", stage, channel)
            return SendOutcome(status=Status.FAILED, detail=str(exc)[:255])
