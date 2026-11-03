# Corpus import

[Back to the README](../README.md)

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
