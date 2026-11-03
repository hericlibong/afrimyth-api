# Editorial moderation

[Back to the README](../README.md)

Three `POST` actions move one record between `draft` and `submitted`. They take
no input.

| Route under `/api/manage/entities/{slug}/` | Allowed transition |
|---|---|
| `submit/` | `draft` → `submitted` |
| `withdraw/` | `submitted` → `draft` |
| `resume/` | `rejected` → `draft` |

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/submit/ \
  -H "Authorization: Bearer <access token>"
```

**Who may act.** The record's **own contributor**, a reviewer or an
administrator — the same three actors for all three actions. A reviewer and an
administrator also act on a record that has no owner. This is **not** the
ordinary update right: a contributor may withdraw its own `submitted` record
even though it may no longer `PATCH` it. No transition changes the owner.

**No input.** Send no body at all, or an empty JSON object `{}`. Any other body
— a non-empty object, an array, a string — returns `400` rather than being
ignored. There is no status, date, actor, review note or business field to
supply.

**What each action writes.**

| Action | Writes |
|---|---|
| `submit/` | `status` = `submitted`, `submitted_at` = now, and clears `reviewed_at`, `reviewed_by` and `review_notes` — a submission opens a fresh review |
| `withdraw/` | `status` = `draft`, `submitted_at` = `null`; the review marks are left untouched, because a withdrawal is not a rejection |
| `resume/` | `status` = `draft`, `submitted_at` = `null`; the last review is **kept**, to guide the corrections, and is cleared by the next submission |

Nothing else moves: the owner, the type, the business fields, the profile, the
reference data, the sources, the relations, the deletion marks and `created_at`
are untouched, and `updated_at` moves only on success. These fields carry the
current state and the last review kept, not an exhaustive history.

Submitting is neither a publication nor a documentary certification: no
completeness threshold is checked, and nothing is filled in or repaired on the
way. While a record is `submitted`, its own contributor keeps reading it but may
no longer update it, nor write its sources and relations; a reviewer still may.
After a withdrawal or a resumption, the ordinary rights of a `draft` apply
again.

| Situation | Response |
|---|---|
| Done | `200` with the private detail payload, references filtered for the caller |
| Wrong starting status, including repeating an action that already succeeded | `400`, nothing written |
| A body was sent | `400`, nothing written |
| No token, or an unusable one | `401` |
| No editorial role, or a record this account may read without being one of its actors | `403` |
| Unknown slug, unreadable record, or deleted record | `404`, with the same body in all three cases |

Each action runs in one transaction, re-reading the record's visibility, the
actor's right and the status on the locked row, so two concurrent submissions
cannot both succeed.

## Publish, reject and reopen a record

Three more `POST` actions carry the moderation decisions.

| Route under `/api/manage/entities/{slug}/` | Transition | Who may act |
|---|---|---|
| `publish/` | `submitted` → `published` | reviewer, administrator |
| `reject/` | `submitted` → `rejected` | reviewer, administrator |
| `reopen/` | `published` → `draft` | **administrator only** |

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/reject/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"review_notes": "Please clarify the source of this claim."}'
```

**Owning a record grants none of these.** A contributor never publishes or
rejects its own work, whatever its status, and a reviewer never reopens a
published record. No self-review rule and no second approver are enforced: the
permission matrix does not require them. Reviewers and administrators also act
on a record that has no owner. Only `submitted` records are published or
rejected, and only a `published` record is reopened: `draft → published`,
`rejected → published` and `published → rejected` do not exist.

**Input.**

| Action | Body |
|---|---|
| `publish/` | no body, `{}`, or the single optional key `review_notes`. An omitted or empty note stores an **empty** note — it never keeps an earlier one — and `null` is not a note |
| `reject/` | a JSON object with `review_notes`, **required** and non-blank: the reason is what lets the contributor correct the record |
| `reopen/` | no body or `{}`, like `withdraw/` and `resume/` |

Every other key — `status`, `reviewed_at`, `reviewed_by`, `submitted_at`,
`created_by`, any business field, any unknown name — returns `400` naming it,
and a JSON body that is not an object is refused too.

**What each action writes.**

| Action | Writes |
|---|---|
| `publish/` | `status` = `published`, `reviewed_at` = now, `reviewed_by` = the calling account, `review_notes` = the validated note; `submitted_at` is kept exactly as it was, even `null` |
| `reject/` | `status` = `rejected`, plus the same three review fields; `submitted_at` is kept |
| `reopen/` | `status` = `draft`, `submitted_at` = `null`; the last review is **kept** to guide the corrections, and the administrator who reopens is **not** recorded as the reviewer |

The actor and the dates always come from the server. Publishing is a human
decision, not a certification engine: no completeness threshold is checked and
nothing is filled in on the way. After a rejection the owner calls `resume/`,
which keeps the review; the next `submit/` clears it.

**Public visibility follows the status**, through the existing public
selection: a published record appears on `/api/entities/`, a rejected one stays
absent, and a reopened one disappears again. The public payloads never carry a
review note or any other editorial field.

| Situation | Response |
|---|---|
| Done | `200` with the private detail payload, references filtered for the caller |
| Wrong starting status, including repeating a decision that already succeeded | `400`, nothing written |
| Missing or blank rejection reason, note sent as `null`, refused key, non-object body | `400`, nothing written |
| No token, or an unusable one | `401` |
| No editorial role, or a readable record this account may not moderate | `403`, before any diagnosis of the status or the body |
| Unknown slug, unreadable record, or deleted record | `404`, with the same body in all three cases |

Each decision runs in one transaction, re-reading the visibility, the actor's
right and the status on the locked row, so two concurrent decisions on the same
submission cannot both succeed.

## Delete a record logically, and restore it

| Operation | Route | Answers |
|---|---|---|
| `DELETE` | `/api/manage/entities/{slug}/` | `204` with no body |
| `POST` | `/api/manage/entities/{slug}/restore/` | `200` with the private detail payload |

```bash
curl -X DELETE http://127.0.0.1:8000/api/manage/entities/example-created-hero/ \
  -H "Authorization: Bearer <access token>"

curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/restore/ \
  -H "Authorization: Bearer <access token>"
```

**The deletion is logical.** Only `deleted_at` and `deleted_by` are written:
no entity, profile, documentary source, relation or reference attachment row is
ever removed, so no child is orphaned and a restoration brings the record back
untouched. This is **not** the `DELETE` of a source or of a relation, which
really removes that one row.

**Who may delete what** — and it is *not* the update right:

| Caller | Deletes |
|---|---|
| contributor | its own `draft` and `rejected` records |
| reviewer | any `draft` or `rejected` record, owned or not — never a `submitted` or `published` one |
| administrator, superuser | any status, owned or not |

A reviewer therefore updates a `submitted` record without being able to delete
it. Restoring is **administrators only**, whatever the status that was kept.

**No input** on either operation: send no body, or an empty JSON object `{}`.
Any other body returns `400`. The date and the actor come from the server; the
status, the owner, the submission and review marks, the business fields, the
profile and the children are all kept.

**An active variant protects its reference.** `DELETE` returns `400` when at
least one non-deleted figure is a direct cultural variant of this one —
whatever that variant's status, owner or readability (ADR 0002). The error
names neither the variants nor their number. A logically deleted variant
protects nothing, and an ordinary relation never blocks a deletion: only
`variant_of` does. Detach or delete the variants first.

Symmetrically, restoring a record that is itself a variant whose reference is
still deleted returns `400`: restore the reference first. No `variant_of` is
cleared and no other record is restored automatically.

**Once deleted**, the record leaves the public endpoints *and* the ordinary
private reads — for every role, administrators included — and accepts no
update, child write or editorial transition: they all answer `404`. Structured
references pointing at it are hidden by the existing filters, and a hidden
target's name is never copied into `to_name`.

**Restoring keeps the previous status.** A record deleted while `published`
**becomes public again** as soon as it is restored; one deleted as a draft,
submitted or rejected stays private under the usual rights. Restoring is
neither a reopening nor a new publication: the review marks are preserved and
the reviewer is never replaced.

| Situation | Response |
|---|---|
| Deleted | `204` with no body |
| Restored | `200` with the private detail payload |
| Active variant protecting the reference, or a body was sent | `400`, nothing written |
| Restoring a record that is not deleted, or whose reference is still deleted | `400`, nothing written |
| No token, or an unusable one | `401` |
| No editorial role, or a readable record this account may not delete | `403` |
| Not an administrator, on `restore/` | `403`, for an existing slug exactly as for an unknown one |
| Unknown slug, unreadable record, or already deleted record, on `DELETE` | `404`, with the same body in all three cases |
| Unknown slug, on `restore/` | `404` |

Each operation runs in one transaction on the locked row, re-reading the
visibility, the right, the state and the variant protection there, so a refused
request leaves every column untouched — `updated_at` included — and two
concurrent requests cannot overwrite marks already set. Every API write that
would make a record an active variant takes that same lock, so none can slip a
live variant under a reference that has just been deleted.

## The other writes are still refused

`PUT` is refused with `405` on both private entity URLs, for every role,
superuser included; `POST` is refused on the private detail URL and `DELETE` on
the collection. The transition, decision and restore routes accept `POST` only.
Full replacement is not part of the contract, and no operation ever removes an
entity row physically.
