from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from ..models import Plan

PLANS_URL = "/api/payments/plans/"


class PlanListViewTests(TestCase):
    """GET /api/payments/plans/ — catálogo público (AllowAny) dos planos
    comercializáveis. Ver PlanListView/PlanSerializer."""

    def test_no_authentication_required(self):
        response = APIClient().get(PLANS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_returns_only_the_three_active_commercial_plans(self):
        response = self.client.get(PLANS_URL)
        codes = {item["code"] for item in response.data}
        self.assertEqual(codes, {"weekly", "lifetime", "lifetime_galaxy"})

    def test_essential_and_stellar_never_appear(self):
        response = self.client.get(PLANS_URL)
        codes = {item["code"] for item in response.data}
        self.assertNotIn("essential", codes)
        self.assertNotIn("stellar", codes)

    def test_an_additional_inactive_plan_never_appears(self):
        Plan.objects.create(code="inactive-plan", name="Inativo", price=Decimal("9.99"), is_active=False)
        response = self.client.get(PLANS_URL)
        codes = {item["code"] for item in response.data}
        self.assertNotIn("inactive-plan", codes)

    def test_results_are_ordered_by_price_ascending(self):
        response = self.client.get(PLANS_URL)
        codes_in_order = [item["code"] for item in response.data]
        self.assertEqual(codes_in_order, ["weekly", "lifetime", "lifetime_galaxy"])

    def test_weekly_plan_shape_and_values(self):
        response = self.client.get(PLANS_URL)
        weekly = next(item for item in response.data if item["code"] == "weekly")
        self.assertEqual(weekly["name"], "MemoVerse 1 Semana")
        # DecimalField serializa como string por padrão no DRF (evita
        # arredondamento de float) — o contrato da API é "0.10", não 0.10.
        # TEMPORÁRIO: preço original 19.90, reduzido por
        # 0007_temp_weekly_price_for_checkout_testing para testes reais de
        # checkout — reverter junto com essa migration.
        self.assertEqual(weekly["price"], "0.10")
        self.assertEqual(weekly["currency"], "BRL")
        self.assertEqual(weekly["features"]["duration_days"], 7)
        self.assertIs(weekly["features"]["is_lifetime"], False)
        self.assertIs(weekly["features"]["galaxy_live_enabled"], False)
        self.assertEqual(
            weekly["features"]["highlights"],
            [
                "Experiência personalizada",
                "Fotos e vídeos",
                "Carta personalizada",
                "Música",
                "Link compartilhável",
                "Disponível por 7 dias",
            ],
        )

    def test_lifetime_plan_shape_and_values(self):
        response = self.client.get(PLANS_URL)
        lifetime = next(item for item in response.data if item["code"] == "lifetime")
        self.assertEqual(lifetime["name"], "MemoVerse Vitalício")
        self.assertEqual(lifetime["price"], "29.90")
        self.assertIs(lifetime["features"]["is_lifetime"], True)
        self.assertIs(lifetime["features"]["galaxy_live_enabled"], False)
        self.assertEqual(
            lifetime["features"]["highlights"],
            [
                "Experiência personalizada",
                "Fotos e vídeos",
                "Carta personalizada",
                "Música",
                "Link compartilhável",
                "Disponível para sempre",
            ],
        )

    def test_lifetime_galaxy_plan_shape_and_values(self):
        response = self.client.get(PLANS_URL)
        lifetime_galaxy = next(item for item in response.data if item["code"] == "lifetime_galaxy")
        self.assertEqual(lifetime_galaxy["name"], "MemoVerse Vitalício + Galáxia Viva")
        self.assertEqual(lifetime_galaxy["price"], "39.90")
        self.assertIs(lifetime_galaxy["features"]["is_lifetime"], True)
        self.assertIs(lifetime_galaxy["features"]["galaxy_live_enabled"], True)
        self.assertEqual(
            lifetime_galaxy["features"]["highlights"],
            [
                "Experiência personalizada",
                "Fotos e vídeos",
                "Carta personalizada",
                "Música",
                "Link compartilhável",
                "Disponível para sempre",
                "Galáxia Viva",
                "Recursos especiais da Galáxia Viva",
            ],
        )

    def test_weekly_and_lifetime_highlights_never_mention_each_other(self):
        # Regra explícita: cada plano é compreensível sozinho — nenhuma
        # frase de herança tipo "Tudo do plano X" em nenhum highlight.
        response = self.client.get(PLANS_URL)
        for item in response.data:
            for highlight in item["features"]["highlights"]:
                self.assertNotIn("Tudo do", highlight)

    def test_response_items_never_expose_internal_fields(self):
        response = self.client.get(PLANS_URL)
        for item in response.data:
            self.assertEqual(set(item.keys()), {"code", "name", "price", "currency", "features"})
            self.assertNotIn("is_active", item)
            self.assertNotIn("id", item)
            self.assertNotIn("created_at", item)
            self.assertNotIn("updated_at", item)
