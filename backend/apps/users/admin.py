from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from apps.users.models import ApiToken, User


class UserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "username")


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserEditForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    list_display = ("email", "username", "is_staff")
    search_fields = ("email", "username")
    ordering = ("email",)


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    # Read-only apart from deleting: keys are created by users, shown once.
    list_display = ("name", "user", "hint", "created_at", "last_used_at")
    search_fields = ("name", "user__email", "user__username")
    readonly_fields = list_display + ("key_hash",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
