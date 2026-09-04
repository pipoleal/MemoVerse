from django.urls import path

from .views import RecoveryTokenRedeemView

urlpatterns = [
    path("redeem/", RecoveryTokenRedeemView.as_view(), name="recovery-redeem"),
]
