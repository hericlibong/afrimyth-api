# Afrimyth and its data model

[Back to the README](../README.md)

## What a record can document

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

## Who it is for

- **Readers** — anyone curious about these mythologies, who wants to browse
  published figures without an account.
- **Contributors** — people who write and correct records.
- **Reviewers** — people who read submitted work and decide whether it is
  published.
- **Developers** — anyone wanting to build a client on top of a documented
  HTTP contract.

## From a draft to a published record

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

## What a reader can consult today

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
