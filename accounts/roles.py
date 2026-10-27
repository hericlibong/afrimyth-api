"""Business roles, read from Django groups on every request.

Three Django groups carry the editorial roles of ADR 0002 — `contributor`,
`reviewer` and `administrator`. There is no duplicate `role` field on the
account, and no role claim inside the JWT.

Two consequences follow, and both are deliberate:

- a group change takes effect on the **next request**, without reissuing or
  refreshing any token;
- groups unrelated to these three names have no effect on business rights,
  and `is_staff` alone grants none either.

This module answers only "which roles does this caller hold". What a role
*allows* on the corpus belongs to `mythology.selectors`.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from accounts.models import User

#: Nom du groupe, en anglais comme tout identifiant du code.
CONTRIBUTOR = "contributor"
REVIEWER = "reviewer"
ADMINISTRATOR = "administrator"

#: Les trois seuls noms de groupe qui portent un rôle métier. La migration de
#: données `accounts.0002` les crée ; cette constante est la référence
#: partagée par la migration, les sélections et les tests.
BUSINESS_ROLE_NAMES = (CONTRIBUTOR, REVIEWER, ADMINISTRATOR)


def business_roles(user: AbstractBaseUser | AnonymousUser | None) -> frozenset[str]:
    """Return the business roles this caller holds, read from the database.

    Anonymous, missing and inactive callers hold no role at all. An
    authenticated account without any of the three groups also holds none:
    signing in never implies the contributor role.

    An **active superuser** is treated as an administrator even without the
    group, which keeps a fallback administration access. `is_staff` is
    ignored: reaching the Django admin is not a right over the corpus.

    Several groups accumulate, and foreign groups are dropped. The membership
    is read from the database at each call, so this function must be called
    once per request, not once per serialised record.
    """
    # `isinstance` écarte d'un coup l'appelant anonyme et l'absence
    # d'appelant : seul un compte réel possède des groupes.
    if not isinstance(user, User) or not user.is_active:
        return frozenset()

    names: set[str] = {
        name
        for name in user.groups.values_list("name", flat=True)
        if name in BUSINESS_ROLE_NAMES
    }
    if user.is_superuser:
        names.add(ADMINISTRATOR)
    return frozenset(names)
