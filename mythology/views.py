"""Vues de lecture du domaine mythologique.

Lecture seule **provisoire** : cet incrément rend la première tranche métier
observable. Les comptes, rôles, permissions au niveau objet, le CRUD et les
transitions de modération validées dans l'ADR 0002 arrivent en phase 4, et le
filtrage sur le statut éditorial avec eux.
"""

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.serializers import BaseSerializer

from mythology.models import Entity
from mythology.serializers import EntityDetailSerializer, EntityListSerializer


class EntityViewSet(viewsets.ReadOnlyModelViewSet[Entity]):
    """Collection et détail des entités, identifiées par leur slug.

    Aucun statut éditorial n'existe encore : la totalité des entités est
    visible. `AllowAny` surcharge ici le défaut `IsAuthenticated` du projet.
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self) -> QuerySet[Entity]:
        """Ne joint les profils que pour le détail, seul à les exposer.

        Les trois relations `OneToOne` sont chargées dans la même requête :
        une entité n'en possède qu'une, mais le serializer de détail interroge
        les trois pour produire un contrat de clés stable.
        """
        queryset = Entity.objects.all()
        if self.action == "retrieve":
            return queryset.select_related(
                "divinity_profile",
                "hero_profile",
                "creature_profile",
            )
        return queryset

    def get_serializer_class(self) -> type[BaseSerializer[Entity]]:
        if self.action == "retrieve":
            return EntityDetailSerializer
        return EntityListSerializer
