# Public API

[Back to the README](../README.md)

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

## Pagination

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

## Search and filters

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

## Errors

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

## Visibility rule

An entity is publicly visible **if and only if** its editorial status is
`published` **and** it has not been logically deleted. This single rule
applies to both endpoints and to every caller — anonymous, authenticated, or
superuser. These are public routes, not private management routes; the Django
admin remains the way to reach unpublished records.

A non-public entity and an unknown slug return the **same** `404`, with the
same body. The response never reveals that a record exists, nor its editorial
status.

## Nested references follow the same rule

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

## Expect an empty collection on a fresh database

Entities are created as `draft`, both by the admin and by the pilot import.
Until a record is explicitly published, `GET /api/entities/` legitimately
returns `[]` and every detail URL returns `404`. That is the intended
behaviour, not a misconfiguration.

## Not available yet

The public routes carry no write operation. Every HTTP write method on
`/api/entities/` is refused with `405`, whether or not a token is supplied.
Creating a record happens on the private collection described below.
