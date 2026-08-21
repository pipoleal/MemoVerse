from django.contrib import admin

from .models import ExperienceDraft, Media, Theme


class ReadOnlyAdminMixin:
    """Etapa 6 — Fase C: esta fase é SOMENTE observabilidade. Negar as três
    permissões abaixo (mantendo view=True, o padrão) faz o Django renderizar
    a página de detalhe em modo view-only de verdade — sem botão Salvar, sem
    Adicionar, sem Excluir (inclusive a action embutida "Excluir
    selecionados") — em vez de confiar só em listar todo campo como
    readonly_fields, que ainda deixaria um form de mudança confuso."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExperienceDraft)
class ExperienceDraftAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "title", "owner", "status", "theme", "slug", "expires_at", "updated_at")
    list_filter = ("status", "theme")
    search_fields = ("id", "slug", "title", "recipient_name", "owner__email")
    ordering = ("-updated_at",)
    # Etapa 10: claim_token nunca deve aparecer em lugar nenhum do admin —
    # ReadOnlyAdminMixin já impede edição, mas sem excluir explicitamente o
    # campo apareceria (visível, não editável) na página de detalhe, já que
    # ModelAdmin mostra todo campo do model por padrão quando fields/exclude
    # não é declarado.
    exclude = ("claim_token",)


@admin.register(Media)
class MediaAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "draft", "media_type", "upload_status", "size_bytes", "created_at", "uploaded_at")
    list_filter = ("media_type", "upload_status")
    search_fields = ("id", "draft__id", "original_filename", "storage_key")
    ordering = ("-created_at",)


@admin.register(Theme)
class ThemeAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("sort_order", "code")
