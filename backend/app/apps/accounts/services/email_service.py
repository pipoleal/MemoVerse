from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, code: str, *, ttl_minutes: int) -> None:
    """Nunca loga `email` nem `code` — só o evento, em
    services.password_reset_service (chamador). O corpo do e-mail é a
    ÚNICA superfície onde o código em texto puro existe fora do processo de
    geração; ele nunca é retornado por nenhum endpoint.

    Sem RESEND_API_KEY configurada (dev local, e sempre durante os testes
    automatizados — a variável nunca é setada nesse ambiente), cai no
    backend de e-mail padrão do Django: console.EmailBackend em dev
    (imprime no terminal do runserver, nunca envia de verdade) e
    locmem.EmailBackend durante `manage.py test` (Django troca isso
    sozinho, populando django.core.mail.outbox — é assim que os testes
    verificam o conteúdo do e-mail sem nenhuma chamada de rede real).
    """

    subject = "Seu código de recuperação de senha — MemoVerse"
    text_body = (
        "Recebemos uma solicitação para redefinir a senha da sua conta MemoVerse.\n\n"
        f"Código de recuperação: {code}\n\n"
        f"Esse código expira em {ttl_minutes} minutos e só pode ser usado uma vez.\n\n"
        "Se você não solicitou isso, pode ignorar este e-mail com segurança."
    )

    api_key = getattr(settings, "RESEND_API_KEY", "")
    if not api_key:
        send_mail(subject, text_body, settings.DEFAULT_FROM_EMAIL, [email])
        return

    # Import tardio, só quando existe de fato uma chave configurada — em
    # dev/teste (sem RESEND_API_KEY) este módulo nunca é sequer importado,
    # então nenhuma chamada de rede é possível a partir daqui.
    import resend  # type: ignore[import]

    resend.api_key = api_key
    resend.Emails.send(
        {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [email],
            "subject": subject,
            "text": text_body,
        }
    )
