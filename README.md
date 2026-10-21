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

## Public read API

Two read-only endpoints, open to anonymous clients:

| Endpoint | Returns |
|---|---|
| `GET /api/entities/` | compact collection: `id`, `slug`, `name`, `entity_type`, `category` |
| `GET /api/entities/{slug}/` | full entity: common fields, reference data, type profile, relations and documentary sources |

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

Pagination, filtering, search and the OpenAPI schema with Swagger or ReDoc
are not implemented. Neither are authentication, JWT, write operations and
the moderation workflow. Every HTTP write method is refused with `405`.

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

Phase 3 in progress: the public read contract now exposes only published,
non-deleted entities, and hides non-public nested references.

The API is **read-only** — every write method returns `405`. Authentication,
object-level permissions, write operations and the moderation workflow are
planned for a later phase, as are pagination, filtering, search and the
OpenAPI schema.
