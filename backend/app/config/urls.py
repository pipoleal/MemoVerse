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
    # Etapa 9B.4: painel administrativo read-only temporário — cada view
    # exige IsAuthenticated + IsProductionAdmin (is_superuser real, ver
    # apps.accounts.permissions.IsProductionAdmin), nunca alcançável sem
    # essas duas checagens. Remover junto com apps.ops quando a 9B.4
    # terminar (ver apps/ops/__init__.py).
    path("api/ops/9b4/", include("apps.ops.urls")),
]
