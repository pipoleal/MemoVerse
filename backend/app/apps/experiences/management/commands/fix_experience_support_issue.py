"""Comando de suporte pontual: corrige music_provider/music_url e/ou troca
o Plan efetivo de uma ExperienceDraft já PUBLISHED, para os dois casos que
motivaram este comando:

1) O bug corrigido em frontend/components/experience/steps/MusicStep.tsx —
   selecionar uma plataforma (ex.: YouTube) já gravava music_provider na
   hora, mas music_url só era gravado ao clicar em "Confirmar música".
   ExperienceBuilder.tsx não validava isso antes da Etapa 7 (Música),
   então dava pra colar o link e seguir direto sem confirmar: a experiência
   publicava com provider preenchido e url vazia, silenciosamente sem
   música nenhuma. O código já foi corrigido (Etapa 7 agora bloqueia
   avançar nesse caso) — este comando é só para consertar o dado de quem já
   publicou antes da correção.

2) Upgrade manual de plano dado como cortesia/compensação (ex.: o caso
   acima) — troca Payment.plan (nunca Payment.amount/currency: o valor
   efetivamente cobrado é histórico e nunca é reescrito, mesmo quando o
   cliente passa a ter direito a mais por cortesia) e recalcula
   ExperienceDraft.expires_at a partir do NOVO plano, reaproveitando
   PublicationService._compute_expires_at — a mesma conta feita na
   primeira publicação, nunca duplicada aqui.

Sempre em modo dry-run por padrão (mostra o que mudaria, sem escrever nada)
— passe --apply para gravar de verdade.

Exemplos:
    # Preview (não escreve nada):
    python manage.py fix_experience_support_issue --slug iY5W3XtU \\
        --music-provider youtube --music-url "https://youtu.be/Dx7kEtMMz2s" \\
        --upgrade-plan-code lifetime_galaxy

    # Aplicação real:
    python manage.py fix_experience_support_issue --slug iY5W3XtU \\
        --music-provider youtube --music-url "https://youtu.be/Dx7kEtMMz2s" \\
        --upgrade-plan-code lifetime_galaxy --apply
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import ExperienceDraft
from ...services.publication_service import PublicationService
from ...youtube import extract_youtube_video_id

VALID_MUSIC_PROVIDERS = ("none", "youtube", "spotify", "apple_music", "external")


class Command(BaseCommand):
    help = (
        "Corrige music_provider/music_url e/ou troca o Plan efetivo de uma "
        "ExperienceDraft PUBLISHED já existente. Dry-run por padrão — "
        "requer --apply para escrever."
    )

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="Slug público da experiência (ExperienceDraft.slug).")
        parser.add_argument(
            "--music-provider",
            choices=VALID_MUSIC_PROVIDERS,
            help="Novo music_provider. Requer --music-url quando != 'none'.",
        )
        parser.add_argument("--music-url", default=None, help="Novo music_url (link completo).")
        parser.add_argument(
            "--upgrade-plan-code",
            default=None,
            help=(
                "Code de um Plan ativo (ex.: lifetime_galaxy) para o qual o "
                "Payment aprovado deste draft passa a apontar. "
                "ExperienceDraft.expires_at é recalculado a partir desse "
                "plano (None se features.is_lifetime for True)."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Grava de verdade. Sem esta flag, só mostra o que mudaria (dry-run).",
        )

    def handle(self, *args, **options):
        # Import tardio: mesmo motivo do import tardio em models.py/
        # publication_service.py — apps.experiences importar apps.payments
        # no nível do módulo inverteria a ordem de carregamento dos apps.
        from apps.payments.models import Payment, Plan

        slug = options["slug"]
        music_provider = options["music_provider"]
        music_url = options["music_url"]
        upgrade_plan_code = options["upgrade_plan_code"]
        apply_changes = options["apply"]

        if music_provider is None and upgrade_plan_code is None:
            raise CommandError(
                "Nada a fazer: passe --music-provider (com --music-url) e/ou --upgrade-plan-code."
            )

        if music_provider is not None and music_provider != "none" and not music_url:
            raise CommandError(f"--music-provider {music_provider} exige --music-url.")

        if music_provider == "youtube" and music_url and not extract_youtube_video_id(music_url):
            raise CommandError(
                f"--music-url {music_url!r} não parece ser um link de vídeo do YouTube reconhecível "
                "(watch, youtu.be ou shorts)."
            )

        try:
            draft = ExperienceDraft.objects.get(slug=slug)
        except ExperienceDraft.DoesNotExist:
            raise CommandError(f"Nenhuma ExperienceDraft com slug={slug!r}.")

        if draft.status != ExperienceDraft.Status.PUBLISHED:
            raise CommandError(
                f"ExperienceDraft {draft.id} (slug={slug!r}) está em status "
                f"{draft.status!r}, não PUBLISHED — este comando só existe para corrigir "
                "experiências já publicadas."
            )

        new_plan = None
        approved_payment = None
        if upgrade_plan_code is not None:
            try:
                new_plan = Plan.objects.get(code=upgrade_plan_code, is_active=True)
            except Plan.DoesNotExist:
                raise CommandError(f"Nenhum Plan ativo com code={upgrade_plan_code!r}.")

            approved_payment = (
                Payment.objects.filter(draft=draft, status=Payment.Status.APPROVED)
                .select_related("plan")
                .order_by("-created_at")
                .first()
            )
            if approved_payment is None:
                raise CommandError(
                    f"ExperienceDraft {draft.id} (slug={slug!r}) não tem nenhum Payment aprovado — "
                    "não há o que fazer upgrade."
                )

        self.stdout.write(f"ExperienceDraft {draft.id} (slug={slug!r})")
        self.stdout.write(f"  título: {draft.title!r}")

        if music_provider is not None:
            self.stdout.write(
                f"  music: provider {draft.music_provider!r} -> {music_provider!r}, "
                f"url {draft.music_url!r} -> {(music_url or '')!r}"
            )

        if new_plan is not None:
            self.stdout.write(
                f"  Payment {approved_payment.id}: plan {approved_payment.plan.code!r} -> {new_plan.code!r} "
                f"(amount/currency ficam como estavam: {approved_payment.amount} {approved_payment.currency} "
                "— histórico do que foi de fato cobrado, nunca reescrito)"
            )
            self.stdout.write(f"  expires_at atual: {draft.expires_at}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("Dry-run — nada foi gravado. Passe --apply para aplicar."))
            return

        with transaction.atomic():
            locked = ExperienceDraft.objects.select_for_update().get(pk=draft.pk)
            update_fields = ["updated_at"]

            if music_provider is not None:
                locked.music_provider = music_provider
                locked.music_url = music_url or ""
                update_fields += ["music_provider", "music_url"]

            if new_plan is not None:
                approved_payment.plan = new_plan
                approved_payment.save(update_fields=["plan", "updated_at"])
                locked.expires_at = PublicationService._compute_expires_at(
                    locked, published_at=locked.published_at
                )
                update_fields.append("expires_at")

            locked.save(update_fields=update_fields)

        self.stdout.write(self.style.SUCCESS(f"Aplicado. ExperienceDraft {draft.id} atualizado."))
        if new_plan is not None:
            self.stdout.write(f"  novo expires_at: {locked.expires_at}")
