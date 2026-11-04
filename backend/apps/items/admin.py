from django.contrib import admin

from apps.items.models import Item, ItemSource


class ItemSourceInline(admin.TabularInline):
    model = ItemSource
    extra = 0
    readonly_fields = ("kind", "filename", "url", "mime", "size", "sha256")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "url")
    inlines = [ItemSourceInline]
