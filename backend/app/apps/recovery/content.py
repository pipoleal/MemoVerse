"""Textos prontos do fluxo de recuperação de carrinho abandonado — 3 etapas
x 2 canais (e-mail/WhatsApp), em português, tom romântico/emocional (público
MemoVerse: casais dando presentes virtuais).

Regra de negócio explícita (auditoria pós-implementação): este fluxo NUNCA
oferece desconto, bônus ou qualquer benefício além do que o produto já
entrega — é só um lembrete carinhoso. Isso não é um detalhe de estilo, é uma
restrição de conteúdo: nenhuma função aqui deve ganhar um parâmetro de
preço/percentual/prazo de novo (ver histórico de git — a versão anterior
tinha um bônus de 15% com prazo, removida a pedido explícito). A etapa de
72h fala em "pagamento processado com segurança" citando a Mercado Pago
(integração real, já em produção) em vez de prometer um prazo de reembolso
— não existe hoje nenhuma política de reembolso documentada em
termos-de-uso, e inventar um número aqui criaria um compromisso comercial
real sem autorização para isso.

Cada função de conteúdo é pura (recebe os dados prontos, devolve texto) —
nenhuma delas consulta o banco ou envia nada; isso é responsabilidade de
apps.recovery.services e do management command.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import CartRecoveryMessage

Stage = CartRecoveryMessage.Stage


@dataclass(frozen=True)
class EmailContent:
    subject: str
    body: str


@dataclass(frozen=True)
class WhatsAppContent:
    body: str


def _first_name_or_fallback(first_name: str) -> str:
    return first_name.strip() or "Olá"


def build_email(stage: str, *, first_name: str, recovery_url: str) -> EmailContent:
    name = _first_name_or_fallback(first_name)

    if stage == Stage.ONE_HOUR:
        return EmailContent(
            subject="Seu presente está esperando por você 💌",
            body=(
                f"Oi, {name}!\n\n"
                "Reparamos que você começou a criar uma experiência muito especial no "
                "MemoVerse, mas ainda não finalizou.\n\n"
                "Ela está guardadinha, do jeitinho que você deixou — falta só voltar e "
                "continuar de onde parou. ✨\n\n"
                "Continuar meu presente:\n"
                f"{recovery_url}\n\n"
                "Com carinho,\nEquipe MemoVerse"
            ),
        )

    if stage == Stage.ONE_DAY:
        return EmailContent(
            subject="Seu presente ainda está esperando por você 💛",
            body=(
                f"{name}, já faz um dia que você começou a criar sua experiência no "
                "MemoVerse — e ela continua exatamente onde você deixou.\n\n"
                "Sabemos como a rotina engole nossas boas intenções. Se ainda faz "
                "sentido pra você, é só voltar e continuar de onde parou.\n\n"
                "Continuar meu presente:\n"
                f"{recovery_url}\n\n"
                "Com carinho,\nEquipe MemoVerse"
            ),
        )

    return EmailContent(
        subject="Milhares de casais já transformaram memórias em presentes 💫",
        body=(
            f"{name}, seu presente continua salvo, esperando por você.\n\n"
            "Todos os dias, casais criam experiências assim para celebrar aniversários, "
            "pedidos de namoro e datas especiais — e recebem de volta a mesma reação: "
            '"nunca ganhei um presente assim".\n\n'
            "O pagamento é processado com segurança pela Mercado Pago, a mesma que você "
            "já deve conhecer de outras compras.\n\n"
            "Continuar meu presente:\n"
            f"{recovery_url}\n\n"
            "Com carinho,\nEquipe MemoVerse"
        ),
    )


def build_whatsapp(stage: str, *, first_name: str, recovery_url: str) -> WhatsAppContent:
    name = _first_name_or_fallback(first_name)

    if stage == Stage.ONE_HOUR:
        return WhatsAppContent(
            body=(
                f"{name}, seu presente no MemoVerse ainda está esperando por você 💌 "
                f"Continuar de onde parei: {recovery_url}"
            )
        )

    if stage == Stage.ONE_DAY:
        return WhatsAppContent(
            body=(
                f"{name}, já faz um dia que seu presente ficou por aqui 💛 Ele continua "
                f"salvo do jeitinho que você deixou. Continuar meu presente: {recovery_url}"
            )
        )

    return WhatsAppContent(
        body=(
            f"{name}, seu presente continua salvo 💫 Já são milhares de casais "
            "transformando memórias em presentes no MemoVerse, com pagamento seguro pela "
            f"Mercado Pago. Continuar meu presente: {recovery_url}"
        )
    )
