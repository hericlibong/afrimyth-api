from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

from accounts.models import User


@admin.register(User)
class AfrimythUserAdmin(UserAdmin[User]):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "display_groups",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        return super().get_queryset(request).prefetch_related("groups")

    @admin.display(description="Groups")
    def display_groups(self, user: User) -> str:
        return ", ".join(sorted(group.name for group in user.groups.all())) or "—"
