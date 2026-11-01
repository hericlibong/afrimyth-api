"""The six editorial transitions of a record.

A transition is not an ordinary write. `is_privately_editable()` refuses a
contributor the modification of its own submitted record — which is exactly
the record it must be able to withdraw. The right, the required start status
and the fields each action writes therefore live here, next to one another.

The right depends on the **action**, never on the route alone: owning a record
allows submitting, withdrawing and resuming it, and nothing more. Publishing
and rejecting need a reviewer or an administrator, and reopening needs an
administrator.
"""

from __future__ import annotations

from django.utils import timezone

from accounts.models import User
from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import Entity, EntityStatus

SUBMIT = "submit"
WITHDRAW = "withdraw"
RESUME = "resume"
PUBLISH = "publish"
REJECT = "reject"
REOPEN = "reopen"

#: Les noms d'action, partagés avec la vue et avec `CanEditEntity`, qui ne
#: gouverne pas ces routes.
TRANSITION_ACTIONS = frozenset({SUBMIT, WITHDRAW, RESUME, PUBLISH, REJECT, REOPEN})

#: Les deux décisions de revue : elles seules enregistrent un relecteur, une
#: date de revue et une note.
DECISIONS = frozenset({PUBLISH, REJECT})

#: Statut de départ exigé par chaque action.
REQUIRED_STATUS = {
    SUBMIT: EntityStatus.DRAFT,
    WITHDRAW: EntityStatus.SUBMITTED,
    RESUME: EntityStatus.REJECTED,
    PUBLISH: EntityStatus.SUBMITTED,
    REJECT: EntityStatus.SUBMITTED,
    REOPEN: EntityStatus.PUBLISHED,
}

WRONG_STATUS_REASONS = {
    SUBMIT: "Only a draft record can be submitted for review.",
    WITHDRAW: "Only a submitted record can be withdrawn.",
    RESUME: "Only a rejected record can be resumed as a draft.",
    PUBLISH: "Only a submitted record can be published.",
    REJECT: "Only a submitted record can be rejected.",
    REOPEN: "Only a published record can be reopened as a draft.",
}

#: Rôles qui suffisent, par action. La modération n'est jamais ouverte par la
#: propriété, et la réouverture d'une fiche publiée n'est jamais ouverte au
#: relecteur.
ALLOWED_ROLES = {
    SUBMIT: frozenset({REVIEWER, ADMINISTRATOR}),
    WITHDRAW: frozenset({REVIEWER, ADMINISTRATOR}),
    RESUME: frozenset({REVIEWER, ADMINISTRATOR}),
    PUBLISH: frozenset({REVIEWER, ADMINISTRATOR}),
    REJECT: frozenset({REVIEWER, ADMINISTRATOR}),
    REOPEN: frozenset({ADMINISTRATOR}),
}

#: Les seules actions qu'un contributeur exécute sur ses propres fiches.
OWNER_ACTIONS = frozenset({SUBMIT, WITHDRAW, RESUME})

NOT_ALLOWED_REASONS = {
    SUBMIT: (
        "Submitting requires being the record's own contributor, a reviewer or "
        "an administrator."
    ),
    WITHDRAW: (
        "Withdrawing requires being the record's own contributor, a reviewer or "
        "an administrator."
    ),
    RESUME: (
        "Resuming requires being the record's own contributor, a reviewer or "
        "an administrator."
    ),
    PUBLISH: (
        "Publishing requires a reviewer or an administrator; owning the record "
        "grants nothing here."
    ),
    REJECT: (
        "Rejecting requires a reviewer or an administrator; owning the record "
        "grants nothing here."
    ),
    REOPEN: "Reopening a published record requires an administrator.",
}

EMPTY_BODY_MESSAGE = (
    "This action takes no input. Send no body at all, or an empty JSON object "
    "`{}`; any other body is refused rather than ignored."
)


def may_transition(
    entity: Entity, action: str, *, roles: frozenset[str], caller_id: int | None
) -> bool:
    """Return whether these roles may run this action on this record.

    Reviewers and administrators act on an ownerless record too. Ownership
    only ever opens the actions listed in `OWNER_ACTIONS`, so a contributor
    never publishes or rejects its own work. No action changes the owner.
    """
    if roles & ALLOWED_ROLES[action]:
        return True
    return (
        action in OWNER_ACTIONS
        and CONTRIBUTOR in roles
        and caller_id is not None
        and entity.created_by_id == caller_id
    )


def not_allowed_reason(action: str) -> str:
    """Explain which actor this action needs, without naming the record."""
    return (
        "This account may read this record but not run this action on it. "
        f"{NOT_ALLOWED_REASONS[action]}"
    )


def wrong_status_reason(entity: Entity, action: str) -> str:
    """Explain the refusal of a transition against the current status."""
    return (
        f"{WRONG_STATUS_REASONS[action]} This record is currently "
        f"'{entity.status}'."
    )


def apply_transition(
    entity: Entity, action: str, *, actor: User, review_notes: str = ""
) -> None:
    """Write the new state of one transition on an already locked record.

    `update_fields` is what keeps the write narrow: the owner, the type, the
    business fields, the profile, the children, `created_at` and the deletion
    marks cannot move as a side effect.
    """
    if action == SUBMIT:
        entity.status = EntityStatus.SUBMITTED
        entity.submitted_at = timezone.now()
        # Une nouvelle soumission ouvre une nouvelle revue : la décision
        # précédente ne doit pas sembler porter sur elle.
        entity.reviewed_at = None
        entity.reviewed_by = None
        entity.review_notes = ""
        written = [
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewed_by",
            "review_notes",
        ]
    elif action in DECISIONS:
        # `submitted_at` est conservé tel quel, même `null` sur une fiche
        # préparée à la main : une date de soumission ne s'invente pas.
        entity.status = (
            EntityStatus.PUBLISHED if action == PUBLISH else EntityStatus.REJECTED
        )
        entity.reviewed_at = timezone.now()
        entity.reviewed_by = actor
        entity.review_notes = review_notes
        written = ["status", "reviewed_at", "reviewed_by", "review_notes"]
    else:
        # Retrait, reprise et réouverture ramènent au brouillon. Les marques de
        # revue sont conservées : `withdraw` n'est pas un rejet, et `resume`
        # comme `reopen` laissent la dernière revue guider les corrections.
        # Rouvrir n'est pas rendre une revue : l'administrateur qui rouvre
        # n'est pas enregistré comme relecteur.
        entity.status = EntityStatus.DRAFT
        entity.submitted_at = None
        written = ["status", "submitted_at"]
    entity.save(update_fields=[*written, "updated_at"])
