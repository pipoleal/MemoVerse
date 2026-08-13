"""Mapeamento de status de Order (Mercado Pago) para Payment.Status.

Fonte: documentação oficial "Status da order" (Orders API), consultada via
MCP. Usamos apenas o campo `status` de topo (não `status_detail`), porque
Payment.Status não tem um estado por `status_detail` — para o MVP eles são
tratados como o mesmo estado de negócio. O `status_detail` completo
continua disponível em Payment.last_sync_payload para auditoria.

Único ponto de verdade: reutilizado tanto pela criação síncrona do checkout
(Fase 3) quanto pela confirmação server-side via webhook (Fase 4), para que
as duas fases nunca divirjam sobre o que um status de Order significa.

Lacunas conhecidas e documentadas (não inventamos estados novos além dos já
existentes em Payment.Status):

- `processed` + `status_detail=partially_refunded`: mapeado para APPROVED,
  igual a `accredited` (mesmo `status` de topo). Payment.Status não
  distingue reembolso parcial de aprovação integral nesta fase.
- `failed`: não existe em Payment.Status; mapeado para REJECTED, o estado
  terminal desfavorável mais próximo.
- `charged_back` (qualquer status_detail): NÃO mapeado de propósito. Uma
  contestação após aprovação é um caso de negócio fora do escopo desta
  fase — ver PaymentConfirmationService, que mantém o status atual e
  registra o evento para auditoria/decisão manual em vez de regredir um
  Payment já aprovado.
"""

from __future__ import annotations

from ..models import Payment

MP_ORDER_STATUS_MAP: dict[str, str] = {
    "created": Payment.Status.PENDING,
    "processing": Payment.Status.IN_PROCESS,
    "action_required": Payment.Status.ACTION_REQUIRED,
    "processed": Payment.Status.APPROVED,
    "canceled": Payment.Status.CANCELLED,
    "expired": Payment.Status.EXPIRED,
    "failed": Payment.Status.REJECTED,
    "refunded": Payment.Status.REFUNDED,
}


def map_order_status(mp_status: str | None) -> str | None:
    """Retorna o Payment.Status correspondente, ou None se o `status` da
    Order não for reconhecido (ex.: `charged_back`) — o chamador decide o
    que fazer com "não reconhecido" (nunca inventamos um valor aqui)."""

    if mp_status is None:
        return None
    return MP_ORDER_STATUS_MAP.get(mp_status)
