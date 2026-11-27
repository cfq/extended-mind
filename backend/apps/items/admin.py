from django.contrib import admin

from apps.items.models import (
    ImageItem,
    Item,
    ItemSource,
    ItemStep,
    ItemStepRun,
    ItemTag,
    PageItem,
    Tag,
)
from apps.items.pipeline import steps


class ItemSourceInline(admin.TabularInline):
    model = ItemSource
    extra = 0
    readonly_fields = ("kind", "filename", "url", "mime", "size", "sha256", "run")


class ItemTagInline(admin.TabularInline):
    model = ItemTag
    extra = 0
    readonly_fields = ("tag", "source", "created_at")


class PageItemInline(admin.StackedInline):
    model = PageItem
    extra = 0
    fields = ("author", "meta")
    readonly_fields = ("meta",)


class ImageItemInline(admin.StackedInline):
    model = ImageItem
    extra = 0
    readonly_fields = ("width", "height")


class ItemStepInline(admin.TabularInline):
    model = ItemStep
    extra = 0
    can_delete = False
    fields = ("name", "state", "created_at")
    readonly_fields = fields

    @admin.display(description="State")
    def state(self, step):
        return steps.state(step)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "status", "url", "user", "created_at")
    list_filter = ("type",)
    search_fields = ("title", "url")
    inlines = [
        PageItemInline,
        ImageItemInline,
        ItemTagInline,
        ItemSourceInline,
        ItemStepInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("steps__runs")

    @admin.display(description="Status")
    def status(self, item):
        return steps.status(item)[0]


RUN_FIELDS = (
    "outcome",
    "message",
    "meta",
    "run_id",
    "started_at",
    "finished_at",
)


@admin.register(ItemStepRun)
class ItemStepRunAdmin(admin.ModelAdmin):
    list_display = ("item", "step", "outcome", "message", "started_at")
    list_filter = ("outcome", "step__name")
    search_fields = ("step__item__title", "step__item__url", "message")
    readonly_fields = ("step", *RUN_FIELDS)
    list_select_related = ("step__item",)

    @admin.display(description="Item")
    def item(self, run):
        return run.step.item.title or run.step.item.url

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "user", "created_at")
    search_fields = ("name",)
