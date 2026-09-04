from django.urls import path

from .views import (
    CartRecoveryMessageListView,
    ExperienceDetailView,
    ExperienceListView,
    FunnelEventListView,
    LifecycleCleanupPreviewView,
    LifecycleInventoryReportView,
    PaymentCancelView,
    PaymentListView,
    PaymentReconcileReportView,
    PlanDiscountDeleteView,
    PlanDiscountListView,
    SettingsSnapshotView,
    UserDeleteView,
    UserListView,
    WebhookEventListView,
)

# URLs fixas, uma por operação — de propósito, em vez de uma única rota
# com um segmento dinâmico tipo <str:operation>/. Cada path aqui resolve,
# em tempo de import (não por requisição), para uma classe de view
# hardcoded — não existe string vinda do cliente usada para escolher qual
# código roda. As 3 primeiras são as da Etapa 9B.4 (relatórios de
# lifecycle/reconciliação); as demais alimentam as listagens/ações do
# painel /admin (usuários/experiências/pagamentos/logs/configurações/
# descontos). Rotas de escrita deste app — ver seus docstrings em views.py
# para as salvaguardas de cada uma: UserDeleteView (DELETE),
# PaymentCancelView (POST), PlanDiscountListView.post (POST) e
# PlanDiscountDeleteView (DELETE).
urlpatterns = [
    path("lifecycle-inventory/", LifecycleInventoryReportView.as_view(), name="ops-lifecycle-inventory"),
    path("payment-reconcile/", PaymentReconcileReportView.as_view(), name="ops-payment-reconcile"),
    path(
        "lifecycle-cleanup-preview/",
        LifecycleCleanupPreviewView.as_view(),
        name="ops-lifecycle-cleanup-preview",
    ),
    path("users/", UserListView.as_view(), name="ops-admin-users"),
    path("users/<uuid:user_id>/", UserDeleteView.as_view(), name="ops-admin-user-delete"),
    path("experiences/", ExperienceListView.as_view(), name="ops-admin-experiences"),
    path("experiences/<uuid:draft_id>/", ExperienceDetailView.as_view(), name="ops-admin-experience-detail"),
    path("payments/", PaymentListView.as_view(), name="ops-admin-payments"),
    path("payments/<uuid:payment_id>/cancel/", PaymentCancelView.as_view(), name="ops-admin-payment-cancel"),
    path("webhook-events/", WebhookEventListView.as_view(), name="ops-admin-webhook-events"),
    path("funnel-events/", FunnelEventListView.as_view(), name="ops-admin-funnel-events"),
    path(
        "cart-recovery-messages/",
        CartRecoveryMessageListView.as_view(),
        name="ops-admin-cart-recovery-messages",
    ),
    path("discounts/", PlanDiscountListView.as_view(), name="ops-admin-discounts"),
    path("discounts/<uuid:discount_id>/", PlanDiscountDeleteView.as_view(), name="ops-admin-discount-delete"),
    path("settings-snapshot/", SettingsSnapshotView.as_view(), name="ops-admin-settings-snapshot"),
]
