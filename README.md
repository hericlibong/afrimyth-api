# afrimyth-api

Django REST API for the Afrimyth project.

## Requirements

- Python 3.12
- PostgreSQL 14+

## Installation

```bash
py -3.12 -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env   # then adjust the values
```

## Environment variables

All environment-dependent settings are read from environment variables; in
development they are loaded from a `.env` file at the repository root. Copy
`.env.example` and adjust it.

| Variable | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | Required unless `DJANGO_DEBUG` is enabled |
| `DJANGO_DEBUG` | Development only — never enable it in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_HOST`, `POSTGRES_PORT` | Development defaults are provided |
| `POSTGRES_PASSWORD` | **Required, no default** — a hard-coded default would quickly become the real password |

Never commit a `.env` file or any real secret. `.env.example` holds
placeholders only.

## Running

```bash
python manage.py migrate
python manage.py runserver
```

The health endpoint is then available at
<http://127.0.0.1:8000/api/health/> and returns `{"status": "ok"}`.

## API documentation

Three routes serve the same generated OpenAPI schema. All are readable
without logging in, like the API they describe.

| Route | Purpose |
|---|---|
| `/api/schema/` | OpenAPI 3 schema, served as YAML |
| `/api/docs/` | Swagger UI — browse the endpoints and run requests with **Try it out** |
| `/api/redoc/` | ReDoc — a reading-oriented rendering of the same schema |

The schema itself is public, including the authentication endpoints: a client
has to be able to read how to obtain a token before it holds one.

No generated schema file is committed: the schema is produced from the code at request time.
To generate and validate it locally:

```bash
python manage.py spectacular --file schema.yml --validate --fail-on-warn
```

The command fails on generator warnings and schema validation errors. It
complements the contract tests; it does not detect every mismatch with runtime
behaviour. CI integration is planned for the delivery phase.

**Using Swagger UI.** The entity list, entity detail and health operations
are `GET` and need no credentials.
Expand an operation, press **Try it out**, optionally fill the collection's
query parameters, then **Execute**. On a database holding only unpublished
drafts, the collection answers `200` with zero results and any detail slug
answers `404` — see the visibility rule below. No write method is offered on
the public entity routes, because none exists.

**Authenticating in Swagger UI.** `GET /api/auth/me/` and every
`/api/manage/` operation require a token; everything else is open.
Run `POST /api/auth/token/` first, copy the `access` value from the response,
press **Authorize**, paste it, then execute the protected operation. Paste the
token alone: Swagger adds the `Bearer ` prefix itself. The public operations
stay available whether or not you are authorised — authenticating changes
nothing about what they return.

**CDN dependency.** Swagger UI and ReDoc load their JavaScript and CSS from a
public CDN. Without internet access the HTML page is still served but will
not render. No offline bundle is shipped, as no such need has been
established.
ReDoc is pinned to version 2.5.3, compatible with the classic-script template
provided by drf-spectacular; it does not follow the CDN's `latest` alias.

## Two read contracts

The corpus is served by two distinct pairs of routes, and they never mix.

| Routes | Who | Shows |
|---|---|---|
| `/api/entities/…` | anyone, no token | published, non-deleted records only |
| `/api/manage/entities/…` | access token **and** an editorial role | the editorial view of the corpus, by role and ownership |

The private routes are also where a record, its profile, its attachments, its
documentary sources and its relations are written, and where it is submitted,
withdrawn or resumed; the public routes carry no write operation at all.

The public routes behave identically for every caller. A reviewer's or a
superuser's token changes neither their selection nor their payload: the
public contract is strictly public.

## Public read API

Two read-only endpoints, open to anonymous clients:

| Endpoint | Returns |
|---|---|
| `GET /api/entities/` | paginated collection of compact items: `id`, `slug`, `name`, `entity_type`, `category` |
| `GET /api/entities/{slug}/` | full entity: common fields, reference data, type profile, relations and documentary sources |

Neither payload carries an editorial field — no `status`, no `created_by`, no
review or deletion mark.

### Pagination

The collection is paginated with a **fixed page size of 20**, selected with
`?page=`. The response is the standard DRF envelope:

```json
{
  "count": 45,
  "next": "http://127.0.0.1:8000/api/entities/?page=2",
  "previous": null,
  "results": [
    {
      "id": "8a71ca00-f976-4d34-82b1-9b8a327e2ca6",
      "slug": "anansi",
      "name": "Anansi",
      "entity_type": "hero",
      "category": "Trickster Spirit"
    }
  ]
}
```

- `count` counts only the public entities matching the current search and
  filters — never private or deleted records.
- `next` and `previous` keep every search and filter parameter, so paging
  through a filtered collection is safe.
- Results are ordered by `name`, then by `id` to break ties between
  identically named figures. Without that tiebreaker a record could move
  between pages from one request to the next.
- A non-existent or malformed `page` returns `404`, the standard DRF
  behaviour.
- The client cannot change the page size.

The detail endpoint and the health endpoint are **not** paginated and keep
their previous shape.

### Search and filters

These parameters select the **collection only**. They never change whether a
detail URL is available: `/api/entities/{slug}/` depends solely on the public
visibility of that slug.

| Parameter | Meaning |
|---|---|
| `search` | Case-insensitive search in `name`, `category`, `cultural_role` and `story_description`. Internal review notes, documentary sources and related entities are **not** searched. |
| `entity_type` | Exact value: `divinity`, `hero` or `creature`. |
| `country` | Two-letter ISO 3166-1 alpha-2 code, normalised to upper case. Matches the **primary or a secondary** country. |
| `cultural_area` | Area slug. Matches a **primary or secondary** attachment to that area **or to any of its descendants**. |

Parameters combine with **AND**; the two attachments of a single filter
combine with **OR**. An entity matching through several attachments appears
only once, and is counted once. An empty parameter does not filter.

Area descendants are resolved from the hierarchy actually stored in `parent`,
with no region name hard-coded. `?cultural_area=central-africa` therefore
includes an entity attached to `congo-basin`, and this works at any depth.
Filtering by area never infers a country.

```
GET /api/entities/?entity_type=divinity
GET /api/entities/?country=CD&entity_type=creature
GET /api/entities/?cultural_area=central-africa
GET /api/entities/?search=anansi
GET /api/entities/?entity_type=hero&page=2
```

### Errors

| Situation | Response |
|---|---|
| Unknown `entity_type` | `400` — `{"entity_type": ["Unknown entity type 'titan'. Expected one of: divinity, hero, creature."]}` |
| Malformed `country` | `400` — `{"country": ["Invalid country code 'NGA'. Expected a two-letter ISO 3166-1 alpha-2 code, for example 'NG'."]}` |
| Well-formed but unknown `country` | `200` with an empty collection |
| Unknown `cultural_area` slug | `200` with an empty collection |
| Non-existent `page` | `404` |

An unknown country code or area slug deliberately returns an empty
collection rather than an error: the response must not reveal which countries
or areas are recorded.

### Visibility rule

An entity is publicly visible **if and only if** its editorial status is
`published` **and** it has not been logically deleted. This single rule
applies to both endpoints and to every caller — anonymous, authenticated, or
superuser. These are public routes, not private management routes; the Django
admin remains the way to reach unpublished records.

A non-public entity and an unknown slug return the **same** `404`, with the
same body. The response never reveals that a record exists, nor its editorial
status.

### Nested references follow the same rule

- `variant_of` is an object when the referenced figure is public, and `null`
  otherwise. A hidden reference leaks neither id, slug, name nor type.
- `relations` keeps links whose resolved target is public, and keeps links
  that were already unresolved (`to_entity: null`, `to_name` filled). A link
  pointing to a non-public resolved target is **omitted entirely** — id, kind
  and notes included. Its name is never copied into `to_name`, which would
  republish the hidden target under another form.
- A public target is only ever rendered as the four-field synthetic
  reference; the detail is never nested recursively.

These rules cover structured references. They do not censor names appearing
in the public narrative text, nor in a genuinely unresolved relation:
reviewing the text itself is editorial work.

### Expect an empty collection on a fresh database

Entities are created as `draft`, both by the admin and by the pilot import.
Until a record is explicitly published, `GET /api/entities/` legitimately
returns `[]` and every detail URL returns `404`. That is the intended
behaviour, not a misconfiguration.

### Not available yet

The public routes carry no write operation. Every HTTP write method on
`/api/entities/` is refused with `405`, whether or not a token is supplied.
Creating a record happens on the private collection described below.

## Private editorial API

Thirteen endpoints for editorial work. They require an access token **and**
membership of one of three editorial groups.

| Endpoint | Returns |
|---|---|
| `GET /api/manage/entities/` | paginated collection: the five public compact fields, plus `status` and `created_by` |
| `GET /api/manage/entities/{slug}/` | full entity: every public business field, plus `status`, `created_by`, `submitted_at`, `reviewed_at`, `reviewed_by` and `review_notes` |
| `POST /api/manage/entities/` | creates one entity and the profile of its type, as a draft owned by the caller; answers `201` with the private detail payload |
| `PATCH /api/manage/entities/{slug}/` | updates the business fields, the existing profile and the attachments; answers `200` with the private detail payload |
| six routes under `{slug}/sources/` and `{slug}/relations/` | create, update and delete the record's documentary sources and relations, one row at a time — see below |
| `POST {slug}/submit/`, `{slug}/withdraw/`, `{slug}/resume/` | submit a draft for review, withdraw a submission, resume a rejected record; answers `200` with the private detail payload |

```bash
curl http://127.0.0.1:8000/api/manage/entities/ \
  -H "Authorization: Bearer <access token>"
```

### Roles, and what they may read, create and update

Roles are three Django groups — `contributor`, `reviewer` and
`administrator` — created by a data migration. There is no `role` field on the
account.

| Caller | Reads on these routes | Creates | Updates | Submits, withdraws, resumes |
|---|---|---|---|---|
| anonymous, or an unusable token | `401` | no | no | no |
| authenticated, no editorial role | `403`, even for a published record | no | no | no |
| contributor | every published record, plus its own `draft`, `submitted` and `rejected` | yes | its own `draft` and `rejected` | its own records |
| reviewer | every record that has not been deleted | yes | every `draft`, `rejected` and `submitted` | every record, owner or not |
| administrator, superuser | every record that has not been deleted | yes | every record that has not been deleted | every record, owner or not |

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

### Account data is not exposed

`created_by` and `reviewed_by` are account **identifiers**. No account object
is serialised: no username, email address, password hash, group list or
administrative flag appears in these payloads.

### Nested references follow the caller's own rule

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

### Navigation and errors

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

### Create an entity and its profile

`POST /api/manage/entities/` creates one entity and the profile of its type, as
a draft owned by the calling account. All four editorial callers may create.

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Example Created Hero", "slug": "example-created-hero", "entity_type": "hero", "gender": "female", "hero_profile": {"titles": ["Synthetic title"]}}'
```

**The server decides four things.** `created_by` is the authenticated account,
`status` is `draft`, the `id` is generated, and `created_at` and `updated_at`
come from the database. None of them can be supplied — not even by an
administrator — and neither can `submitted_at`, `reviewed_at`, `reviewed_by`,
`review_notes`, `deleted_at` or `deleted_by`. Sending one of these keys returns
`400` naming it; it is never silently dropped.

**Required fields.** `name`, `slug`, `entity_type` and `gender`. The slug is
taken as given: it is never generated from the name, nor suffixed to resolve a
collision.

**The profile follows the type.** Put it under the matching key —
`divinity_profile`, `hero_profile` or `creature_profile`. The key may be
omitted or sent as `{}`, in which case the profile is created with its default
values: an entity never exists without the profile of its type. The two other
keys are refused, as is a profile sent as `null`, and a profile may not name
its own `entity` or `id`.

**Reference data is attached by identifier**, under the field names the detail
payload already uses: `primary_country`, `secondary_countries`,
`primary_ethnicity`, `secondary_ethnicities`, `primary_cultural_area`,
`secondary_cultural_areas` and `domains`. Primary anchors are optional and may
be `null`; the collections are optional and default to empty. No reference
record is ever created here, and the same value cannot be both a primary anchor
and a secondary attachment of the same dimension — decisions 1, 2 and 3 of
ADR 0002.

**`variant_of`** takes the UUID of a figure the calling account may read
privately. An unreadable record, a deleted record and an unknown identifier are
refused with the same message, which never confirms that a record exists.

**All or nothing.** The entity, its profile and its attachments are written in
a single transaction. An invalid request returns `400` and creates nothing —
never an entity without its profile, nor a record with half of its
attachments.

| Situation | Response |
|---|---|
| Created | `201` with the private detail payload of the new draft |
| Missing or invalid field, duplicate name or slug, unknown reference | `400`, one key per field at fault |
| Server-controlled field supplied | `400` naming that field |
| `sources` or `relations` supplied | `400` — nested creation is deferred |
| Unrecognised field name | `400` — a typo is reported, not ignored |
| No token, or an unusable one | `401` |
| Valid token, no editorial role | `403` |

A new record is readable at once on the private endpoints by its owner, and
absent from the public API until it is published.

### Update an entity, its profile and its attachments

`PATCH /api/manage/entities/{slug}/` updates one record. Who may update what is
in the table above.

```bash
curl -X PATCH http://127.0.0.1:8000/api/manage/entities/example-created-hero/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"category": "Revised subtitle", "hero_profile": {"titles": ["Revised title"]}}'
```

**Partial by nature.** An omitted field keeps its value. A supplied list
replaces that list entirely, and `[]` empties it. `null` is accepted only on
fields that are nullable — the three primary anchors and `variant_of`. Omitted
collections are left intact.

**The entity type cannot change.** Supplying `entity_type` returns `400`:
moving a figure to another type means creating the profile of the new type and
deciding what becomes of the previous one, which a deliberate reclassifying
operation will handle (ADR 0005). The `id` never changes; the `slug` may, and
keeps its uniqueness.

**The profile is patched under the key of the current type.** Only the supplied
profile fields change; an omitted or empty profile erases nothing. A profile
sent as `null`, a profile key of another type, and a profile naming an `entity`
or an identifier are refused. A record that does not already carry exactly the
profile of its type is refused with `400` and left untouched: an ordinary
update never repairs that inconsistency silently.

**The server still decides the rest.** The owner, the editorial status, the
identifier, the technical timestamps and the review or deletion marks cannot be
supplied — no ownership transfer, not even for an administrator — and
documentary sources and relations cannot be written here yet. Any unrecognised
key is refused too.

**Attachments use existing identifiers**, and no reference record is created.
The rule keeping a primary anchor distinct from the secondary attachments of
the same dimension is checked on the **final state**, combining the stored
values with the request: swapping an anchor and a secondary value in one
request is therefore accepted. `variant_of` still accepts only a figure this
account may read, refuses a self-reference, and reports an unreadable, deleted
or unknown target identically.

**All or nothing.** The record, its profile and its attachments are written in
a single transaction, and the update right is re-evaluated on the locked row,
so a concurrent status change cannot be overwritten. A refused request changes
nothing at all.

| Situation | Response |
|---|---|
| Updated | `200` with the private detail payload |
| Invalid field, duplicate name or slug, unknown reference, overlapping attachment | `400`, one key per field at fault |
| `entity_type`, a server-controlled field, `sources`, `relations` or an unknown key supplied | `400` naming that field |
| No token, or an unusable one | `401` |
| No editorial role, or a record this account may read but not modify | `403` |
| Unknown slug, unreadable record, or deleted record | `404`, with the same body in all three cases |

### Write the documentary sources and relations of a record

`sources` and `relations` are **not** written through the entity payload: each
row has its own route under the record. Sending either key to `POST` or `PATCH`
on an entity returns `400` pointing here.

| Method and route | Does |
|---|---|
| `POST /api/manage/entities/{slug}/sources/` | adds one source; `201` with the created source |
| `PATCH /api/manage/entities/{slug}/sources/{source_id}/` | updates one source; `200` |
| `DELETE /api/manage/entities/{slug}/sources/{source_id}/` | removes one source; `204`, no body |
| `POST /api/manage/entities/{slug}/relations/` | adds one outgoing relation; `201` |
| `PATCH /api/manage/entities/{slug}/relations/{relation_id}/` | updates one relation; `200` |
| `DELETE /api/manage/entities/{slug}/relations/{relation_id}/` | removes one relation; `204`, no body |

```bash
curl -X POST http://127.0.0.1:8000/api/manage/entities/example-created-hero/relations/ \
  -H "Authorization: Bearer <access token>" \
  -H "Content-Type: application/json" \
  -d '{"kind": "parent", "to_name": "Figure Without A Record"}'
```

**Rights are the record's own update rights** — the table above — and nothing
else. A record this account may read but not update returns `403`. The
identifiers are the integers already shown in the `sources` and `relations`
arrays of the private detail, and a row is always looked up **inside** the
record named by the slug: an identifier that does not exist, or belongs to
another record, returns the same `404`. Nothing is ever moved from one record
to another.

**Reading stays in the private detail.** There is no list route and no
pagination for the children; `GET` on these URLs is refused with `405`.

**The record itself is never touched.** Its status, owner, type, profile,
review marks and `updated_at` are left exactly as they were — writing a child
is content editing, not an entity write.

**A source** takes `label` and `kind` (required on creation), plus `url`,
`accessed_at` and `notes`. `url` may be empty — a book or an oral testimony has
none — and is only checked for format, never fetched. `accessed_at` is a
consultation date and the only key accepting `null`. No uniqueness is enforced:
two sources with the same label or URL on one record are legitimate.

**A relation** takes `kind` and **exactly one** target: `to_entity`, the UUID of
a figure this account may read, or `to_name`, a non-blank name for a figure that
has no record. Supplying both or neither returns `400`. Reading the target is
enough; updating it is not required. An unreadable, deleted or unknown UUID is
refused with the same message, which never discloses the target's name,
identifier or status, and a relation from a record to itself is refused. The
same triple — record, target, kind — cannot be recorded twice, though a pair of
figures may carry several kinds.

A patch keeps every omitted key and clears neither target form implicitly, so
resolving a cited name takes both keys in one request:
`{"to_entity": "<uuid>", "to_name": ""}`; un-resolving takes
`{"to_entity": null, "to_name": "Some Name"}`. No name is ever resolved
automatically. `kind` keeps its direction — `parent` means the target is a
parent of this record — and no inverse, reciprocal or cycle check is added.

**A deletion removes only that row.** No entity, profile or target figure is
ever deleted here, and there is no recycle bin or history for a child. A
relation towards a target this account may not read stays unreachable, with the
same `404`, even if its identifier is guessed.

### Submit, withdraw and resume a record

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

### The other writes are still refused

`PUT` and `DELETE` are refused with `405` on both private entity URLs, for every
role, superuser included, and `POST` is refused on the private detail URL. The
transition routes accept `POST` only. Full replacement, the moderation
decisions — publication, rejection, reopening — and the logical deletion or
restoration of an entity belong to later increments.

## Authentication

Three endpoints issue, refresh and verify JSON Web Tokens. They carry
credentials in a request body, and create no content.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/token/` | none | Exchange credentials for a token pair |
| `POST` | `/api/auth/token/refresh/` | none | Exchange a refresh token for a new access token |
| `GET` | `/api/auth/me/` | access token | Return the caller's own identity |

The access token is also what opens the private editorial routes described
above — together with an editorial group.

### Obtain a token pair

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "<username>", "password": "<password>"}'
```

```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi..."
}
```

- **`access`** lives 5 minutes outside development and is sent on every request
  that needs authentication. With `DJANGO_DEBUG=True`, its lifetime defaults
  to 20 minutes for exercises, configurable through `JWT_DEV_ACCESS_MINUTES`.
  This override is ignored when debug is disabled.
- **`refresh`** lives 1 day and is sent **only** to the refresh endpoint.

The two are not interchangeable: a refresh token is refused as an access
token, and an access token is refused as a refresh token.

Errors: `400` when `username` or `password` is missing, `401` when the
credentials are refused. The `401` body is identical whether the account does
not exist, the password is wrong, or the account is inactive — it never
reveals which.

### Use the access token

```bash
curl http://127.0.0.1:8000/api/auth/me/ \
  -H "Authorization: Bearer <access token>"
```

```json
{"id": 1, "username": "example-contributor"}
```

The response carries `id` and `username` only. Email address, password hash,
permissions, group membership and administrative flags are deliberately not
exposed.

`401` is returned when no token is sent, or when the token is malformed,
expired, signed with another key, is a refresh token, or belongs to an account
that has since been deactivated or deleted. This endpoint accepts JWT only: an
open administration session is not enough, because its purpose is to prove
that a *token* works.

### Refresh the access token

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh token>"}'
```

```json
{"access": "eyJhbGciOi..."}
```

No `Authorization` header is needed: the refresh token in the body *is* the
credential. The response carries a new `access` and nothing else — rotation is
disabled, so the client keeps the refresh token it already has.

### Authentication is not authorisation

Holding a token proves who the caller is; it does not say what the caller may
do. On the public routes a valid token changes nothing at all: they return
exactly what a stranger sees. Access to the private editorial routes requires
a Django group on top of the token, checked server-side on every request — and
an account with a token but no group is refused with `403`.

Every write is private, and none lets a client choose the owner or the
editorial status, whatever its role. The right to write on one record — its own
fields or one of its children — is checked on that record, not only on the
route.

### Caveats

- **No revocation.** Rotation and token blacklisting are not enabled.
  Refreshing does not invalidate the previous access token, which stays usable
  until it expires on its own, and discarding a token in your client does not
  cancel it server-side. There is no logout endpoint, and none is implied. A
  compromised token therefore stays valid for up to its lifetime — 5 minutes
  for an access token (20 minutes by default in development), 1 day for a
  refresh token.
- **Use HTTPS outside localhost.** Tokens are bearer credentials: anyone
  holding one is the account until it expires. Over plain HTTP they travel in
  clear text and can be captured and replayed. The same applies to the
  password sent to the token endpoint.
- **No brute-force protection.** The token endpoint has no rate limit, no
  attempt counter and no lockout. On a public deployment, throttling has to be
  added — DRF throttling, a reverse proxy, or both.
- **Signing key.** Tokens are signed with HS256 using `DJANGO_SECRET_KEY`.
  Rotating that key invalidates every token in circulation. Use a key of at
  least 32 bytes: a shorter one is accepted but weakens the signature, and
  PyJWT warns about it.
- **An invalid `Authorization` header breaks public reads too.** DRF
  authenticates before it checks permissions, so a stale or mistyped Bearer
  header produces `401` even on an endpoint that needs no authentication at
  all. If a public read suddenly fails, remove the header before suspecting
  the API.
- **No self-service.** There is no registration endpoint and no password
  reset. Accounts are created through the Django administration.

## Pilot corpus import

A management command imports a small pilot selection from the historical V2
corpus, in order to confront the data model with real data before the full
import.

```bash
# Simulate: validates and attempts every write, then rolls back
python manage.py import_mythology_pilot --input "/path/to/mythology_data.json" --dry-run

# Import for real
python manage.py import_mythology_pilot --input "/path/to/mythology_data.json"
```

- **External input.** The corpus file lives outside this repository and its
  path is always passed with `--input`; no path is hard-coded, and no corpus
  file is copied into the repository.
- **Pilot selection.** Only three figures are imported — `Oya` (divinity),
  `Anansi` (hero) and `Mokele-mbembe` (creature) — one per entity type. The
  remaining figures of the corpus are left untouched; the full import belongs
  to a later phase.
- **Simulation.** `--dry-run` performs the validation and the writes inside a
  transaction that is rolled back at the end, then prints the same summary.
  Nothing is persisted.
- **Re-running is safe.** An entity whose name, type and slug already match an
  existing record is reported as skipped: its fields, profile, collections and
  relations are left untouched. Nothing is overwritten and no duplicate is
  created. A partial identity match — for instance a slug already used by a
  different figure — stops the command with an explicit conflict error rather
  than silently suffixing the slug. There is no `--force`, merge or bulk
  update mode.
- **Transactional.** A single transaction covers reference data, entities,
  profiles, collections and relations. Any blocking error cancels everything
  the call would have added.
- Imported entities are created as `draft`, without owner or review marks.
  Rendering data (prompts, images, style matrix) is out of scope.

The command prints a summary listing created and skipped entities, relations,
and every transformation, omission or ambiguity it encountered.

## Verification

A `.env` file must exist before running any command: `config/settings.py`
refuses to start without `DJANGO_SECRET_KEY` when `DJANGO_DEBUG` is not
enabled.

```bash
pytest                 # tests
ruff check .           # lint
ruff format --check .  # formatting
mypy .                 # type checking
```

## Project status

Phase 2 completed: the domain model has been exercised through a three-entity
pilot import and manual API review. Available so far: the technical foundation (Django and
Django REST Framework, environment-based configuration, custom user model,
health endpoint, quality tooling), the `Entity` common trunk with its
`DivinityProfile`, `HeroProfile` and `CreatureProfile` profiles, the cultural
and geographic reference models, cultural variants, relations between figures,
documentary sources, editorial state fields, the Django admin, a read-only
list/detail API, and the pilot corpus import described above.

Phase 3 completed after code review and manual Swagger/ReDoc checks: the public read contract exposes only
published, non-deleted entities and hides non-public nested references, the
collection is paginated, searchable and filterable, and the contract is
published as an OpenAPI schema with Swagger UI and ReDoc.

Phase 4 is under way. Increment 1 delivered JWT token issuance, refresh and
the protected identity route, validated with manual Postman exercises.
Increment 2 adds the three editorial groups, created by a data migration, and
the private read endpoints described above: role and ownership select the
records, and nested references follow the caller's own rule. Increment 3 opens
the private creation of an entity and its profile, as a draft owned by the
caller. Increment 4A adds the private partial update of the business fields,
the existing profile and the reference attachments, by role, ownership and
status. Increment 4B adds the write routes of a record's documentary sources
and relations, one row at a time, under the same rights. Increment 5 adds the
submission of a draft, the withdrawal of a submission and the resumption of a
rejected record.

The public routes stay read-only. Full replacement and deletion of entities stay
refused, and the moderation decisions (publication, rejection, reopening),
logical deletion and restoration, and the reclassification of an entity's type
are not implemented yet.
