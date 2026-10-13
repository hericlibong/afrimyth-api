# CLAUDE.md

Instructions pour les agents Claude travaillant sur `afrimyth-api`.

## Nature du projet

API REST Django (Python 3.12, Django 5.2 LTS, Django REST Framework,
PostgreSQL) pour le projet Afrimyth. Le dépôt est au tout début de la phase 1 :
seul le socle technique existe.

## Structure

```
config/        Projet Django (settings, urls, wsgi/asgi, vues techniques)
accounts/      Utilisateurs et authentification — contient le modèle `User`
mythology/     Domaine mythologique — aucun modèle pour l'instant
tests/         Tests transverses (socle, endpoints techniques)
docs/reports/  Rapport d'intervention, un fichier par incrément
```

## Règles de travail

- **Périmètre.** N'implémente que ce qui est demandé. Ne devance pas la
  roadmap : à ce stade, `Entity` et les profils métier ne doivent pas exister.
- **Pas d'abstraction anticipée.** Pas de couche service/repository, pas de
  `BaseModel` générique, pas de mixins spéculatifs. Du Django idiomatique.
- **Configuration.** Toute valeur dépendante de l'environnement passe par une
  variable d'environnement déclarée dans `.env.example`. Jamais de secret en
  dur ni dans le dépôt.
- **Modèle utilisateur.** `accounts.User` est déclaré via `AUTH_USER_MODEL` et
  créé dans `accounts/migrations/0001_initial.py`. Ne le remplace pas et ne
  supprime pas cette migration.
- **Migrations.** Une migration par changement de modèle, générée avec
  `makemigrations`, committée avec le code qu'elle accompagne.
- **Tests.** Tout endpoint ou comportement ajouté vient avec un test pytest.
- **Rapport.** Chaque intervention crée ou actualise un rapport sous
  `docs/reports/`, contenant : objectif et périmètre, fichiers touchés,
  décisions prises, commandes de vérification et leurs résultats, blocages
  rencontrés et leur résolution, état Git final. Aucun secret, aucune valeur de
  `.env`, aucun mot de passe n'y figure.
- **Langue.** Code et identifiants en anglais ; commentaires, docstrings et
  documentation en français.

## Hors périmètre à ce stade

Docker, CI, authentification JWT, génération d'images, et tout contenu issu
d'un dossier `_audit` (à ne jamais recopier).

## Commandes

```bash
py -3.12 -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
cp .env.example .env

python manage.py migrate
python manage.py runserver

pytest                 # tests
ruff check .           # lint
ruff format --check .  # format
mypy .                 # typage
```

Un fichier `.env` est nécessaire à toutes ces commandes : `config/settings.py`
refuse de démarrer sans `DJANGO_SECRET_KEY` hors `DJANGO_DEBUG=True`.

`pytest` n'a pas besoin de PostgreSQL tant qu'aucun test ne touche la base ;
`migrate` et `runserver` en ont besoin.
