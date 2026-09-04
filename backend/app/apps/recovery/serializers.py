from rest_framework import serializers


class RecoveryRedeemSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64)
