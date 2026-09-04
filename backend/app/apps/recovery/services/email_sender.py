from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_recovery_email(*, to_email: str, subject: str, body: str) -> None:
    """Mesmo padrão de
    apps.accounts.services.email_service.send_password_reset_email: sem
    RESEND_API_KEY configurada (dev local e testes automatizados), cai no
    backend de e-mail padrão do Django (console em dev, locmem em
    `manage.py test`) — nunca uma chamada de rede real nesses dois casos.
    Nunca loga `to_email`/`body` — só o evento, no chamador (management
    command)."""

    api_key = getattr(settings, "RESEND_API_KEY", "")
    if not api_key:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email])
        return

    import resend  # type: ignore[import]

    resend.api_key = api_key
    resend.Emails.send(
        {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
    )
