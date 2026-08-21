"""Etapa 9B.3 — Reconciliação read-only de Payment ativo contra o estado real
na Mercado Pago. NÃO decide, NÃO transiciona, NÃO apaga nada — só consulta a
Mercado Pago (chamada de rede real, só leitura: GET /v1/orders/{id}) e
reporta o que a reconciliação REAL (PaymentConfirmationService, já em
produção) faria se fosse chamada agora.

Por que isto existe (Etapa 9B.2): o único jeito hoje de um Payment "ativo
travado" avançar é o webhook da Mercado Pago chegar, ou o passo síncrono no
próprio momento do checkout. Se o webhook nunca chega (segredo mal
configurado, MP para de tentar, rede caiu), ou se o Payment nunca teve uma
Order criada do lado da MP (ver o invariante "Payment ativo com draft fora
de AWAITING_PAYMENT", também investigado na 9B.2), não existe hoje nenhum
mecanismo de fallback. Este comando é esse fallback — mas, nesta fase,
apenas o PREVIEW dele: nenhuma chamada de escrita à Mercado Pago é feita
(get_order é só leitura), e NENHUMA escrita no banco acontece em nenhuma
circunstância. A aplicação real (chamar de fato
PaymentConfirmationService.confirm_from_result) fica para uma etapa
posterior, autorizada separadamente.

Uso mínimo (o único suportado nesta fase — ver --dry-run abaixo):
    python manage.py payment_reconcile --dry-run
"""

from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta

from apps.experiences.models import ExperienceDraft

from ...models import Payment
from ...services.mercadopago_client import (
    MercadoPagoClient,
    MercadoPagoClientError,
    MercadoPagoConfigurationError,
)
from ...services.payment_confirmation_service import PaymentConfirmationService
from ...services.status_mapping import map_order_status

DEFAULT_STALE_MINUTES = 60
DEFAULT_LIMIT = 50


class Command(BaseCommand):
    help = (
        "Etapa 9B.3: reconciliação read-only de Payment ativo contra o "
        "estado real na Mercado Pago. Nunca escreve no banco nem chama "
        "nenhum endpoint de escrita da Mercado Pago — só consulta "
        "(GET /v1/orders/{id}) e reporta o que a aplicação real faria. "
        "Não aplica nenhuma transição (ver Etapa 9B.4)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Obrigatório nesta fase (9B.3). O comando é sempre "
                "somente-leitura em relação ao banco, com ou sem esta "
                "flag — ela é exigida mesmo assim para deixar explícito "
                "no comando exato usado que nenhuma transição está sendo "
                "aplicada, e para manter a mesma forma de invocação que "
                "uma futura etapa de aplicação real vai exigir para o "
                "preview."
            ),
        )
        parser.add_argument(
            "--stale-minutes",
            type=int,
            default=DEFAULT_STALE_MINUTES,
            help=(
                f"Só considera Payment ativo (pending/in_process/"
                f"action_required) sem atualização há pelo menos N minutos "
                f"(default: {DEFAULT_STALE_MINUTES}). Evita consultar a MP "
                f"para tentativas em andamento há segundos, que ainda "
                f"devem se resolver sozinhas pelo fluxo síncrono/webhook."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help=(
                f"Máximo de Payments consultados na Mercado Pago nesta "
                f"execução (default: {DEFAULT_LIMIT}) — protege contra "
                f"rajadas de chamadas de rede em produção."
            ),
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Formato do relatório (default: text).",
        )

    def handle(self, *args, **options):
        if not options["dry_run"]:
            raise CommandError(
                "Etapa 9B.3: este comando só suporta --dry-run no momento. "
                "Rode: python manage.py payment_reconcile --dry-run"
            )

        report = self.build_report(stale_minutes=options["stale_minutes"], limit=options["limit"])

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._render_text(report)

    # ------------------------------------------------------------------
    # Etapa 9B.4: extraído de handle() para ser reutilizável fora do CLI —
    # apps.ops importa esta classe e chama build_report() diretamente, com
    # valores já validados (nunca via argparse/Namespace), para nunca
    # duplicar estas queries nem a chamada de leitura à Mercado Pago.
    # ------------------------------------------------------------------

    def build_report(self, *, stale_minutes: int = DEFAULT_STALE_MINUTES, limit: int = DEFAULT_LIMIT) -> dict:
        cutoff = timezone.now() - timedelta(minutes=stale_minutes)

        candidates = list(
            Payment.objects.filter(status__in=Payment.ACTIVE_STATUSES, updated_at__lt=cutoff)
            .select_related("draft")
            .order_by("updated_at")[:limit]
        )

        without_order = [p for p in candidates if not p.mp_order_id]
        with_order = [p for p in candidates if p.mp_order_id]

        client = None
        client_error = None
        if with_order:
            try:
                client = MercadoPagoClient()
            except MercadoPagoConfigurationError as exc:
                client_error = str(exc)

        rows = []
        query_errors = 0
        for payment in with_order:
            if client is None:
                rows.append(self._row_for_query_error(payment, client_error or "Mercado Pago não configurada."))
                query_errors += 1
                continue
            try:
                result = client.get_order(order_id=payment.mp_order_id)
            except MercadoPagoClientError as exc:
                rows.append(self._row_for_query_error(payment, str(exc)))
                query_errors += 1
                continue
            rows.append(self._row_for_result(payment, result))

        report = {
            "generated_at": timezone.now().isoformat(),
            "mode": "dry-run (somente leitura — nenhuma escrita no banco; get_order é leitura na Mercado Pago)",
            "stale_minutes_used": stale_minutes,
            "limit_used": limit,
            "active_payments_matching_staleness": len(candidates),
            "candidates_capped": len(candidates) == limit,
            "without_mp_order_id": [self._row_for_no_order(p) for p in without_order],
            "queried": rows,
            "query_errors": query_errors,
        }

        return report

    # ------------------------------------------------------------------
    # Classificação (só leitura — nenhuma chamada a
    # PaymentConfirmationService.confirm_from_result acontece aqui)
    # ------------------------------------------------------------------

    @staticmethod
    def _row_for_no_order(payment: Payment) -> dict:
        return {
            "payment_id": str(payment.id),
            "draft_id": str(payment.draft_id),
            "local_status": payment.status,
            "draft_status": payment.draft.status,
            "draft_status_consistent": payment.draft.status == ExperienceDraft.Status.AWAITING_PAYMENT,
            "updated_at": payment.updated_at.isoformat(),
            "recommended_action": (
                "Sem mp_order_id — nunca existiu Order do lado da Mercado Pago; "
                "não é possível reconciliar via consulta. Requer decisão manual "
                "(ex.: cancelar localmente após grace period, ver Etapa 9B.2)."
            ),
        }

    @staticmethod
    def _row_for_query_error(payment: Payment, detail: str) -> dict:
        return {
            "payment_id": str(payment.id),
            "draft_id": str(payment.draft_id),
            "local_status": payment.status,
            "draft_status": payment.draft.status,
            "mp_order_id": payment.mp_order_id,
            "query_error": detail,
            "recommended_action": "Falha ao consultar a Mercado Pago — tentar novamente depois.",
        }

    @staticmethod
    def _row_for_result(payment: Payment, result) -> dict:
        mapped = map_order_status(result.status)
        next_status = PaymentConfirmationService._next_status(payment.status, mapped)
        would_change = next_status != payment.status
        draft_consistent = payment.draft.status == ExperienceDraft.Status.AWAITING_PAYMENT

        if not would_change:
            action = "Nenhuma mudança — Mercado Pago ainda reporta o mesmo estado (ou status não reconhecido)."
        elif next_status == Payment.Status.APPROVED:
            action = (
                "Aplicaria PaymentConfirmationService.confirm_from_result: "
                "Payment -> approved, Draft -> paid."
            )
        elif next_status in (Payment.Status.REJECTED, Payment.Status.CANCELLED, Payment.Status.EXPIRED):
            action = (
                f"Aplicaria PaymentConfirmationService.confirm_from_result: "
                f"Payment -> {next_status}"
                + (", Draft -> payment_failed." if draft_consistent else " (Draft já não está em awaiting_payment — no-op sobre o Draft).")
            )
        else:
            action = f"Aplicaria PaymentConfirmationService.confirm_from_result: Payment -> {next_status}."

        return {
            "payment_id": str(payment.id),
            "draft_id": str(payment.draft_id),
            "local_status": payment.status,
            "draft_status": payment.draft.status,
            "draft_status_consistent": draft_consistent,
            "mp_order_id": payment.mp_order_id,
            "mp_raw_status": result.status,
            "mapped_local_status": mapped,
            "would_transition_to": next_status if would_change else None,
            "recommended_action": action,
        }

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------

    def _render_text(self, report: dict) -> None:
        w = self.stdout.write
        w(f"Etapa 9B.3 — Reconciliação de Payment ({report['generated_at']})")
        w(f"Modo: {report['mode']}")
        w(
            f"Payments ativos parados há mais de {report['stale_minutes_used']}min: "
            f"{report['active_payments_matching_staleness']} (limite: {report['limit_used']}, "
            f"capado: {report['candidates_capped']})"
        )
        w("")

        w("SEM mp_order_id (não é possível reconciliar via consulta)")
        if not report["without_mp_order_id"]:
            w("- nenhum")
        for row in report["without_mp_order_id"]:
            w(
                f"- Payment {row['payment_id']} (draft {row['draft_id']}, "
                f"status={row['local_status']}, draft_status={row['draft_status']}, "
                f"consistente={row['draft_status_consistent']})"
            )
            w(f"    -> {row['recommended_action']}")
        w("")

        w("CONSULTADOS na Mercado Pago")
        if not report["queried"]:
            w("- nenhum")
        for row in report["queried"]:
            if "query_error" in row:
                w(f"- Payment {row['payment_id']} (draft {row['draft_id']}): ERRO — {row['query_error']}")
                continue
            w(
                f"- Payment {row['payment_id']} (draft {row['draft_id']}): "
                f"local={row['local_status']} mp={row['mp_raw_status']} "
                f"mapeado={row['mapped_local_status']} "
                f"mudaria_para={row['would_transition_to']}"
            )
            w(f"    -> {row['recommended_action']}")
        w("")
        w(f"Erros de consulta: {report['query_errors']}")
