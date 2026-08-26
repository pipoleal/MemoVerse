import logging
import secrets
import uuid
from pathlib import PurePath

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import ExperienceDraft, ExperienceRecipient, Media, Theme
from .serializers import (
    ExperienceDraftSerializer,
    GalaxySaveResponseSerializer,
    MediaCaptionUpdateSerializer,
    PublicExperienceSerializer,
    PublishResponseSerializer,
    ThemeSerializer,
    UploadIntentSerializer,
)
from .services.draft_deletion import DraftDeletionService, DraftNotDeletable
from .services.media_cleanup import cleanup_abandoned_media
from .services.publication_service import DraftNotPayable, PublicationService
from .storage import delete_object, generate_presigned_read_url, get_r2_client

logger = logging.getLogger(__name__)


def get_owned_draft_or_404(request, draft_id):
    return get_object_or_404(ExperienceDraft, id=draft_id, owner=request.user)


def get_accessible_draft_or_404(request, draft_id):
    """Etapa 10: mesma garantia de get_owned_draft_or_404, mas aceita
    também um visitante anônimo dono do X-Draft-Claim-Token exato de um
    draft ainda não reivindicado (owner IS NULL) — usado pelos endpoints
    de texto/mídia que o wizard usa em nome de um visitante que ainda não
    tem conta (ver DraftListCreateView.post e DraftClaimView).

    Dois caminhos, nunca combinados na mesma chamada:
    1. Usuário autenticado -> exige owner=request.user, exatamente como
       get_owned_draft_or_404 (usuário autenticado NUNCA passa a acessar
       um draft de outro só por também carregar um token de algum outro
       draft anônimo por acaso).
    2. Visitante anônimo -> exige X-Draft-Claim-Token (só header, nunca
       querystring/corpo — nunca aparece em URL nem em log de acesso) e
       owner__isnull=True com aquele token exato.

    Qualquer combinação que não bata cai em Http404 — nunca 401/403,
    nunca revela se o draft existe, se pertence a outro usuário, ou se já
    foi reivindicado (as três situações são indistinguíveis de fora).
    """

    if request.user.is_authenticated:
        return get_object_or_404(ExperienceDraft, id=draft_id, owner=request.user)

    token = request.headers.get("X-Draft-Claim-Token")
    if not token:
        raise Http404
    return get_object_or_404(ExperienceDraft, id=draft_id, owner__isnull=True, claim_token=token)


class ThemeListView(APIView):
    """GET /api/experiences/themes/

    Catálogo dos temas disponíveis no momento. Sem autenticação (mesmo
    padrão de PublicExperienceView/PlanListView): tema não é dado sensível,
    e o wizard pode chegar à etapa de escolha de tema antes de qualquer
    chamada autenticada acontecer.

    is_active=True é o único filtro — Theme.Meta.ordering já é
    ["sort_order", "code"], então a resposta já sai ordenada sem precisar
    de order_by() explícito aqui.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        themes = Theme.objects.filter(is_active=True)
        return Response(ThemeSerializer(themes, many=True).data)


class DraftListCreateView(APIView):
    # Etapa 10: GET (listar meus drafts) continua exigindo autenticação de
    # verdade — nunca lista draft anônimo nenhum, de ninguém. POST passa a
    # aceitar visitante anônimo (ver post() abaixo) — permission_classes
    # dividido por método com get_permissions(), não um AllowAny amplo na
    # view inteira.
    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.request.method == "POST" and not self.request.user.is_authenticated:
            self.throttle_scope = "anonymous_draft_create"
            return [ScopedRateThrottle()]
        return []

    def get(self, request):
        drafts = ExperienceDraft.objects.filter(owner=request.user).prefetch_related("media")
        return Response(ExperienceDraftSerializer(drafts, many=True).data)

    def post(self, request):
        serializer = ExperienceDraftSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            # Etapa 7 — Fase C: só o evento, nunca o payload (carta/mensagem
            # podem estar aqui) — a resposta de erro da API não muda.
            logger.warning("draft.create.failure")
            raise

        if request.user.is_authenticated:
            # Caminho de sempre, byte a byte igual a antes da Etapa 10.
            draft = serializer.save(owner=request.user)
            logger.info("draft.create.success")
            return Response(ExperienceDraftSerializer(draft).data, status=status.HTTP_201_CREATED)

        # Visitante anônimo (Etapa 10): draft sem dono, com um token de
        # posse temporária. secrets.token_urlsafe(32) -> 256 bits de
        # entropia, nunca derivado de e-mail/IP/sessão. O token só existe
        # nesta variável local e no banco — nunca é logado (o evento abaixo
        # não carrega o valor), e só é devolvido UMA VEZ, aqui, no corpo
        # desta resposta: ExperienceDraftSerializer nunca inclui
        # claim_token (ver Meta.fields em serializers.py), então nenhuma
        # outra resposta (GET/PATCH/claim) jamais o repete.
        claim_token = secrets.token_urlsafe(32)
        draft = serializer.save(owner=None, claim_token=claim_token)
        logger.info("draft.create.success.anonymous")
        data = {**ExperienceDraftSerializer(draft).data, "claim_token": claim_token}
        return Response(data, status=status.HTTP_201_CREATED)


class DraftDetailView(APIView):
    # Etapa 10: GET/PATCH aceitam visitante anônimo dono do
    # X-Draft-Claim-Token certo (via get_accessible_draft_or_404) — DELETE
    # continua exigindo autenticação de verdade, sem mudança nenhuma (não é
    # exigido pelo fluxo de retomada, e manter o escopo mínimo evita trocar
    # IsAuthenticated por AllowAny em mais operações do que o necessário).
    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, draft_id):
        draft = get_accessible_draft_or_404(request, draft_id)
        return Response(ExperienceDraftSerializer(draft).data)

    def patch(self, request, draft_id):
        draft = get_accessible_draft_or_404(request, draft_id)
        serializer = ExperienceDraftSerializer(draft, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            logger.warning("draft.patch.failure")
            raise
        serializer.save()
        logger.info("draft.patch.success")
        return Response(serializer.data)

    def delete(self, request, draft_id):
        # get_owned_draft_or_404 já garante autenticação (IsAuthenticated),
        # ownership e 404 (nunca 403) tanto para draft inexistente quanto
        # para draft de outro usuário — nenhuma distinção revelada, mesmo
        # padrão do resto do app. owner/status nunca vêm do request: o
        # owner é sempre request.user, e o status é sempre o valor já
        # persistido no banco (lido de dentro de DraftDeletionService).
        draft = get_owned_draft_or_404(request, draft_id)
        try:
            DraftDeletionService.delete(draft)
        except DraftNotDeletable:
            return Response(
                {"detail": "Este draft não pode ser excluído no status atual."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DraftPublishView(APIView):
    """POST /api/experiences/drafts/<uuid:draft_id>/publish/

    Publica um ExperienceDraft já pago (status=paid), gerando um slug
    público via PublicationService. Idempotente: publicar um draft já
    publicado retorna o mesmo slug, sem efeito colateral adicional.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id):
        # Mesmo padrão do resto do app: draft de outro usuário -> 404,
        # nunca revelando que existe.
        draft = get_owned_draft_or_404(request, draft_id)

        try:
            published = PublicationService.publish(draft)
        except DraftNotPayable:
            return Response(
                {"detail": "Este draft ainda não foi pago."},
                status=status.HTTP_409_CONFLICT,
            )

        response_data = {
            "slug": published.slug,
            "status": published.status,
            "published_at": published.published_at,
        }
        return Response(PublishResponseSerializer(response_data).data, status=status.HTTP_200_OK)


class PublicExperienceView(APIView):
    """GET /api/public/experiences/<slug:slug>/

    Único endpoint deste app sem autenticação — quem recebeu o link de uma
    experiência publicada não tem (nem deveria precisar de) conta no
    MemoVerse. Só retorna o necessário para renderizar a experiência.
    """

    permission_classes = [AllowAny]

    def get(self, request, slug):
        # slug inexistente, draft existente-mas-não-publicado E draft
        # expirado caem todos no MESMO Http404 (a query exige as três
        # condições de uma vez, dentro da MESMA chamada a
        # get_object_or_404) — nunca uma mensagem ou status diferente que
        # denunciasse qual dos três casos aconteceu, mesmo padrão de "nunca
        # revelar existência" já usado em get_owned_draft_or_404.
        draft = get_object_or_404(
            ExperienceDraft.objects.prefetch_related(
                Prefetch("media", queryset=Media.objects.filter(upload_status=Media.UploadStatus.UPLOADED))
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())),
            slug=slug,
            status=ExperienceDraft.Status.PUBLISHED,
        )

        media_items = []
        for media in draft.media.all():
            try:
                url = generate_presigned_read_url(media.storage_key)
            except ImproperlyConfigured:
                # Mesmo tratamento de infraestrutura indisponível já usado em
                # MediaUploadIntentView — nunca deixa o traceback chegar ao
                # cliente.
                return Response(
                    {"detail": "Mídia temporariamente indisponível."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            media_items.append(
                {
                    "id": media.id,
                    "media_type": media.media_type,
                    "url": url,
                    "original_filename": media.original_filename,
                    "sort_order": media.sort_order,
                    "caption": media.caption,
                }
            )

        response_data = {
            "slug": draft.slug,
            "title": draft.title,
            "experience_type": draft.experience_type,
            "theme": draft.theme,
            "recipient_name": draft.recipient_name,
            "creator_name": draft.creator_name,
            "event_date": draft.event_date,
            "letter": draft.letter,
            "short_message": draft.short_message,
            "context_answer": draft.context_answer,
            "music": {"provider": draft.music_provider, "url": draft.music_url},
            "media": media_items,
            "published_at": draft.published_at,
            "viewer_can_manage": bool(
                request.user.is_authenticated and draft.owner_id == request.user.id
            ),
        }
        return Response(PublicExperienceSerializer(response_data).data)


class SaveExperienceToGalaxyView(APIView):
    """POST /api/experiences/public/<slug:slug>/save/

    Guarda, para request.user, uma referência à experiência pública `slug`
    na própria Galáxia — NUNCA transfere propriedade (ver
    models.ExperienceRecipient; draft.owner nunca é alterado aqui).

    O draft é resolvido pela MESMA query de PublicExperienceView (slug +
    status=PUBLISHED + não expirado), nunca por um id vindo do cliente —
    não existe caminho para associar um draft privado, ainda não publicado
    ou expirado: ele simplesmente não é encontrado (404), o mesmo 404
    genérico de "não existe" que PublicExperienceView já devolve para os
    três casos, sem distingui-los.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        draft = get_object_or_404(
            ExperienceDraft.objects.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())),
            slug=slug,
            status=ExperienceDraft.Status.PUBLISHED,
        )

        if draft.owner_id == request.user.id:
            # O próprio criador "salvando" a própria experiência: ela já
            # está na Galáxia dele por ser dono — no-op idempotente, nunca
            # cria um ExperienceRecipient de si mesmo (evita uma segunda
            # estrela duplicada quando GET /experiences/received/ e GET
            # /experiences/drafts/ forem combinados no frontend).
            logger.info("experience.save_to_galaxy.owner_noop")
            return Response(GalaxySaveResponseSerializer({"id": draft.id, "slug": draft.slug}).data)

        # get_or_create já é seguro contra a corrida de duplo clique/dupla
        # aba (a UniqueConstraint do banco é quem decide de verdade) — o
        # atomic aqui só mantém o mesmo estilo do resto do app (ex.:
        # DraftClaimView), não é estritamente necessário para a segurança.
        with transaction.atomic():
            ExperienceRecipient.objects.get_or_create(user=request.user, draft=draft)

        logger.info("experience.save_to_galaxy.success")
        return Response(GalaxySaveResponseSerializer({"id": draft.id, "slug": draft.slug}).data)


class ReceivedExperiencesListView(APIView):
    """GET /api/experiences/received/

    Experiências que request.user recebeu (guardou na própria Galáxia via
    "Criar minha Galáxia") — nunca inclui as que ele possui como dono, essa
    lista já é GET /experiences/drafts/. Mesmo ExperienceDraftSerializer:
    o frontend já sabe consumir esse shape, e a posição da estrela em
    lib/galaxyStars.ts é semeada por draft.id — devolver o MESMO id da
    ExperienceDraft original é o que garante posição determinística sem
    nenhuma mudança no sistema de estrelas.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        drafts = (
            ExperienceDraft.objects.filter(recipients__user=request.user)
            .prefetch_related("media")
            .order_by("-recipients__received_at")
        )
        return Response(ExperienceDraftSerializer(drafts, many=True).data)


class MediaUploadIntentView(APIView):
    # Etapa 10: visitante anônimo dono do X-Draft-Claim-Token certo pode
    # subir mídia normalmente — autorização real é 100% de
    # get_accessible_draft_or_404 (nunca 404 revela mais que "não achei").
    permission_classes = [AllowAny]

    def post(self, request, draft_id):
        draft = get_accessible_draft_or_404(request, draft_id)
        serializer = UploadIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        media_type = data["media_type"]
        limits = {Media.Type.PHOTO: 10, Media.Type.VIDEO: 3}
        # Antes de contar a quota: descarta pendências abandonadas (upload
        # nunca confirmado via .../complete/) para que elas nunca prendam a
        # quota do usuário indefinidamente — ver services.media_cleanup.
        cleanup_abandoned_media(draft)

        filename = PurePath(data["filename"]).name
        stem = slugify(PurePath(filename).stem) or "media"
        extension = PurePath(filename).suffix.lower()[:12]

        # select_for_update() serializa upload-intents concorrentes do MESMO
        # draft — sem o lock, duas requisições (ex.: selecionar várias fotos
        # de uma vez, que dispara uma chamada por arquivo em paralelo) podem
        # ler o mesmo Max(sort_order) antes de qualquer uma persistir sua
        # própria Media, gerando sort_order duplicado. Mesmo padrão já usado
        # em DraftClaimView/CheckoutService/PublicationService — no-op
        # seguro em SQLite (testes), efetivo em Postgres (produção). Como
        # efeito colateral correto (não uma mudança de comportamento): a
        # checagem de quota, que tinha a mesma janela de corrida, passa a
        # ser igualmente atômica.
        with transaction.atomic():
            draft = ExperienceDraft.objects.select_for_update().get(pk=draft.pk)
            active_media = draft.media.exclude(upload_status=Media.UploadStatus.FAILED)
            if active_media.filter(media_type=media_type).count() >= limits[media_type]:
                return Response({"detail": "Limite de mídias atingido."}, status=status.HTTP_400_BAD_REQUEST)
            # NUNCA `max_order or -1`: quando já existe uma mídia com
            # sort_order=0 (o caso mais comum — a primeira foto do draft),
            # `0 or -1` avalia para -1 em Python (0 é falsy), fazendo toda
            # mídia seguinte voltar a receber sort_order=0 em vez de
            # avançar — um bug que já reproduzia mesmo sem nenhuma
            # concorrência, só com uploads sequenciais. Só None (nenhuma
            # mídia ainda) deve cair no -1 inicial.
            max_order = active_media.filter(media_type=media_type).aggregate(max_order=Max("sort_order"))["max_order"]
            next_order = (max_order if max_order is not None else -1) + 1
            media_id = uuid.uuid4()
            media = Media.objects.create(
                id=media_id,
                draft=draft,
                media_type=media_type,
                storage_key=f"drafts/{draft.id}/{media_type}s/{media_id}-{stem}{extension}",
                original_filename=filename,
                mime_type=data["mime_type"],
                size_bytes=data["size_bytes"],
                sort_order=next_order,
            )
        try:
            upload_url = get_r2_client().generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.R2_BUCKET_NAME,
                    "Key": media.storage_key,
                    "ContentType": media.mime_type,
                },
                ExpiresIn=settings.R2_PRESIGNED_URL_TTL_SECONDS,
            )
        except ImproperlyConfigured:
            media.delete()
            return Response({"detail": "Cloudflare R2 ainda não está configurado."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "media_id": str(media.id),
                "upload_url": upload_url,
                "method": "PUT",
                "headers": {"Content-Type": media.mime_type},
                "expires_in": settings.R2_PRESIGNED_URL_TTL_SECONDS,
            },
            status=status.HTTP_201_CREATED,
        )


class MediaUploadCompleteView(APIView):
    # Etapa 10: mesmo raciocínio de MediaUploadIntentView.
    permission_classes = [AllowAny]

    def post(self, request, draft_id, media_id):
        draft = get_accessible_draft_or_404(request, draft_id)
        media = get_object_or_404(Media, id=media_id, draft=draft)
        try:
            metadata = get_r2_client().head_object(Bucket=settings.R2_BUCKET_NAME, Key=media.storage_key)
        except (ImproperlyConfigured, ClientError):
            return Response({"detail": "Não foi possível confirmar o upload."}, status=status.HTTP_400_BAD_REQUEST)
        if metadata.get("ContentLength", 0) > media.size_bytes or metadata.get("ContentType") != media.mime_type:
            media.upload_status = Media.UploadStatus.FAILED
            media.save(update_fields=["upload_status"])
            return Response({"detail": "O arquivo enviado não confere com a solicitação."}, status=status.HTTP_400_BAD_REQUEST)
        media.upload_status = Media.UploadStatus.UPLOADED
        media.uploaded_at = timezone.now()
        media.save(update_fields=["upload_status", "uploaded_at"])
        return Response({"id": str(media.id), "upload_status": media.upload_status})


class MediaDeleteView(APIView):
    """DELETE, PATCH /api/experiences/drafts/<uuid:draft_id>/media/<uuid:media_id>/

    DELETE remove uma mídia (em qualquer upload_status) do draft do
    usuário.

    Best-effort quanto ao R2 (ver storage.delete_object): uma falha ao
    remover o objeto do bucket nunca impede a remoção do registro — o
    usuário pediu para a mídia sumir da experiência, e é isso que o
    registro no banco representa. Um objeto órfão no R2, se isso acontecer,
    nunca é servido a ninguém: generate_presigned_read_url só é chamado
    para mídia com upload_status=UPLOADED referenciada por um draft
    PUBLISHED.

    PATCH (Fase 2.2) atualiza só a legenda (caption) da mídia — mesma
    view/URL/autorização do DELETE, de propósito: não existe uma segunda
    estrutura de autorização pra mídia, só mais um verbo na mesma view.
    """

    # Etapa 10: mesmo raciocínio de MediaUploadIntentView — visitante
    # anônimo pode remover (ou, desde a Fase 2.2, legendar) a própria
    # mídia (do próprio draft ainda não reivindicado) antes de ter conta.
    permission_classes = [AllowAny]

    def delete(self, request, draft_id, media_id):
        draft = get_accessible_draft_or_404(request, draft_id)
        media = get_object_or_404(Media, id=media_id, draft=draft)
        try:
            delete_object(media.storage_key)
        except (ImproperlyConfigured, ClientError):
            pass
        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, draft_id, media_id):
        draft = get_accessible_draft_or_404(request, draft_id)
        media = get_object_or_404(Media, id=media_id, draft=draft)
        serializer = MediaCaptionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media.caption = serializer.validated_data["caption"]
        media.save(update_fields=["caption"])
        return Response({"id": str(media.id), "caption": media.caption})


class DraftClaimView(APIView):
    """POST /api/experiences/drafts/<uuid:draft_id>/claim/

    Etapa 10 — reivindica, para request.user, um draft criado
    anonimamente (owner IS NULL) por um visitante que acabou de se
    cadastrar ou entrar. Chamado automaticamente pelo frontend logo após
    login/cadastro bem-sucedido (nunca uma ação manual do usuário) — ver
    lib/anonymousDraft.ts e RegisterForm/LoginForm no frontend.

    claim_token só é aceito no CORPO da requisição — nunca em querystring
    (nunca aparece em URL, nunca em log de acesso/analytics que capture a
    URL da requisição) — e nunca é logado por este view em nenhuma
    circunstância, sucesso ou falha.

    transaction.atomic() + select_for_update() torna duas tentativas de
    reivindicar o MESMO draft ao mesmo tempo (ex.: duplo clique, StrictMode,
    duas abas) seguras: a segunda só roda depois que a primeira já
    commitou, e nesse ponto ou já é idempotente (mesmo usuário) ou já
    falha honestamente (owner não é mais None).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "draft_claim"

    def post(self, request, draft_id):
        token = request.data.get("claim_token")
        if not token or not isinstance(token, str):
            # Nunca 400 aqui: um claim_token ausente/malformado não deve
            # ser distinguível de "draft não encontrado" — mesma postura de
            # "nunca revelar existência" do resto do app.
            raise Http404

        with transaction.atomic():
            try:
                draft = ExperienceDraft.objects.select_for_update().get(id=draft_id)
            except ExperienceDraft.DoesNotExist:
                raise Http404

            if draft.owner_id == request.user.id:
                # Idempotente: já é deste mesmo usuário (retry, duplo clique,
                # segunda aba que ganhou a corrida depois desta) — sucesso
                # sem reaplicar nada, nunca um erro para quem já é o dono.
                logger.info("draft.claim.success")
                return Response(ExperienceDraftSerializer(draft).data)

            # secrets.compare_digest evita vazar, por tempo de resposta,
            # quantos caracteres do token bateram — draft.claim_token é ""
            # (nunca None) no comparando quando já foi reivindicado, só
            # para manter os dois lados sempre string.
            token_matches = secrets.compare_digest(draft.claim_token or "", token)
            if draft.owner_id is not None or not token_matches:
                # ATENÇÃO: nunca diferenciar "já reivindicado por outro",
                # "token errado" e "draft não existe" — os três caem aqui,
                # sempre 404, sempre a mesma mensagem genérica do DRF.
                logger.warning("draft.claim.failure")
                raise Http404

            draft.owner = request.user
            draft.claim_token = None
            draft.save(update_fields=["owner", "claim_token", "updated_at"])

        logger.info("draft.claim.success")
        return Response(ExperienceDraftSerializer(draft).data)
