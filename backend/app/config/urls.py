from django.contrib import admin
from django.urls import include, path

from apps.experiences.views import PublicExperienceView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/experiences/", include("apps.experiences.urls")),
    path("api/payments/", include("apps.payments.urls")),
    # Único prefixo sem autenticação de toda a API — deliberadamente fora de
    # api/experiences/ (que é toda autenticada/ownership) para deixar
    # explícito, só pela URL, que esta rota é pública.
    path("api/public/experiences/<slug:slug>/", PublicExperienceView.as_view(), name="public-experience"),
]
