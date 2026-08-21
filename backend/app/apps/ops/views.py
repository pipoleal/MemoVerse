"""Etapa 9B.4 — 3 endpoints GET-only, administrativos, read-only.

Cada view abaixo é uma casca fina em volta de UM Command já existente e já
testado (lifecycle_inventory/payment_reconcile/lifecycle_cleanup): valida
os query params (apps.ops.serializers, tipados e limitados — nunca um nome
de model/método/função), instancia a MESMA classe Command usada pelo CLI, e
chama Command.build_report(**kwargs) — o mesmo método que o CLI chama, sem
nenhuma lógica duplicada.

Não existe nenhum quarto caminho: só estas 3 operações, cada uma com sua
própria URL fixa (ver urls.py) e sua própria classe de view. Nenhuma delas
aceita um parâmetro que selecione QUAL função roda — a função é sempre a
mesma, hardcoded no import no topo deste módulo.

Cada view define só `get()`. DRF (APIView.dispatch) responde 405 Method Not
Allowed sozinho para POST/PUT/PATCH/DELETE — não há necessidade (nem
intenção) de tratá-los aqui.
"""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsProductionAdmin
from apps.experiences.management.commands.lifecycle_cleanup import Command as LifecycleCleanupCommand
from apps.experiences.management.commands.lifecycle_inventory import Command as LifecycleInventoryCommand
from apps.payments.management.commands.payment_reconcile import Command as PaymentReconcileCommand

from .serializers import (
    LifecycleCleanupPreviewQuerySerializer,
    LifecycleInventoryQuerySerializer,
    PaymentReconcileQuerySerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class _BaseOpsReportView(APIView):
    """Só GET (nada mais é definido), só admin real — IsAuthenticated vem
    antes de IsProductionAdmin de propósito, para que um pedido sem token
    volte 401 (não autenticado) em vez de 403 (autenticado mas sem
    permissão), mesma distinção HTTP que o resto da API já usa."""

    permission_classes = [IsAuthenticated, IsProductionAdmin]


class LifecycleInventoryReportView(_BaseOpsReportView):
    """GET /api/ops/9b4/lifecycle-inventory/

    Mesmo relatório de `python manage.py lifecycle_inventory --dry-run`,
    acrescido de `users.total` (Etapa 9B.5 — o painel administrativo
    precisa de uma contagem total de usuários que nenhum dos 3 management
    commands expõe; é uma única query trivial, montada aqui, nunca dentro
    de Command.build_report() — o CLI e seu contrato/testes continuam
    exatamente como estavam)."""

    def get(self, request):
        query = LifecycleInventoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        logger.info("ops.lifecycle_inventory.accessed")
        report = LifecycleInventoryCommand().build_report(
            stale_media_minutes=data.get("stale_media_minutes"),
            check_r2=data.get("check_r2", False),
            r2_sample_limit=data.get("r2_sample_limit", 200),
            r2_list_limit=data.get("r2_list_limit", 5000),
        )
        report["users"] = {"total": User.objects.count()}
        return Response(report)


class PaymentReconcileReportView(_BaseOpsReportView):
    """GET /api/ops/9b4/payment-reconcile/

    Mesmo relatório de `python manage.py payment_reconcile --dry-run`.
    Faz chamadas de rede reais, só leitura (GET /v1/orders/{id}), contra a
    Mercado Pago — nunca escreve lá nem aqui."""

    def get(self, request):
        query = PaymentReconcileQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        logger.info("ops.payment_reconcile.accessed")
        report = PaymentReconcileCommand().build_report(
            stale_minutes=data.get("stale_minutes", 60),
            limit=data.get("limit", 50),
        )
        return Response(report)


class LifecycleCleanupPreviewView(_BaseOpsReportView):
    """GET /api/ops/9b4/lifecycle-cleanup-preview/

    Mesmo relatório de `python manage.py lifecycle_cleanup --dry-run`
    (com `--check-r2` opcional). Nunca implementa `--apply` — esse modo
    não existe em nenhuma classe Command reutilizada aqui."""

    def get(self, request):
        query = LifecycleCleanupPreviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        logger.info("ops.lifecycle_cleanup_preview.accessed")
        report = LifecycleCleanupCommand().build_report(
            draft_abandoned_days=data.get("draft_abandoned_days", 30),
            payment_failed_days=data.get("payment_failed_days", 30),
            media_failed_days=data.get("media_failed_days", 7),
            r2_orphan_grace_days=data.get("r2_orphan_grace_days", 30),
            stale_media_minutes=data.get("stale_media_minutes"),
            check_r2=data.get("check_r2", False),
            r2_list_limit=data.get("r2_list_limit", 5000),
        )
        return Response(report)
