"""The three editorial transitions: submit, withdraw and resume.

A transition is not an ordinary write. `is_privately_editable()` refuses a
contributor the modification of its own submitted record — which is exactly
the record it must be able to withdraw. The right, the required start status
and the fields each transition writes therefore live here, next to one
another, and nothing else is decided: publication, rejection and reopening
belong to a later increment.
"""

from __future__ import annotations

from django.utils import timezone

from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
from mythology.models import Entity, EntityStatus

SUBMIT = "submit"
WITHDRAW = "withdraw"
RESUME = "resume"

#: Les noms d'action, partagés avec la vue et avec `CanEditEntity`, qui ne
#: gouverne pas ces routes.
TRANSITION_ACTIONS = frozenset({SUBMIT, WITHDRAW, RESUME})

#: Statut de départ exigé par chaque action.
REQUIRED_STATUS = {
    SUBMIT: EntityStatus.DRAFT,
    WITHDRAW: EntityStatus.SUBMITTED,
    RESUME: EntityStatus.REJECTED,
}

WRONG_STATUS_REASONS = {
    SUBMIT: "Only a draft record can be submitted for review.",
    WITHDRAW: "Only a submitted record can be withdrawn.",
    RESUME: "Only a rejected record can be resumed as a draft.",
}

NOT_ALLOWED_MESSAGE = (
    "This account may read this record but not run an editorial transition on "
    "it. Submitting, withdrawing and resuming require being the record's own "
    "contributor, a reviewer or an administrator."
)

EMPTY_BODY_MESSAGE = (
    "This action takes no input. Send no body at all, or an empty JSON object "
    "`{}`; any other body is refused rather than ignored."
)


def may_transition(
    entity: Entity, *, roles: frozenset[str], caller_id: int | None
) -> bool:
    """Return whether these roles may run a transition on this record.

    The three actions share one actor rule: the record's own contributor, a
    reviewer or an administrator. Reviewers and administrators act on an
    ownerless record too; no transition ever changes the owner.
    """
    if roles & {REVIEWER, ADMINISTRATOR}:
        return True
    return (
        CONTRIBUTOR in roles
        and caller_id is not None
        and entity.created_by_id == caller_id
    )


def wrong_status_reason(entity: Entity, action: str) -> str:
    """Explain the refusal of a transition against the current status."""
    return (
        f"{WRONG_STATUS_REASONS[action]} This record is currently "
        f"'{entity.status}'."
    )


def apply_transition(entity: Entity, action: str) -> None:
    """Write the new state of one transition on an already locked record.

    Only the status, the submission date and — for a submission — the review
    marks are saved, so no business field, profile or ownership can move as a
    side effect.
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
    else:
        # Retrait et reprise ramènent au brouillon. `resume` conserve la revue
        # du rejet pour guider les corrections ; `withdraw` n'est pas un rejet
        # et n'a donc rien à effacer.
        entity.status = EntityStatus.DRAFT
        entity.submitted_at = None
        written = ["status", "submitted_at"]
    entity.save(update_fields=[*written, "updated_at"])
