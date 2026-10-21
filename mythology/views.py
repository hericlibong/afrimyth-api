"""Vues de lecture publique du domaine mythologique.

Lecture seule : aucune écriture HTTP n'est exposée. Les comptes, rôles,
permissions au niveau objet, le CRUD et les transitions de modération
validées dans l'ADR 0002 arrivent en phase 4.

La visibilité publique est définie une seule fois, dans
`mythology.selectors` : ces vues s'y branchent sans redéfinir la règle.
"""

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.serializers import BaseSerializer

from mythology.models import Entity
from mythology.selectors import public_entities, public_entity_detail
from mythology.serializers import EntityDetailSerializer, EntityListSerializer


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
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self) -> QuerySet[Entity]:
        """Sélection publique, enrichie des jointures pour le détail.

        Les deux actions partent de la même règle de visibilité, définie dans
        `mythology.selectors`. Le détail y ajoute les jointures et
        préchargements, dont les relations sortantes **déjà filtrées** ; la
        liste reste nue, puisqu'elle n'expose ni profil, ni référentiel, ni
        relation, ni source.
        """
        if self.action == "retrieve":
            return public_entity_detail()
        return public_entities()

    def get_serializer_class(self) -> type[BaseSerializer[Entity]]:
        if self.action == "retrieve":
            return EntityDetailSerializer
        return EntityListSerializer
