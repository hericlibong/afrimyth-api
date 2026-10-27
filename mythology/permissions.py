"""Permission class guarding the private editorial routes.

One global check, deliberately coarse: does the caller hold a business role at
all. Which records that role then selects is the job of
`mythology.selectors`, applied to the queryset.

The split matters. A permission alone would be the wrong tool for a
collection: an object-level permission is never consulted for the records a
list does *not* return, so filtering has to happen in the queryset. Hence a
role check here and a real selection there, rather than a generic permission
engine.
"""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasBusinessRole(BasePermission):
    """Allow only callers holding one of the three business roles.

    An authenticated account with no business role is refused, even when the
    record it asks for is published: the public endpoints remain the way to
    read published content. Membership of the Django staff grants nothing
    here.
    """

    message = (
        "This account holds no editorial role. Private editorial access "
        "requires membership of the contributor, reviewer or administrator "
        "group, granted by an administrator."
    )

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Read the roles the view computed once for this request.

        The roles are taken from `view.caller_roles` rather than recomputed,
        so a request reads its group membership from the database exactly
        once. A view that does not expose that attribute gets an empty set and
        is therefore refused: the fallback is restrictive, never permissive.
        """
        return bool(getattr(view, "caller_roles", frozenset()))
