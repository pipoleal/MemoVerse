"""Envio de WhatsApp via WhatsApp Cloud API (Meta) — a API oficial da Meta,
não um SDK de terceiros; escolhida por ser a única forma de enviar mensagem
de negócio para WhatsApp sem depender de um provedor adicional (Twilio,
Gupshup etc.) além da própria Meta.

IMPORTANTE — restrição real da própria Meta, não deste código: fora de uma
janela de 24h de conversa iniciada PELO CLIENTE, uma empresa só pode
iniciar contato via WhatsApp usando um "Message Template" pré-aprovado pela
Meta (texto fixo com variáveis nomeadas, ex.: "Olá {{1}}, seu presente..."),
nunca texto livre — uma chamada com texto livre fora dessa janela é
rejeitada pela própria API deles, não é um limite arbitrário imposto aqui.
Por isso este serviço manda por TEMPLATE (nome configurável por etapa via
settings.WHATSAPP_TEMPLATE_<ETAPA>), nunca texto livre — mesmo que o corpo
"livre" já exista em apps.recovery.content para referência humana (o que
esses templates devem dizer, para cadastrar na Meta Business Manager).

Sem WHATSAPP_API_TOKEN/WHATSAPP_PHONE_NUMBER_ID configurados (o caso hoje,
em todo ambiente — nenhuma conta WhatsApp Business foi conectada ainda),
is_whatsapp_configured() volta False e nenhuma chamada de rede é feita:
nunca finge um envio que não aconteceu.
"""

from __future__ import annotations

from django.conf import settings

GRAPH_API_VERSION = "v21.0"


class WhatsAppNotConfiguredError(Exception):
    pass


class WhatsAppSendError(Exception):
    pass


def is_whatsapp_configured() -> bool:
    return bool(settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def template_name_for_stage(stage: str) -> str:
    return getattr(settings, "WHATSAPP_TEMPLATES", {}).get(stage, "")


def send_whatsapp_template(*, to_phone: str, template_name: str, body_params: list[str]) -> None:
    """`to_phone` sempre em formato E.164 (ex.: 5511999999999, sem "+" nem
    espaços) — a própria Cloud API exige esse formato. `body_params` são os
    valores, em ORDEM, das variáveis {{1}}, {{2}}... do template já
    aprovado na Meta Business Manager (nunca o texto do template em si —
    esse fica só do lado deles, uma vez aprovado)."""

    if not is_whatsapp_configured():
        raise WhatsAppNotConfiguredError("WHATSAPP_API_TOKEN/WHATSAPP_PHONE_NUMBER_ID não configurados.")

    if not template_name:
        raise WhatsAppNotConfiguredError("Nenhum template configurado para esta etapa (settings.WHATSAPP_TEMPLATES).")

    # Import tardio, mesmo raciocínio de apps.recovery.services.email_sender
    # com `resend`: sem credenciais configuradas, este módulo nunca precisa
    # de `requests` instalado nem faz nenhuma chamada de rede possível.
    import requests

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in body_params],
                }
            ],
        },
    }
    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}"},
        timeout=10,
    )
    if response.status_code >= 400:
        raise WhatsAppSendError(f"WhatsApp Cloud API respondeu {response.status_code}: {response.text[:300]}")
