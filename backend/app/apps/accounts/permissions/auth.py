from rest_framework.permissions import BasePermission


class IsProductionAdmin(BasePermission):
    """Permissão administrativa real: usuário autenticado E is_superuser.

    Deliberadamente mais estrita que a IsAdminUser padrão do DRF (que só
    checa is_staff): is_staff=True sozinho já é usado neste projeto para
    contas técnicas de baixa confiança sem nenhum privilégio administrativo
    real (ver apps.accounts.migrations.0002_sandbox_apro_test_runner —
    is_staff=True, is_superuser=False, deliberadamente sem acesso a nada
    sensível). Qualquer view que exponha dado agregado de produção
    (lifecycle/payments — ver apps.ops, Etapa 9B.4) exige is_superuser.

    is_active já é garantido por JWTAuthentication (rest_framework_simplejwt
    rejeita token de usuário inativo antes desta permissão ser avaliada),
    mas é checado aqui de novo como defesa em profundidade — nunca confiar
    só na camada de autenticação para uma permissão deste nível.
    """

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)
