"""Etapa 10 — draft anônimo com reivindicação (claim).

Um visitante sem conta pode criar um ExperienceDraft (owner=None) e subir
mídia normalmente, usando um claim_token opaco (secrets.token_urlsafe(32),
256 bits) devolvido só uma vez, na criação. Ao se cadastrar/logar, o
frontend chama POST .../claim/ para transferir esse draft (texto E mídia,
sem duplicar nada) para a conta recém-autenticada.

Estes testes cobrem, nesta ordem: criação anônima, imprevisibilidade e
não-vazamento do token, autorização de PATCH/mídia por token, o endpoint
de claim (sucesso, idempotência, falha, corrida), o que passa a ser
proibido depois de reivindicado, e que checkout/publicação continuam
inalcançáveis para um draft ainda não reivindicado.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, connection
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.payments.models import Payment

from .models import ExperienceDraft, Media

User = get_user_model()

DRAFTS_URL = "/api/experiences/drafts/"


def draft_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/"


def claim_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/claim/"


def publish_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/publish/"


def upload_intent_url(draft_id):
    return f"/api/experiences/drafts/{draft_id}/media/upload-intents/"


def upload_complete_url(draft_id, media_id):
    return f"/api/experiences/drafts/{draft_id}/media/{media_id}/complete/"


def media_delete_url(draft_id, media_id):
    return f"/api/experiences/drafts/{draft_id}/media/{media_id}/"


def checkout_url(draft_id):
    return f"/api/payments/drafts/{draft_id}/checkout/"


def make_user(email="user@example.com", **overrides):
    defaults = {"first_name": "Test", "last_name": "User", "password": "strong-pass-123"}
    defaults.update(overrides)
    return User.objects.create_user(email=email, **defaults)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def anon_client():
    return APIClient()


def create_anonymous_draft(client=None, **payload):
    client = client or anon_client()
    response = client.post(DRAFTS_URL, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED, response.data
    return response.data["id"], response.data["claim_token"]


def patch_r2_upload():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://r2.example/upload-signed"
    return patch("apps.experiences.views.get_r2_client", return_value=mock_client)


def patch_r2_complete(content_length=1000, content_type="image/jpeg"):
    mock_client = MagicMock()
    mock_client.head_object.return_value = {"ContentLength": content_length, "ContentType": content_type}
    return patch("apps.experiences.views.get_r2_client", return_value=mock_client)


# ---------------------------------------------------------------------------
# 1/2 — criação anônima + imprevisibilidade do token
# ---------------------------------------------------------------------------


class AnonymousDraftCreationTests(TestCase):
    def setUp(self):
        # anonymous_draft_create é limitado por IP via cache (LocMemCache
        # nos testes) — não é limpo entre métodos de teste sozinho, então
        # cada teste começa com o próprio orçamento de 20/hora.
        cache.clear()

    def test_anonymous_visitor_can_create_a_draft(self):
        response = anon_client().post(DRAFTS_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ExperienceDraft.objects.filter(id=response.data["id"], owner__isnull=True).exists())

    def test_anonymous_creation_response_includes_claim_token(self):
        response = anon_client().post(DRAFTS_URL, {}, format="json")
        self.assertIn("claim_token", response.data)
        self.assertTrue(response.data["claim_token"])

    def test_claim_token_has_at_least_256_bits_of_entropy_and_is_url_safe(self):
        # secrets.token_urlsafe(32) produz >= 43 caracteres em base64 URL-safe
        # (256 bits) — checagem de forma, não tenta medir entropia de verdade.
        _, token = create_anonymous_draft()
        self.assertGreaterEqual(len(token), 43)
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        self.assertTrue(set(token) <= allowed)

    def test_two_anonymous_drafts_never_share_a_claim_token(self):
        _, token_a = create_anonymous_draft()
        _, token_b = create_anonymous_draft()
        self.assertNotEqual(token_a, token_b)

    def test_authenticated_creation_response_never_includes_claim_token(self):
        user = make_user()
        response = auth_client(user).post(DRAFTS_URL, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("claim_token", response.data)

    def test_authenticated_creation_behaves_exactly_as_before(self):
        user = make_user()
        response = auth_client(user).post(DRAFTS_URL, {"title": "Minha experiência"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        draft = ExperienceDraft.objects.get(id=response.data["id"])
        self.assertEqual(draft.owner, user)
        self.assertIsNone(draft.claim_token)

    def test_anonymous_draft_never_appears_in_any_authenticated_users_list(self):
        create_anonymous_draft()
        user = make_user()
        response = auth_client(user).get(DRAFTS_URL)
        self.assertEqual(response.data, [])

    def test_listing_drafts_still_requires_real_authentication(self):
        response = anon_client().get(DRAFTS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 3 — claim_token nunca aparece em log nenhum
# ---------------------------------------------------------------------------


class ClaimTokenNeverLoggedTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_token_never_appears_in_logs_across_creation_patch_and_claim(self):
        wrong_token = "this-token-value-must-never-be-logged"

        with self.assertLogs("apps", level="INFO") as captured:
            draft_id, token = create_anonymous_draft()

            anon_client().patch(
                draft_url(draft_id), {"title": "Carta para você"}, format="json",
                HTTP_X_DRAFT_CLAIM_TOKEN=token,
            )

            other_draft_id, _ = create_anonymous_draft()
            user = make_user("claimer@example.com")
            auth_client(user).post(claim_url(other_draft_id), {"claim_token": wrong_token}, format="json")
            auth_client(user).post(claim_url(draft_id), {"claim_token": token}, format="json")

        all_messages = "\n".join(record.getMessage() for record in captured.records)
        self.assertNotIn(token, all_messages)
        self.assertNotIn(wrong_token, all_messages)


# ---------------------------------------------------------------------------
# 4/5/6 — PATCH anônimo só com o token correto
# ---------------------------------------------------------------------------


class AnonymousPatchAuthorizationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_patch_with_correct_token_succeeds(self):
        draft_id, token = create_anonymous_draft()
        response = anon_client().patch(
            draft_url(draft_id), {"title": "Título novo"}, format="json", HTTP_X_DRAFT_CLAIM_TOKEN=token
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ExperienceDraft.objects.get(id=draft_id).title, "Título novo")

    def test_patch_without_any_token_is_404(self):
        draft_id, _ = create_anonymous_draft()
        response = anon_client().patch(draft_url(draft_id), {"title": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_with_wrong_token_is_404(self):
        draft_id, _ = create_anonymous_draft()
        response = anon_client().patch(
            draft_url(draft_id), {"title": "x"}, format="json", HTTP_X_DRAFT_CLAIM_TOKEN="totally-wrong-token"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotEqual(ExperienceDraft.objects.get(id=draft_id).title, "x")

    def test_correct_token_for_a_different_draft_id_is_404(self):
        draft_a_id, token_a = create_anonymous_draft()
        draft_b_id, _ = create_anonymous_draft()

        response = anon_client().patch(
            draft_url(draft_b_id), {"title": "x"}, format="json", HTTP_X_DRAFT_CLAIM_TOKEN=token_a
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotEqual(ExperienceDraft.objects.get(id=draft_b_id).title, "x")

    def test_anonymous_get_with_correct_token_returns_the_draft(self):
        draft_id, token = create_anonymous_draft(title="Minha carta")
        response = anon_client().get(draft_url(draft_id), HTTP_X_DRAFT_CLAIM_TOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], draft_id)

    def test_anonymous_get_response_never_includes_claim_token(self):
        draft_id, token = create_anonymous_draft()
        response = anon_client().get(draft_url(draft_id), HTTP_X_DRAFT_CLAIM_TOKEN=token)
        self.assertNotIn("claim_token", response.data)

    def test_anonymous_cannot_delete_the_whole_draft(self):
        # Escopo deliberadamente mínimo (ver arquitetura aprovada): DELETE
        # do draft inteiro continua exigindo autenticação de verdade.
        draft_id, token = create_anonymous_draft()
        response = anon_client().delete(draft_url(draft_id), HTTP_X_DRAFT_CLAIM_TOKEN=token)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(ExperienceDraft.objects.filter(id=draft_id).exists())


# ---------------------------------------------------------------------------
# 8/9/10 — upload de foto/vídeo/remoção para draft anônimo
# ---------------------------------------------------------------------------


class AnonymousMediaUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.draft_id, self.token = create_anonymous_draft()

    def _headers(self, token=None):
        return {"HTTP_X_DRAFT_CLAIM_TOKEN": token if token is not None else self.token}

    def test_anonymous_photo_upload_full_flow_succeeds(self):
        with patch_r2_upload():
            intent = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(),
            )
        self.assertEqual(intent.status_code, status.HTTP_201_CREATED)
        media_id = intent.data["media_id"]

        with patch_r2_complete(content_length=1000, content_type="image/jpeg"):
            complete = anon_client().post(
                upload_complete_url(self.draft_id, media_id), **self._headers()
            )
        self.assertEqual(complete.status_code, status.HTTP_200_OK)
        media = Media.objects.get(id=media_id)
        self.assertEqual(media.upload_status, Media.UploadStatus.UPLOADED)
        self.assertEqual(str(media.draft_id), self.draft_id)

    def test_anonymous_video_upload_full_flow_succeeds(self):
        with patch_r2_upload():
            intent = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "video", "filename": "video.mp4", "mime_type": "video/mp4", "size_bytes": 5000},
                format="json",
                **self._headers(),
            )
        self.assertEqual(intent.status_code, status.HTTP_201_CREATED)
        media_id = intent.data["media_id"]

        with patch_r2_complete(content_length=5000, content_type="video/mp4"):
            complete = anon_client().post(
                upload_complete_url(self.draft_id, media_id), **self._headers()
            )
        self.assertEqual(complete.status_code, status.HTTP_200_OK)
        self.assertEqual(Media.objects.get(id=media_id).media_type, Media.Type.VIDEO)

    def test_upload_intent_without_token_is_404_and_creates_no_media_row(self):
        with patch_r2_upload():
            response = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.count(), 0)

    def test_upload_intent_with_wrong_token_is_404(self):
        with patch_r2_upload():
            response = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(token="wrong"),
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.count(), 0)

    def test_media_delete_with_correct_token_succeeds(self):
        with patch_r2_upload():
            intent = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(),
            )
        media_id = intent.data["media_id"]

        with patch("apps.experiences.views.delete_object"):
            response = anon_client().delete(media_delete_url(self.draft_id, media_id), **self._headers())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Media.objects.filter(id=media_id).exists())

    def test_media_delete_without_token_is_404_and_media_survives(self):
        with patch_r2_upload():
            intent = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(),
            )
        media_id = intent.data["media_id"]

        response = anon_client().delete(media_delete_url(self.draft_id, media_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Media.objects.filter(id=media_id).exists())

    def test_media_delete_with_wrong_token_is_404_and_media_survives(self):
        with patch_r2_upload():
            intent = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(),
            )
        media_id = intent.data["media_id"]

        response = anon_client().delete(media_delete_url(self.draft_id, media_id), **self._headers(token="wrong"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Media.objects.filter(id=media_id).exists())

    def test_r2_unavailable_still_returns_503_for_anonymous_same_as_authenticated(self):
        with patch(
            "apps.experiences.views.get_r2_client",
            side_effect=ImproperlyConfigured("Cloudflare R2 is not configured."),
        ):
            response = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(),
            )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Media.objects.count(), 0)


class ConcurrentUploadIntentSortOrderTests(TransactionTestCase):
    """MediaUploadIntentView.post() calculava next_order (Max(sort_order)+1)
    e criava a Media sem nenhum lock entre a leitura e a escrita — quando o
    usuário seleciona várias fotos de uma vez, o frontend dispara uma
    upload-intent por arquivo em paralelo, e duas requisições concorrentes
    podiam ler o mesmo Max antes de qualquer uma persistir, gerando
    sort_order duplicado (0, 0, 0 em vez de 0, 1, 2). A correção usa
    select_for_update() no draft, mesmo padrão de ClaimRaceConditionTests
    acima. TransactionTestCase (não TestCase) é necessário aqui pelo mesmo
    motivo daquela classe: cada thread precisa de uma transação real
    própria, o que TestCase (uma única transação externa por teste) não
    permite."""

    serialized_rollback = True

    def setUp(self):
        cache.clear()

    def _concurrent_uploads(self, *, make_client, draft_id, count=3):
        # make_client é chamado ANTES do barrier (fora da seção
        # cronometrada) especificamente para que qualquer I/O de setup do
        # cliente (ex.: emitir um JWT para o caso autenticado) nunca
        # concorra, no SQLite de teste, com as próprias upload-intents que
        # este teste está tentando cronometrar — evitaria travar
        # "database is locked" por um motivo alheio ao que está sendo
        # testado.
        clients = [make_client() for _ in range(count)]
        barrier = threading.Barrier(count)
        results = []
        errors = []

        def worker(index, client):
            try:
                barrier.wait(timeout=10)
                for attempt in range(8):
                    try:
                        with patch_r2_upload():
                            resp = client.post(
                                upload_intent_url(draft_id),
                                {
                                    "media_type": "photo",
                                    "filename": f"foto-{index}.jpg",
                                    "mime_type": "image/jpeg",
                                    "size_bytes": 1000,
                                },
                                format="json",
                            )
                        results.append(resp)
                        return
                    except OperationalError:
                        if attempt == 7:
                            raise
                        time.sleep(0.05 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(i, clients[i])) for i in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), count)
        return results

    def _assert_no_duplicate_contiguous_orders(self, draft_id, *, minimum):
        orders = sorted(Media.objects.filter(draft_id=draft_id).values_list("sort_order", flat=True))
        # A propriedade que importa (o bug original) é ausência de
        # duplicata — nunca duas mídias com o mesmo sort_order. O SQLite de
        # teste, sob "database table is locked", ocasionalmente força um
        # retry de uma requisição já commitada no servidor (o cliente não
        # viu a resposta a tempo), produzindo uma linha genuína a mais; por
        # isso a asserção é "sem duplicata e contígua a partir de 0" em vez
        # de um tamanho fixo — em Postgres (produção), com select_for_update
        # de verdade, o caminho comum é sempre exatamente `minimum` linhas.
        self.assertEqual(len(orders), len(set(orders)), f"sort_order duplicado: {orders}")
        self.assertGreaterEqual(len(orders), minimum)
        self.assertEqual(orders, list(range(len(orders))))

    def test_concurrent_uploads_by_anonymous_visitor_never_duplicate_sort_order(self):
        draft_id, token = create_anonymous_draft()

        def make_client():
            client = anon_client()
            client.credentials(HTTP_X_DRAFT_CLAIM_TOKEN=token)
            return client

        results = self._concurrent_uploads(make_client=make_client, draft_id=draft_id)
        for resp in results:
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        self._assert_no_duplicate_contiguous_orders(draft_id, minimum=len(results))

    def test_concurrent_uploads_by_authenticated_owner_never_duplicate_sort_order(self):
        user = make_user("racer-media@example.com")
        response = auth_client(user).post(DRAFTS_URL, {}, format="json")
        draft_id = response.data["id"]
        # Token emitido uma vez aqui (fora das threads) pelo mesmo motivo
        # documentado em _concurrent_uploads.
        bearer = f"Bearer {RefreshToken.for_user(user).access_token}"

        def make_client():
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=bearer)
            return client

        results = self._concurrent_uploads(make_client=make_client, draft_id=draft_id)
        for resp in results:
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        self._assert_no_duplicate_contiguous_orders(draft_id, minimum=len(results))


class AnonymousMediaCaptionUpdateTests(TestCase):
    """Fase 2.2 — PATCH .../media/<id>/ (legenda) reaproveita exatamente a
    mesma autorização por claim_token que upload/delete já usam."""

    def setUp(self):
        cache.clear()
        self.draft_id, self.token = create_anonymous_draft()

    def _headers(self, token=None):
        return {"HTTP_X_DRAFT_CLAIM_TOKEN": token if token is not None else self.token}

    def _upload_photo(self):
        with patch_r2_upload():
            intent = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                **self._headers(),
            )
        media_id = intent.data["media_id"]
        with patch_r2_complete(content_length=1000, content_type="image/jpeg"):
            anon_client().post(upload_complete_url(self.draft_id, media_id), **self._headers())
        return media_id

    def test_caption_update_with_correct_token_succeeds(self):
        media_id = self._upload_photo()
        response = anon_client().patch(
            media_delete_url(self.draft_id, media_id),
            {"caption": "Nosso primeiro passeio juntos."},
            format="json",
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Media.objects.get(id=media_id).caption, "Nosso primeiro passeio juntos.")

    def test_caption_update_without_token_is_404_and_caption_unchanged(self):
        media_id = self._upload_photo()
        response = anon_client().patch(
            media_delete_url(self.draft_id, media_id), {"caption": "Tentativa sem token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.get(id=media_id).caption, "")

    def test_caption_update_with_wrong_token_is_404_and_caption_unchanged(self):
        media_id = self._upload_photo()
        response = anon_client().patch(
            media_delete_url(self.draft_id, media_id),
            {"caption": "Tentativa com token errado"},
            format="json",
            **self._headers(token="wrong"),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Media.objects.get(id=media_id).caption, "")


# ---------------------------------------------------------------------------
# 11/12/13/15 — claim: sucesso, idempotência, apagamento do token
# ---------------------------------------------------------------------------


class ClaimTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_claim_with_correct_token_sets_owner(self):
        draft_id, token = create_anonymous_draft()
        user = make_user()

        response = auth_client(user).post(claim_url(draft_id), {"claim_token": token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        draft = ExperienceDraft.objects.get(id=draft_id)
        self.assertEqual(draft.owner_id, user.id)

    def test_claim_deletes_the_claim_token(self):
        draft_id, token = create_anonymous_draft()
        user = make_user()
        auth_client(user).post(claim_url(draft_id), {"claim_token": token}, format="json")

        self.assertIsNone(ExperienceDraft.objects.get(id=draft_id).claim_token)

    def test_claim_response_never_includes_claim_token(self):
        draft_id, token = create_anonymous_draft()
        user = make_user()
        response = auth_client(user).post(claim_url(draft_id), {"claim_token": token}, format="json")
        self.assertNotIn("claim_token", response.data)

    def test_claim_requires_authentication(self):
        draft_id, token = create_anonymous_draft()
        response = anon_client().post(claim_url(draft_id), {"claim_token": token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIsNone(ExperienceDraft.objects.get(id=draft_id).owner_id)

    def test_claim_is_idempotent_when_repeated_by_the_same_user(self):
        draft_id, token = create_anonymous_draft()
        user = make_user()
        client = auth_client(user)

        first = client.post(claim_url(draft_id), {"claim_token": token}, format="json")
        second = client.post(claim_url(draft_id), {"claim_token": token}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(ExperienceDraft.objects.get(id=draft_id).owner_id, user.id)

    def test_claim_with_wrong_token_is_404_and_draft_stays_unclaimed(self):
        draft_id, _ = create_anonymous_draft()
        user = make_user()

        response = auth_client(user).post(claim_url(draft_id), {"claim_token": "wrong-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIsNone(ExperienceDraft.objects.get(id=draft_id).owner_id)

    def test_claim_of_already_claimed_by_another_user_is_404(self):
        draft_id, token = create_anonymous_draft()
        first_user = make_user("first@example.com")
        second_user = make_user("second@example.com")

        auth_client(first_user).post(claim_url(draft_id), {"claim_token": token}, format="json")
        response = auth_client(second_user).post(claim_url(draft_id), {"claim_token": token}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ExperienceDraft.objects.get(id=draft_id).owner_id, first_user.id)

    def test_claim_of_nonexistent_draft_is_404(self):
        import uuid

        user = make_user()
        response = auth_client(user).post(
            claim_url(uuid.uuid4()), {"claim_token": "whatever"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_claim_missing_token_in_body_is_404_not_400(self):
        draft_id, _ = create_anonymous_draft()
        user = make_user()
        response = auth_client(user).post(claim_url(draft_id), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_claiming_an_already_owned_authenticated_draft_with_made_up_token_is_404(self):
        # Um draft que NUNCA foi anônimo (owner sempre foi de alguém) não
        # pode ser "reivindicado" por outro usuário só inventando um token.
        owner = make_user("owner@example.com")
        draft = ExperienceDraft.objects.create(owner=owner)
        other_user = make_user("other@example.com")

        response = auth_client(other_user).post(claim_url(draft.id), {"claim_token": "anything"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ExperienceDraft.objects.get(id=draft.id).owner_id, owner.id)

    def test_failed_claim_attempt_writes_nothing(self):
        draft_id, _ = create_anonymous_draft()
        user = make_user()
        before = ExperienceDraft.objects.get(id=draft_id)

        auth_client(user).post(claim_url(draft_id), {"claim_token": "wrong"}, format="json")

        after = ExperienceDraft.objects.get(id=draft_id)
        self.assertEqual(before.updated_at, after.updated_at)
        self.assertIsNone(after.owner_id)


class ClaimRaceConditionTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        cache.clear()

    def test_two_concurrent_claims_by_different_users_never_produce_two_owners(self):
        client = APIClient()
        response = client.post(DRAFTS_URL, {}, format="json")
        draft_id, token = response.data["id"], response.data["claim_token"]

        user_a = make_user("racer-a@example.com")
        user_b = make_user("racer-b@example.com")

        barrier = threading.Barrier(2)
        results = []
        errors = []

        def worker(user):
            try:
                thread_client = auth_client(user)
                barrier.wait(timeout=5)
                for attempt in range(5):
                    try:
                        resp = thread_client.post(claim_url(draft_id), {"claim_token": token}, format="json")
                        results.append((user.id, resp.status_code))
                        return
                    except OperationalError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(u,)) for u in (user_a, user_b)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)

        successes = [uid for uid, code in results if code == status.HTTP_200_OK]
        failures = [uid for uid, code in results if code == status.HTTP_404_NOT_FOUND]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)

        draft = ExperienceDraft.objects.get(id=draft_id)
        self.assertEqual(draft.owner_id, successes[0])
        self.assertIsNone(draft.claim_token)


# ---------------------------------------------------------------------------
# 7/16 — draft reivindicado: só o dono; nunca mais aceita token anônimo
# ---------------------------------------------------------------------------


class PostClaimAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.draft_id, self.token = create_anonymous_draft(title="Antes de reivindicar")
        self.owner = make_user("owner@example.com")
        auth_client(self.owner).post(claim_url(self.draft_id), {"claim_token": self.token}, format="json")

    def test_owner_can_access_normally_after_claim(self):
        response = auth_client(self.owner).get(draft_url(self.draft_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_patch_normally_after_claim(self):
        response = auth_client(self.owner).patch(
            draft_url(self.draft_id), {"title": "Depois de reivindicar"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_another_authenticated_user_cannot_access_the_claimed_draft(self):
        other_user = make_user("intruder@example.com")
        response = auth_client(other_user).get(draft_url(self.draft_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_another_authenticated_user_cannot_patch_the_claimed_draft(self):
        other_user = make_user("intruder@example.com")
        response = auth_client(other_user).patch(
            draft_url(self.draft_id), {"title": "invadido"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotEqual(ExperienceDraft.objects.get(id=self.draft_id).title, "invadido")

    def test_old_anonymous_token_no_longer_grants_get_access(self):
        response = anon_client().get(draft_url(self.draft_id), HTTP_X_DRAFT_CLAIM_TOKEN=self.token)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_anonymous_token_no_longer_grants_patch_access(self):
        response = anon_client().patch(
            draft_url(self.draft_id), {"title": "x"}, format="json", HTTP_X_DRAFT_CLAIM_TOKEN=self.token
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_anonymous_token_no_longer_grants_media_upload(self):
        with patch_r2_upload():
            response = anon_client().post(
                upload_intent_url(self.draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
                HTTP_X_DRAFT_CLAIM_TOKEN=self.token,
            )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# 17/18 — checkout e publicação continuam inalcançáveis para draft anônimo
# ---------------------------------------------------------------------------


class AnonymousDraftCannotReachCheckoutOrPublishTests(TestCase):
    def setUp(self):
        cache.clear()
        self.draft_id, self.token = create_anonymous_draft()

    def test_anonymous_checkout_attempt_is_401(self):
        response = anon_client().post(
            checkout_url(self.draft_id), {"plan_code": "weekly"}, format="json",
            HTTP_X_DRAFT_CLAIM_TOKEN=self.token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_cannot_checkout_an_unclaimed_draft(self):
        # Mesmo autenticado, um draft que ainda não é seu (owner=None) não
        # aparece pra ele — get_object_or_404(..., owner=request.user)
        # nunca bate com owner=None.
        user = make_user()
        response = auth_client(user).post(
            checkout_url(self.draft_id), {"plan_code": "weekly"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Payment.objects.count(), 0)

    def test_anonymous_publish_attempt_is_401(self):
        response = anon_client().post(publish_url(self.draft_id), HTTP_X_DRAFT_CLAIM_TOKEN=self.token)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_cannot_publish_an_unclaimed_draft(self):
        user = make_user()
        response = auth_client(user).post(publish_url(self.draft_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ExperienceDraft.objects.get(id=self.draft_id).status, ExperienceDraft.Status.DRAFT)

    def test_claimed_draft_can_reach_checkout_normally(self):
        # Regressão: depois de reivindicado, o fluxo de pagamento volta a
        # ser 100% o de sempre — nada na Etapa 10 muda checkout/pagamento.
        user = make_user()
        auth_client(user).post(claim_url(self.draft_id), {"claim_token": self.token}, format="json")

        fake_client = MagicMock()
        fake_client.create_order.return_value = MagicMock(
            order_id="ORD-1", status="action_required", status_detail=None, payment_id=None, raw={}
        )
        with patch("apps.payments.services.checkout_service.MercadoPagoClient", return_value=fake_client):
            response = auth_client(user).post(
                checkout_url(self.draft_id), {"plan_code": "weekly"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(draft_id=self.draft_id).count(), 1)


# ---------------------------------------------------------------------------
# 19 — usuário autenticado continua exatamente como antes
# ---------------------------------------------------------------------------


class AuthenticatedFlowUnchangedTests(TestCase):
    def test_full_authenticated_create_patch_get_round_trip(self):
        user = make_user()
        client = auth_client(user)

        created = client.post(DRAFTS_URL, {"title": "Minha experiência"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        draft_id = created.data["id"]

        patched = client.patch(draft_url(draft_id), {"letter": "Uma carta"}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_200_OK)

        fetched = client.get(draft_url(draft_id))
        self.assertEqual(fetched.status_code, status.HTTP_200_OK)
        self.assertEqual(fetched.data["letter"], "Uma carta")

    def test_authenticated_media_upload_still_works_without_any_header(self):
        user = make_user()
        client = auth_client(user)
        draft_id = client.post(DRAFTS_URL, {}, format="json").data["id"]

        with patch_r2_upload():
            intent = client.post(
                upload_intent_url(draft_id),
                {"media_type": "photo", "filename": "foto.jpg", "mime_type": "image/jpeg", "size_bytes": 1000},
                format="json",
            )
        self.assertEqual(intent.status_code, status.HTTP_201_CREATED)

        with patch_r2_complete():
            complete = client.post(upload_complete_url(draft_id, intent.data["media_id"]))
        self.assertEqual(complete.status_code, status.HTTP_200_OK)

    def test_other_users_draft_is_still_404_for_get_patch_delete(self):
        owner = make_user("owner@example.com")
        stranger = make_user("stranger@example.com")
        draft_id = auth_client(owner).post(DRAFTS_URL, {}, format="json").data["id"]

        stranger_client = auth_client(stranger)
        self.assertEqual(stranger_client.get(draft_url(draft_id)).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            stranger_client.patch(draft_url(draft_id), {"title": "x"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(stranger_client.delete(draft_url(draft_id)).status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Auditoria de segurança (Achado #1) — NUM_PROXIES=1 também protege
# draft_claim, o outro throttle deste app (além de anonymous_draft_create)
# afetado pelo bypass via X-Forwarded-For. Mesma configuração global de
# config/settings.py — ver apps.accounts.tests.RateLimitProxyIdentificationTests
# para os testes equivalentes em login/register.
# ---------------------------------------------------------------------------


class DraftClaimThrottleProxyIdentificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()
        self.client = auth_client(self.user)

    def test_varying_the_forwarded_for_prefix_no_longer_bypasses_the_draft_claim_throttle(self):
        # DEFAULT_THROTTLE_RATES["draft_claim"] = "20/hour". claim_token
        # errado de propósito em toda tentativa — só nos interessa o
        # status 429 (throttle), nunca o 404 do claim em si.
        real_client_ip = "203.0.113.9"
        draft_id, _token = create_anonymous_draft()

        for attempt in range(20):
            response = self.client.post(
                claim_url(draft_id),
                {"claim_token": "wrong-token"},
                format="json",
                HTTP_X_FORWARDED_FOR=f"10.0.0.{attempt},{real_client_ip}",
            )
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        response = self.client.post(
            claim_url(draft_id),
            {"claim_token": "wrong-token"},
            format="json",
            HTTP_X_FORWARDED_FOR=f"10.0.0.99,{real_client_ip}",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Variar o prefixo de X-Forwarded-For não deve mais escapar do rate limit de draft_claim.",
        )
