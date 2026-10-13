# Rapport — Phase 1, incrément 1 : socle technique

- **Date :** 13 octobre 2026
- **Dépôt :** `afrimyth-api`
- **Branche :** `main`
- **Statut :** incrément terminé, phase 1 toujours en cours

## 1. Objectif et périmètre

Obtenir le premier socle technique exécutable de la phase 1 : un projet Django
qui démarre, une base PostgreSQL migrable, un modèle utilisateur personnalisé
figé dès la première migration, un endpoint public de santé testé et
l'outillage qualité en place.

Périmètre volontairement exclu de cet incrément :

- `Entity`, `DivinityProfile` et tout autre modèle métier ;
- l'administration Django des entités et la lecture liste/détail ;
- Docker, CI, authentification JWT, génération d'images ;
- toute reprise de code depuis le dossier `_audit/` de `django-portfolio`.

Ces éléments restent ouverts dans `docs/roadmap-projet-1.md`.

## 2. Choix techniques

| Sujet | Choix | Motif |
|---|---|---|
| Runtime | Python 3.12, Django 5.2 LTS (`Django~=5.2.18`) | Version LTS, alignée sur la roadmap |
| API | Django REST Framework 3.16 | Pile prévue pour les phases 3 et 4 |
| Base de données | PostgreSQL via `psycopg[binary]~=3.2` | Décision actée en ADR 0002 : PostgreSQL devient la source de vérité |
| Configuration | Variables d'environnement, `.env` local chargé par `python-dotenv` | Aucun secret dans le dépôt |
| Modèle utilisateur | `accounts.User(AbstractUser)`, sans champ supplémentaire | Identifiant `username` conservé ; déclaré via `AUTH_USER_MODEL` dès `0001_initial` pour ne jamais avoir à migrer un modèle utilisateur en production |
| Clé primaire | `BigAutoField` | Fixée par `DEFAULT_AUTO_FIELD` et `AccountsConfig.default_auto_field` |
| Permissions DRF | `IsAuthenticated` par défaut, `AllowAny` explicite sur la santé | Le défaut ferme l'API ; chaque ouverture est un choix visible |
| Structure | `config/`, `accounts/`, `mythology/`, `tests/` | Django idiomatique, sans couche service ni abstraction anticipée |

Deux décisions de détail méritent d'être consignées.

**`config/settings.py` échoue au démarrage plutôt que de deviner.** La fonction
`env()` lève `RuntimeError` si une variable requise est absente et sans valeur
de repli. `DJANGO_SECRET_KEY` n'admet un repli que sous `DJANGO_DEBUG=True`, et
`POSTGRES_PASSWORD` n'en admet aucun. Conséquence pratique : un fichier `.env`
est nécessaire avant toute commande, y compris `mypy`, dont le plugin Django
importe les settings.

**`accounts.User` ne déclare pas de classe `Meta`.** Une `Meta(AbstractUser.Meta)`
vide avait été écrite initialement ; elle produisait deux erreurs mypy, car
`AbstractUser.Meta` n'est pas typé par `django-stubs`. Django recopie de
lui-même la `Meta` du parent abstrait, donc la supprimer ne change pas la
migration générée — vérifié par `makemigrations --check --dry-run`.

## 3. Fichiers créés ou modifiés

Un squelette partiel issu d'une exécution interrompue existait déjà. Il a été
conservé, et seuls les écarts réels ont été corrigés.

**Racine**

- `manage.py`
- `pyproject.toml` — pytest/pytest-django, Ruff, mypy (`strict`, `warn_unreachable`)
- `requirements.txt`, `requirements-dev.txt`
- `.gitignore`, `.env.example`
- `README.md`, `CLAUDE.md`, `AGENTS.md`
- `docs/reports/phase-1-increment-1.md` (ce rapport)

**`config/`**

- `settings.py`, `urls.py`, `views.py` (`HealthView`), `wsgi.py`, `asgi.py`, `__init__.py`

**`accounts/`**

- `models.py` (`User`), `apps.py`, `admin.py`, `__init__.py`
- `migrations/0001_initial.py` — **générée par `makemigrations`**, non écrite à la main
- `migrations/__init__.py`

**`mythology/`**

- `apps.py`, `models.py` (aucun modèle à ce stade), `admin.py`, `__init__.py`
- `migrations/__init__.py`

**`tests/`**

- `test_health.py` — l'endpoint de santé répond 200 sans authentification
- `test_settings.py` — `AUTH_USER_MODEL` pointe bien sur `accounts.User`
- `test_user_model.py` — `USERNAME_FIELD == "username"` et PK `BigAutoField`
- `__init__.py`

Les trois tests de modèle et de settings passent par introspection : ils ne
touchent pas la base, ce qui garde la suite rapide et exécutable sans serveur.

**Non suivi par Git :** `.env` (copie locale de `.env.example`).

## 4. Correctifs apportés au squelette existant

| Écart | Correction |
|---|---|
| `manage.py` non conforme à `ruff format` (ligne vide manquante après la docstring de module) | ligne ajoutée |
| `accounts.User` déclarait une `Meta(AbstractUser.Meta)` vide → 2 erreurs mypy | `Meta` supprimée, migration inchangée |
| Aucun `.env` local → `mypy` et `pytest` échouaient à l'import des settings | `.env` créé depuis `.env.example`, hors suivi Git |
| `CLAUDE.md` indiquait `python -m venv` et taisait la dépendance à `.env` | corrigé en `py -3.12 -m venv`, prérequis `.env` documenté |
| Branche locale nommée `master` | renommée en `main` |
| `POSTGRES_PASSWORD` avait une valeur par défaut en dur dans `settings.py` et dans `.env.example`, devenue de fait le mot de passe réel du rôle local | défaut supprimé dans `settings.py` (variable désormais obligatoire), placeholder neutre dans `.env.example` |

Aucune fonctionnalité nouvelle n'a été ajoutée hors du périmètre déjà réalisé.

## 5. Base de données PostgreSQL

### Blocage initial

Au premier passage, un serveur PostgreSQL écoutait bien sur `localhost:5432`,
mais l'authentification du rôle applicatif échouait :

```
FATAL: authentification par mot de passe échouée pour l'utilisateur « afrimyth »
```

Conséquence : `manage.py migrate` et `runserver` étaient inutilisables.
Les six vérifications passaient malgré tout, aucun test ne touchant la base et
`makemigrations --check` n'émettant qu'un `RuntimeWarning` sans effet sur son
code de sortie.

Pour ne pas livrer une migration initiale non éprouvée, la chaîne complète
avait alors été appliquée sur un backend SQLite jetable, hors du dépôt : les
19 migrations, dont `accounts.0001_initial`, s'appliquaient sans erreur.

### Résolution

Le rôle et la base applicatifs ont été créés manuellement côté serveur, hors
du dépôt. Forme des commandes, sans valeur de mot de passe :

```sql
CREATE ROLE afrimyth WITH LOGIN PASSWORD '<défini hors dépôt>';
CREATE DATABASE afrimyth OWNER afrimyth;
```

Le mot de passe ne figure ni dans ce rapport, ni dans `.env.example`, ni dans
aucun fichier suivi par Git. Il est lu depuis `.env`, qui est ignoré.

### Confirmation

- **PostgreSQL 16 accessible** : la connexion depuis Django renvoie
  `PostgreSQL 16.3, compiled by Visual C++ build 1939, 64-bit`.
- **Base et rôle `afrimyth` opérationnels** : connexion établie avec les
  paramètres lus dans l'environnement.
- **Migrations appliquées sur PostgreSQL** : `manage.py migrate` ne signale
  plus aucune opération restante (`No migrations to apply.`).
- **`manage.py showmigrations`** marque toutes les migrations `[X]` :
  `accounts` (1), `admin` (3), `auth` (12), `contenttypes` (2), `sessions` (1).
  `mythology` affiche `(no migrations)`, ce qui est attendu : l'app n'a encore
  aucun modèle.
- **`manage.py check`** réussit : `System check identified no issues (0 silenced).`

## 6. Commandes de vérification et résultats

Exécutées depuis la racine du dépôt, avec PostgreSQL accessible.

| Commande | Sortie | Code |
|---|---|---|
| `python manage.py check` | `System check identified no issues (0 silenced).` | 0 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` | 0 |
| `pytest` | `4 passed in 0.63s` | 0 |
| `ruff check .` | `All checks passed!` | 0 |
| `ruff format --check .` | `19 files already formatted` | 0 |
| `mypy .` | `Success: no issues found in 19 source files` | 0 |

Exclusions Git confirmées par `git check-ignore -v` : `.env`, `.venv/`,
`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `__pycache__/`.

## 7. État Git avant commit

```
## No commits yet on main
?? .env.example
?? .gitignore
?? AGENTS.md
?? CLAUDE.md
?? README.md
?? accounts/
?? config/
?? manage.py
?? mythology/
?? pyproject.toml
?? requirements-dev.txt
?? requirements.txt
?? tests/
```

Le dépôt n'avait aucun commit. Tout l'incrément entre donc dans le commit
initial `chore: initialize Django REST API`. Le répertoire `docs/` est ajouté
par le présent rapport. Aucun fichier `.env` n'est indexé.

## 8. Tâches restant ouvertes dans la phase 1

- [ ] Créer `Entity` et `DivinityProfile` avec leur relation `OneToOne`.
- [ ] Ajouter les migrations correspondantes et l'administration Django minimale.
- [ ] Exposer une première lecture liste/détail des entités.
- [ ] Compléter les tests de modèles et d'API sur cette première ressource.

La phase 1 n'est donc pas close. Les tâches de socle, d'outillage et
d'endpoint de santé sont en revanche terminées et cochées dans
`docs/roadmap-projet-1.md` du dépôt `django-portfolio`.
