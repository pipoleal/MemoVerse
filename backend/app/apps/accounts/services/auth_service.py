from apps.accounts.managers import UserManager

from typing import cast

from django.db import transaction

from apps.accounts.managers import UserManager
from apps.accounts.models import User


class AuthService:
    """
    Serviço responsável pelas regras de autenticação.
    """

    @staticmethod
    @transaction.atomic
    def register(
        *,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
    ) -> User:
        """
        Cria um novo usuário.
        """

        manager = cast(UserManager, User.objects)

        user = manager.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )

        return user