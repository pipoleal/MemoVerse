from django.contrib import admin

from .models import Payment, Plan, WebhookEvent


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "price", "currency", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("code", "name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "draft", "owner", "plan", "attempt_number", "amount", "status", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("external_reference", "mp_order_id", "mp_payment_id")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("notification_id", "topic", "resource_id", "status", "created_at", "processed_at")
    list_filter = ("status", "topic")
    search_fields = ("notification_id", "resource_id")
