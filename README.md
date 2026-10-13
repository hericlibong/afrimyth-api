# afrimyth-api

API REST Django du projet Afrimyth.

## Prérequis

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
cp .env.example .env   # puis adapter les valeurs
```

## Lancement

```bash
python manage.py migrate
python manage.py runserver
```

L'endpoint de santé est alors disponible sur
<http://127.0.0.1:8000/api/health/> et répond `{"status": "ok"}`.

## Vérifications

Le fichier `.env` doit exister avant toute commande : `config/settings.py`
refuse de démarrer sans `DJANGO_SECRET_KEY` lorsque `DJANGO_DEBUG` n'est pas
activé.

```bash
pytest                 # tests
ruff check .           # lint
ruff format --check .  # format
mypy .                 # typage
```

## État d'avancement

Phase 1, incrément 1 : socle technique uniquement (projet Django + DRF,
configuration par variables d'environnement, modèle utilisateur personnalisé,
endpoint de santé, outillage qualité). Le domaine mythologique n'est pas
encore modélisé.
