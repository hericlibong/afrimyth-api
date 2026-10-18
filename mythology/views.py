"""Vues de lecture du domaine mythologique.

Lecture seule **provisoire** : cet incrément rend la première tranche métier
observable. Les comptes, rôles, permissions au niveau objet, le CRUD et les
transitions de modération validées dans l'ADR 0002 arrivent en phase 4, et le
filtrage sur le statut éditorial avec eux.
"""

from django.db.models import Prefetch, QuerySet
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.serializers import BaseSerializer

from mythology.models import Entity, EntityRelation
from mythology.serializers import EntityDetailSerializer, EntityListSerializer


class EntityViewSet(viewsets.ReadOnlyModelViewSet[Entity]):
    """Collection et détail des entités, identifiées par leur slug.

    Aucun statut éditorial n'existe encore : la totalité des entités est
    visible. `AllowAny` surcharge ici le défaut `IsAuthenticated` du projet.
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self) -> QuerySet[Entity]:
        """Ne joint profils, référentiels et liens que pour le détail.

        Le détail charge en une requête les trois profils `OneToOne`, les
        trois ancrages principaux et la figure de référence, puis une requête
        par collection préchargée. Les relations sortantes sont préchargées
        avec leur cible jointe : une seule requête supplémentaire, quel que
        soit le nombre de liens.

        La liste n'expose ni profils, ni référentiels, ni relations : son
        queryset reste nu, ce qui évite de payer ces jointures pour une
        réponse compacte.
        """
        queryset = Entity.objects.all()
        if self.action == "retrieve":
            return queryset.select_related(
                "divinity_profile",
                "hero_profile",
                "creature_profile",
                "primary_country",
                "primary_ethnicity",
                "primary_cultural_area",
                "variant_of",
            ).prefetch_related(
                "secondary_countries",
                "secondary_ethnicities",
                "secondary_cultural_areas",
                "domains",
                Prefetch(
                    "relations_from",
                    queryset=EntityRelation.objects.select_related("to_entity"),
                ),
            )
        return queryset

    def get_serializer_class(self) -> type[BaseSerializer[Entity]]:
        if self.action == "retrieve":
            return EntityDetailSerializer
        return EntityListSerializer
