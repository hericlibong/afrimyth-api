"""Sérialiseurs de lecture du domaine mythologique.

Deux représentations distinctes de `Entity` : une forme compacte pour la
collection et une forme détaillée qui imbrique le profil métier. Cette
séparation est celle attendue en phase 3 ; les serializers d'écriture
arriveront avec le CRUD de la phase 4.
"""

from rest_framework import serializers

from mythology.models import (
    Country,
    CreatureProfile,
    CulturalArea,
    DivinityProfile,
    Domain,
    Entity,
    EntityRelation,
    Ethnicity,
    HeroProfile,
    Source,
)


class SourceSerializer(serializers.ModelSerializer[Source]):
    """Référence documentaire, imbriquée dans le détail d'une entité.

    `entity` n'est pas réexposé : la source est déjà lue depuis sa fiche.
    """

    class Meta:
        model = Source
        fields = ["id", "label", "kind", "url", "accessed_at", "notes"]


class EntityReferenceSerializer(serializers.ModelSerializer[Entity]):
    """Référence synthétique vers une entité.

    Volontairement limitée à quatre champs : imbriquer le détail d'une cible
    ferait repartir la sérialisation dans ses propres relations, donc une
    récursion. Le client obtient un `slug` suffisant pour aller chercher la
    fiche complète s'il en a besoin.
    """

    class Meta:
        model = Entity
        fields = ["id", "slug", "name", "entity_type"]


class EntityRelationSerializer(serializers.ModelSerializer[EntityRelation]):
    """Relation sortante d'une entité.

    `to_entity` porte la cible résolue, `to_name` le nom brut d'une figure
    sans fiche. Exactement l'un des deux est renseigné.
    """

    to_entity = EntityReferenceSerializer(read_only=True)

    class Meta:
        model = EntityRelation
        fields = ["id", "kind", "to_entity", "to_name", "notes"]


class CountrySerializer(serializers.ModelSerializer[Country]):
    """Identité d'un pays : socle commun plus son code ISO."""

    class Meta:
        model = Country
        fields = ["id", "slug", "name", "iso_code"]


class CulturalAreaSerializer(serializers.ModelSerializer[CulturalArea]):
    """Identité d'une aire culturelle : socle commun plus sa nature.

    `parent` et `children` ne sont pas imbriqués : les exposer ici
    déclencherait une cascade de sérialisation et des requêtes sans rapport
    avec la lecture d'une entité.
    """

    class Meta:
        model = CulturalArea
        fields = ["id", "slug", "name", "kind"]


class EthnicitySerializer(serializers.ModelSerializer[Ethnicity]):
    """Identité d'une ethnie, réduite au socle commun.

    `primary_cultural_area` est volontairement absent : l'aire de l'entité
    elle-même est déjà exposée, et imbriquer celle de son ethnie ajouterait un
    niveau de graphe sans besoin client établi.
    """

    class Meta:
        model = Ethnicity
        fields = ["id", "slug", "name"]


class DomainSerializer(serializers.ModelSerializer[Domain]):
    """Identité d'un domaine, réduite au socle commun."""

    class Meta:
        model = Domain
        fields = ["id", "slug", "name"]


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

    primary_country = CountrySerializer(read_only=True)
    secondary_countries = CountrySerializer(many=True, read_only=True)
    primary_ethnicity = EthnicitySerializer(read_only=True)
    secondary_ethnicities = EthnicitySerializer(many=True, read_only=True)
    primary_cultural_area = CulturalAreaSerializer(read_only=True)
    secondary_cultural_areas = CulturalAreaSerializer(many=True, read_only=True)
    domains = DomainSerializer(many=True, read_only=True)

    variant_of = EntityReferenceSerializer(read_only=True)
    # Seules les relations sortantes sont exposées. Les relations entrantes
    # — `relations_to` — et les variantes inverses viendront si un besoin
    # client le justifie ; les ajouter maintenant doublerait la charge utile
    # sans usage établi.
    relations = EntityRelationSerializer(
        many=True,
        read_only=True,
        source="relations_from",
    )
    sources = SourceSerializer(many=True, read_only=True)

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
            "primary_country",
            "secondary_countries",
            "primary_ethnicity",
            "secondary_ethnicities",
            "primary_cultural_area",
            "secondary_cultural_areas",
            "domains",
            "variant_of",
            "relations",
            "sources",
            "created_at",
            "updated_at",
            "divinity_profile",
            "hero_profile",
            "creature_profile",
        ]
