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


def string_array() -> ArrayField[list[str], list[str]]:
    """Construit un `ArrayField` de courtes chaînes, vide par défaut.

    Les cinq listes symboliques de `Entity` et les cinq listes de culte de
    `DivinityProfile` partagent exactement la même définition ; la factoriser
    évite dix répétitions sans introduire d'abstraction de modèle.
    """
    return ArrayField(models.CharField(max_length=100), default=list, blank=True)


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
            raise ValidationError(
                {
                    "entity": (
                        "Un profil de divinité ne peut être rattaché qu'à une "
                        "entité de type « divinity »."
                    )
                }
            )
