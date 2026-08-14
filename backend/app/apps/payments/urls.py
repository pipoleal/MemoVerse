from django.urls import path

from .views import DraftCheckoutView, DraftPaymentStatusView, MercadoPagoWebhookView

urlpatterns = [
    path("drafts/<uuid:draft_id>/checkout/", DraftCheckoutView.as_view(), name="draft-checkout"),
    path("drafts/<uuid:draft_id>/status/", DraftPaymentStatusView.as_view(), name="draft-payment-status"),
    path("webhooks/mercadopago/", MercadoPagoWebhookView.as_view(), name="mercadopago-webhook"),
]
