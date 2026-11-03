# Editorial API

[Back to the README](../README.md)

Eighteen endpoints for editorial work. They require an access token **and**
membership of one of three editorial groups.

| Endpoint | Returns |
|---|---|
| `GET /api/manage/entities/` | paginated collection: the five public compact fields, plus `status` and `created_by` |
| `GET /api/manage/entities/{slug}/` | full entity: every public business field, plus `status`, `created_by`, `submitted_at`, `reviewed_at`, `reviewed_by` and `review_notes` |
| `POST /api/manage/entities/` | creates one entity and the profile of its type, as a draft owned by the caller; answers `201` with the private detail payload |
| `PATCH /api/manage/entities/{slug}/` | updates the business fields, the existing profile and the attachments; answers `200` with the private detail payload |
| six routes under `{slug}/sources/` and `{slug}/relations/` | create, update and delete the record's documentary sources and relations, one row at a time — see below |
| `POST {slug}/submit/`, `{slug}/withdraw/`, `{slug}/resume/` | submit a draft for review, withdraw a submission, resume a rejected record; answers `200` with the private detail payload |
| `POST {slug}/publish/`, `{slug}/reject/`, `{slug}/reopen/` | publish or reject a submission, reopen a published record; answers `200` with the private detail payload |
| `DELETE {slug}/` and `POST {slug}/restore/` | delete one record logically, then restore it; answer `204` and `200` |

```bash
curl http://127.0.0.1:8000/api/manage/entities/ \
  -H "Authorization: Bearer <access token>"
```

## Roles, and what they may read, create and update

Roles are three Django groups — `contributor`, `reviewer` and
`administrator` — created by a data migration. There is no `role` field on the
account.

| Caller | Reads on these routes | Creates | Updates | Submits, withdraws, resumes | Moderates | Deletes | Restores |
|---|---|---|---|---|---|---|---|
| anonymous, or an unusable token | `401` | no | no | no | no | no | no |
| authenticated, no editorial role | `403`, even for a published record | no | no | no | no | no | no |
| contributor | every published record, plus its own `draft`, `submitted` and `rejected` | yes | its own `draft` and `rejected` | its own records | no | its own `draft` and `rejected` | no |
| reviewer | every record that has not been deleted | yes | every `draft`, `rejected` and `submitted` | every record, owner or not | publish, reject | every `draft` and `rejected` | no |
| administrator, superuser | every record that has not been deleted | yes | every record that has not been deleted | every record, owner or not | publish, reject, reopen | every status | yes |

**Reading does not imply updating.** A contributor reads a published record
but does not modify it; so does a reviewer. A record this account may read and
not modify returns `403`, while an unknown slug, an unreadable record and a
deleted record all return the same `404`.

- **Signing in grants nothing.** An account with no editorial group is
  refused. Reading published content is what the public routes are for.
- **`is_staff` is not a role.** Reaching the Django admin is not a right over
  the corpus.
- **An active superuser is treated as an administrator**, even without the
  group — a fallback administration access.
- **Groups accumulate**, and groups unrelated to those three names are
  ignored.
- **Logically deleted records are excluded for everyone**, administrators
  included. Restoration is a separate, later operation.
- **An unowned record belongs to no contributor.** An imported record whose
  `created_by` is `null` is invisible to contributors while it is unpublished;
  reviewers and administrators still read it.

Roles are read from group membership on **every request**, never from a claim
inside the token. Adding or removing a group therefore takes effect on the
next request, with the same token — no reissue, no refresh.

## Account data is not exposed

`created_by` and `reviewed_by` are account **identifiers**. No account object
is serialised: no username, email address, password hash, group list or
administrative flag appears in these payloads.

## Nested references follow the caller's own rule

- `variant_of` is `null` when the reference figure is not readable by the
  calling account, leaking neither id, slug, name nor type.
- A relation whose resolved target is not readable is **omitted entirely**,
  and the hidden target's name is never copied into `to_name`.
- Genuinely unresolved relations (`to_entity: null`, `to_name` filled) stay
  readable, as on the public endpoint.
- Deleted records stay hidden in these references too, and targets are
  rendered as the four-field compact reference only.

A reviewer and a contributor can therefore receive different nested
references for the same record. That is intended, not a bug.

## Navigation and errors

The navigation is the public one, reused as is: fixed page size of 20, the
same `page`, `search`, `entity_type`, `country` and `cultural_area`
parameters, the same validation and the same ordering. `count` only ever
counts records the account may read, and **no parameter can widen that
selection**.

| Situation | Response |
|---|---|
| No token, or an unusable one | `401` — these routes accept JWT only; an admin session is not enough |
| Valid token, no editorial role | `403` |
| Unknown slug, unreadable record, or deleted record | `404`, with the same body in all three cases |
| Malformed `entity_type` or `country` | `400`, with the public messages |
| Non-existent `page` | `404` |

- [Create, update, sources and relations](editorial-writes.md)
- [Submission, moderation and restoration](editorial-moderation.md)
