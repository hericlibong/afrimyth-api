# afrimyth-api

**Afrimyth is a cultural project with an encyclopedic purpose, devoted to the
mythologies of Africa and of its diasporas.** It gathers, in one structured
place, what is told about divinities, heroes and creatures: where a figure is
rooted, what it is said to govern, how it appears, who it is linked to, and
which sources say so.

This repository holds `afrimyth-api`, the Django REST API behind that corpus.
The API has two jobs: letting anyone **consult** what has been published, and
letting an editorial team **contribute** to and review what has not been yet.

> **Ambition and current scope are not the same thing.** The sections below
> separate them deliberately. Afrimyth aims to become a durable reference;
> what exists today is a working API, a data model exercised against a
> historical corpus, and a local installation. There is no hosted public
> instance, no published dataset and no finished encyclopedia.

**What this project does not claim.** It is not exhaustive: African and
diasporic mythologies are vast, plural and unevenly documented, and a corpus
of a few dozen figures touches a fraction of them. It is not an editorial
authority: the content reproduces and reorganises existing material, whose
accuracy, spelling, classification and cultural framing stay under review.
Several questions are knowingly left open rather than settled by software —
which name is canonical, whether two close ethnonyms are the same, or how a
cited descendant relates to a figure. The import report records unresolved
mapping decisions, and a relation can cite a name when its target is missing.

---

## 1. Discover

### What a record can document

One record is one figure. Around it, the model holds four kinds of
information:

| | What it holds |
|---|---|
| **The figure** | Its name, its type — divinity, hero or creature —, an editorial subtitle, its gender, its cultural role, a narrative description, how it manifests, and symbolic attributes: signs, symbols, objects, animals |
| **Its cultural context** | The country or countries it is attached to, the ethnicity it is anchored in, and the cultural area that situates it — an African region, a transregional scope such as pan-African, or a diasporic one |
| **Its relations** | Links to other figures: parent, child, consort, ally, enemy. A link may point to a record that exists, or simply cite a name for a figure not yet documented |
| **Its references** | Documentary sources: a book, an article, a website, a museum reference, an oral testimony, with optional URL, consultation date and notes |

Beyond the common trunk, each type carries its own profile: a divinity has
its cult — offerings, taboos, rites —, a hero has titles, achievements,
artefacts and legacy, a creature has habitat, powers, strengths, weaknesses,
diet, size and an optional threat level.

A figure may also be recorded as a **cultural variant** of another: a
regional form of the same figure, kept as its own record rather than merged,
because the variation is itself part of what is documented.

### Who it is for

- **Readers** — anyone curious about these mythologies, who wants to browse
  published figures without an account.
- **Contributors** — people who write and correct records.
- **Reviewers** — people who read submitted work and decide whether it is
  published.
- **Developers** — anyone wanting to build a client on top of a documented
  HTTP contract.

### From a draft to a published record

Nothing becomes public by accident. A record travels through four states, and
a person's role decides what they may do with it.

```
draft     ──submit──▶   submitted
submitted ──withdraw──▶ draft
submitted ──publish──▶  published
submitted ──reject──▶   rejected
rejected  ──resume──▶   draft
published ──reopen──▶   draft
```

In plain words:

- A **contributor** writes. They create a record, which starts as a private
  **draft**, correct it freely, and **submit** it when they consider it
  ready. While it is submitted they can still read it but no longer change
  it — which is what makes a review meaningful. They may **withdraw** it to
  get back to work.
- A **reviewer** decides. They read everything that is not deleted, and
  either **publish** a submitted record or **reject** it with a written
  reason. Owning a record grants no right to publish it: writing and
  approving are separate acts.
- An **administrator** can do both, and two things more: **reopen** a
  published record back to draft, and **restore** a record that was deleted.
- A **rejected** record is not lost. Its author **resumes** it, keeps the
  rejection note in view to guide corrections, and submits it again.

The API marks deleted records and hides them from entity listings. An
administrator can restore them through the API.

### What a reader can consult today

Only records that are **published and not deleted**. That rule holds for
everyone — anonymous visitor, contributor, reviewer, administrator — because
the public routes are public for all. A record that is not public and a name
that does not exist give exactly the same answer, so a response never reveals
that a hidden record exists.

**A fresh installation legitimately shows nothing.** Imported records are
created as drafts. Until someone publishes one, the public collection returns
zero results and every public detail URL answers `404`. That is the system
working as designed, not a failure.

---

## 2. Install

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

### Path A — with Docker

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

### Path B — without Docker

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

### Environment variables

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

### A fresh installation has its own, empty database

A new install creates its own database, with the tables and no content: no
account, no reference data, no figure. Restarting does not reset it — the
data persists — but nothing is seeded for you.

### Importing the historical corpus

The project can import a historical V2 corpus of African mythological
figures. **That corpus is not in this repository** and is not distributed
with it: the import reads an external JSON file whose path you pass
explicitly. Without that file there is nothing to import, and the
installation stays empty until you create records through the API.

Imported records arrive as **drafts**, with no owner and no review marks, so
an import never publishes anything. See
[Corpus import](#corpus-import) for the commands and the documented limits.

---

## 3. Try it

Short, reproducible examples. **Every value below is fictitious** — invented
for the demonstration, attributed to no tradition and belonging to no real
corpus. Replace `8000` with `8001` if you started the Docker path.

### What you need first

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

### Read, without an account

```bash
curl http://127.0.0.1:8000/api/entities/
```

Expected on a fresh install: `200` with
`{"count": 0, "next": null, "previous": null, "results": []}` — the envelope
is there, the corpus is empty. Once a record is published, it appears in
`results`, and its detail is at `/api/entities/<slug>/`.

Asking for a slug that is unpublished or unknown gives the same `404` in both
cases.

### Get a token

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "<your username>", "password": "<your password>"}'
```

Expected: `200` with an `access` and a `refresh` token. Send the access token
as `Authorization: Bearer <access token>` on every request below. Check that
it works with `GET /api/auth/me/`.

### Contribute — create a draft

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

### Review — publish or reject

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

### Administer — delete logically, then restore

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

### At a glance

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
[Private editorial API](#private-editorial-api).

---

## 4. Understand the code

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
## Two read contracts

The corpus is served by two distinct pairs of routes, and they never mix.

| Routes | Who | Shows |
|---|---|---|
| `/api/entities/…` | anyone, no token | published, non-deleted records only |
| `/api/manage/entities/…` | access token **and** an editorial role | the editorial view of the corpus, by role and ownership |

The private routes are also where a record, its profile, its attachments, its
documentary sources and its relations are written, and where it is submitted,
withdrawn, resumed, published, rejected, reopened, logically deleted and
restored; the public routes carry no write operation at all.

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

### Roles, and what they may read, create and update

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

### Publish, reject and reopen a record

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

### Delete a record logically, and restore it

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

### The other writes are still refused

`PUT` is refused with `405` on both private entity URLs, for every role,
superuser included; `POST` is refused on the private detail URL and `DELETE` on
the collection. The transition, decision and restore routes accept `POST` only.
Full replacement is not part of the contract, and no operation ever removes an
entity row physically.

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

## Corpus import

A management command imports figures from the historical V2 corpus: a three
figure pilot selection by default, or the whole file with `--all`.

```bash
# Simulate: validates and attempts every write, then rolls back
python manage.py import_mythology_pilot --input "/path/to/mythology_data.json" --dry-run

# Import the pilot selection for real
python manage.py import_mythology_pilot --input "/path/to/mythology_data.json"

# Import every figure of the file
python manage.py import_mythology_pilot --input "/path/to/mythology_data.json" --all
```

- **External input.** The corpus file lives outside this repository and its
  path is always passed with `--input`; no path is hard-coded, and no corpus
  file is copied into the repository.
- **Pilot selection.** Without `--all`, only three figures are imported —
  `Oya` (divinity), `Anansi` (hero) and `Mokele-mbembe` (creature) — one per
  entity type, and the command fails if one of them is missing from the file.
- **`--all`.** Every figure of the file is imported instead, with the same
  transformations, the same `draft` state and the same re-run guarantees. The
  option is explicit: the default behaviour is unchanged. A figure without a
  name, with an unknown `entity_type`, or whose name appears twice in the
  file stops the command — the import never renames, merges or guesses.
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

The command prints a summary listing figures read and selected, created and
skipped entities, relations resolved or merely cited by name, and every
transformation, omission or ambiguity it encountered.

**Limits of the import, by design.** Relations are resolved against the
figures of the same call only: a target that has no record is preserved in
`to_name` instead of being matched approximately or turned into a stub entity.
A `descendants` list is reported but never converted into links, since a cited
descendant is not necessarily a direct child. Cultural areas, countries,
ethnicities and domains come from explicit mapping tables: a value that is
absent from them is reported — a country without an ISO code keeps an empty
one — and never inferred. Debatable domain synonyms and near-identical
ethnonyms are reported as distinct values, never merged. An existing record is
never updated, restored or returned to `draft`, including a logically deleted
one, which is also excluded from relation resolution. Upgrading the relations
of an earlier import is therefore a separate operation, not a side effect of
re-running the command.

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

Phase 4 is complete after review, automated tests and manual exercises.
Increment 1 delivered JWT token issuance, refresh and
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
rejected record. Increment 6 adds the moderation decisions: publishing or
rejecting a submission, and reopening a published record. Increment 7 adds the
logical deletion of a record and its restoration.

The public routes stay read-only. Full replacement stays refused, and the
reclassification of an entity's type is not implemented yet.

Phase 5 covers the corpus import. The pilot command was extended with an
explicit `--all` option, and the full historical corpus was imported into the
local database as drafts: existing records were skipped rather than
overwritten, and re-running the command adds nothing. The mapping decisions
it could not settle — a country name that does not identify one country,
close ethnonyms, debatable domain synonyms, the direction of a cited
descendant — are reported by the command instead of being resolved.

Phase 6 covers the local setup and the release. A Dockerfile and a two-service
Compose file start the API and PostgreSQL locally; one GitHub Actions workflow
runs lint, formatting, types, the Django checks, the schema validation and the
tests with coverage on pull requests and on pushes to `main`; and this README
was rewritten for a reader discovering the project.

**Version.** This release is `1.0.0`, declared in `pyproject.toml` and
reported as `info.version` in the OpenAPI schema. It names the delivery, not
a version of the contract: the routes stay under `/api/` with no version
segment, and no version negotiation is exposed. A future breaking change
would therefore need a versioning scheme that does not exist yet.

The Django administration is a trusted technical maintenance tool, not the
editorial interface. Its entity forms do not enforce the API's type/profile
pairing and still allow physical deletion. These limitations are documented
and deferred; normal editorial work uses the API. A separate basic editorial
interface will use these API permissions later, outside the corpus import.

**Older records are never repaired by the import**, and a database that was
populated before the current rules can hold two kinds of leftovers: an entity
saved without the profile of its type, which the API then refuses to update
with an explicit `400`, and relations that still cite a name although the
matching record exists today. Both are deliberate: the import skips an
existing record entirely rather than rewriting it, so correcting such records
is a separate editorial operation. A fresh installation starts empty and has
neither.
