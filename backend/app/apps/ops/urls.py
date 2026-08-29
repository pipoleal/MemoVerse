from django.urls import path

from .views import (
    ExperienceListView,
    LifecycleCleanupPreviewView,
    LifecycleInventoryReportView,
    PaymentListView,
    PaymentReconcileReportView,
    SettingsSnapshotView,
    UserListView,
    WebhookEventListView,
)

# URLs fixas, uma por operação — de propósito, em vez de uma única rota
# com um segmento dinâmico tipo <str:operation>/. Cada path aqui resolve,
# em tempo de import (não por requisição), para uma classe de view
# hardcoded — não existe string vinda do cliente usada para escolher qual
# código roda. As 3 primeiras são as da Etapa 9B.4 (relatórios de
# lifecycle/reconciliação); as demais alimentam as listagens do painel
# /admin (usuários/experiências/pagamentos/logs/configurações).
urlpatterns = [
    path("lifecycle-inventory/", LifecycleInventoryReportView.as_view(), name="ops-lifecycle-inventory"),
    path("payment-reconcile/", PaymentReconcileReportView.as_view(), name="ops-payment-reconcile"),
    path(
        "lifecycle-cleanup-preview/",
        LifecycleCleanupPreviewView.as_view(),
        name="ops-lifecycle-cleanup-preview",
    ),
    path("users/", UserListView.as_view(), name="ops-admin-users"),
    path("experiences/", ExperienceListView.as_view(), name="ops-admin-experiences"),
    path("payments/", PaymentListView.as_view(), name="ops-admin-payments"),
    path("webhook-events/", WebhookEventListView.as_view(), name="ops-admin-webhook-events"),
    path("settings-snapshot/", SettingsSnapshotView.as_view(), name="ops-admin-settings-snapshot"),
]
