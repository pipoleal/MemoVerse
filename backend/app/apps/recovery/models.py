import uuid

from django.conf import settings
from django.db import models


class CartRecoveryMessage(models.Model):
    """Registro de idempotência de UM envio (draft, etapa, canal) do fluxo
    de recuperação de carrinho abandonado (ver
    apps.recovery.management.commands.cart_recovery).

    A UniqueConstraint abaixo é a ÚNICA garantia real de "nunca manda a
    mesma mensagem duas vezes para o mesmo draft": o comando roda
    periodicamente (cron) e sempre re-consulta todos os drafts elegíveis a
    cada execução — sem esta constraint, cada execução reenviaria tudo de
    novo. status=skipped_* também cria uma linha (nunca deixa o draft
    "pendurado" para ser reconsiderado toda vez) — só não conta como uma
    mensagem de verdade entregue.
    """

    class Stage(models.TextChoices):
        ONE_HOUR = "1h", "1 hora"
        ONE_DAY = "24h", "24 horas"
        THREE_DAYS = "72h", "72 horas"

    class Channel(models.TextChoices):
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        # Reserva a linha (via UniqueConstraint) ANTES de qualquer chamada de
        # rede — ver Command._claim em cart_recovery.py. Nunca o estado
        # final de um envio bem-sucedido; existe só para o instante entre
        # "eu ganhei a corrida contra um cron concorrente" e "eu já sei se o
        # envio deu certo".
        IN_PROGRESS = "in_progress", "Em andamento"
        SENT = "sent", "Enviado"
        # Nunca um estado terminal permanente: uma linha FAILED é elegível a
        # nova tentativa na próxima execução, enquanto o draft ainda
        # estiver dentro da janela da etapa (ver STAGE_WINDOWS) — diferente
        # de SENT/SKIPPED_*, que nunca são reconsiderados.
        FAILED = "failed", "Falhou"
        # Sem telefone cadastrado (User.phone vazio) — nunca um erro de
        # verdade, só a ausência do dado necessário para este canal.
        SKIPPED_NO_CONTACT = "skipped_no_contact", "Sem contato"
        # Sem WHATSAPP_API_TOKEN/WHATSAPP_PHONE_NUMBER_ID configurados (ver
        # apps.recovery.services.whatsapp_service) — nunca finge que enviou.
        SKIPPED_NOT_CONFIGURED = "skipped_not_configured", "Canal não configurado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        "experiences.ExperienceDraft",
        on_delete=models.CASCADE,
        related_name="recovery_messages",
    )
    stage = models.CharField(max_length=8, choices=Stage.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices)
    status = models.CharField(max_length=32, choices=Status.choices)
    error_detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Único propósito: distinguir um IN_PROGRESS travado há segundos (outro
    # processo ainda trabalhando de verdade) de um travado há minutos (o
    # processo anterior morreu no meio do envio) — ver
    # Command.STALE_CLAIM_AFTER. Também serve de auditoria geral (quando um
    # FAILED foi re-tentado pela última vez).
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart_recovery_messages"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "stage", "channel"],
                name="uniq_cart_recovery_message",
            )
        ]

    def __str__(self):
        return f"{self.draft_id} {self.stage}/{self.channel} -> {self.status}"


class RecoveryLoginToken(models.Model):
    """Link mágico de uso único: leva quem clicou direto para o rascunho
    dele, já autenticado — sem digitar e-mail/senha de novo. Mesmo
    raciocínio de entropia de ExperienceDraft.claim_token (Etapa 10):
    secrets.token_urlsafe(32) = 256 bits, nunca hasheado (a chance de
    adivinhação já é desprezível; o valor é de uso único e de vida curta) —
    ver apps.recovery.services.recovery_link. Ao contrário de
    PasswordResetCode, aqui não há um e-mail/usuário já identificado ANTES
    de validar o token (o clique no e-mail é o único contexto disponível),
    então o token precisa ser buscável diretamente por igualdade — daí não
    ser hasheado, exatamente como claim_token."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recovery_login_tokens",
    )
    draft = models.ForeignKey(
        "experiences.ExperienceDraft",
        on_delete=models.CASCADE,
        related_name="recovery_login_tokens",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recovery_login_tokens"
