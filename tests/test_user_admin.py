"""Group display on the user administration list."""

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import RequestFactory

from accounts.admin import AfrimythUserAdmin
from accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ([], "—"),
        (["contributor"], "contributor"),
        (["reviewer", "contributor"], "contributor, reviewer"),
    ],
)
def test_user_groups_display(names: list[str], expected: str) -> None:
    user = User.objects.create(username="admin-display-test")
    for name in names:
        user.groups.add(Group.objects.get(name=name))

    user_admin = AfrimythUserAdmin(User, admin.site)

    assert "display_groups" in user_admin.list_display
    assert user_admin.display_groups(user) == expected


def test_group_display_uses_prefetched_groups(
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    user = User.objects.create(username="prefetch-test")
    user.groups.add(Group.objects.get(name="reviewer"))
    user_admin = AfrimythUserAdmin(User, admin.site)
    request = RequestFactory().get("/admin/accounts/user/")
    loaded = user_admin.get_queryset(request).get(pk=user.pk)

    with django_assert_num_queries(0):
        assert user_admin.display_groups(loaded) == "reviewer"
