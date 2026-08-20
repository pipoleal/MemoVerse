from rest_framework import serializers

from ..models import Plan


class CheckoutRequestSerializer(serializers.Serializer):
    """Aceita plan_code, payment_method e (somente para payment_method="card")
    os dados de token gerados pelo Card Payment Brick. Qualquer outro campo
    enviado (amount, price, currency, draft_id, external_reference,
    idempotency_key, ...) é ignorado pelo DRF por não estar declarado aqui —
    nunca influencia o fluxo.

    payment_method default="pix" preserva o contrato exato que o frontend já
    usa hoje (POST só com plan_code) — nada muda para o fluxo Pix existente.

    Os campos de cartão carregam apenas o token de uso único devolvido pelo
    Card Payment Brick e metadados não sensíveis (bandeira, parcelas) — nunca
    número do cartão, CVV ou validade, que o Brick nunca envia ao backend."""

    plan_code = serializers.CharField(max_length=50)
    payment_method = serializers.ChoiceField(choices=["pix", "card"], default="pix")

    # Somente para payment_method="card". token/payment_method_id/installments
    # são obrigatórios nesse caso (validate() abaixo); issuer_id é aceito mas
    # opcional — o Card Payment Brick o devolve, mas ele não é enviado à
    # Orders API neste primeiro escopo (não confirmado no payload documentado).
    token = serializers.CharField(required=False, allow_blank=False, trim_whitespace=False)
    payment_method_id = serializers.CharField(required=False, allow_blank=False)
    installments = serializers.IntegerField(required=False, min_value=1)
    issuer_id = serializers.CharField(required=False, allow_blank=False)

    def validate_plan_code(self, value):
        try:
            plan = Plan.objects.get(code=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plano inválido ou indisponível.")
        return plan

    def validate(self, attrs):
        if attrs.get("payment_method") == "card":
            errors = {}
            for field in ("token", "payment_method_id", "installments"):
                if field not in attrs:
                    errors[field] = "Este campo é obrigatório para pagamento com cartão."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class PlanSummarySerializer(serializers.Serializer):
    """price/currency aqui vêm sempre de Payment.amount/Payment.currency
    (congelados na criação da tentativa — ver CheckoutService._create_attempt),
    nunca de Plan.price diretamente: é o valor que será (ou foi) realmente
    cobrado, o que também cobre corretamente o override temporário de R$1
    da conta de teste (ver checkout_service.py)."""

    code = serializers.CharField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    features = serializers.DictField()


class CheckoutResponseSerializer(serializers.Serializer):
    """Somente os dados que o frontend precisa para continuar o fluxo nesta
    fase. Nunca inclui access token, secrets ou o payload bruto da MP."""

    payment_id = serializers.UUIDField()
    status = serializers.CharField()
    plan = PlanSummarySerializer()
    checkout = serializers.DictField()
