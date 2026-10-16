from django.contrib import admin

from mythology.models import CreatureProfile, DivinityProfile, Entity, HeroProfile


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin[Entity]):
    list_display = ["name", "entity_type", "category", "gender", "updated_at"]
    list_filter = ["entity_type", "gender"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["id", "created_at", "updated_at"]


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
