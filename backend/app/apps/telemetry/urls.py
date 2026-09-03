from django.urls import path

from .views import FunnelEventCreateView

urlpatterns = [
    path("", FunnelEventCreateView.as_view(), name="funnel-event-create"),
]
