# Afrimyth API

[![CI](https://github.com/hericlibong/afrimyth-api/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/hericlibong/afrimyth-api/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](docs/installation.md)
[![Django](https://img.shields.io/badge/Django-5.2-092E20)](docs/development.md)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/hericlibong/afrimyth-api/tree/v1.0.0)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Afrimyth is a cultural project with an encyclopedic purpose. It documents
divinities, heroes and creatures from African and diasporic mythologies,
along with their stories, cultural contexts, relationships and sources.
Its aim is to make these traditions easier to explore while preserving
variants and documenting uncertainty.

This repository contains the Django REST API. Readers can browse published
records, contributors can draft entries, and reviewers can decide what to
publish. The API supports an evolving collection of material from diverse
traditions.

[Quick start](#quick-start) · [First request](#first-request) · [Documentation](#documentation)

## Quick start

Install Git and Docker with Compose, then start the Docker engine.

```bash
git clone https://github.com/hericlibong/afrimyth-api.git
cd afrimyth-api
cp .env.docker.example .env.docker
```

Set a unique `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD` in `.env.docker`.
Start the API and its PostgreSQL database together.

```bash
docker compose --env-file .env.docker up -d --build
```

For Windows and Linux setup details, configuration, stopping the services
and running without Docker, see the [installation guide](docs/installation.md).

## First request

Open [API health](http://127.0.0.1:8001/api/health/) and look for
`{"status":"ok"}`. Then open [Swagger UI](http://127.0.0.1:8001/api/docs/)
and try `GET /api/entities/`.

A fresh database returns an empty collection. The historical corpus is
supplied separately. To explore the API with your own example, follow the
[editorial walkthrough](docs/editorial-walkthrough.md).

## Documentation

| Topic | What you will find |
| --- | --- |
| [Afrimyth and its data model](docs/project.md) | Cultural scope, records, roles and editorial states |
| [Installation](docs/installation.md) | Docker, native setup and environment variables |
| [Editorial walkthrough](docs/editorial-walkthrough.md) | Examples from a first read through contribution and review |
| [Public API](docs/public-api.md) | Endpoints, pagination, search, filters and visibility |
| [Editorial API](docs/editorial-api.md) | Private reads, permissions, writes and moderation |
| [Authentication](docs/authentication.md) | JWT access and refresh tokens |
| [Corpus import](docs/corpus-import.md) | Import options, data mapping and limitations |
| [Architecture and checks](docs/development.md) | Project layout, OpenAPI, tests, coverage and CI |
| [Project status](docs/project-status.md) | Delivery history, release version and known limits |

## Licensing

The API code and software documentation are available under the [MIT License](LICENSE).
The mythological corpus, including its records, descriptions and editorial
content, is outside that grant. Its license remains to be determined.
