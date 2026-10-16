"""Sérialiseurs de lecture du domaine mythologique.

Deux représentations distinctes de `Entity` : une forme compacte pour la
collection et une forme détaillée qui imbrique le profil métier. Cette
séparation est celle attendue en phase 3 ; les serializers d'écriture
arriveront avec le CRUD de la phase 4.
"""

from rest_framework import serializers

from mythology.models import CreatureProfile, DivinityProfile, Entity, HeroProfile


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


class HeroProfileSerializer(serializers.ModelSerializer[HeroProfile]):
    """Profil de héros, imbriqué dans le détail d'une entité."""

    class Meta:
        model = HeroProfile
        fields = [
            "titles",
            "achievements",
            "quests",
            "weapons_or_artifacts",
            "legacy",
            "historical_context",
        ]


class CreatureProfileSerializer(serializers.ModelSerializer[CreatureProfile]):
    """Profil de créature, imbriqué dans le détail d'une entité."""

    class Meta:
        model = CreatureProfile
        fields = [
            "habitat",
            "powers",
            "strengths",
            "weaknesses",
            "encounter_omens",
            "encounter_rules",
            "known_sightings",
            "diet",
            "size",
            "appearance_notes",
            "threat_level",
        ]


class EntityListSerializer(serializers.ModelSerializer[Entity]):
    """Représentation compacte, suffisante pour afficher une collection."""

    class Meta:
        model = Entity
        fields = ["id", "slug", "name", "entity_type", "category"]


class EntityDetailSerializer(serializers.ModelSerializer[Entity]):
    """Représentation détaillée, profil métier inclus lorsqu'il existe.

    Les trois clés de profil sont **toujours présentes** : celle qui
    correspond au type porte l'objet, les deux autres valent `null`. Un
    contrat de clés stable évite au client de tester l'existence d'une clé en
    plus de sa valeur, et rend la réponse lisible quel que soit le type.
    """

    divinity_profile = DivinityProfileSerializer(read_only=True)
    hero_profile = HeroProfileSerializer(read_only=True)
    creature_profile = CreatureProfileSerializer(read_only=True)

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
            "hero_profile",
            "creature_profile",
        ]
