"""Minha Galáxia do destinatário — "Criar minha Galáxia".

Um visitante que recebe o link de uma experiência publicada pode guardá-la
na própria Galáxia sem se tornar dono dela (ver models.ExperienceRecipient).
Estes testes cobrem os cenários A-G descritos na tarefa: isolamento entre
experiências de um mesmo criador (A), associação idempotente (E), rejeição
de drafts privados/não publicados/de outro dono manipulados por slug ou id
(F), e que o criador continua acessando/editando a própria experiência
normalmente (G). Os cenários B/D (fluxo completo de cadastro/login) são
majoritariamente frontend (localStorage + redirecionamento) — aqui só se
testa o contrato que esse fluxo depende: o endpoint funciona para qualquer
usuário autenticado, imediatamente após login/cadastro.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ExperienceDraft, ExperienceRecipient

User = get_user_model()

RECEIVED_URL = "/api/experiences/received/"
DRAFTS_URL = "/api/experiences/drafts/"


def save_url(slug):
    return f"/api/experiences/public/{slug}/save/"


def make_user(email="user@example.com", **overrides):
    defaults = {"first_name": "Test", "last_name": "User", "password": "strong-pass-123"}
    defaults.update(overrides)
    return User.objects.create_user(email=email, **defaults)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def make_published_draft(owner, slug, **overrides):
    defaults = {
        "title": "Experiência de teste",
        "experience_type": "letter",
        "status": ExperienceDraft.Status.PUBLISHED,
        "slug": slug,
        "published_at": timezone.now(),
        "expires_at": None,
    }
    defaults.update(overrides)
    return ExperienceDraft.objects.create(owner=owner, **defaults)


class SaveToGalaxyAccessScopeTests(TestCase):
    """Cenário A: Gabriel recebe A, nunca ganha acesso a B (ou a qualquer
    outra experiência do mesmo criador que ele não tenha salvo)."""

    def setUp(self):
        self.felipe = make_user("felipe@example.com")
        self.gabriel = make_user("gabriel@example.com")
        self.experience_a = make_published_draft(self.felipe, "experience-a")
        self.experience_b = make_published_draft(self.felipe, "experience-b")

    def test_saving_a_does_not_grant_access_to_b(self):
        auth_client(self.gabriel).post(save_url("experience-a"))

        response = auth_client(self.gabriel).get(RECEIVED_URL)

        slugs = {item["slug"] for item in response.data}
        self.assertEqual(slugs, {"experience-a"})
        self.assertNotIn("experience-b", slugs)

    def test_received_experience_appears_with_same_id_as_the_public_one(self):
        auth_client(self.gabriel).post(save_url("experience-a"))

        response = auth_client(self.gabriel).get(RECEIVED_URL)

        # A mesma id da ExperienceDraft original — é isso que garante que a
        # posição da estrela (lib/galaxyStars.ts, semeada por draft.id) seja
        # determinística, sem duplicar nenhum dado.
        self.assertEqual(response.data[0]["id"], str(self.experience_a.id))

    def test_gabriel_cannot_list_felipes_drafts_endpoint(self):
        # GET /experiences/drafts/ continua exigindo ownership real — Gabriel
        # nunca vê nada do Felipe por ali, mesmo depois de salvar A.
        auth_client(self.gabriel).post(save_url("experience-a"))

        response = auth_client(self.gabriel).get(DRAFTS_URL)

        self.assertEqual(response.data, [])

    def test_only_one_recipient_row_is_ever_created_for_a_given_pair(self):
        client = auth_client(self.gabriel)
        client.post(save_url("experience-a"))
        client.post(save_url("experience-a"))
        client.post(save_url("experience-a"))

        count = ExperienceRecipient.objects.filter(user=self.gabriel, draft=self.experience_a).count()
        self.assertEqual(count, 1)


class SaveToGalaxyIdempotencyTests(TestCase):
    """Cenário E: clicar duas vezes (ou repetir a chamada) nunca duplica a
    relação nem a estrela."""

    def setUp(self):
        self.felipe = make_user("felipe@example.com")
        self.gabriel = make_user("gabriel@example.com")
        self.draft = make_published_draft(self.felipe, "abc123")

    def test_saving_twice_returns_200_both_times_and_creates_a_single_row(self):
        client = auth_client(self.gabriel)

        first = client.post(save_url("abc123"))
        second = client.post(save_url("abc123"))

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(ExperienceRecipient.objects.filter(user=self.gabriel).count(), 1)

    def test_received_list_never_shows_a_duplicate_star(self):
        client = auth_client(self.gabriel)
        client.post(save_url("abc123"))
        client.post(save_url("abc123"))

        response = client.get(RECEIVED_URL)

        self.assertEqual(len(response.data), 1)


class SaveToGalaxyManipulationTests(TestCase):
    """Cenário F: tentar associar uma experiência privada/draft/de outro
    status, ou manipular o request para obter uma experiência arbitrária."""

    def setUp(self):
        self.felipe = make_user("felipe@example.com")
        self.gabriel = make_user("gabriel@example.com")

    def test_unpublished_draft_is_not_accessible_even_with_a_slug_forced_in_db(self):
        # Um draft nunca publicado não deveria nem ter slug na prática (só
        # PublicationService atribui um) — mas mesmo que um exista por algum
        # motivo, status != PUBLISHED sozinho já basta para negar acesso,
        # exatamente como PublicExperienceView.
        draft = ExperienceDraft.objects.create(
            owner=self.felipe,
            title="Rascunho privado",
            experience_type="letter",
            status=ExperienceDraft.Status.DRAFT,
            slug="leaked-slug",
        )

        response = auth_client(self.gabriel).post(save_url(draft.slug))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(ExperienceRecipient.objects.filter(user=self.gabriel).exists())

    def test_awaiting_payment_draft_is_not_accessible(self):
        draft = ExperienceDraft.objects.create(
            owner=self.felipe,
            title="Aguardando pagamento",
            experience_type="letter",
            status=ExperienceDraft.Status.AWAITING_PAYMENT,
        )
        # Um draft neste status nunca tem slug de verdade; simulamos o pior
        # caso adversarial mesmo assim (alguém adivinhando/vazando um slug).
        draft.slug = "awaiting-slug"
        draft.save(update_fields=["slug"])

        response = auth_client(self.gabriel).post(save_url("awaiting-slug"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_expired_published_draft_is_not_accessible(self):
        draft = make_published_draft(
            self.felipe,
            "expired-slug",
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )

        response = auth_client(self.gabriel).post(save_url(draft.slug))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_slug_returns_404(self):
        response = auth_client(self.gabriel).post(save_url("does-not-exist"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_endpoint_never_accepts_a_draft_id_in_place_of_a_slug(self):
        # O endpoint só tem um parâmetro de rota (slug) — não existe um
        # segundo caminho por draft_id. Mandar o UUID como se fosse slug
        # simplesmente não bate com slug nenhum (404), provando que não há
        # forma de "enviar arbitrariamente IDs de experiências privadas".
        draft = ExperienceDraft.objects.create(
            owner=self.felipe,
            title="Privado",
            experience_type="letter",
            status=ExperienceDraft.Status.PAID,
        )

        response = auth_client(self.gabriel).post(save_url(str(draft.id)))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_visitor_cannot_call_the_save_endpoint(self):
        draft = make_published_draft(self.felipe, "public-slug")

        response = APIClient().post(save_url(draft.slug))

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertFalse(ExperienceRecipient.objects.exists())


class SaveToGalaxyOwnerNoopTests(TestCase):
    """O próprio criador nunca ganha um ExperienceRecipient de si mesmo
    (evitaria uma estrela duplicada quando /drafts/ e /received/ forem
    combinados no frontend)."""

    def setUp(self):
        self.felipe = make_user("felipe@example.com")
        self.draft = make_published_draft(self.felipe, "own-experience")

    def test_owner_saving_own_experience_is_a_noop(self):
        response = auth_client(self.felipe).post(save_url("own-experience"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ExperienceRecipient.objects.filter(user=self.felipe).exists())

    def test_owner_never_appears_in_own_received_list(self):
        auth_client(self.felipe).post(save_url("own-experience"))

        response = auth_client(self.felipe).get(RECEIVED_URL)

        self.assertEqual(response.data, [])


class CreatorUnaffectedTests(TestCase):
    """Cenário G: Felipe continua acessando/editando a própria experiência
    normalmente, mesmo depois de Gabriel salvá-la."""

    def setUp(self):
        self.felipe = make_user("felipe@example.com")
        self.gabriel = make_user("gabriel@example.com")
        self.draft = make_published_draft(self.felipe, "felipes-experience")
        auth_client(self.gabriel).post(save_url("felipes-experience"))

    def test_felipe_still_owns_and_can_edit_his_draft(self):
        response = auth_client(self.felipe).patch(
            f"/api/experiences/drafts/{self.draft.id}/",
            {"title": "Título atualizado"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title, "Título atualizado")
        self.assertEqual(self.draft.owner_id, self.felipe.id)

    def test_felipe_still_sees_his_own_draft_in_his_own_list(self):
        response = auth_client(self.felipe).get(DRAFTS_URL)

        slugs = {item["slug"] for item in response.data}
        self.assertIn("felipes-experience", slugs)

    def test_felipes_received_list_is_unaffected_by_gabriels_save(self):
        response = auth_client(self.felipe).get(RECEIVED_URL)
        self.assertEqual(response.data, [])
