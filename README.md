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

Phase 2 in progress. Available so far: the technical foundation (Django and
Django REST Framework, environment-based configuration, custom user model,
health endpoint, quality tooling), the `Entity` common trunk with its
`DivinityProfile`, `HeroProfile` and `CreatureProfile` profiles, the Django
admin, and a read-only list/detail API.

The API is currently **read-only and open** — no authentication, no editorial
status filtering. Authentication, object-level permissions, write operations
and the moderation workflow are planned for a later phase.
