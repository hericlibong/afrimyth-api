"""Modèles du domaine mythologique.

Cet incrément pose le tronc commun `Entity` et le premier profil métier
`DivinityProfile`. Les référentiels (pays, ethnies, aires culturelles,
domaines), les deux autres profils, les relations entre entités, le workflow
éditorial et les données de rendu visuel appartiennent aux phases suivantes de
la roadmap.
"""

from __future__ import annotations

import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models


class EntityType(models.TextChoices):
    """Type d'une figure mythologique.

    Le type gouverne le profil métier attendu. Il reste distinct de
    `Entity.category`, qui est un sous-titre éditorial libre.
    """

    DIVINITY = "divinity", "Divinité"
    HERO = "hero", "Héros"
    CREATURE = "creature", "Créature"


class Gender(models.TextChoices):
    """Genre de la figure, limité aux valeurs observées dans le corpus."""

    MALE = "male", "Masculin"
    FEMALE = "female", "Féminin"
    NEUTRAL = "neutral", "Neutre"
    ANDROGYNOUS = "androgynous", "Androgyne"
    FLUID = "fluid", "Fluide"


class ThreatLevel(models.TextChoices):
    """Niveau de menace d'une créature, facultatif."""

    LOW = "low", "Faible"
    MEDIUM = "medium", "Modéré"
    HIGH = "high", "Élevé"
    MYTHIC = "mythic", "Mythique"


def string_array() -> ArrayField[list[str], list[str]]:
    """Construit un `ArrayField` de courtes chaînes, vide par défaut.

    Les listes symboliques de `Entity` et les listes des trois profils
    partagent exactement la même définition ; la factoriser évite une
    vingtaine de répétitions sans introduire d'abstraction de modèle.
    """
    return ArrayField(models.CharField(max_length=100), default=list, blank=True)


def wrong_entity_type_error(profile_label: str, expected: str) -> ValidationError:
    """Construit l'erreur de validation commune aux trois profils.

    Seul le message est factorisé : chaque profil garde son propre `clean()`
    explicite, afin que la règle reste lisible à l'endroit où elle s'applique.
    """
    return ValidationError(
        {
            "entity": (
                f"Un {profile_label} ne peut être rattaché qu'à une entité "
                f"de type « {expected} »."
            )
        }
    )


class Entity(models.Model):
    """Tronc commun à toutes les figures mythologiques.

    Porte les faits réutilisables quel que soit le type : identification,
    récit, apparence et attributs symboliques. Les données propres à un type
    vivent dans un profil relié en `OneToOne`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    category = models.CharField(
        max_length=255,
        blank=True,
        help_text="Sous-titre éditorial libre, par exemple « Orisha of Lightning ».",
    )
    gender = models.CharField(max_length=20, choices=Gender.choices)
    cultural_role = models.CharField(max_length=255, blank=True)
    alignment = models.CharField(max_length=100, blank=True)
    story_description = models.TextField(blank=True)
    characteristics = string_array()
    physical_signs = string_array()
    symbols = string_array()
    power_objects = string_array()
    symbolic_animals = string_array()
    manifestations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "entité"
        verbose_name_plural = "entités"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "entity_type"],
                name="unique_entity_name_per_type",
            )
        ]
        indexes = [models.Index(fields=["entity_type"], name="entity_type_idx")]

    def __str__(self) -> str:
        return self.name


class DivinityProfile(models.Model):
    """Données propres aux divinités.

    Ne contient que le culte : les attributs symboliques communs restent sur
    `Entity`, conformément à la décision 4 de l'ADR 0002 qui impose un
    emplacement unique pour les domaines et les attributs partagés.
    """

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="divinity_profile",
    )
    cult_offerings = string_array()
    cult_taboos = string_array()
    cult_rituals = string_array()
    cult_places = string_array()
    cult_festivals = string_array()

    class Meta:
        verbose_name = "profil de divinité"
        verbose_name_plural = "profils de divinité"

    def __str__(self) -> str:
        return f"Profil de divinité — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type.

        Cette règle ne peut pas devenir une contrainte de base : elle porte sur
        une colonne d'une autre table. Elle est donc appliquée par
        `full_clean()`, donc par l'administration et par les formulaires. Un
        appel direct à `objects.create()` ne la déclenche pas — la garantie
        complète « une entité possède exactement le profil de son type »
        viendra avec les services de création métier.
        """
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.DIVINITY
        ):
            raise wrong_entity_type_error("profil de divinité", EntityType.DIVINITY)


class HeroProfile(models.Model):
    """Données propres aux héros.

    Les alliés et les ennemis ne sont pas ici : ce sont des relations entre
    entités, qui seront portées par `EntityRelation` dans un incrément
    ultérieur de la phase 2.
    """

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="hero_profile",
    )
    titles = string_array()
    achievements = string_array()
    quests = string_array()
    weapons_or_artifacts = string_array()
    legacy = models.TextField(blank=True)
    historical_context = models.TextField(blank=True)

    class Meta:
        verbose_name = "profil de héros"
        verbose_name_plural = "profils de héros"

    def __str__(self) -> str:
        return f"Profil de héros — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type."""
        super().clean()
        if self.entity_id is not None and self.entity.entity_type != EntityType.HERO:
            raise wrong_entity_type_error("profil de héros", EntityType.HERO)


class CreatureProfile(models.Model):
    """Données propres aux créatures."""

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="creature_profile",
    )
    habitat = string_array()
    powers = string_array()
    strengths = string_array()
    weaknesses = string_array()
    encounter_omens = string_array()
    encounter_rules = string_array()
    known_sightings = string_array()
    diet = models.CharField(max_length=255, blank=True)
    size = models.CharField(max_length=255, blank=True)
    appearance_notes = models.TextField(blank=True)
    # `null=True` sur un champ textuel est signalé par Ruff (DJ001) parce
    # qu'il ouvre deux représentations de l'absence, `NULL` et `""`.
    # L'écart est délibéré, mais il n'est pas sans effet : il est seulement
    # borné pour l'instant.
    #
    # Ce qui est garanti : pour un champ à `choices` nullable,
    # `Field.formfield()` impose `empty_value=None`, donc un choix laissé vide
    # dans un formulaire ou dans l'administration est enregistré `NULL`.
    # Ce qui ne l'est pas : un appel ORM direct — `objects.create(
    # threat_level="")` — ou un futur serializer d'écriture peut toujours
    # stocker `""`. L'API étant en lecture seule, ce cas n'est pas exposé
    # aujourd'hui. La normalisation de `""` vers `None` sera imposée dans les
    # serializers ou services d'écriture de la phase 4 ; aucune contrainte ni
    # abstraction n'est ajoutée maintenant.
    threat_level = models.CharField(  # noqa: DJ001
        max_length=10,
        choices=ThreatLevel.choices,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "profil de créature"
        verbose_name_plural = "profils de créatures"

    def __str__(self) -> str:
        return f"Profil de créature — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type."""
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.CREATURE
        ):
            raise wrong_entity_type_error("profil de créature", EntityType.CREATURE)
