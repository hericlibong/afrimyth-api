# Project status

[Back to the README](../README.md)

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
