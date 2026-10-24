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
entities, because none exists.

**Authenticating in Swagger UI.** Only `GET /api/auth/me/` requires a token.
Run `POST /api/auth/token/` first, copy the `access` value from the response,
press **Authorize**, paste it, then execute `me`. Paste the token alone:
Swagger adds the `Bearer ` prefix itself. The other operations stay available
whether or not you are authorised — authenticating changes nothing about what
they return.

**CDN dependency.** Swagger UI and ReDoc load their JavaScript and CSS from a
public CDN. Without internet access the HTML page is still served but will
not render. No offline bundle is shipped, as no such need has been
established.
ReDoc is pinned to version 2.5.3, compatible with the classic-script template
provided by drf-spectacular; it does not follow the CDN's `latest` alias.

## Public read API

Two read-only endpoints, open to anonymous clients:

| Endpoint | Returns |
|---|---|
| `GET /api/entities/` | paginated collection of compact items: `id`, `slug`, `name`, `entity_type`, `category` |
| `GET /api/entities/{slug}/` | full entity: common fields, reference data, type profile, relations and documentary sources |

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

Write operations and the moderation workflow are not implemented. Every HTTP
write method on `/api/entities/` is refused with `405`, whether or not a token
is supplied.

## Authentication

Three endpoints issue, refresh and verify JSON Web Tokens. They are the only
`POST` operations in the API, and they create no content.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/token/` | none | Exchange credentials for a token pair |
| `POST` | `/api/auth/token/refresh/` | none | Exchange a refresh token for a new access token |
| `GET` | `/api/auth/me/` | access token | Return the caller's own identity |

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

- **`access`** lives 5 minutes and is sent on every request that needs
  authentication.
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

Being authenticated grants **no** additional access at this stage. Reading
entities is anonymous, and a valid token reveals nothing a stranger cannot
already see: drafts and deleted records stay hidden, and writes stay refused.
Role-based authorisation will arrive with write operations, carried by Django
groups checked server-side.

### Caveats

- **No revocation.** Rotation and token blacklisting are not enabled.
  Refreshing does not invalidate the previous access token, which stays usable
  until it expires on its own, and discarding a token in your client does not
  cancel it server-side. There is no logout endpoint, and none is implied. A
  compromised token therefore stays valid for up to its lifetime — 5 minutes
  for an access token, 1 day for a refresh token.
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

Mythological content remains **read-only**: its write methods return `405`.
JWT token issuance, refresh and the protected identity route were validated
in phase 4 increment 1, including manual Postman exercises. Object-level permissions,
content write operations and the moderation workflow are not implemented yet.
