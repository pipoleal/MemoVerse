from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/experiences/", include("apps.experiences.urls")),
    path("api/payments/", include("apps.payments.urls")),
]
