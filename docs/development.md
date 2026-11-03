# Architecture and checks

[Back to the README](../README.md)

### Layout

| Path | What lives there |
|---|---|
| `config/` | Project settings, root URLs, the health endpoint |
| `accounts/` | Custom user model, the three business-role groups, the JWT routes |
| `mythology/models.py` | The domain: the `Entity` trunk, three profiles, four reference models, relations, sources |
| `mythology/selectors.py` | **Visibility policy** — which records a given caller may read, public or private |
| `mythology/services.py` | Creation of an entity together with the profile of its type, in one transaction |
| `mythology/transitions.py` | The six editorial transitions and the role each one needs |
| `mythology/deletion.py` | Logical deletion and restoration, with the variant protection |
| `mythology/permissions.py` | Role check, then an object-level check for modification |
| `mythology/serializers.py` | The public and private payloads |
| `mythology/views.py` | The public and private viewsets |
| `mythology/management/commands/` | The corpus import command |
| `docs/` | Internal guides and per-increment reports, in French |

Two deliberate choices are worth knowing before reading further. **Visibility
lives in the queryset, not only in permissions**, because an object-level
permission is never consulted for the records a list does not return.
And **each rule is enforced at the level where it can be**: database
constraints where a constraint is possible, Django validation where it is
not — the docstrings say which, for each rule.

### The generated OpenAPI schema

Three routes serve the same schema, all readable without logging in:

| Route | Purpose |
|---|---|
| `/api/schema/` | OpenAPI 3 schema, served as YAML |
| `/api/docs/` | Swagger UI — browse the endpoints and run requests with **Try it out** |
| `/api/redoc/` | ReDoc — a reading-oriented rendering of the same schema |

No schema file is committed: it is produced from the code at request time.
To generate and validate it locally:

```bash
python manage.py spectacular --file schema.yml --validate --fail-on-warn
```

The command fails on generator warnings and validation errors. It complements
the contract tests; it does not detect every mismatch with runtime behaviour.

**Using Swagger UI.** The entity list, entity detail and health operations are
`GET` and need no credentials. Expand an operation, press **Try it out**,
optionally fill the collection's query parameters, then **Execute**. On a
database holding only unpublished drafts, the collection answers `200` with
zero results and any detail slug answers `404`. No write method is offered on
the public entity routes, because none exists.

**Authenticating in Swagger UI.** `GET /api/auth/me/` and every `/api/manage/`
operation require a token; everything else is open. Run
`POST /api/auth/token/` first, copy the `access` value, press **Authorize**,
paste it, then execute the protected operation. Paste the token alone:
Swagger adds the `Bearer ` prefix itself.

**CDN dependency.** Swagger UI and ReDoc load their JavaScript and CSS from a
public CDN. Without internet access the HTML page is still served but will
not render. No offline bundle is shipped, as no such need has been
established. ReDoc is pinned to version 2.5.3, compatible with the
classic-script template provided by drf-spectacular; it does not follow the
CDN's `latest` alias.

### Running the checks

Four commands cover tests, lint, formatting and types; coverage and
continuous integration run the same set. The commands, their prerequisite and
the coverage threshold are under [Verification](#verification).

### Reference

The sections that follow are the detailed contract — route by route, payload
by payload, with the error cases. They are reference material, not a first
read: start with **Try it** above, and come back here when you need the exact
behaviour.

---

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

### Coverage

Coverage is not measured on every run, because day-to-day work runs targeted
tests. Measure it explicitly:

```bash
pytest --cov --cov-report=term-missing
```

The measured scope is the three application packages — `accounts`, `config`
and `mythology` — with tests and migrations excluded. Branch coverage is on,
so a conditional with only one exercised outcome counts as partial. The
minimum is `fail_under` in `pyproject.toml`: the command fails below it.

### Continuous integration

One GitHub Actions workflow, `.github/workflows/ci.yml`, runs on pull
requests and on pushes to `main`. It uses a single environment — Python 3.12
and a PostgreSQL 16 service container with throwaway credentials — and reads
no `.env` file, no V2 corpus and no local database. It runs the same checks
as above, each as its own step, and fails on the first one that fails:

`ruff check` · `ruff format --check` · `mypy` · `manage.py check` ·
`makemigrations --check --dry-run` ·
`spectacular --validate --fail-on-warn` · `pytest --cov`
