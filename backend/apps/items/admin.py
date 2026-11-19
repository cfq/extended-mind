from django.contrib import admin

from apps.items.models import FetchAttempt, Item, ItemSource, ItemTag, Tag


class ItemSourceInline(admin.TabularInline):
    model = ItemSource
    extra = 0
    readonly_fields = ("kind", "filename", "url", "mime", "size", "sha256")


FETCH_ATTEMPT_FIELDS = (
    "method",
    "outcome",
    "http_status",
    "message",
    "started_at",
    "finished_at",
)


class FetchAttemptInline(admin.TabularInline):
    model = FetchAttempt
    extra = 0
    can_delete = False
    readonly_fields = FETCH_ATTEMPT_FIELDS
    fields = FETCH_ATTEMPT_FIELDS

    def has_add_permission(self, request, obj=None):
        return False


class ItemTagInline(admin.TabularInline):
    model = ItemTag
    extra = 0
    readonly_fields = ("tag", "source", "created_at")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "url")
    inlines = [ItemTagInline, ItemSourceInline, FetchAttemptInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "user", "created_at")
    search_fields = ("name",)


@admin.register(FetchAttempt)
class FetchAttemptAdmin(admin.ModelAdmin):
    list_display = ("item", "method", "outcome", "http_status", "message", "started_at")
    list_filter = ("outcome", "method")
    search_fields = ("item__title", "item__url", "message")
    readonly_fields = ("item", *FETCH_ATTEMPT_FIELDS)
    list_select_related = ("item",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
