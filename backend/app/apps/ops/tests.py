"""Testes da Etapa 9B.4 — painel administrativo read-only (apps.ops).

Cobre exatamente as garantias exigidas para esta ferramenta existir:
- as 3 operações fixas (inventory, payment_reconcile, cleanup_preview)
  retornam o mesmo formato de relatório dos management commands que elas
  envolvem, sem duplicar a lógica (mockamos o Command.build_report para
  provar que É ELE quem é chamado, com os kwargs certos — não uma cópia);
- usuário anônimo -> 401, autenticado sem ser admin real -> 403 (inclusive
  is_staff=True sem is_superuser, o padrão de conta técnica já usado no
  projeto para o sandbox-apro-runner);
- POST/PUT/PATCH/DELETE nunca são aceitos, nem por um admin real;
- nenhuma escrita no banco acontece em nenhum cenário, mesmo com
  candidatos/dados reais nas 3 operações;
- query params desconhecidos/maliciosos (ex.: tentando nomear um
  model/método) não têm nenhum efeito — são ignorados, nunca lidos;
- não existe nenhuma rota além das 3 fixas.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.experiences.models import ExperienceDraft, Media
from apps.payments.models import Payment, Plan, WebhookEvent

User = get_user_model()

INVENTORY_URL = "/api/ops/9b4/lifecycle-inventory/"
RECONCILE_URL = "/api/ops/9b4/payment-reconcile/"
CLEANUP_URL = "/api/ops/9b4/lifecycle-cleanup-preview/"
ALL_URLS = (INVENTORY_URL, RECONCILE_URL, CLEANUP_URL)


def make_regular_user(email="user@example.com"):
    return User.objects.create_user(
        email=email, first_name="Test", last_name="User", password="strong-pass-123"
    )


def make_staff_non_superuser(email="staff@example.com"):
    # Mesmo padrão de accounts/migrations/0002_sandbox_apro_test_runner:
    # is_staff=True não é, por si só, permissão administrativa real.
    return User.objects.create_user(
        email=email, first_name="Staff", last_name="User", password="strong-pass-123",
        is_staff=True, is_superuser=False,
    )


def make_superuser(email="admin@example.com"):
    return User.objects.create_user(
        email=email, first_name="Admin", last_name="User", password="strong-pass-123",
        is_staff=True, is_superuser=True,
    )


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


def make_draft(owner, **overrides):
    defaults = {"owner": owner}
    defaults.update(overrides)
    return ExperienceDraft.objects.create(**defaults)


def make_payment(*, draft, attempt_number=1, status=Payment.Status.APPROVED, **overrides):
    plan = Plan.objects.get(code="weekly")
    defaults = {
        "draft": draft, "owner": draft.owner, "plan": plan, "attempt_number": attempt_number,
        "amount": plan.price, "currency": plan.currency, "status": status,
        "external_reference": f"memoverse-draft-{draft.id}-attempt-{attempt_number}",
        "idempotency_key": f"mv:{draft.id}:{attempt_number}",
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


def make_media(draft, **overrides):
    media_id = overrides.pop("id", uuid.uuid4())
    defaults = {
        "id": media_id, "draft": draft, "media_type": Media.Type.PHOTO,
        "storage_key": f"drafts/{draft.id}/photos/{media_id}-test.jpg",
        "original_filename": "test.jpg", "mime_type": "image/jpeg", "size_bytes": 1024,
    }
    defaults.update(overrides)
    return Media.objects.create(**defaults)


@contextmanager
def assert_no_writes():
    with patch.object(Model, "save") as mock_save, patch.object(
        Model, "delete"
    ) as mock_model_delete, patch.object(QuerySet, "update") as mock_qs_update, patch.object(
        QuerySet, "delete"
    ) as mock_qs_delete, patch.object(
        QuerySet, "bulk_create"
    ) as mock_bulk_create, patch.object(
        QuerySet, "bulk_update"
    ) as mock_bulk_update:
        try:
            yield
        finally:
            mock_save.assert_not_called()
            mock_model_delete.assert_not_called()
            mock_qs_update.assert_not_called()
            mock_qs_delete.assert_not_called()
            mock_bulk_create.assert_not_called()
            mock_bulk_update.assert_not_called()


class AuthenticationTests(TestCase):
    """401 sem token, 403 com token mas sem permissão de admin — para as 3
    rotas. Etapa 9B.6: admin agora também pode vir de
    settings.MEMOVERSE_ADMIN_EMAIL, não só de is_superuser — ver
    EmailBasedAdminTests logo abaixo para essa cobertura específica."""

    def test_anonymous_gets_401_on_all_three_routes(self):
        client = APIClient()
        for url in ALL_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, url)

    def test_regular_authenticated_user_gets_403_on_all_three_routes(self):
        user = make_regular_user()
        client = auth_client(user)
        for url in ALL_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_staff_without_superuser_gets_403_on_all_three_routes(self):
        # is_staff=True sozinho (o mesmo perfil da conta técnica
        # sandbox-apro-runner) não é suficiente — precisa de is_superuser.
        user = make_staff_non_superuser()
        client = auth_client(user)
        for url in ALL_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_superuser_gets_200_on_all_three_routes(self):
        admin = make_superuser()
        client = auth_client(admin)
        for url in ALL_URLS:
            with assert_no_writes():
                response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, url)

    def test_inactive_superuser_is_rejected(self):
        admin = make_superuser("inactive-admin@example.com")
        admin.is_active = False
        admin.save(update_fields=["is_active"])
        client = auth_client(admin)
        response = client.get(INVENTORY_URL)
        # SimpleJWT já rejeita usuário inativo na própria autenticação.
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class EmailBasedAdminTests(TestCase):
    """Etapa 9B.6: settings.MEMOVERSE_ADMIN_EMAIL como segundo caminho de
    admin, sem depender de is_superuser — contra os endpoints reais
    (não só o helper isolado, já coberto em
    apps.accounts.tests.IsProductionAdminHelperTests)."""

    @override_settings(MEMOVERSE_ADMIN_EMAIL="memoversebr@gmail.com")
    def test_matching_email_regular_user_gets_200_on_all_three_routes(self):
        user = make_regular_user("memoversebr@gmail.com")
        client = auth_client(user)
        for url in ALL_URLS:
            with assert_no_writes():
                response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, url)

    @override_settings(MEMOVERSE_ADMIN_EMAIL="memoversebr@gmail.com")
    def test_different_email_regular_user_still_gets_403(self):
        user = make_regular_user("someone-else@example.com")
        client = auth_client(user)
        for url in ALL_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    @override_settings(MEMOVERSE_ADMIN_EMAIL="memoversebr@gmail.com")
    def test_inactive_user_with_matching_email_is_rejected(self):
        user = make_regular_user("memoversebr@gmail.com")
        user.is_active = False
        user.save(update_fields=["is_active"])
        client = auth_client(user)
        response = client.get(INVENTORY_URL)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_matching_email_without_memoverse_admin_email_configured_gets_403(self):
        # Sem a variável de ambiente setada (default ""), o mesmo e-mail
        # que seria admin em produção não tem nenhum privilégio especial
        # aqui — comportamento idêntico ao de antes da 9B.6.
        user = make_regular_user("memoversebr@gmail.com")
        client = auth_client(user)
        response = client.get(INVENTORY_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(MEMOVERSE_ADMIN_EMAIL="memoversebr@gmail.com")
    def test_email_admin_never_writes_even_with_check_r2_and_real_candidates(self):
        # Mesma garantia de read-only da 9B.4/9B.5, agora para o segundo
        # caminho de admin também — não é suficiente só checar 200, tem
        # que continuar sem nenhuma escrita. R2 mockado (mesmo padrão de
        # ReportContentAndReadOnlyTests) para nunca depender de rede real.
        user = make_regular_user("memoversebr@gmail.com")
        client = auth_client(user)

        mock_r2_client = MagicMock()
        mock_r2_client.head_object.return_value = {}
        mock_r2_client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}

        with patch(
            "apps.experiences.management.commands.lifecycle_cleanup.r2_is_configured", return_value=True
        ), patch(
            "apps.experiences.management.commands.lifecycle_cleanup.get_r2_client", return_value=mock_r2_client
        ), patch(
            "apps.experiences.management.commands.lifecycle_cleanup.settings.R2_BUCKET_NAME", "test-bucket"
        ):
            with assert_no_writes():
                response = client.get(CLEANUP_URL, {"check_r2": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class MethodNotAllowedTests(TestCase):
    """Nem um admin real consegue POST/PUT/PATCH/DELETE nestas rotas."""

    def setUp(self):
        self.client = auth_client(make_superuser())

    def test_post_put_patch_delete_are_rejected_on_all_three_routes(self):
        for url in ALL_URLS:
            for method in ("post", "put", "patch", "delete"):
                with assert_no_writes():
                    response = getattr(self.client, method)(url, data={})
                self.assertEqual(
                    response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED, f"{method.upper()} {url}"
                )


class NoRouteOtherThanTheThreeFixedOnesTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser())

    def test_unknown_ops_path_is_404_not_a_dynamic_dispatch(self):
        # Prova que não existe um <str:operation>/ genérico: qualquer outro
        # segmento sob /api/ops/9b4/ simplesmente não resolve a rota nenhuma.
        for path in ("lifecycle_inventory", "payment-reconcile-apply", "cleanup", "apply", "shell", "sql"):
            response = self.client.get(f"/api/ops/9b4/{path}/")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, path)


class UnknownQueryParamsAreIgnoredTests(TestCase):
    """Nenhum query param não-declarado tem qualquer efeito — em particular,
    nenhum nome de model/método/função passado na query influencia o que
    roda."""

    def setUp(self):
        self.client = auth_client(make_superuser())

    def test_extraneous_and_malicious_looking_params_have_no_effect(self):
        baseline = self.client.get(INVENTORY_URL).json()
        baseline.pop("generated_at")

        malicious = self.client.get(
            INVENTORY_URL,
            {
                "model": "Payment",
                "method": "delete",
                "function": "os.system",
                "apply": "true",
                "__class__": "x",
                "eval": "__import__('os').system('id')",
            },
        ).json()
        malicious.pop("generated_at")

        self.assertEqual(baseline, malicious)

    def test_apply_param_has_no_effect_on_cleanup_preview(self):
        # Não existe nenhum modo de aplicar exclusão nesta view — passar
        # apply=true na query é só mais um param desconhecido, ignorado.
        with assert_no_writes():
            response = self.client.get(CLEANUP_URL, {"apply": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("candidates", response.json())
        self.assertIn("never_removed", response.json())


class QueryValidationTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser())

    def test_out_of_bounds_limit_is_rejected_with_400(self):
        response = self.client.get(RECONCILE_URL, {"limit": "999999"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_days_is_rejected_with_400(self):
        response = self.client.get(CLEANUP_URL, {"draft_abandoned_days": "-1"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_integer_value_is_rejected_with_400(self):
        response = self.client.get(INVENTORY_URL, {"stale_media_minutes": "not-a-number"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReusesExactCommandLogicTests(TestCase):
    """Prova mais direta do requisito 'reutilizar exatamente as queries':
    mocka Command.build_report inteiro e confere que a view chama
    exatamente esse método, com os kwargs derivados 1:1 da query string —
    nenhuma reimplementação, nenhum passo intermediário que transforme o
    resultado."""

    def setUp(self):
        self.client = auth_client(make_superuser())

    def test_inventory_view_delegates_to_command_build_report_with_exact_kwargs(self):
        # build_report() é mockado com um dict NOVO a cada chamada (nunca
        # reaproveitando a mesma instância) para que a asserção abaixo prove
        # de verdade que a view mescla "users" por cima do que o Command
        # devolveu, em vez de só coincidir por os dois lados apontarem para
        # o mesmo objeto mutado in-place.
        with patch(
            "apps.ops.views.LifecycleInventoryCommand.build_report",
            side_effect=lambda **kwargs: {"drafts": "fake"},
        ) as mock_build:
            response = self.client.get(INVENTORY_URL, {"check_r2": "true", "r2_sample_limit": "50"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # setUp() cria exatamente 1 usuário (o superuser autenticado).
        self.assertEqual(response.json(), {"drafts": "fake", "users": {"total": 1}})
        mock_build.assert_called_once_with(
            stale_media_minutes=None, check_r2=True, r2_sample_limit=50, r2_list_limit=5000
        )

    def test_reconcile_view_delegates_to_command_build_report_with_exact_kwargs(self):
        fake_report = {"queried": "fake"}
        with patch(
            "apps.ops.views.PaymentReconcileCommand.build_report", return_value=fake_report
        ) as mock_build:
            response = self.client.get(RECONCILE_URL, {"stale_minutes": "30", "limit": "10"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), fake_report)
        mock_build.assert_called_once_with(stale_minutes=30, limit=10)

    def test_cleanup_preview_view_delegates_to_command_build_report_with_exact_kwargs(self):
        fake_report = {"candidates": "fake"}
        with patch(
            "apps.ops.views.LifecycleCleanupCommand.build_report", return_value=fake_report
        ) as mock_build:
            response = self.client.get(CLEANUP_URL, {"draft_abandoned_days": "10", "check_r2": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), fake_report)
        mock_build.assert_called_once_with(
            draft_abandoned_days=10, draft_anonymous_unclaimed_hours=48, payment_failed_days=30,
            media_failed_days=7, r2_orphan_grace_days=30, stale_media_minutes=None, check_r2=True,
            r2_list_limit=5000,
        )


class ReportContentAndReadOnlyTests(TestCase):
    """Fim-a-fim (sem mockar build_report): monta dado real, chama a view
    de verdade, confere que o relatório tem cara de relatório real e que
    nada foi escrito — inclusive nos casos com --check-r2/rede mockada."""

    def setUp(self):
        self.admin_client = auth_client(make_superuser())
        owner = make_regular_user("owner@example.com")
        self.draft = make_draft(owner, status=ExperienceDraft.Status.AWAITING_PAYMENT)
        self.payment = make_payment(draft=self.draft, status=Payment.Status.PENDING, mp_order_id="ORD-1")
        make_media(self.draft, upload_status=Media.UploadStatus.PENDING)

    def test_inventory_report_has_expected_shape(self):
        with assert_no_writes():
            response = self.admin_client.get(INVENTORY_URL)
        body = response.json()
        self.assertEqual(
            set(body.keys()), {"generated_at", "mode", "drafts", "payments", "media", "r2", "users"}
        )
        self.assertGreaterEqual(body["payments"]["total"], 1)
        # 2 usuários existem neste teste: o superuser autenticado (setUp) e
        # o owner do draft/payment/media de fixture.
        self.assertEqual(body["users"]["total"], 2)

    def test_cleanup_preview_report_has_expected_shape(self):
        with assert_no_writes():
            response = self.admin_client.get(CLEANUP_URL)
        body = response.json()
        self.assertIn("candidates", body)
        self.assertIn("never_removed", body)
        self.assertNotIn("apply", body)

    def test_reconcile_report_never_calls_confirmation_service_and_never_writes(self):
        mock_client = MagicMock()
        mock_client.get_order.return_value = MagicMock(
            status="processed", status_detail=None, payment_id="PAY-1", raw={}, order_id="ORD-1"
        )
        with patch(
            "apps.payments.management.commands.payment_reconcile.MercadoPagoClient",
            return_value=mock_client,
        ), patch(
            "apps.payments.management.commands.payment_reconcile.PaymentConfirmationService.confirm_from_result"
        ) as mock_confirm:
            with assert_no_writes():
                response = self.admin_client.get(RECONCILE_URL, {"stale_minutes": "1"})

        body = response.json()
        self.assertIn("queried", body)
        mock_confirm.assert_not_called()

    def test_cleanup_preview_with_check_r2_never_writes_even_with_real_looking_candidates(self):
        mock_r2_client = MagicMock()
        mock_r2_client.head_object.return_value = {}
        mock_r2_client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}

        with patch(
            "apps.experiences.management.commands.lifecycle_cleanup.r2_is_configured", return_value=True
        ), patch(
            "apps.experiences.management.commands.lifecycle_cleanup.get_r2_client", return_value=mock_r2_client
        ), patch(
            "apps.experiences.management.commands.lifecycle_cleanup.settings.R2_BUCKET_NAME", "test-bucket"
        ):
            with assert_no_writes():
                response = self.admin_client.get(CLEANUP_URL, {"check_r2": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["candidates"]["r2_orphans_past_grace"]["checked"])

    def test_snapshot_is_identical_before_and_after_hitting_all_three_routes(self):
        def snapshot():
            return (
                list(ExperienceDraft.objects.order_by("id").values_list("id", "status", "updated_at")),
                list(Payment.objects.order_by("id").values_list("id", "status", "updated_at")),
                list(Media.objects.order_by("id").values_list("id", "upload_status")),
            )

        before = snapshot()
        self.admin_client.get(INVENTORY_URL)
        self.admin_client.get(CLEANUP_URL)
        with patch("apps.payments.management.commands.payment_reconcile.MercadoPagoClient") as mock_cls:
            mock_cls.return_value.get_order.return_value = MagicMock(
                status="created", status_detail=None, payment_id=None, raw={}, order_id="ORD-1"
            )
            self.admin_client.get(RECONCILE_URL, {"stale_minutes": "1"})
        after = snapshot()

        self.assertEqual(before, after)


# ----------------------------------------------------------------------
# Listagens administrativas do painel /admin (Usuários/Experiências/
# Pagamentos/Logs/Configurações) — mesmas garantias de auth/read-only das
# 3 rotas da 9B.4, cobertas em classes separadas (não misturadas em
# ALL_URLS) para manter os nomes dos testes acima ("...on_all_three_
# routes") literalmente corretos.
# ----------------------------------------------------------------------

ADMIN_USERS_URL = "/api/ops/9b4/users/"
ADMIN_EXPERIENCES_URL = "/api/ops/9b4/experiences/"
ADMIN_PAYMENTS_URL = "/api/ops/9b4/payments/"
ADMIN_WEBHOOK_EVENTS_URL = "/api/ops/9b4/webhook-events/"
ADMIN_SETTINGS_URL = "/api/ops/9b4/settings-snapshot/"
ADMIN_LIST_URLS = (
    ADMIN_USERS_URL,
    ADMIN_EXPERIENCES_URL,
    ADMIN_PAYMENTS_URL,
    ADMIN_WEBHOOK_EVENTS_URL,
    ADMIN_SETTINGS_URL,
)


class AdminListEndpointsAuthenticationTests(TestCase):
    def test_anonymous_gets_401_on_all_admin_list_routes(self):
        client = APIClient()
        for url in ADMIN_LIST_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, url)

    def test_regular_authenticated_user_gets_403_on_all_admin_list_routes(self):
        user = make_regular_user()
        client = auth_client(user)
        for url in ADMIN_LIST_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_staff_without_superuser_gets_403_on_all_admin_list_routes(self):
        user = make_staff_non_superuser()
        client = auth_client(user)
        for url in ADMIN_LIST_URLS:
            response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_superuser_gets_200_on_all_admin_list_routes(self):
        admin = make_superuser()
        client = auth_client(admin)
        for url in ADMIN_LIST_URLS:
            with assert_no_writes():
                response = client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, url)


class AdminListEndpointsMethodNotAllowedTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser())

    def test_post_put_patch_delete_are_rejected(self):
        for url in ADMIN_LIST_URLS:
            for method in ("post", "put", "patch", "delete"):
                with assert_no_writes():
                    response = getattr(self.client, method)(url, data={})
                self.assertEqual(
                    response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED, f"{method.upper()} {url}"
                )


class UserListViewTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser("admin-lister@example.com"))

    def test_never_exposes_password_field(self):
        make_regular_user("someone-listed@example.com")
        response = self.client.get(ADMIN_USERS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn("results", body)
        self.assertGreater(len(body["results"]), 0)
        for row in body["results"]:
            self.assertNotIn("password", row)

    def test_is_admin_reflects_is_production_admin_never_a_second_rule(self):
        make_regular_user("regular-for-list@example.com")
        make_superuser("super-for-list@example.com")
        response = self.client.get(ADMIN_USERS_URL)
        rows_by_email = {row["email"]: row for row in response.json()["results"]}
        self.assertFalse(rows_by_email["regular-for-list@example.com"]["is_admin"])
        self.assertTrue(rows_by_email["super-for-list@example.com"]["is_admin"])

    def test_pagination_limit_and_offset_are_respected(self):
        for i in range(5):
            make_regular_user(f"paginated-{i}@example.com")
        response = self.client.get(ADMIN_USERS_URL, {"limit": "2", "offset": "0"})
        body = response.json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["limit"], 2)
        self.assertGreaterEqual(body["count"], 6)

    def test_out_of_bounds_limit_is_rejected_with_400(self):
        response = self.client.get(ADMIN_USERS_URL, {"limit": "999999"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ExperienceListViewTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser("admin-exp@example.com"))

    def test_never_exposes_private_content_fields(self):
        owner = make_regular_user("owner-exp@example.com")
        make_draft(owner, title="Titulo Secreto", letter="Carta privada", recipient_name="Fulano")
        response = self.client.get(ADMIN_EXPERIENCES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for row in response.json()["results"]:
            for forbidden_field in (
                "title",
                "letter",
                "recipient_name",
                "creator_name",
                "short_message",
                "context_answer",
                "music_url",
            ):
                self.assertNotIn(forbidden_field, row)

    def test_status_filter_only_returns_matching_rows(self):
        owner = make_regular_user("owner-exp-2@example.com")
        make_draft(owner, status=ExperienceDraft.Status.PUBLISHED, slug="abcdefgh")
        make_draft(owner, status=ExperienceDraft.Status.DRAFT)
        response = self.client.get(ADMIN_EXPERIENCES_URL, {"status": "published"})
        body = response.json()
        self.assertGreater(len(body["results"]), 0)
        self.assertTrue(all(row["status"] == "published" for row in body["results"]))

    def test_invalid_status_is_rejected_with_400(self):
        response = self.client.get(ADMIN_EXPERIENCES_URL, {"status": "not-a-real-status"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PaymentListViewTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser("admin-pay@example.com"))

    def test_never_exposes_last_sync_payload(self):
        owner = make_regular_user("owner-pay@example.com")
        draft = make_draft(owner)
        make_payment(draft=draft, last_sync_payload={"card_secret": "should-never-leak"})
        response = self.client.get(ADMIN_PAYMENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertGreater(len(results), 0)
        for row in results:
            self.assertNotIn("last_sync_payload", row)

    def test_status_filter_only_returns_matching_rows(self):
        owner = make_regular_user("owner-pay-2@example.com")
        draft1 = make_draft(owner)
        make_payment(draft=draft1, status=Payment.Status.APPROVED)
        draft2 = make_draft(owner)
        make_payment(draft=draft2, status=Payment.Status.REJECTED)
        response = self.client.get(ADMIN_PAYMENTS_URL, {"status": "approved"})
        body = response.json()
        self.assertGreater(len(body["results"]), 0)
        self.assertTrue(all(row["status"] == "approved" for row in body["results"]))


class WebhookEventListViewTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser("admin-log@example.com"))

    def test_never_exposes_raw_payload(self):
        WebhookEvent.objects.create(
            notification_id="notif-admin-panel-test",
            topic="payment",
            resource_id="res-1",
            payload={"card": {"secret": "should-never-leak"}},
            status=WebhookEvent.Status.PROCESSED,
        )
        response = self.client.get(ADMIN_WEBHOOK_EVENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertGreater(len(results), 0)
        for row in results:
            self.assertNotIn("payload", row)


class SettingsSnapshotViewTests(TestCase):
    def setUp(self):
        self.client = auth_client(make_superuser("admin-settings@example.com"))

    def test_never_exposes_secret_looking_fields(self):
        response = self.client.get(ADMIN_SETTINGS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        forbidden_keys = {
            "secret_key",
            "mp_access_token",
            "mp_webhook_secret",
            "r2_access_key_id",
            "r2_secret_access_key",
            "database_url",
            "resend_api_key",
        }
        self.assertFalse(forbidden_keys & set(body.keys()))

    def test_returns_expected_shape(self):
        response = self.client.get(ADMIN_SETTINGS_URL)
        body = response.json()
        for key in ("debug", "mercado_pago_environment", "r2_configured", "email_backend", "allowed_hosts"):
            self.assertIn(key, body)
