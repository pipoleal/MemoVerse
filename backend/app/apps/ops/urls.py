from django.urls import path

from .views import (
    LifecycleCleanupPreviewView,
    LifecycleInventoryReportView,
    PaymentReconcileReportView,
)

# 3 URLs fixas, uma por operação — de propósito, em vez de uma única rota
# com um segmento dinâmico tipo <str:operation>/. Cada path aqui resolve,
# em tempo de import (não por requisição), para uma classe de view
# hardcoded — não existe string vinda do cliente usada para escolher qual
# código roda.
urlpatterns = [
    path("lifecycle-inventory/", LifecycleInventoryReportView.as_view(), name="ops-lifecycle-inventory"),
    path("payment-reconcile/", PaymentReconcileReportView.as_view(), name="ops-payment-reconcile"),
    path(
        "lifecycle-cleanup-preview/",
        LifecycleCleanupPreviewView.as_view(),
        name="ops-lifecycle-cleanup-preview",
    ),
]
