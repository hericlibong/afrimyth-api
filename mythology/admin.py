from django.contrib import admin

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


@admin.register(CulturalArea)
class CulturalAreaAdmin(admin.ModelAdmin[CulturalArea]):
    list_display = ["name", "kind", "parent"]
    list_filter = ["kind"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["parent"]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin[Country]):
    list_display = ["name", "iso_code"]
    search_fields = ["name", "slug", "iso_code"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Ethnicity)
class EthnicityAdmin(admin.ModelAdmin[Ethnicity]):
    list_display = ["name", "primary_cultural_area"]
    list_filter = ["primary_cultural_area__kind"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["primary_cultural_area"]


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin[Domain]):
    list_display = ["name"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin[Entity]):
    list_display = [
        "name",
        "entity_type",
        "category",
        "gender",
        "primary_country",
        "primary_ethnicity",
        "updated_at",
    ]
    list_filter = ["entity_type", "gender", "primary_cultural_area__kind"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["id", "created_at", "updated_at"]
    # Les rattachements principaux passent par une recherche plutôt qu'une
    # liste déroulante, et les rattachements multiples par le widget
    # horizontal : le formulaire reste celui de Django, sans personnalisation.
    autocomplete_fields = [
        "primary_country",
        "primary_ethnicity",
        "primary_cultural_area",
        "variant_of",
    ]
    filter_horizontal = [
        "secondary_countries",
        "secondary_ethnicities",
        "secondary_cultural_areas",
        "domains",
    ]


@admin.register(EntityRelation)
class EntityRelationAdmin(admin.ModelAdmin[EntityRelation]):
    list_display = ["from_entity", "kind", "to_entity", "to_name"]
    list_filter = ["kind"]
    search_fields = ["from_entity__name", "to_entity__name", "to_name"]
    autocomplete_fields = ["from_entity", "to_entity"]
    list_select_related = ["from_entity", "to_entity"]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin[Source]):
    list_display = ["label", "entity", "kind", "accessed_at"]
    list_filter = ["kind"]
    search_fields = ["label", "entity__name"]
    autocomplete_fields = ["entity"]
    list_select_related = ["entity"]


@admin.register(DivinityProfile)
class DivinityProfileAdmin(admin.ModelAdmin[DivinityProfile]):
    list_display = ["entity"]
    search_fields = ["entity__name"]
    autocomplete_fields = ["entity"]


@admin.register(HeroProfile)
class HeroProfileAdmin(admin.ModelAdmin[HeroProfile]):
    list_display = ["entity"]
    search_fields = ["entity__name"]
    autocomplete_fields = ["entity"]


@admin.register(CreatureProfile)
class CreatureProfileAdmin(admin.ModelAdmin[CreatureProfile]):
    list_display = ["entity", "threat_level"]
    list_filter = ["threat_level"]
    search_fields = ["entity__name"]
    autocomplete_fields = ["entity"]
