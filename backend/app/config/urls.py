from django.urls import include, path

from apps.experiences.views import PublicExperienceView

from .views import HealthCheckView

urlpatterns = [
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/experiences/", include("apps.experiences.urls")),
    path("api/payments/", include("apps.payments.urls")),
    # Único prefixo sem autenticação de toda a API — deliberadamente fora de
    # api/experiences/ (que é toda autenticada/ownership) para deixar
    # explícito, só pela URL, que esta rota é pública.
    path("api/public/experiences/<slug:slug>/", PublicExperienceView.as_view(), name="public-experience"),
    # Backend read-only do painel administrativo (frontend em /admin) —
    # cada view exige IsAuthenticated + IsProductionAdmin (ver
    # apps.accounts.permissions.IsProductionAdmin), nunca alcançável sem
    # essas duas checagens (ver apps/ops/__init__.py).
    path("api/ops/9b4/", include("apps.ops.urls")),
]
