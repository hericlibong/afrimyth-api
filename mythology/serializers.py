"""Sérialiseurs de lecture du domaine mythologique.

Deux représentations distinctes de `Entity` : une forme compacte pour la
collection et une forme détaillée qui imbrique le profil métier. Cette
séparation est celle attendue en phase 3 ; les serializers d'écriture
arriveront avec le CRUD de la phase 4.
"""

from rest_framework import serializers

from mythology.models import DivinityProfile, Entity


class DivinityProfileSerializer(serializers.ModelSerializer[DivinityProfile]):
    """Profil de divinité, imbriqué dans le détail d'une entité."""

    class Meta:
        model = DivinityProfile
        fields = [
            "cult_offerings",
            "cult_taboos",
            "cult_rituals",
            "cult_places",
            "cult_festivals",
        ]


class EntityListSerializer(serializers.ModelSerializer[Entity]):
    """Représentation compacte, suffisante pour afficher une collection."""

    class Meta:
        model = Entity
        fields = ["id", "slug", "name", "entity_type", "category"]


class EntityDetailSerializer(serializers.ModelSerializer[Entity]):
    """Représentation détaillée, profil métier inclus lorsqu'il existe.

    `divinity_profile` vaut `null` pour une entité qui n'a pas de profil, ce
    qui est le cas des héros et des créatures tant que leurs profils
    n'existent pas.
    """

    divinity_profile = DivinityProfileSerializer(read_only=True)

    class Meta:
        model = Entity
        fields = [
            "id",
            "slug",
            "name",
            "entity_type",
            "category",
            "gender",
            "cultural_role",
            "alignment",
            "story_description",
            "characteristics",
            "physical_signs",
            "symbols",
            "power_objects",
            "symbolic_animals",
            "manifestations",
            "created_at",
            "updated_at",
            "divinity_profile",
        ]
