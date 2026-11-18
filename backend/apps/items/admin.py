from django.contrib import admin

from apps.items.models import Item, ItemSource, ItemTag, Tag


class ItemSourceInline(admin.TabularInline):
    model = ItemSource
    extra = 0
    readonly_fields = ("kind", "filename", "url", "mime", "size", "sha256")


class ItemTagInline(admin.TabularInline):
    model = ItemTag
    extra = 0
    readonly_fields = ("tag", "source", "created_at")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "url")
    inlines = [ItemTagInline, ItemSourceInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "user", "created_at")
    search_fields = ("name",)
