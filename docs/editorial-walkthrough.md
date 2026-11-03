# Editorial walkthrough

[Back to the README](../README.md)

Short, reproducible examples. **Every value below is fictitious** — invented
for the demonstration, attributed to no tradition and belonging to no real
corpus. Replace `8000` with `8001` if you started the Docker path.

## What you need first

Reading needs nothing. Writing needs an account **and** an editorial role.

The three groups — `contributor`, `reviewer`, `administrator` — are created
by a migration, so they already exist after `migrate`. Create a superuser
using the command for your installation above. Sign in at `/admin/` on the
same port and use **Users** to create two ordinary accounts. Assign one to
`contributor` and the other to `reviewer`. Keep both accounts active and
leave their staff and superuser flags disabled. Use the original superuser
for the administrator example. The HTTP examples below use Bash syntax.

Roles are read from group membership on **every** request, never from the
token, so a group change takes effect immediately with the same token.

## Read, without an account

```bash
curl http://127.0.0.1:8000/api/entities/
```

Expected on a fresh install: `200` with
`{"count": 0, "next": null, "previous": null, "results": []}` — the envelope
is there, the corpus is empty. Once a record is published, it appears in
`results`, and its detail is at `/api/entities/<slug>/`.

Asking for a slug that is unpublished or unknown gives the same `404` in both
cases.

## Get a token

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "<your username>", "password": "<your password>"}'
```

Expected: `200` with an `access` and a `refresh` token. Send the access token
as `Authorization: Bearer <access token>` on every request below. Check that
it works with `GET /api/auth/me/`.

## Contribute — create a draft

With an account in the `contributor` group:

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Example Created Hero", "slug": "example-created-hero", "entity_type": "hero", "gender": "female", "hero_profile": {"titles": ["Synthetic title"]}}'
```

Expected: `201` with the private detail of the new record. The server imposes
the owner — your account — and the `draft` status; neither can be supplied.
The record is readable at once on `/api/manage/entities/` and **absent** from
`/api/entities/`.

Correct it with a partial update, which leaves every omitted field alone:

```bash
curl -X PATCH http://127.0.0.1:8000/api/manage/entities/example-created-hero/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"cultural_role": "Synthetic role"}'
```

Add a documentary source — again, a fictitious one:

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/sources/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"label": "Synthetic Reference, 2026", "kind": "book", "notes": "Fictitious entry for demonstration."}'
```

Then hand it over for review:

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/submit/ \
  -H "Authorization: Bearer <access token>"
```

Expected: `200`, status `submitted`, `submitted_at` set by the server. These
transition endpoints take **no body**. From now on the contributor can read
the record but a further `PATCH` answers `403` — use `withdraw/` to get back
to drafting.

## Review — publish or reject

With an account in the `reviewer` group:

```bash
# Publish, with an optional note
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/publish/ \
  -H "Authorization: Bearer <reviewer access token>" \
  -H "Content-Type: application/json" \
  -d '{"review_notes": "Fictitious approval note."}'
```

Expected: `200`, status `published`, `reviewed_at` and `reviewed_by` set by
the server. The record now appears on the **public** collection — and public
payloads never carry a review note.

Rejecting instead requires a non-empty reason:

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/reject/ \
  -H "Authorization: Bearer <reviewer access token>" \
  -H "Content-Type: application/json" \
  -d '{"review_notes": "Fictitious reason: sources need checking."}'
```

Expected: `200` and status `rejected`; an empty reason answers `400`. The
author then calls `resume/` to return to `draft`, keeping that note in view.

**Owning a record does not grant publication.** A contributor calling
`publish/` on its own record gets `403`.

## Administer — delete logically, then restore

Deletion with a `contributor` or `reviewer` token works on drafts and
rejected records; restoration is for administrators only.

```bash
curl -X DELETE http://127.0.0.1:8000/api/manage/entities/example-created-hero/ \
  -H "Authorization: Bearer <access token>"
```

Expected: `204`. The record leaves both the public and the ordinary private
listings, keeps its status, and no row is physically removed. A figure that
still has an **active** cultural variant is protected and answers `400`.

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/restore/ \
  -H "Authorization: Bearer <administrator access token>"
```

Expected: `200`, the deletion marks cleared and the previous status kept — so
a record deleted while published becomes public again. Any other role gets
`403`.

## At a glance

| Action | Who may do it |
|---|---|
| Read published records | anyone, no account |
| Read the editorial corpus | contributor (published + its own unpublished), reviewer, administrator |
| Create a record | any editorial role |
| Update a record | its own contributor on `draft`/`rejected`; a reviewer also on `submitted`; an administrator on anything not deleted |
| Submit, withdraw, resume | the record's own contributor, a reviewer or an administrator |
| Publish, reject | reviewer or administrator — **not** the owner as such |
| Reopen a published record | administrator |
| Delete logically | own contributor on `draft`/`rejected`; reviewer on any `draft`/`rejected`; administrator on any status |
| Restore | administrator |

An authenticated account with **no** editorial role is refused with `403` on
every private route, even for a published record: reading published content
is what the public routes are for. Being Django staff grants nothing here.

The full matrix, payloads and error cases are in
[Private editorial API](editorial-api.md).

---
