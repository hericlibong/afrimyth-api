"""Configuration Django du projet afrimyth-api.

Toute la configuration sensible ou dépendante de l'environnement est lue dans
les variables d'environnement. En développement, un fichier `.env` à la racine
du dépôt est chargé automatiquement (voir `.env.example`).
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str:
    """Retourne la variable d'environnement `name`.

    Lève `RuntimeError` si la variable est absente et sans valeur par défaut :
    on préfère un démarrage impossible à une configuration silencieusement
    incorrecte.
    """
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variable d'environnement requise manquante : {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# --- Sécurité -----------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", default=False)

# En développement on tolère une clé de repli pour pouvoir lancer le projet
# immédiatement ; hors DEBUG la variable devient obligatoire.
if DEBUG:
    SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-only-key")
else:
    SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")


# --- Applications -------------------------------------------------------------

INSTALLED_APPS = [
    # **En premier, volontairement.** `ready()` de cette app applique le
    # correctif de typage avant que l'autodiscover de l'administration
    # importe `mythology/admin.py`, qui indexe des classes génériques. Voir
    # `config/apps.py` pour le détail.
    "config.apps.TypingPatchConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
    "mythology",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- Base de données ----------------------------------------------------------

# `POSTGRES_PASSWORD` est volontairement sans valeur par défaut : un mot de
# passe en dur dans le dépôt deviendrait vite le mot de passe réellement
# utilisé. Les autres paramètres ont des valeurs de développement anodines.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "afrimyth"),
        "USER": env("POSTGRES_USER", "afrimyth"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}


# --- Authentification ---------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Django REST Framework ----------------------------------------------------

REST_FRAMEWORK = {
    # JWT d'abord : c'est le mécanisme des clients d'API. La session reste
    # ensuite, pour l'API navigable de DRF et l'administration.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Défaut fermé : toute vue qui n'ouvre pas explicitement l'accès exige une
    # authentification. Les vues publiques déclarent `AllowAny` une par une.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # drf-spectacular remplace le générateur de schéma par défaut de DRF.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


# --- Jetons JWT ---------------------------------------------------------------

# Durées délibérément courtes pour un premier incrément : un accès de cinq
# minutes limite la fenêtre d'un jeton intercepté, et un renouvellement d'un
# jour évite de se reconnecter sans cesse pendant les essais.
#
# Ni rotation, ni liste de révocation, ni route de déconnexion ne sont
# activées. **Conséquence à connaître** : renouveler n'invalide pas l'accès
# précédent, qui reste valable jusqu'à son expiration, et supprimer un jeton
# côté client ne le révoque pas côté serveur. Il n'y a donc aucune promesse
# de déconnexion ni de révocation immédiate à ce stade.
#
# La signature reprend le réglage standard de la bibliothèque : HS256 avec
# `SECRET_KEY`. Aucun secret supplémentaire, aucun rôle métier dans les
# claims — les autorisations viendront des groupes Django, pas du jeton.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}


# --- Schéma OpenAPI -----------------------------------------------------------

# Les textes de cette section sont publics : ils apparaissent dans le schéma,
# dans Swagger UI et dans ReDoc. Ils sont donc en anglais, conformément à
# l'ADR 0003.
SPECTACULAR_SETTINGS = {
    "TITLE": "Afrimyth API",
    "DESCRIPTION": (
        "Read-only API for African mythological figures: divinities, heroes "
        "and creatures, with their cultural and geographic reference data, "
        "their relations to one another and their documentary sources."
        "\n\n"
        "## Two distinct read contracts\n\n"
        "`/api/entities/` is **public**: it serves published content to "
        "anyone. `/api/manage/entities/` is **private**: it serves the "
        "editorial view of the corpus to accounts holding an editorial role. "
        "They are separate routes with separate payloads; the public one "
        "never changes its shape or its selection according to who calls "
        "it.\n\n"
        "## Public visibility\n\n"
        "An entity is publicly visible **if and only if** its editorial "
        "status is `published` and it has not been logically deleted. This "
        "rule applies to both public endpoints and to every caller — "
        "anonymous, authenticated, reviewer or superuser alike. A non-public "
        "entity and an unknown "
        "slug return the same `404`, with the same body: the response never "
        "reveals that a record exists, nor its editorial status.\n\n"
        "Nested references follow the same rule. `variant_of` is `null` when "
        "the referenced figure is not public, and a relation whose resolved "
        "target is not public is omitted entirely — its name is never copied "
        "into `to_name`.\n\n"
        "The public payloads carry no editorial field: neither `status`, nor "
        "`created_by`, nor any review or deletion mark.\n\n"
        "## Private editorial read\n\n"
        "`/api/manage/entities/` requires an access token **and** membership "
        "of one of three Django groups: `contributor`, `reviewer` or "
        "`administrator`. An authenticated account holding none of them is "
        "refused with `403`, even for a published record — reading published "
        "content is what the public endpoints are for.\n\n"
        "A contributor reads every published record, plus its own records in "
        "`draft`, `submitted` or `rejected`. A reviewer, an administrator and "
        "a superuser read every record that has not been deleted. Deleted "
        "records are excluded for everyone. These payloads add `status` and "
        "`created_by`, and the detail adds the review marks; nested "
        "references follow the caller's own rule rather than the public "
        "one.\n\n"
        "Roles are read from group membership on every request, never from a "
        "claim inside the token: a group change takes effect on the next "
        "request, with the same token.\n\n"
        "## Read-only content\n\n"
        "Mythological content is read-only. On `/api/entities/` and on "
        "`/api/manage/entities/`, only `GET` is available; `POST`, `PUT`, "
        "`PATCH` and `DELETE` are refused with `405 Method Not Allowed`, for "
        "every role. Write operations and the moderation workflow are planned "
        "for a later phase and are **not** part of this contract.\n\n"
        "The `/api/auth/` endpoints are the exception: issuing and refreshing "
        "a token are `POST` operations, because they carry credentials in the "
        "request body. They create no content.\n\n"
        "## Authentication\n\n"
        "`POST /api/auth/token/` exchanges a username and password for an "
        "access token and a refresh token. The access token is then sent as "
        "`Authorization: Bearer <access token>`, and "
        "`POST /api/auth/token/refresh/` issues a new one when it expires.\n\n"
        "Authentication is **not** required to read entities on the public "
        "endpoints, and it changes nothing about what they return. Holding a "
        "token is still not authorisation by itself: what an account may read "
        "privately depends on its groups, checked server-side on every "
        "request.\n\n"
        "`GET /api/auth/me/` returns the caller's own identity and exists to "
        "let a client verify that its token works. It says nothing about what "
        "the account may do.\n\n"
        "Tokens cannot be revoked at this stage. Refreshing does not "
        "invalidate the previous access token, and discarding a token on the "
        "client does not cancel it on the server: it stays valid until it "
        "expires. There is no logout endpoint.\n\n"
        "## Expect an empty collection\n\n"
        "Entities are created as drafts. Until a record is explicitly "
        "published, the public collection legitimately returns zero results "
        "and every public detail URL returns `404`. On the current "
        "development database the imported pilot figures are still drafts, so "
        "they are absent from the public API and reachable only through the "
        "private endpoints, by an account holding an editorial role.\n\n"
        "## Editorial caveat\n\n"
        "Imported content reproduces a historical corpus. Its accuracy, "
        "completeness and classification are under editorial review and are "
        "not warranted by this API."
    ),
    "VERSION": "0.1.0",
    # Le gabarit de drf-spectacular charge un script classique. ReDoc 3,
    # désormais servi par @latest, exige un module et laisse une page blanche.
    # Fixer une version 2 compatible évite les changements implicites du CDN.
    "REDOC_DIST": "https://cdn.jsdelivr.net/npm/redoc@2.5.3",
    # Le schéma décrit l'API sous `/api/`, mais les routes de documentation
    # elles-mêmes n'ont pas à figurer dans le contrat.
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "ENUM_NAME_OVERRIDES": {
        "EntityTypeEnum": "mythology.models.EntityType.choices",
        "EntityStatusEnum": "mythology.models.EntityStatus.choices",
        "GenderEnum": "mythology.models.Gender.choices",
        "ThreatLevelEnum": "mythology.models.ThreatLevel.choices",
        "RelationKindEnum": "mythology.models.RelationKind.choices",
        "SourceKindEnum": "mythology.models.SourceKind.choices",
        "CulturalAreaKindEnum": "mythology.models.CulturalAreaKind.choices",
    },
    "TAGS": [
        {"name": "entities", "description": "Public read access to figures."},
        {
            "name": "management",
            "description": (
                "Private read access for editorial work, by role. Requires an "
                "access token and membership of one of the three editorial "
                "groups."
            ),
        },
        {
            "name": "authentication",
            "description": "Token issuance, refresh and identity check.",
        },
        {"name": "service", "description": "Operational endpoints."},
    ],
}


# --- Internationalisation -----------------------------------------------------

# L'anglais est la langue du produit public, conformément à l'ADR 0003 : les
# messages standards de Django et de DRF rendus par l'API — dont les 404 et
# 405 — doivent être en anglais. Le travail interne reste en français.
# Aucun middleware de langue, aucune architecture i18n n'est ajouté.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Fichiers statiques -------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# --- Correctif de typage ------------------------------------------------------

# Aucun import de DRF ici. Le correctif de typage vit désormais dans
# `config/apps.py`, appliqué par le `ready()` de `TypingPatchConfig`, placé en
# premier dans `INSTALLED_APPS`.
#
# Deux raisons, toutes deux constatées :
#
# 1. placé en **tête** de ce fichier, l'import de `rest_framework.generics`
#    faisait lire `REST_FRAMEWORK` avant sa définition, et DRF mémorisait un
#    dictionnaire vide — `DEFAULT_PERMISSION_CLASSES` retombait alors
#    silencieusement sur le défaut ouvert `AllowAny` ;
# 2. placé en **fin** de ce fichier, le même import résout désormais
#    `JWTAuthentication`, qui importe `django.contrib.auth.models` avant que
#    le registre d'applications soit prêt — `AppRegistryNotReady`.
#
# Un test de non-régression garde les valeurs effectivement appliquées.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
