# Installation

[Back to the README](../README.md)

Two independent paths. Pick one; they do not share a database.

- **With Docker** — two containers, nothing to install on the machine beyond
  Docker itself. Good for a first look.
- **Without Docker** — a virtual environment plus a PostgreSQL you installed
  yourself. Good if you intend to work on the code.

Clone the repository first and work from its root:

```bash
git clone https://github.com/hericlibong/afrimyth-api.git
cd afrimyth-api
```

Everything below assumes that directory as the working directory.

## Path A — with Docker

**You need** Docker Desktop with its Linux engine running — it provides both
`docker` and `docker compose`. Nothing else: PostgreSQL does not have to be
installed on the host.

**Prepare the local environment file.** Copy the example and replace its
values. The real file is ignored by Git and never enters the image:

```bash
cp .env.docker.example .env.docker
```

**Start.** The first run builds the image, waits for the database to report
healthy, applies the migrations, then serves HTTP:

```bash
docker compose --env-file .env.docker up -d --build
```

The API listens on **<http://127.0.0.1:8001>**, so a non-Docker installation
keeps port 8000 for itself:

| URL | What you get |
|---|---|
| <http://127.0.0.1:8001/api/health/> | `{"status": "ok"}` |
| <http://127.0.0.1:8001/api/docs/> | Swagger UI — browse and run requests |
| <http://127.0.0.1:8001/api/schema/> | The OpenAPI 3 schema, as YAML |
| <http://127.0.0.1:8001/api/entities/> | The public collection — empty on a fresh install |

**Stop**, keeping the data:

```bash
docker compose --env-file .env.docker down
```

The named volume survives, so restarting keeps the tables and the applied
migrations. Adding `-v` would delete the database; do not use it to stop the
services.

**Optional administrative account.** Nothing creates one for you:

```bash
docker compose --env-file .env.docker exec api python manage.py createsuperuser
```

This setup runs the **Django development server**. It is meant for local work
and makes no production promise: no reverse proxy, no WSGI server, no task
queue.

## Path B — without Docker

**You need** Python 3.12 and PostgreSQL 14 or later, both already installed
and running.

```bash
# Windows PowerShell
py -3.12 -m venv .venv
.venv\Scripts\activate
# Linux / macOS
python3.12 -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env   # then adjust the values
```

Create the database and the role named in your `.env`, then:

```bash
python manage.py migrate
python manage.py runserver
```

The API listens on **<http://127.0.0.1:8000>**; the same four URLs as above
apply on that port. Create an account with
`python manage.py createsuperuser` when you need one.

## Environment variables

All environment-dependent settings are read from environment variables; in
development they are loaded from a `.env` file at the repository root — or
from `.env.docker` for the container path.

| Variable | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | Required unless `DJANGO_DEBUG` is enabled |
| `DJANGO_DEBUG` | Development only — never enable it in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_HOST`, `POSTGRES_PORT` | Development defaults are provided |
| `POSTGRES_PASSWORD` | **Required, no default** — a hard-coded default would quickly become the real password |

Never commit a `.env` file or any real secret. `.env.example` and
`.env.docker.example` hold placeholders only.

## A fresh installation has its own, empty database

A new install creates its own database, with the tables and no content: no
account, no reference data, no figure. Restarting does not reset it — the
data persists — but nothing is seeded for you.

## Importing the historical corpus

The project can import a historical V2 corpus of African mythological
figures. **That corpus is not in this repository** and is not distributed
with it: the import reads an external JSON file whose path you pass
explicitly. Without that file there is nothing to import, and the
installation stays empty until you create records through the API.

Imported records arrive as **drafts**, with no owner and no review marks, so
an import never publishes anything. See
[Corpus import](corpus-import.md) for the commands and the documented limits.

---
