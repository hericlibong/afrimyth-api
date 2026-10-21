"""Vues de lecture publique du domaine mythologique.

Lecture seule : aucune écriture HTTP n'est exposée. Les comptes, rôles,
permissions au niveau objet, le CRUD et les transitions de modération
validées dans l'ADR 0002 arrivent en phase 4.

La visibilité publique est définie une seule fois, dans
`mythology.selectors` : ces vues s'y branchent sans redéfinir la règle.
"""

import re
from typing import Any

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.serializers import BaseSerializer

from mythology.models import Entity, EntityType
from mythology.pagination import EntityPagination
from mythology.selectors import (
    filter_public_entities,
    public_entities,
    public_entity_detail,
)
from mythology.serializers import EntityDetailSerializer, EntityListSerializer

#: Un code ISO 3166-1 alpha-2 : exactement deux lettres. Un format invalide
#: est une erreur d'appel — 400 — tandis qu'un code bien formé mais inconnu
#: donne simplement une liste vide.
ISO_CODE_PATTERN = re.compile(r"^[A-Za-z]{2}$")


class EntityViewSet(viewsets.ReadOnlyModelViewSet[Entity]):
    """Collection et détail **publics** des entités, identifiées par leur slug.

    Ne sont visibles que les fiches `published` et non supprimées
    logiquement. La règle est la même pour tous les appelants — anonyme,
    connecté, superutilisateur — parce que ces routes sont publiques et non
    des routes privées de gestion. `AllowAny` surcharge le défaut
    `IsAuthenticated` du projet.

    Une fiche non publique et un slug inexistant renvoient le même **404**,
    sans message distinguant l'un de l'autre : la réponse ne doit pas révéler
    l'existence ni l'état éditorial d'une fiche masquée.

    **Navigation.** La collection est paginée et accepte `search`,
    `entity_type`, `country` et `cultural_area`. Ces paramètres ne
    s'appliquent qu'à la liste : ils ne changent jamais la disponibilité du
    détail, qui ne dépend que de la visibilité publique du slug demandé.
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"
    pagination_class = EntityPagination
    filter_backends = [SearchFilter]
    #: Recherche limitée aux champs publics de la fiche elle-même. Ni les
    #: notes internes, ni les sources, ni les fiches liées n'y entrent : une
    #: recherche ne doit pas devenir un chemin d'accès indirect à des données
    #: qui ne sont pas exposées.
    search_fields = ["name", "category", "cultural_role", "story_description"]

    def get_queryset(self) -> QuerySet[Entity]:
        """Sélection publique, filtrée pour la liste, enrichie pour le détail.

        Les deux actions partent de la même règle de visibilité, définie dans
        `mythology.selectors`. Le détail y ajoute les jointures et
        préchargements, dont les relations sortantes **déjà filtrées**, et
        ignore les paramètres de collection. La liste applique les filtres et
        reste nue, puisqu'elle n'expose ni profil, ni référentiel, ni
        relation, ni source.
        """
        if self.action == "retrieve":
            return public_entity_detail()
        return filter_public_entities(
            public_entities(),
            entity_type=self._validated_entity_type(),
            country=self._validated_country(),
            cultural_area=self._query_param("cultural_area"),
        )

    def filter_queryset(self, queryset: QuerySet[Entity, Any]) -> QuerySet[Entity, Any]:
        """N'applique les filtres de collection qu'à la liste.

        Sans cette garde, DRF appliquerait aussi `SearchFilter` dans
        `get_object()` : `GET /api/entities/shango/?search=introuvable`
        renverrait alors 404 pour une fiche parfaitement publique. Les
        paramètres de collection ne doivent jamais changer la disponibilité
        du détail, qui ne dépend que de la visibilité publique du slug.
        """
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def get_serializer_class(self) -> type[BaseSerializer[Entity]]:
        if self.action == "retrieve":
            return EntityDetailSerializer
        return EntityListSerializer

    # --- Validation des paramètres de collection ------------------------

    def _query_param(self, name: str) -> str | None:
        """Retourne le paramètre nettoyé, ou `None` s'il est vide.

        Un paramètre présent mais vide — `?entity_type=` — ne filtre pas,
        plutôt que de ne rien retourner.
        """
        raw = self.request.query_params.get(name)
        if raw is None:
            return None
        cleaned = raw.strip()
        return cleaned or None

    def _validated_entity_type(self) -> str | None:
        """Valide `entity_type` contre les trois valeurs techniques connues."""
        value = self._query_param("entity_type")
        if value is None:
            return None
        if value not in EntityType.values:
            expected = ", ".join(EntityType.values)
            raise ValidationError(
                {
                    "entity_type": [
                        f"Unknown entity type '{value}'. Expected one of: "
                        f"{expected}."
                    ]
                }
            )
        return value

    def _validated_country(self) -> str | None:
        """Valide le format du code pays et le normalise en majuscules.

        Seul le **format** est vérifié : un code bien formé mais absent de la
        base donne une liste vide, sans révéler quels pays sont enregistrés.
        """
        value = self._query_param("country")
        if value is None:
            return None
        if not ISO_CODE_PATTERN.match(value):
            raise ValidationError(
                {
                    "country": [
                        f"Invalid country code '{value}'. Expected a two-letter "
                        "ISO 3166-1 alpha-2 code, for example 'NG'."
                    ]
                }
            )
        return value.upper()
