import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
)
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Modelo principal de usuário do MemoVerse.

    Utiliza autenticação por e-mail e serve como base para
    Galáxias, Experiências e todos os demais módulos da plataforma.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    email = models.EmailField(
        unique=True,
    )

    first_name = models.CharField(
        max_length=100,
    )

    last_name = models.CharField(
        max_length=100,
    )

    stars_count = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_staff = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
    ]

    class Meta:
        db_table = "users"
        ordering = ["first_name"]

    def __str__(self):
        return self.email