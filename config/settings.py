"""Configuration Django du projet afrimyth-api.

Toute la configuration sensible ou dépendante de l'environnement est lue dans
les variables d'environnement. En développement, un fichier `.env` à la racine
du dépôt est chargé automatiquement (voir `.env.example`).
"""

from __future__ import annotations

import os
from pathlib import Path

import django_stubs_ext
from dotenv import load_dotenv
from rest_framework.generics import GenericAPIView
from rest_framework.serializers import BaseSerializer

# Les classes génériques de Django et de DRF ne le sont que pour les stubs.
# Ce correctif les rend indexables à l'exécution, afin que le code puisse être
# annoté — `ModelAdmin[Entity]`, `ModelSerializer[Entity]` — sous mypy strict.
django_stubs_ext.monkeypatch(extra_classes=[BaseSerializer, GenericAPIView])

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
}


# --- Internationalisation -----------------------------------------------------

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# --- Fichiers statiques -------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
