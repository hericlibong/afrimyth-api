"""Soft deletion and restoration of a record.

Deleting is neither an ordinary write nor an editorial transition: no status
changes, and the right is not the one `is_privately_editable()` grants. A
reviewer updates a submitted record but may not delete it, so the rules of
these two operations live here.

Nothing is ever physically removed: only `deleted_at` and `deleted_by` move,
and every profile, source, relation and collection row stays in place.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.utils import timezone

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import Entity, EntityStatus

#: Les deux noms d'action, partagés avec `CanEditEntity`, qui ne les gouverne
#: pas : leur droit est décidé par `may_delete()` et `may_restore()`.
DELETION_ACTIONS = frozenset({"destroy", "restore"})

#: Statuts qu'un contributeur et un relecteur peuvent supprimer logiquement,
#: selon la matrice de l'ADR 0002. Un administrateur n'est pas listé : il
#: supprime tous les statuts.
DELETABLE_STATUSES = (EntityStatus.DRAFT, EntityStatus.REJECTED)

NOT_DELETABLE_MESSAGE = (
    "This account may read this record but not delete it. A contributor "
    "deletes its own draft and rejected records, a reviewer any draft or "
    "rejected record; a submitted or published record requires an "
    "administrator."
)

NOT_RESTORABLE_MESSAGE = (
    "Restoring a deleted record requires an administrator. No other account "
    "is told whether a given slug exists among the deleted records."
)

NOT_DELETED_MESSAGE = (
    "This record is not deleted, so there is nothing to restore. Its state is "
    "left untouched."
)

PROTECTED_BY_VARIANT_MESSAGE = (
    "This figure is still used as the reference of at least one active "
    "cultural variant, so it cannot be deleted (ADR 0002). Deal with the "
    "variants first — detach or delete them — then delete this record."
)

DELETED_REFERENCE_MESSAGE = (
    "This record is a cultural variant of a reference that is itself still "
    "deleted. Restore the reference first, so no variant is left pointing at "
    "a deleted figure."
)


def may_delete(entity: Entity, *, roles: frozenset[str], caller_id: int | None) -> bool:
    """Return whether these roles may soft-delete this record.

    An administrator deletes any status, owned or not. A reviewer deletes any
    draft or rejected record but neither a submitted nor a published one. A
    contributor only deletes its own draft and rejected records.
    """
    if ADMINISTRATOR in roles:
        return True
    if REVIEWER in roles and entity.status in DELETABLE_STATUSES:
        return True
    return (
        CONTRIBUTOR in roles
        and caller_id is not None
        and entity.created_by_id == caller_id
        and entity.status in DELETABLE_STATUSES
    )


def may_restore(roles: frozenset[str]) -> bool:
    """Return whether these roles may restore a deleted record."""
    return ADMINISTRATOR in roles


def locked_in_pk_order(identifiers: Iterable[Any]) -> dict[Any, Entity]:
    """Lock the named records in one query, in primary-key order.

    Every API path that needs two rows at once — a record and the reference it
    is a variant of — acquires them here. One statement ordered by primary key
    gives every caller the same acquisition order, so two simultaneous writes
    on the same pair cannot take them the other way round and deadlock.
    `ORDER BY` puts the locking step above the sort, so the rows really are
    locked in that order.

    The lock is also what coordinates these writes with a soft deletion: the
    deletion holds the reference row while it looks for active variants, so a
    creation, a patched `variant_of` or a restored variant waits here and then
    sees the deletion.
    """
    wanted = {identifier for identifier in identifiers if identifier is not None}
    if not wanted:
        return {}
    locked = Entity.objects.select_for_update().filter(pk__in=wanted).order_by("pk")
    return {row.pk: row for row in locked}


def has_active_variant(entity: Entity) -> bool:
    """Report whether a non-deleted figure is a direct variant of this one.

    A plain query is enough **because the caller holds the row lock on
    `entity`**: every API write that would create such a variant acquires that
    same row through `locked_in_pk_order()` first. Status, owner and
    readability are irrelevant — a variant nobody may read still protects its
    reference — and a logically deleted variant does not protect anything.
    """
    return Entity.objects.filter(variant_of=entity, deleted_at__isnull=True).exists()


def apply_deletion(entity: Entity, *, actor: User) -> None:
    """Mark one locked record as deleted, without removing a single row."""
    entity.deleted_at = timezone.now()
    entity.deleted_by = actor
    entity.save(update_fields=["deleted_at", "deleted_by", "updated_at"])


def apply_restoration(entity: Entity) -> None:
    """Clear the deletion marks of one locked record.

    The editorial status is kept, so a record deleted while published becomes
    public again: restoring is neither a reopening nor a new publication, and
    it never replaces the reviewer.
    """
    entity.deleted_at = None
    entity.deleted_by = None
    entity.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
