"""Configuration Django du projet afrimyth-api.

Toute la configuration sensible ou dépendante de l'environnement est lue dans
les variables d'environnement. En développement, un fichier `.env` à la racine
du dépôt est chargé automatiquement (voir `.env.example`).
"""

from __future__ import annotations

import os
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
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # drf-spectacular remplace le générateur de schéma par défaut de DRF.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


# --- Schéma OpenAPI -----------------------------------------------------------

# Les textes de cette section sont publics : ils apparaissent dans le schéma,
# dans Swagger UI et dans ReDoc. Ils sont donc en anglais, conformément à
# l'ADR 0003.
SPECTACULAR_SETTINGS = {
    "TITLE": "Afrimyth API",
    "DESCRIPTION": (
        "Public read-only API for African mythological figures: divinities, "
        "heroes and creatures, with their cultural and geographic reference "
        "data, their relations to one another and their documentary sources."
        "\n\n"
        "## Visibility\n\n"
        "An entity is publicly visible **if and only if** its editorial "
        "status is `published` and it has not been logically deleted. This "
        "rule applies to both endpoints and to every caller — anonymous, "
        "authenticated or superuser alike. A non-public entity and an unknown "
        "slug return the same `404`, with the same body: the response never "
        "reveals that a record exists, nor its editorial status.\n\n"
        "Nested references follow the same rule. `variant_of` is `null` when "
        "the referenced figure is not public, and a relation whose resolved "
        "target is not public is omitted entirely — its name is never copied "
        "into `to_name`.\n\n"
        "## Read-only\n\n"
        "Only `GET` is available. `POST`, `PUT`, `PATCH` and `DELETE` are "
        "refused with `405 Method Not Allowed`. Authentication, write "
        "operations and the moderation workflow are planned for a later "
        "phase and are **not** part of this contract.\n\n"
        "## Expect an empty collection\n\n"
        "Entities are created as drafts. Until a record is explicitly "
        "published, the collection legitimately returns zero results and "
        "every detail URL returns `404`. On the current development database "
        "the imported pilot figures are still drafts, so they are absent "
        "from this API.\n\n"
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
        "GenderEnum": "mythology.models.Gender.choices",
        "ThreatLevelEnum": "mythology.models.ThreatLevel.choices",
        "RelationKindEnum": "mythology.models.RelationKind.choices",
        "SourceKindEnum": "mythology.models.SourceKind.choices",
        "CulturalAreaKindEnum": "mythology.models.CulturalAreaKind.choices",
    },
    "TAGS": [
        {"name": "entities", "description": "Public read access to figures."},
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

# Les classes génériques de Django et de DRF ne le sont que pour les stubs.
# Ce correctif les rend indexables à l'exécution, afin que le code puisse être
# annoté — `ModelAdmin[Entity]`, `ModelSerializer[Entity]` — sous mypy strict.
#
# **Il doit rester en fin de fichier.** Importer `rest_framework.generics`
# évalue `api_settings.DEFAULT_FILTER_BACKENDS` dans le corps de
# `GenericAPIView`, ce qui fait lire et mettre en cache `REST_FRAMEWORK`.
# Placé en tête, cet import survenait avant la définition du réglage, et DRF
# mémorisait un dictionnaire vide : tous nos réglages étaient alors ignorés,
# dont `DEFAULT_PERMISSION_CLASSES`, qui retombait silencieusement sur le
# défaut ouvert `AllowAny`. Un test garde ce comportement.
import django_stubs_ext  # noqa: E402
from rest_framework.generics import GenericAPIView  # noqa: E402
from rest_framework.serializers import BaseSerializer  # noqa: E402

django_stubs_ext.monkeypatch(extra_classes=[BaseSerializer, GenericAPIView])

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
