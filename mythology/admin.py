from django.contrib import admin

from mythology.models import DivinityProfile, Entity


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
