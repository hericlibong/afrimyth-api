# Editorial writes

[Back to the README](../README.md)

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

## Update an entity, its profile and its attachments

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

## Write the documentary sources and relations of a record

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
