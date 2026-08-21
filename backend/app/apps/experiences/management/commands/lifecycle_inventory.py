"""Etapa 9B.1 — Inventário read-only de lifecycle (ExperienceDraft/Payment/
Media/R2). NÃO apaga, NÃO atualiza, NÃO cria nada — só lê e reporta.

Esta fase é deliberadamente só um inventário: a política de retenção (por
quanto tempo um draft/Payment/mídia "abandonados" devem ser mantidos antes
de qualquer ação) ainda NÃO foi decidida em nenhum lugar do código, então
este comando não presume nenhum prazo além do único que já existe de fato
em produção — settings.PENDING_MEDIA_EXPIRATION_MINUTES, já usado por
apps.experiences.services.media_cleanup.cleanup_abandoned_media. Qualquer
outro corte de idade só aparece no relatório se for passado explicitamente
via flag; sem a flag, o comando reporta contagens/idades factuais, nunca uma
lista de "isto pode ser apagado".

Uso mínimo (o único suportado nesta fase — ver --dry-run abaixo):
    python manage.py lifecycle_inventory --dry-run

Uso com checagem real contra o R2 (rede, mais lento, opcional):
    python manage.py lifecycle_inventory --dry-run --check-r2
"""

from __future__ import annotations

import json
from datetime import timedelta

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min
from django.utils import timezone

from apps.payments.models import Payment

from ...models import ExperienceDraft, Media
from ...storage import get_r2_client, r2_is_configured


def _age_days(moment) -> float | None:
    if moment is None:
        return None
    return round((timezone.now() - moment).total_seconds() / 86400, 1)


class Command(BaseCommand):
    help = (
        "Etapa 9B.1: inventário read-only do lifecycle de ExperienceDraft/"
        "Payment/Media/R2. Nunca escreve no banco nem no R2 — só lê e "
        "reporta. Não implementa nenhuma exclusão (ver Etapa 9B.2)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Obrigatório nesta fase (9B.1). O comando é sempre "
                "somente-leitura, com ou sem esta flag — ela é exigida "
                "mesmo assim para deixar explícito no comando exato usado "
                "que nenhuma escrita está sendo feita, e para manter a "
                "mesma forma de invocação que uma futura Etapa 9B.2 (modo "
                "de execução real) vai exigir para o preview."
            ),
        )
        parser.add_argument(
            "--stale-media-minutes",
            type=int,
            default=None,
            help=(
                "Corte, em minutos, para contar Media PENDING como "
                "'parada'. Default: settings.PENDING_MEDIA_EXPIRATION_MINUTES "
                "(o único prazo que já existe de fato no código hoje, via "
                "media_cleanup.cleanup_abandoned_media) — nenhum novo prazo "
                "é inventado aqui, só reaproveitado."
            ),
        )
        parser.add_argument(
            "--check-r2",
            action="store_true",
            help=(
                "Faz checagens reais (rede) contra o bucket R2 configurado: "
                "confirma se objetos referenciados no banco existem, e lista "
                "o bucket para detectar objetos sem referência no banco. "
                "Desligado por default (evita chamadas de rede em execuções "
                "rotineiras/testes). Requer R2 configurado."
            ),
        )
        parser.add_argument(
            "--r2-sample-limit",
            type=int,
            default=200,
            help="Máximo de linhas de Media verificadas contra o R2 (default: 200).",
        )
        parser.add_argument(
            "--r2-list-limit",
            type=int,
            default=5000,
            help="Máximo de objetos listados do bucket R2 (default: 5000).",
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
                "Etapa 9B.1: este comando só suporta --dry-run no momento. "
                "Rode: python manage.py lifecycle_inventory --dry-run"
            )

        report = self.build_report(
            stale_media_minutes=options["stale_media_minutes"],
            check_r2=options["check_r2"],
            r2_sample_limit=options["r2_sample_limit"],
            r2_list_limit=options["r2_list_limit"],
        )

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._render_text(report)

    # ------------------------------------------------------------------
    # Etapa 9B.4: extraído de handle() para ser reutilizável fora do CLI —
    # apps.ops (o painel administrativo read-only da 9B.4) importa esta
    # classe e chama build_report() diretamente, com valores já validados
    # (nunca via argparse/Namespace), para nunca duplicar estas queries.
    # Só monta e retorna o dict do relatório — nenhuma escrita, nenhuma
    # decisão de formato/saída (isso continua em handle(), só do CLI).
    # ------------------------------------------------------------------

    def build_report(
        self,
        *,
        stale_media_minutes: int | None = None,
        check_r2: bool = False,
        r2_sample_limit: int = 200,
        r2_list_limit: int = 5000,
    ) -> dict:
        resolved_stale_media_minutes = (
            stale_media_minutes if stale_media_minutes is not None else settings.PENDING_MEDIA_EXPIRATION_MINUTES
        )

        return {
            "generated_at": timezone.now().isoformat(),
            "mode": "dry-run (somente leitura — nenhuma escrita foi ou será feita)",
            "drafts": self._inventory_drafts(),
            "payments": self._inventory_payments(),
            "media": self._inventory_media(resolved_stale_media_minutes),
            "r2": self._inventory_r2(
                check=check_r2,
                sample_limit=r2_sample_limit,
                list_limit=r2_list_limit,
            ),
        }

    # ------------------------------------------------------------------
    # Coleta (só leitura — nenhum .save()/.delete()/.update() em lugar nenhum)
    # ------------------------------------------------------------------

    def _inventory_drafts(self) -> dict:
        qs = ExperienceDraft.objects.all()
        by_status = {}
        for status_value, _label in ExperienceDraft.Status.choices:
            status_qs = qs.filter(status=status_value)
            oldest = status_qs.aggregate(oldest=Min("created_at"))["oldest"]
            by_status[status_value] = {
                "count": status_qs.count(),
                "oldest_created_at": oldest.isoformat() if oldest else None,
                "oldest_age_days": _age_days(oldest),
            }

        published_qs = qs.filter(status=ExperienceDraft.Status.PUBLISHED)
        now = timezone.now()
        expired = published_qs.filter(expires_at__isnull=False, expires_at__lt=now).count()
        never_expires = published_qs.filter(expires_at__isnull=True).count()
        not_yet_expired = published_qs.filter(expires_at__isnull=False, expires_at__gte=now).count()

        return {
            "total": qs.count(),
            "by_status": by_status,
            "published_expired": expired,
            "published_never_expires": never_expires,
            "published_not_yet_expired": not_yet_expired,
        }

    def _inventory_payments(self) -> dict:
        qs = Payment.objects.all()
        by_status = {}
        for status_value, _label in Payment.Status.choices:
            status_qs = qs.filter(status=status_value)
            oldest = status_qs.aggregate(oldest=Min("created_at"))["oldest"]
            by_status[status_value] = {
                "count": status_qs.count(),
                "oldest_created_at": oldest.isoformat() if oldest else None,
                "oldest_age_days": _age_days(oldest),
            }

        without_order = qs.filter(mp_order_id__isnull=True).count()

        # Checagem de invariante (deveria ser sempre 0, dado o código atual):
        # um Payment em status ativo (pending/in_process/action_required)
        # cujo draft NÃO está em AWAITING_PAYMENT. Não é uma ação de
        # cleanup — é uma checagem de consistência para acusar se algum
        # caminho futuro quebrou esse invariante.
        active_payments_with_inconsistent_draft = (
            qs.filter(status__in=Payment.ACTIVE_STATUSES)
            .exclude(draft__status=ExperienceDraft.Status.AWAITING_PAYMENT)
            .count()
        )

        return {
            "total": qs.count(),
            "by_status": by_status,
            "without_mp_order_id": without_order,
            "active_payment_with_inconsistent_draft_status": active_payments_with_inconsistent_draft,
        }

    def _inventory_media(self, stale_media_minutes: int) -> dict:
        qs = Media.objects.all()
        by_upload_status = {}
        for status_value, _label in Media.UploadStatus.choices:
            by_upload_status[status_value] = qs.filter(upload_status=status_value).count()

        # Estrutural: Media.draft é FK obrigatória (NOT NULL) — isto deveria
        # ser sempre 0. Verificado defensivamente, não assumido.
        without_draft = qs.filter(draft__isnull=True).count()

        cutoff = timezone.now() - timedelta(minutes=stale_media_minutes)
        stale_pending = qs.filter(
            upload_status=Media.UploadStatus.PENDING, created_at__lt=cutoff
        ).count()

        # Mídia vinculada a um draft que nunca avançou (ainda em DRAFT) —
        # não é "órfã" no sentido de referência quebrada, mas é o grupo mais
        # próximo de "pode nunca vir a ser usada" que dá para identificar
        # sem presumir um prazo. Reportado como contagem factual.
        media_on_never_advanced_drafts = qs.filter(
            draft__status=ExperienceDraft.Status.DRAFT
        ).count()

        return {
            "total": qs.count(),
            "by_upload_status": by_upload_status,
            "without_draft": without_draft,
            "stale_media_minutes_used": stale_media_minutes,
            "pending_older_than_threshold": stale_pending,
            "media_on_never_advanced_drafts": media_on_never_advanced_drafts,
        }

    def _inventory_r2(self, *, check: bool, sample_limit: int, list_limit: int) -> dict:
        if not check:
            return {
                "checked": False,
                "reason": "Passe --check-r2 para habilitar (faz chamadas de rede reais).",
            }

        if not r2_is_configured():
            return {"checked": False, "reason": "R2 não configurado neste ambiente."}

        client = get_r2_client()
        bucket = settings.R2_BUCKET_NAME

        # 1) Banco -> R2: para cada Media (até sample_limit), confirma que o
        # objeto existe. Só leitura (head_object nunca apaga nem cria nada).
        media_rows = list(
            Media.objects.all().order_by("-created_at").values_list("id", "storage_key")[:sample_limit]
        )
        db_refs_missing_object = []
        check_errors = 0
        for media_id, storage_key in media_rows:
            try:
                client.head_object(Bucket=bucket, Key=storage_key)
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in ("404", "NoSuchKey", "NotFound"):
                    db_refs_missing_object.append(storage_key)
                else:
                    check_errors += 1

        # 2) R2 -> Banco: lista o bucket (paginado, até list_limit) e
        # compara contra o conjunto de storage_key conhecidos. Só leitura
        # (list_objects_v2 nunca apaga nem cria nada).
        known_keys = set(Media.objects.values_list("storage_key", flat=True))
        listed_keys = []
        truncated = False
        continuation_token = None
        while len(listed_keys) < list_limit:
            kwargs = {"Bucket": bucket, "Prefix": "drafts/", "MaxKeys": min(1000, list_limit - len(listed_keys))}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            page = client.list_objects_v2(**kwargs)
            for obj in page.get("Contents", []):
                listed_keys.append(obj["Key"])
            if page.get("IsTruncated"):
                continuation_token = page.get("NextContinuationToken")
                if len(listed_keys) >= list_limit:
                    truncated = True
                    break
            else:
                break

        objects_without_db_reference = [key for key in listed_keys if key not in known_keys]

        return {
            "checked": True,
            "bucket": bucket,
            "media_rows_checked": len(media_rows),
            "media_rows_checked_capped": len(media_rows) == sample_limit,
            "db_references_missing_object_count": len(db_refs_missing_object),
            "db_references_missing_object_sample": db_refs_missing_object[:20],
            "head_object_check_errors": check_errors,
            "bucket_objects_scanned": len(listed_keys),
            "bucket_scan_truncated": truncated,
            "objects_without_db_reference_count": len(objects_without_db_reference),
            "objects_without_db_reference_sample": objects_without_db_reference[:20],
        }

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------

    def _render_text(self, report: dict) -> None:
        w = self.stdout.write
        w(f"Etapa 9B.1 — Inventário de lifecycle ({report['generated_at']})")
        w(f"Modo: {report['mode']}")
        w("")

        d = report["drafts"]
        w("DRAFTS")
        w(f"- total: {d['total']}")
        for status_value, data in d["by_status"].items():
            age = f", mais antigo: {data['oldest_age_days']}d" if data["oldest_age_days"] is not None else ""
            w(f"  - {status_value}: {data['count']}{age}")
        w(f"- PUBLISHED expirados: {d['published_expired']}")
        w(f"- PUBLISHED nunca expiram: {d['published_never_expires']}")
        w(f"- PUBLISHED ainda não expirados: {d['published_not_yet_expired']}")
        w("")

        p = report["payments"]
        w("PAYMENTS")
        w(f"- total: {p['total']}")
        for status_value, data in p["by_status"].items():
            age = f", mais antigo: {data['oldest_age_days']}d" if data["oldest_age_days"] is not None else ""
            w(f"  - {status_value}: {data['count']}{age}")
        w(f"- sem mp_order_id (nunca criaram Order na MP): {p['without_mp_order_id']}")
        w(
            "- INVARIANTE (deveria ser sempre 0) Payment ativo com draft fora "
            f"de AWAITING_PAYMENT: {p['active_payment_with_inconsistent_draft_status']}"
        )
        w("")

        m = report["media"]
        w("MEDIA")
        w(f"- total: {m['total']}")
        for status_value, count in m["by_upload_status"].items():
            w(f"  - {status_value}: {count}")
        w(f"- sem draft (estrutural, deveria ser sempre 0): {m['without_draft']}")
        w(
            f"- pending mais velha que {m['stale_media_minutes_used']}min: "
            f"{m['pending_older_than_threshold']}"
        )
        w(f"- mídia em drafts que nunca avançaram (status=draft): {m['media_on_never_advanced_drafts']}")
        w("")

        r = report["r2"]
        w("R2")
        if not r["checked"]:
            w(f"- não verificado: {r['reason']}")
        else:
            w(f"- bucket: {r['bucket']}")
            w(f"- linhas de Media verificadas: {r['media_rows_checked']} (capado: {r['media_rows_checked_capped']})")
            w(f"- referências no banco sem objeto no R2: {r['db_references_missing_object_count']}")
            if r["db_references_missing_object_sample"]:
                w(f"  amostra: {r['db_references_missing_object_sample']}")
            w(f"- erros ao checar (não classificados como ausentes): {r['head_object_check_errors']}")
            w(f"- objetos escaneados no bucket: {r['bucket_objects_scanned']} (parcial: {r['bucket_scan_truncated']})")
            w(f"- objetos no bucket sem referência no banco: {r['objects_without_db_reference_count']}")
            if r["objects_without_db_reference_sample"]:
                w(f"  amostra: {r['objects_without_db_reference_sample']}")
