import uuid

from django.conf import settings
from django.db import models


class Theme(models.Model):
    """Catálogo de temas visuais disponíveis para experiências.

    Mesma filosofia de apps.payments.models.Plan: este model é a fonte de
    verdade sobre QUAIS temas existem, seus metadados comerciais/de catálogo
    (nome, ativo, ordem) e espaço para expansão futura (features). A
    implementação visual em si (cores, classes, tipografia) vive só no
    frontend (Theme Registry) — este model nunca decide como um tema é
    desenhado, só o que existe e está disponível.

    Deliberadamente SEM relação (FK) com ExperienceDraft.theme, que
    continua sendo um CharField livre — ver o comentário em
    ExperienceDraft.theme para o porquê.
    """

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    features = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "experience_themes"
        ordering = ["sort_order", "code"]

    def __str__(self):
        return self.code

    def get_feature(self, key, default=None):
        return self.features.get(key, default)


class ExperienceDraft(models.Model):
    """A private, editable experience saved before payment and publication."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"
        PAYMENT_FAILED = "payment_failed", "Pagamento falhou"
        PAID = "paid", "Pago"
        PUBLISHED = "published", "Publicado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # null=True (Etapa 10): um draft anônimo (criado por um visitante sem
    # conta, ver views.DraftListCreateView.post) começa com owner=None e
    # claim_token preenchido. Vira permanentemente não-nulo assim que
    # views.DraftClaimView reivindica o draft para um usuário autenticado —
    # nenhum código depois desse ponto (checkout, publicação) precisa saber
    # que este campo já foi nulo um dia, porque só é alcançável através de
    # get_owned_draft_or_404 (que já exige owner=request.user).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="experience_drafts",
        null=True,
        blank=True,
    )
    # Token opaco de posse temporária (Etapa 10) — só é não-nulo enquanto
    # owner for None. Gerado com secrets.token_urlsafe(32) (256 bits) em
    # views.DraftListCreateView.post, nunca reaproveitado, nunca derivado de
    # e-mail/IP/sessão. Apagado (None) no instante em que o draft é
    # reivindicado (views.DraftClaimView) — mesmo que vaze depois de
    # reivindicado, não abre acesso a nada. unique=True também serve de
    # índice para o lookup em get_accessible_draft_or_404. NUNCA incluído em
    # ExperienceDraftSerializer nem em ExperienceDraftAdmin (ver admin.py) —
    # só aparece uma vez, no corpo da resposta de criação anônima.
    claim_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    # Gerado só na primeira publicação (nunca antes, nunca a partir de
    # título/dado editável) — ver apps.experiences.services.publication_service.
    # null=True: rascunhos não publicados não têm slug; UNIQUE permite
    # múltiplos NULL no Postgres, então isso não exige constraint condicional.
    slug = models.CharField(max_length=32, unique=True, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # Só é calculado e gravado no momento da publicação (nunca antes — criar
    # o draft ou iniciar o checkout não inicia a contagem), a partir da
    # duração do Plan pago — ver
    # apps.experiences.services.publication_service.PublicationService.
    # None para planos vitalícios (nunca expira) e para publicações antigas
    # feitas antes desta feature existir.
    expires_at = models.DateTimeField(null=True, blank=True)
    experience_type = models.CharField(max_length=100, blank=True)
    # Deliberadamente uma string livre, NUNCA uma FK para Theme — uma FK
    # exigiria migrar/backfillar todo draft e experiência publicada já
    # existente para apontar a uma linha real de Theme (ou aceitar NULL em
    # dados antigos), e uma futura desativação/remoção de tema no catálogo
    # poderia quebrar leituras antigas. A validação de que o valor
    # corresponde a um Theme ativo acontece só na ESCRITA (ver
    # ExperienceDraftSerializer.validate_theme) — a leitura de um draft ou
    # experiência publicada nunca é revalidada contra o catálogo atual, o
    # que preserva 100% de compatibilidade para qualquer valor histórico,
    # mesmo um que não exista (mais) em Theme.
    theme = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=200, blank=True)
    recipient_name = models.CharField(max_length=200, blank=True)
    creator_name = models.CharField(max_length=200, blank=True)
    event_date = models.DateField(null=True, blank=True)
    letter = models.TextField(blank=True)
    short_message = models.TextField(blank=True)
    # Fase 2.1: segundo campo de contexto livre, ao lado de short_message —
    # o par dos dois é o que alimenta as duas perguntas contextuais por
    # tipo de experiência na Etapa 3 (ver frontend/informationStepConfig.ts).
    # Deliberadamente genérico (não uma coluna por tipo): o prompt exibido
    # muda por experience_type no frontend, o dado armazenado é sempre só
    # texto livre. blank=True (sem null=True), mesmo padrão de letter/
    # short_message — draft antigo sem este campo simplesmente lê "".
    context_answer = models.TextField(blank=True)
    music_provider = models.CharField(max_length=32, default="none")
    music_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "experience_drafts"
        ordering = ["-updated_at"]

    def get_galaxy_live_enabled(self) -> bool:
        """Etapa Galáxia Viva: benefício da experiência paga (via
        Payment.plan.get_feature("galaxy_live_enabled")), NUNCA da conta —
        mesmo dono pode ter uma experiência comum e outra Galáxia Viva ao
        mesmo tempo (ver apps.payments.tests.test_models.
        GalaxyLiveEntitlementTests). Mesma resolução de "pagamento aprovado
        deste draft" já usada em
        services.publication_service._compute_expires_at — nunca duplicada
        como uma segunda query solta, só reaproveitada aqui.

        Lê de `approved_payments_list` quando a queryset já veio com esse
        prefetch (ver views.py: DraftListCreateView.get/
        ReceivedExperiencesListView.get — evita N+1 numa lista); sem esse
        prefetch (ex.: resposta de criar/editar um draft único), cai numa
        query avulsa — nunca quebra, só custa 1 query a mais nesse caso.
        """
        # Import tardio: mesmo motivo do import tardio em
        # publication_service._compute_expires_at — apps.experiences
        # importar apps.payments no nível do módulo (aqui, models.py)
        # inverteria a ordem de carregamento dos apps.
        from apps.payments.models import Payment

        prefetched = getattr(self, "approved_payments_list", None)
        if prefetched is not None:
            approved_payment = prefetched[0] if prefetched else None
        else:
            approved_payment = (
                Payment.objects.filter(draft=self, status=Payment.Status.APPROVED)
                .select_related("plan")
                .order_by("-created_at")
                .first()
            )

        if approved_payment is None:
            return False
        return bool(approved_payment.plan.get_feature("galaxy_live_enabled"))


class ExperienceRecipient(models.Model):
    """Marca que `user` guardou a experiência pública `draft` na própria
    Galáxia — NUNCA transfere propriedade (draft.owner nunca muda aqui).

    Deliberadamente uma relação intermediária enxuta (sem duplicar
    ExperienceDraft/Media/etc.): a "estrela" do destinatário na Galáxia é a
    mesma linha de ExperienceDraft do criador, só referenciada por mais um
    usuário. on_delete=CASCADE nos dois lados é seguro porque um
    ExperienceDraft PUBLISHED nunca é deletável (ver
    services.draft_deletion.DraftDeletionService — só aceita status=DRAFT
    sem slug), então na prática o CASCADE em `draft` nunca dispara; existe
    só como a mesma rede de segurança que Media.draft já usa.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_experiences",
    )
    draft = models.ForeignKey(
        ExperienceDraft,
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "experience_recipients"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "draft"], name="uniq_user_draft_recipient"),
        ]

    def __str__(self):
        return f"{self.user_id} <- {self.draft_id}"


class Media(models.Model):
    """Metadata for a private media object stored in Cloudflare R2."""

    class Type(models.TextChoices):
        PHOTO = "photo", "Foto"
        VIDEO = "video", "Vídeo"

    class UploadStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        UPLOADED = "uploaded", "Enviado"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(ExperienceDraft, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=10, choices=Type.choices)
    storage_key = models.CharField(max_length=500, unique=True)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()
    duration_seconds = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    upload_status = models.CharField(
        max_length=16, choices=UploadStatus.choices, default=UploadStatus.PENDING
    )
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Fase 2.2: legenda individual, opcional — editada via MediaDeleteView.patch
    # (a mesma view/URL do DELETE, ver views.py), nunca através do
    # ExperienceDraftSerializer. blank=True sem null=True, mesmo padrão de
    # short_message/context_answer em ExperienceDraft — mídia antiga lê "".
    # 140 caracteres: curto o bastante para não desequilibrar o grid
    # compacto de PhotosStep.tsx no mobile, com folga sobre os exemplos de
    # produto (~30-55 caracteres).
    caption = models.CharField(max_length=140, blank=True)

    class Meta:
        db_table = "experience_media"
        ordering = ["media_type", "sort_order", "created_at"]
