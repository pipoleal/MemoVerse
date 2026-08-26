from django.conf import settings
from rest_framework.permissions import BasePermission


def is_production_admin(user) -> bool:
    """Único ponto de verdade sobre "esta conta é administradora do
    MemoVerse?" — usado tanto por IsProductionAdmin (o gate real dos
    endpoints /api/ops/9b4/*) quanto por MeView (o campo is_admin, que o
    painel /admin usa para decidir se renderiza). Nunca duplicar esta
    lógica em nenhum outro lugar.

    Dois caminhos, qualquer um já basta (Etapa 9B.6):

    1. is_superuser=True — o caminho original, continua funcionando
       exatamente como antes, sem nenhuma mudança de comportamento.
    2. is_active=True e email == settings.MEMOVERSE_ADMIN_EMAIL — uma
       conta administrativa nomeada por e-mail, habilitada só por
       variável de ambiente (nunca hardcoded aqui, nunca no banco/numa
       migration, nunca uma senha em lugar nenhum). Comparação
       case-insensitive, mesmo padrão já usado em
       RegisterSerializer.validate_email (email__iexact). Só entra em
       jogo quando MEMOVERSE_ADMIN_EMAIL está de fato configurada —
       settings vazio (default) nunca casa com nada, então sem a
       variável de ambiente definida o comportamento é idêntico ao de
       antes desta etapa para todo mundo.

    is_active é checado explicitamente aqui como defesa em profundidade,
    mesmo já sendo garantido por JWTAuthentication (que rejeita usuário
    inativo antes de qualquer permissão ser avaliada) — nunca confiar só
    na camada de autenticação para uma decisão deste nível.
    """

    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False

    if user.is_superuser:
        return True

    admin_email = settings.MEMOVERSE_ADMIN_EMAIL
    return bool(admin_email) and user.email.lower() == admin_email.lower()


class IsProductionAdmin(BasePermission):
    """Permissão administrativa real — ver is_production_admin() acima
    para os dois caminhos aceitos. Deliberadamente mais estrita que a
    IsAdminUser padrão do DRF (que só checa is_staff): is_staff=True
    sozinho já é usado neste projeto para contas técnicas de baixa
    confiança sem nenhum privilégio administrativo real (ver
    apps.accounts.migrations.0002_sandbox_apro_test_runner —
    is_staff=True, is_superuser=False, deliberadamente sem acesso a nada
    sensível). Qualquer view que exponha dado agregado de produção
    (lifecycle/payments — ver apps.ops) exige is_production_admin(user).
    """

    def has_permission(self, request, view) -> bool:
        return is_production_admin(getattr(request, "user", None))
