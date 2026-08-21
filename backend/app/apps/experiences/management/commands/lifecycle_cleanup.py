"""Etapa 9B.3 — Preview read-only de limpeza de lifecycle, a partir da
política de retenção aprovada na Etapa 9B.2.

NÃO apaga, NÃO atualiza, NÃO cria nada — mesmo contrato de
lifecycle_inventory (Etapa 9B.1), do qual este comando reaproveita as
queries de contagem. A diferença é que este comando aplica os CORTES DE
RETENÇÃO já aprovados para classificar cada linha em duas listas: "seria
removida" (candidatos) e "nunca será removida automaticamente" (protegida
por regra de negócio, não por falta de implementação).

Esta fase (9B.3) NÃO IMPLEMENTA --apply. Isto é deliberado, não um
esquecimento: a exclusão real só entra em uma etapa posterior, autorizada
separadamente, depois de este relatório ter sido revisado. Não existe
nenhum caminho de código aqui que grave ou apague qualquer linha, objeto R2
ou arquivo.

Regra de ouro (nunca automatizado, nesta ferramenta ou em qualquer futura):
Payment aprovado, Draft PAID e Draft PUBLISHED nunca entram em rotina
automática de limpeza — aparecem no relatório só como alerta/inventário.

Cortes de retenção aplicados (aprovados na 9B.2, todos com flag de
override para testes/ajuste sem precisar de deploy):

- Draft `draft` (nunca avançou), sem nenhum Payment: 30 dias sem updated_at.
- Draft `payment_failed`: 30 dias sem updated_at (ver ATENÇÃO no relatório:
  Payment.draft é on_delete=PROTECT — um Draft com Payment associado NÃO
  PODE ser hard-deleted enquanto o Payment existir; ver seção de riscos).
- Media PENDING além do cutoff: settings.PENDING_MEDIA_EXPIRATION_MINUTES
  (mesmo prazo já usado por services.media_cleanup.cleanup_abandoned_media,
  aqui aplicado a TODOS os drafts, não só ao que está sendo editado agora).
- Media FAILED: 7 dias desde created_at.
- Objetos R2 sem referência no banco (órfãos): 30 dias de grace period
  (só com --check-r2, usando o LastModified do próprio objeto).

Nunca candidatos a remoção automática (sempre no bloco "never_removed"):
Draft PAID sem publicação, Draft PUBLISHED expirado, todo Payment em
status terminal (histórico financeiro), o invariante "Payment ativo com
Draft fora de AWAITING_PAYMENT" (requer payment_reconcile primeiro, nunca
esta ferramenta), objetos R2 referenciados no banco mas ausentes no bucket,
e WebhookEvent (só inventariado — política de retenção própria ainda não
definida).

Uso mínimo (o único suportado nesta fase — ver --dry-run abaixo):
    python manage.py lifecycle_cleanup --dry-run
    python manage.py lifecycle_cleanup --dry-run --check-r2
"""

from __future__ import annotations

import json
from datetime import timedelta

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.payments.models import Payment, WebhookEvent

from ...models import ExperienceDraft, Media
from ...storage import get_r2_client, r2_is_configured

DEFAULT_DRAFT_ABANDONED_DAYS = 30
DEFAULT_PAYMENT_FAILED_DAYS = 30
DEFAULT_MEDIA_FAILED_DAYS = 7
DEFAULT_R2_ORPHAN_GRACE_DAYS = 30
SAMPLE_LIMIT = 20


def _age_days(moment) -> float | None:
    if moment is None:
        return None
    return round((timezone.now() - moment).total_seconds() / 86400, 1)


class Command(BaseCommand):
    help = (
        "Etapa 9B.3: preview read-only de limpeza de lifecycle, aplicando a "
        "política de retenção aprovada na 9B.2. Nunca escreve no banco nem "
        "no R2 — só lê e classifica. --apply não existe nesta fase (ver "
        "docstring do módulo)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Obrigatório nesta fase (9B.3) — mesmo racional do "
                "lifecycle_inventory: o comando é sempre somente-leitura, "
                "mas a flag é exigida para deixar explícito no comando "
                "usado que nenhuma exclusão está sendo feita, e para "
                "manter a mesma forma de invocação que uma futura etapa "
                "de --apply vai exigir."
            ),
        )
        parser.add_argument("--draft-abandoned-days", type=int, default=DEFAULT_DRAFT_ABANDONED_DAYS)
        parser.add_argument("--payment-failed-days", type=int, default=DEFAULT_PAYMENT_FAILED_DAYS)
        parser.add_argument("--media-failed-days", type=int, default=DEFAULT_MEDIA_FAILED_DAYS)
        parser.add_argument("--r2-orphan-grace-days", type=int, default=DEFAULT_R2_ORPHAN_GRACE_DAYS)
        parser.add_argument(
            "--stale-media-minutes",
            type=int,
            default=None,
            help="Default: settings.PENDING_MEDIA_EXPIRATION_MINUTES (mesmo prazo do lifecycle_inventory).",
        )
        parser.add_argument(
            "--check-r2",
            action="store_true",
            help="Lista o bucket R2 para calcular órfãos além do grace period (rede real, opcional).",
        )
        parser.add_argument("--r2-list-limit", type=int, default=5000)
        parser.add_argument("--format", choices=["text", "json"], default="text")

    def handle(self, *args, **options):
        if not options["dry_run"]:
            raise CommandError(
                "Etapa 9B.3: este comando só suporta --dry-run no momento — "
                "não existe --apply nesta fase. Rode: "
                "python manage.py lifecycle_cleanup --dry-run"
            )

        report = self.build_report(
            draft_abandoned_days=options["draft_abandoned_days"],
            payment_failed_days=options["payment_failed_days"],
            media_failed_days=options["media_failed_days"],
            r2_orphan_grace_days=options["r2_orphan_grace_days"],
            stale_media_minutes=options["stale_media_minutes"],
            check_r2=options["check_r2"],
            r2_list_limit=options["r2_list_limit"],
        )

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._render_text(report)

    # ------------------------------------------------------------------
    # Etapa 9B.4: extraído de handle() para ser reutilizável fora do CLI —
    # apps.ops importa esta classe e chama build_report() diretamente, com
    # valores já validados (nunca via argparse/Namespace), para nunca
    # duplicar estas queries.
    # ------------------------------------------------------------------

    def build_report(
        self,
        *,
        draft_abandoned_days: int = DEFAULT_DRAFT_ABANDONED_DAYS,
        payment_failed_days: int = DEFAULT_PAYMENT_FAILED_DAYS,
        media_failed_days: int = DEFAULT_MEDIA_FAILED_DAYS,
        r2_orphan_grace_days: int = DEFAULT_R2_ORPHAN_GRACE_DAYS,
        stale_media_minutes: int | None = None,
        check_r2: bool = False,
        r2_list_limit: int = 5000,
    ) -> dict:
        resolved_stale_media_minutes = (
            stale_media_minutes if stale_media_minutes is not None else settings.PENDING_MEDIA_EXPIRATION_MINUTES
        )

        policy = {
            "draft_abandoned_days": draft_abandoned_days,
            "payment_failed_days": payment_failed_days,
            "media_pending_minutes": resolved_stale_media_minutes,
            "media_failed_days": media_failed_days,
            "r2_orphan_grace_days": r2_orphan_grace_days,
        }

        report = {
            "generated_at": timezone.now().isoformat(),
            "mode": (
                "dry-run (somente leitura — nenhuma exclusão foi ou será feita; "
                "--apply não existe nesta fase, ver Etapa 9B.4)"
            ),
            "policy": policy,
            "candidates": {
                "draft_abandoned": self._draft_abandoned(draft_abandoned_days),
                "draft_payment_failed": self._draft_payment_failed(payment_failed_days),
                "media_pending_stale": self._media_pending_stale(resolved_stale_media_minutes),
                "media_failed_stale": self._media_failed_stale(media_failed_days),
            },
            "never_removed": {
                "draft_paid_unpublished": self._draft_paid_unpublished(),
                "draft_published_expired": self._draft_published_expired(),
                "payment_financial_terminal": self._payment_financial_terminal(),
                "payment_invariant_inconsistent": self._payment_invariant_inconsistent(),
                "webhook_events": self._webhook_events(),
            },
        }

        if check_r2:
            r2_candidates, r2_never = self._r2(grace_days=r2_orphan_grace_days, list_limit=r2_list_limit)
            report["candidates"]["r2_orphans_past_grace"] = r2_candidates
            report["never_removed"]["r2_missing_but_referenced"] = r2_never
        else:
            report["candidates"]["r2_orphans_past_grace"] = {
                "checked": False,
                "reason": "Passe --check-r2 para habilitar (faz chamadas de rede reais).",
            }
            report["never_removed"]["r2_missing_but_referenced"] = {
                "checked": False,
                "reason": "Passe --check-r2 para habilitar (faz chamadas de rede reais).",
            }

        return report

    # ------------------------------------------------------------------
    # Candidatos (leitura + classificação — nenhuma escrita)
    # ------------------------------------------------------------------

    def _draft_abandoned(self, days: int) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        qs = ExperienceDraft.objects.filter(status=ExperienceDraft.Status.DRAFT, updated_at__lt=cutoff)

        # Rede de segurança, mesmo padrão defensivo do lifecycle_inventory:
        # um Draft em status DRAFT nunca deveria ter Payment (ver
        # DraftDeletionService, que também exige isso) — excluído dos
        # candidatos se acontecer, e contado à parte para investigação.
        with_payment = qs.filter(payments__isnull=False).distinct()
        clean_qs = qs.exclude(payments__isnull=False)

        return {
            "count": clean_qs.count(),
            "excluded_unexpectedly_has_payment": with_payment.count(),
            "sample_ids": list(clean_qs.order_by("updated_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "reason": f"status=draft, sem nenhum Payment, sem atualização há mais de {days} dias.",
            "would_delete_media_and_r2_too": True,
        }

    def _draft_payment_failed(self, days: int) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        qs = ExperienceDraft.objects.filter(
            status=ExperienceDraft.Status.PAYMENT_FAILED, updated_at__lt=cutoff
        )

        # Um Draft payment_failed NÃO deveria ter Payment ativo (esse é
        # exatamente o invariante da Etapa 9B.2 — ver
        # _payment_invariant_inconsistent) — mas dados legados anteriores à
        # correção da 9B.3 em checkout_service podem violar isso. Excluído
        # dos candidatos e contado à parte: um Draft com pagamento ainda em
        # andamento nunca pode ser tratado como "abandonado", idade nenhuma
        # justifica isso — precisa passar por payment_reconcile primeiro.
        with_active_payment = qs.filter(payments__status__in=Payment.ACTIVE_STATUSES).distinct()
        clean_qs = qs.exclude(payments__status__in=Payment.ACTIVE_STATUSES)

        return {
            "count": clean_qs.count(),
            "excluded_has_active_payment_requires_reconcile_first": with_active_payment.count(),
            "sample_ids": list(clean_qs.order_by("updated_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "reason": f"status=payment_failed, sem atualização há mais de {days} dias.",
            "blocked_by_protect_constraint": True,
            "warning": (
                "Payment.draft é on_delete=PROTECT: nenhum destes Drafts pode "
                "ser hard-deleted enquanto o(s) Payment(s) dele existir(em), e a "
                "regra de ouro proíbe apagar Payment automaticamente. Uma "
                "futura Etapa --apply precisa de uma decisão de produto "
                "separada aqui (ex.: soft-delete/anonimização do conteúdo do "
                "Draft mantendo a linha e o Payment intactos) — não é possível "
                "hard-deletar este grupo com o schema atual."
            ),
        }

    def _media_pending_stale(self, stale_minutes: int) -> dict:
        cutoff = timezone.now() - timedelta(minutes=stale_minutes)
        qs = Media.objects.filter(upload_status=Media.UploadStatus.PENDING, created_at__lt=cutoff)
        return {
            "count": qs.count(),
            "sample_ids": list(qs.order_by("created_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "reason": (
                f"upload_status=pending, criada há mais de {stale_minutes}min "
                "(mesmo prazo e mesma regra de services.media_cleanup."
                "cleanup_abandoned_media, aqui aplicada a todos os drafts)."
            ),
            "existing_reference_implementation": "apps.experiences.services.media_cleanup.cleanup_abandoned_media",
        }

    def _media_failed_stale(self, days: int) -> dict:
        cutoff = timezone.now() - timedelta(days=days)
        qs = Media.objects.filter(upload_status=Media.UploadStatus.FAILED, created_at__lt=cutoff)
        return {
            "count": qs.count(),
            "sample_ids": list(qs.order_by("created_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "reason": f"upload_status=failed, criada há mais de {days} dias.",
        }

    # ------------------------------------------------------------------
    # Nunca removidos automaticamente (informativo/alerta apenas)
    # ------------------------------------------------------------------

    def _draft_paid_unpublished(self) -> dict:
        qs = ExperienceDraft.objects.filter(status=ExperienceDraft.Status.PAID)
        oldest = qs.order_by("updated_at").values_list("id", "updated_at").first()
        return {
            "count": qs.count(),
            "sample_ids": list(qs.order_by("updated_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "oldest_updated_at": oldest[1].isoformat() if oldest else None,
            "oldest_age_days": _age_days(oldest[1]) if oldest else None,
            "reason": (
                "REGRA DE OURO: cliente já pagou — nunca apagado automaticamente. "
                "Só alerta/inventário para investigação manual (possível fricção "
                "no fluxo de publicação)."
            ),
        }

    def _draft_published_expired(self) -> dict:
        qs = ExperienceDraft.objects.filter(
            status=ExperienceDraft.Status.PUBLISHED, expires_at__isnull=False, expires_at__lt=timezone.now()
        )
        return {
            "count": qs.count(),
            "sample_ids": list(qs.order_by("expires_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "reason": (
                "Decisão explícita (Etapa 9B.2/9B.3): mantido banco e mídia/R2 "
                "até existir uma política de renovação definida — não apagado "
                "nesta primeira versão."
            ),
        }

    def _payment_financial_terminal(self) -> dict:
        terminal_statuses = [s for s in Payment.Status.values if s not in Payment.ACTIVE_STATUSES]
        qs = Payment.objects.filter(status__in=terminal_statuses)
        by_status = {s: qs.filter(status=s).count() for s in terminal_statuses}
        return {
            "count": qs.count(),
            "by_status": by_status,
            "reason": (
                "REGRA DE OURO: histórico financeiro — nunca apagado "
                "automaticamente. Arquivamento (não exclusão) é decisão de "
                "produto/compliance separada."
            ),
        }

    def _payment_invariant_inconsistent(self) -> dict:
        qs = Payment.objects.filter(status__in=Payment.ACTIVE_STATUSES).exclude(
            draft__status=ExperienceDraft.Status.AWAITING_PAYMENT
        )
        return {
            "count": qs.count(),
            "sample_ids": list(qs.order_by("updated_at").values_list("id", flat=True)[:SAMPLE_LIMIT]),
            "reason": (
                "Payment ativo com Draft fora de awaiting_payment (invariante "
                "da Etapa 9B.2) — nunca apagado automaticamente. Requer "
                "'python manage.py payment_reconcile --dry-run' primeiro; "
                "correção real fica para uma etapa de aplicação separada."
            ),
        }

    def _webhook_events(self) -> dict:
        qs = WebhookEvent.objects.all()
        by_status = {s: qs.filter(status=s).count() for s, _ in WebhookEvent.Status.choices}
        oldest = qs.order_by("created_at").values_list("created_at", flat=True).first()
        return {
            "count": qs.count(),
            "by_status": by_status,
            "oldest_age_days": _age_days(oldest),
            "reason": (
                "Incluído no inventário por decisão explícita da 9B.3, mas "
                "sem candidatos ainda: política de retenção própria para "
                "WebhookEvent ainda não foi definida (proposta pendente)."
            ),
        }

    # ------------------------------------------------------------------
    # R2 (só com --check-r2)
    # ------------------------------------------------------------------

    def _r2(self, *, grace_days: int, list_limit: int) -> tuple[dict, dict]:
        if not r2_is_configured():
            not_checked = {"checked": False, "reason": "R2 não configurado neste ambiente."}
            return not_checked, not_checked

        client = get_r2_client()
        bucket = settings.R2_BUCKET_NAME
        grace_cutoff = timezone.now() - timedelta(days=grace_days)

        known_keys = set(Media.objects.values_list("storage_key", flat=True))
        listed = []
        continuation_token = None
        truncated = False
        while len(listed) < list_limit:
            kwargs = {"Bucket": bucket, "Prefix": "drafts/", "MaxKeys": min(1000, list_limit - len(listed))}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            page = client.list_objects_v2(**kwargs)
            for obj in page.get("Contents", []):
                listed.append(obj)
            if page.get("IsTruncated"):
                continuation_token = page.get("NextContinuationToken")
                if len(listed) >= list_limit:
                    truncated = True
                    break
            else:
                break

        orphans = [obj for obj in listed if obj["Key"] not in known_keys]
        orphans_past_grace = [obj for obj in orphans if obj.get("LastModified") and obj["LastModified"] < grace_cutoff]
        orphans_within_grace = len(orphans) - len(orphans_past_grace)

        candidates = {
            "checked": True,
            "bucket": bucket,
            "bucket_objects_scanned": len(listed),
            "bucket_scan_truncated": truncated,
            "orphans_total": len(orphans),
            "orphans_within_grace_period_excluded": orphans_within_grace,
            "count": len(orphans_past_grace),
            "sample_keys": [o["Key"] for o in orphans_past_grace[:SAMPLE_LIMIT]],
            "reason": (
                f"Objeto sob drafts/ sem storage_key correspondente em Media, "
                f"com mais de {grace_days} dias desde o LastModified do "
                f"próprio objeto no R2 (nunca é servido a ninguém, ver "
                f"Etapa 9B.2)."
            ),
        }

        media_rows = list(Media.objects.all().values_list("id", "storage_key")[:SAMPLE_LIMIT])
        missing = []
        for media_id, storage_key in media_rows:
            try:
                client.head_object(Bucket=bucket, Key=storage_key)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in ("404", "NoSuchKey", "NotFound"):
                    missing.append(storage_key)

        never_removed = {
            "checked": True,
            "sample_checked": len(media_rows),
            "count": len(missing),
            "sample_keys": missing[:SAMPLE_LIMIT],
            "reason": (
                "Referenciado no banco mas ausente no bucket — nunca "
                "apagado/alterado automaticamente; apenas reportado (decisão "
                "explícita da Etapa 9B.2, requer investigação manual)."
            ),
        }

        return candidates, never_removed

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------

    def _render_text(self, report: dict) -> None:
        w = self.stdout.write
        w(f"Etapa 9B.3 — Preview de limpeza de lifecycle ({report['generated_at']})")
        w(f"Modo: {report['mode']}")
        w(f"Política: {report['policy']}")
        w("")

        w("=== CANDIDATOS (seriam removidos sob a política aprovada) ===")
        for key, data in report["candidates"].items():
            w(f"- {key}: {data}")
        w("")

        w("=== NUNCA REMOVIDOS AUTOMATICAMENTE (regra de negócio) ===")
        for key, data in report["never_removed"].items():
            w(f"- {key}: {data}")
