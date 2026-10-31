"""Permission classes guarding the private editorial routes.

One global check, deliberately coarse: does the caller hold a business role at
all. Which records that role then selects is the job of
`mythology.selectors`, applied to the queryset. A second, object-level check
decides whether a readable record may also be modified.

The split matters. A permission alone would be the wrong tool for a
collection: an object-level permission is never consulted for the records a
list does *not* return, so filtering has to happen in the queryset. Hence a
role check here and a real selection there, rather than a generic permission
engine.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from mythology.models import Entity
from mythology.selectors import is_privately_editable
from mythology.transitions import TRANSITION_ACTIONS

#: Message du 403 d'une fiche lisible mais non modifiable. Public, donc en
#: anglais ; partagé avec le refus posé sur l'état verrouillé à l'écriture.
NOT_EDITABLE_MESSAGE = (
    "This account may read this record but not modify it. A contributor "
    "modifies its own draft and rejected records; a reviewer also modifies "
    "submitted records; every other case requires an administrator."
)


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


class CanEditEntity(BasePermission):
    """Allow modifying one record only when role, ownership and status permit.

    Object level is the right level here: the queryset has already decided
    what this account may read, and a readable record is not necessarily a
    modifiable one. Reading is left untouched.
    """

    message = NOT_EDITABLE_MESSAGE

    def has_object_permission(
        self, request: Request, view: APIView, obj: Entity
    ) -> bool:
        """Refuse an unsafe method on a record this account may not modify."""
        if request.method in SAFE_METHODS:
            return True
        # Une transition n'est pas une écriture ordinaire : un contributeur
        # retire sa propre fiche soumise, que cette règle lui refuse justement
        # de modifier. Son droit est décidé par `may_transition()`.
        if getattr(view, "action", None) in TRANSITION_ACTIONS:
            return True
        return is_privately_editable(
            obj,
            roles=getattr(view, "caller_roles", frozenset()),
            caller_id=getattr(view, "caller_id", None),
        )
