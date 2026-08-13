from django.urls import path

from .views import DraftCheckoutView

urlpatterns = [
    path("drafts/<uuid:draft_id>/checkout/", DraftCheckoutView.as_view(), name="draft-checkout"),
]
