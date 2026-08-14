from django.urls import path

from .views import DraftCheckoutView, DraftPaymentStatusView, MercadoPagoWebhookView
from .views.sandbox_apro_test import SandboxAproTestView  # TEST-ONLY / TEMPORARY

urlpatterns = [
    path("drafts/<uuid:draft_id>/checkout/", DraftCheckoutView.as_view(), name="draft-checkout"),
    path("drafts/<uuid:draft_id>/status/", DraftPaymentStatusView.as_view(), name="draft-payment-status"),
    path("webhooks/mercadopago/", MercadoPagoWebhookView.as_view(), name="mercadopago-webhook"),
    # TEST-ONLY / TEMPORARY — remover junto com views/sandbox_apro_test.py
    # e accounts/migrations/0002_sandbox_apro_test_runner.py depois do teste.
    path("sandbox-apro-test/", SandboxAproTestView.as_view(), name="sandbox-apro-test"),
]
