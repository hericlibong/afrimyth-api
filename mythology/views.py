"""Public read views and the private editorial views, driven by selectors."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cached_property
from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import User
from accounts.roles import business_roles
from mythology.models import Entity, EntityRelation, EntityType, Source
from mythology.pagination import EntityPagination
from mythology.permissions import NOT_EDITABLE_MESSAGE, CanEditEntity, HasBusinessRole
from mythology.schema import (
    CHILD_INVALID_RESPONSE,
    CHILD_NOT_FOUND_RESPONSE,
    DETAIL_DESCRIPTION,
    DETAIL_EXAMPLE,
    ENTITY_NOT_FOUND_RESPONSE,
    INVALID_PARAMETER_RESPONSE,
    LIST_DESCRIPTION,
    LIST_EXAMPLE,
    LIST_PARAMETERS,
    PAGE_NOT_FOUND_RESPONSE,
    PRIVATE_CREATE_DESCRIPTION,
    PRIVATE_CREATE_INVALID_RESPONSE,
    PRIVATE_CREATE_REQUEST_EXAMPLE,
    PRIVATE_CREATE_RESPONSE_EXAMPLE,
    PRIVATE_DETAIL_DESCRIPTION,
    PRIVATE_DETAIL_EXAMPLE,
    PRIVATE_FORBIDDEN_RESPONSE,
    PRIVATE_LIST_DESCRIPTION,
    PRIVATE_LIST_EXAMPLE,
    PRIVATE_NOT_EDITABLE_RESPONSE,
    PRIVATE_NOT_FOUND_RESPONSE,
    PRIVATE_UNAUTHENTICATED_RESPONSE,
    PRIVATE_UPDATE_DESCRIPTION,
    PRIVATE_UPDATE_INVALID_RESPONSE,
    PRIVATE_UPDATE_REQUEST_EXAMPLE,
    RELATION_CREATE_DESCRIPTION,
    RELATION_DELETE_DESCRIPTION,
    RELATION_ID_PARAMETER,
    RELATION_REQUEST_EXAMPLE,
    RELATION_UPDATE_DESCRIPTION,
    SOURCE_CREATE_DESCRIPTION,
    SOURCE_DELETE_DESCRIPTION,
    SOURCE_ID_PARAMETER,
    SOURCE_REQUEST_EXAMPLE,
    SOURCE_UPDATE_DESCRIPTION,
)
from mythology.selectors import (
    filter_entities,
    is_privately_editable,
    private_entities,
    private_entity_detail,
    private_relations,
    public_entities,
    public_entity_detail,
)
from mythology.serializers import (
    EntityDetailSerializer,
    EntityListSerializer,
    EntityRelationSerializer,
    PrivateEntityCreateSerializer,
    PrivateEntityDetailSerializer,
    PrivateEntityListSerializer,
    PrivateEntityUpdateSerializer,
    RelationWriteSerializer,
    SourceSerializer,
    SourceWriteSerializer,
)

#: Un code ISO 3166-1 alpha-2 : exactement deux lettres. Un format invalide
#: est une erreur d'appel — 400 — tandis qu'un code bien formé mais inconnu
#: donne simplement une liste vide.
ISO_CODE_PATTERN = re.compile(r"^[A-Za-z]{2}$")

#: Les quatre actions d'écriture d'enfants : elles n'ont besoin que de la
#: sélection privée du parent, sans préchargement du détail ni filtres de
#: collection.
CHILD_ACTIONS = frozenset(
    {"create_source", "source_detail", "create_relation", "relation_detail"}
)


class EntityNavigationViewSet(viewsets.ReadOnlyModelViewSet[Entity]):
    """Share list navigation without selecting a visibility policy.

    This unrouted base shares pagination, search and filter validation.
    Concrete views supply their querysets, serializers and OpenAPI annotations;
    keeping annotations off the base prevents public/private schema leakage.
    """

    lookup_field = "slug"
    pagination_class = EntityPagination
    filter_backends = [SearchFilter]
    #: Recherche limitée aux champs métier de la fiche elle-même. Ni les
    #: notes internes, ni les sources, ni les fiches liées n'y entrent : une
    #: recherche ne doit pas devenir un chemin d'accès indirect à des données
    #: qui ne sont pas exposées.
    search_fields = ["name", "category", "cultural_role", "story_description"]

    def filter_queryset(self, queryset: QuerySet[Entity, Any]) -> QuerySet[Entity, Any]:
        """N'applique les filtres de collection qu'à la liste.

        Sans cette garde, DRF appliquerait aussi `SearchFilter` dans
        `get_object()` : `GET /api/entities/shango/?search=introuvable`
        renverrait alors 404 pour une fiche parfaitement visible. Les
        paramètres de collection ne doivent jamais changer la disponibilité du
        détail, qui ne dépend que de la politique appliquée au slug demandé.
        """
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

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


@extend_schema_view(
    # Les paramètres sont déclarés **ici** et non globalement : ils ne doivent
    # apparaître que sur la liste. `parameters=[]` sur le détail empêche
    # l'héritage éventuel et garde sa signature limitée au slug.
    list=extend_schema(
        operation_id="entities_list",
        summary="List public entities",
        description=LIST_DESCRIPTION,
        parameters=LIST_PARAMETERS,
        responses={
            200: EntityListSerializer(many=True),
            400: INVALID_PARAMETER_RESPONSE,
            404: PAGE_NOT_FOUND_RESPONSE,
        },
        examples=[LIST_EXAMPLE],
        auth=[],
    ),
    retrieve=extend_schema(
        operation_id="entities_retrieve",
        summary="Retrieve one public entity",
        description=DETAIL_DESCRIPTION,
        parameters=[],
        responses={
            200: EntityDetailSerializer,
            404: ENTITY_NOT_FOUND_RESPONSE,
        },
        examples=[DETAIL_EXAMPLE],
        auth=[],
    ),
)
class EntityViewSet(EntityNavigationViewSet):
    """Collection et détail **publics** des entités, identifiées par leur slug.

    Ne sont visibles que les fiches `published` et non supprimées
    logiquement. La règle est la même pour tous les appelants — anonyme,
    connecté, relecteur, superutilisateur — parce que ces routes sont
    publiques et non des routes privées de gestion : détenir un jeton de
    relecteur ne change rien à ce qu'elles renvoient. `AllowAny` surcharge le
    défaut `IsAuthenticated` du projet.

    Une fiche non publique et un slug inexistant renvoient le même **404**,
    sans message distinguant l'un de l'autre : la réponse ne doit pas révéler
    l'existence ni l'état éditorial d'une fiche masquée.

    **Navigation.** Héritée d'`EntityNavigationViewSet` : la collection est
    paginée et accepte `search`, `entity_type`, `country` et `cultural_area`.
    Ces paramètres ne s'appliquent qu'à la liste.
    """

    permission_classes = [AllowAny]

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
        return filter_entities(
            public_entities(),
            entity_type=self._validated_entity_type(),
            country=self._validated_country(),
            cultural_area=self._query_param("cultural_area"),
        )

    def get_serializer_class(self) -> type[BaseSerializer[Entity]]:
        if self.action == "retrieve":
            return EntityDetailSerializer
        return EntityListSerializer


@extend_schema_view(
    list=extend_schema(
        operation_id="managed_entities_list",
        tags=["management"],
        summary="List entities readable for editorial work",
        description=PRIVATE_LIST_DESCRIPTION,
        parameters=LIST_PARAMETERS,
        responses={
            200: PrivateEntityListSerializer(many=True),
            400: INVALID_PARAMETER_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_FORBIDDEN_RESPONSE,
            404: PAGE_NOT_FOUND_RESPONSE,
        },
        examples=[PRIVATE_LIST_EXAMPLE],
    ),
    retrieve=extend_schema(
        operation_id="managed_entities_retrieve",
        tags=["management"],
        summary="Retrieve one entity readable for editorial work",
        description=PRIVATE_DETAIL_DESCRIPTION,
        parameters=[],
        responses={
            200: PrivateEntityDetailSerializer,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_FORBIDDEN_RESPONSE,
            404: PRIVATE_NOT_FOUND_RESPONSE,
        },
        examples=[PRIVATE_DETAIL_EXAMPLE],
    ),
    create=extend_schema(
        operation_id="managed_entities_create",
        tags=["management"],
        summary="Create a draft entity with its profile",
        description=PRIVATE_CREATE_DESCRIPTION,
        request=PrivateEntityCreateSerializer,
        responses={
            201: PrivateEntityDetailSerializer,
            400: PRIVATE_CREATE_INVALID_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_FORBIDDEN_RESPONSE,
        },
        examples=[PRIVATE_CREATE_REQUEST_EXAMPLE, PRIVATE_CREATE_RESPONSE_EXAMPLE],
    ),
    partial_update=extend_schema(
        operation_id="managed_entities_partial_update",
        tags=["management"],
        summary="Update one entity, its profile and its attachments",
        description=PRIVATE_UPDATE_DESCRIPTION,
        parameters=[],
        request=PrivateEntityUpdateSerializer,
        responses={
            200: PrivateEntityDetailSerializer,
            400: PRIVATE_UPDATE_INVALID_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: PRIVATE_NOT_FOUND_RESPONSE,
        },
        examples=[PRIVATE_UPDATE_REQUEST_EXAMPLE],
    ),
)
class PrivateEntityViewSet(mixins.CreateModelMixin, EntityNavigationViewSet):
    """Read editorial records by role and ownership, create one, patch one.

    JWT and a business role grant route access; queryset filtering protects
    individual records and list counts. Object permissions alone do not
    protect a list, and a readable record is not necessarily a modifiable one.

    Write actions are added one by one to a read-only base rather than by
    switching to a full `ModelViewSet`: `PUT` and `DELETE` are never routed,
    so they stay refused with `405`.
    """

    # Comme sur `me`, seule l'authentification JWT est acceptée : une session
    # d'administration ouverte dans le navigateur ne doit pas suffire à ouvrir
    # ces routes. `IsAuthenticated` donne le 401 des appelants anonymes, avant
    # que `HasBusinessRole` produise le 403 des comptes sans rôle métier.
    # `CanEditEntity` n'intervient qu'au niveau objet, sur une écriture.
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, HasBusinessRole, CanEditEntity]

    @cached_property
    def caller_roles(self) -> frozenset[str]:
        """Business roles of this caller, read from the database once.

        `cached_property` is what keeps the group membership to a single query
        per request: the permission check reads it first, then the queryset
        and the serializer context reuse the same value. The view instance
        lives for one request only, so nothing is cached across requests and a
        group change applies immediately, with the same token.
        """
        return business_roles(self.request.user)

    @property
    def caller_id(self) -> int | None:
        """Identifier of the calling account, or `None` without one.

        `None` never occurs behind the permission classes above; it keeps the
        selection restrictive if this view is instantiated outside a request.
        """
        user = self.request.user
        return user.pk if isinstance(user, User) else None

    def get_queryset(self) -> QuerySet[Entity]:
        """Apply the private policy before list filters or detail preloading."""
        if self.action in {"retrieve", "partial_update"}:
            return private_entity_detail(
                roles=self.caller_roles, caller_id=self.caller_id
            )
        private = private_entities(roles=self.caller_roles, caller_id=self.caller_id)
        if self.action in CHILD_ACTIONS:
            return private
        return filter_entities(
            private,
            entity_type=self._validated_entity_type(),
            country=self._validated_country(),
            cultural_area=self._query_param("cultural_area"),
        )

    def get_serializer_class(self) -> type[BaseSerializer[Entity]]:
        if self.action == "create":
            return PrivateEntityCreateSerializer
        if self.action == "partial_update":
            return PrivateEntityUpdateSerializer
        if self.action == "retrieve":
            return PrivateEntityDetailSerializer
        return PrivateEntityListSerializer

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Apply the patch and answer with the private detail representation.

        Written out rather than taken from `UpdateModelMixin`, which would also
        route `PUT` as a full replacement.
        """
        entity = self.get_object()
        serializer = self.get_serializer(entity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def get_serializer_context(self) -> dict[str, Any]:
        """Pass server-derived roles and identity to nested reference guards."""
        context = super().get_serializer_context()
        context["caller_roles"] = self.caller_roles
        context["caller_id"] = self.caller_id
        return context

    # --- Écritures des enfants d'une fiche ------------------------------
    #
    # Quatre actions imbriquées plutôt qu'une bibliothèque de routeurs
    # imbriqués : le parent est celui du détail, et ses droits sont déjà
    # évalués par `get_object()`.

    @contextmanager
    def locked_record(self) -> Iterator[Entity]:
        """Lock the record named by the URL and re-check the right to edit it.

        The right is evaluated twice on purpose: once by the object
        permission, then again on the locked row, so a concurrent status
        change cannot be overwritten by a child write.
        """
        entity = self.get_object()
        with transaction.atomic():
            locked = Entity.objects.select_for_update().get(pk=entity.pk)
            if not is_privately_editable(
                locked, roles=self.caller_roles, caller_id=self.caller_id
            ):
                raise PermissionDenied(NOT_EDITABLE_MESSAGE)
            yield locked

    def saved_child(
        self,
        serializer_class: type[BaseSerializer[Any]],
        instance: Source | EntityRelation | None = None,
        **attached: Entity,
    ) -> Any:
        """Validate the request body and save one child row.

        The parent is passed through `save()` rather than read from the body:
        it comes from the URL, and no row is ever moved to another record.
        """
        serializer = serializer_class(
            instance,
            data=self.request.data,
            partial=instance is not None,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save(**attached)

    def readable_relations(self, entity: Entity) -> QuerySet[EntityRelation]:
        """Outgoing relations of this record whose target this caller may read.

        Keeping the read filter here is what makes a relation towards a hidden
        target unreachable even when its identifier is guessed.
        """
        return private_relations(
            roles=self.caller_roles, caller_id=self.caller_id
        ).filter(from_entity=entity)

    @extend_schema(
        operation_id="managed_entities_sources_create",
        tags=["management"],
        summary="Add one documentary source to an entity",
        description=SOURCE_CREATE_DESCRIPTION,
        request=SourceWriteSerializer,
        responses={
            201: SourceSerializer,
            400: CHILD_INVALID_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: PRIVATE_NOT_FOUND_RESPONSE,
        },
        examples=[SOURCE_REQUEST_EXAMPLE],
    )
    @action(detail=True, methods=["post"], url_path="sources", url_name="sources")
    def create_source(self, request: Request, **kwargs: Any) -> Response:
        """Create one documentary source on this record."""
        with self.locked_record() as entity:
            source = self.saved_child(SourceWriteSerializer, entity=entity)
        return Response(SourceSerializer(source).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        methods=["PATCH"],
        operation_id="managed_entities_sources_partial_update",
        tags=["management"],
        summary="Update one documentary source of an entity",
        description=SOURCE_UPDATE_DESCRIPTION,
        parameters=[SOURCE_ID_PARAMETER],
        request=SourceWriteSerializer,
        responses={
            200: SourceSerializer,
            400: CHILD_INVALID_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: CHILD_NOT_FOUND_RESPONSE,
        },
        examples=[SOURCE_REQUEST_EXAMPLE],
    )
    @extend_schema(
        methods=["DELETE"],
        operation_id="managed_entities_sources_destroy",
        tags=["management"],
        summary="Delete one documentary source of an entity",
        description=SOURCE_DELETE_DESCRIPTION,
        parameters=[SOURCE_ID_PARAMETER],
        request=None,
        responses={
            204: None,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: CHILD_NOT_FOUND_RESPONSE,
        },
    )
    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"sources/(?P<source_id>[0-9]+)",
        url_name="source-detail",
    )
    def source_detail(self, request: Request, **kwargs: Any) -> Response:
        """Update or delete one documentary source of this record."""
        with self.locked_record() as entity:
            source = get_object_or_404(entity.sources.all(), pk=kwargs["source_id"])
            if request.method == "DELETE":
                source.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            self.saved_child(SourceWriteSerializer, instance=source)
        return Response(SourceSerializer(source).data)

    @extend_schema(
        operation_id="managed_entities_relations_create",
        tags=["management"],
        summary="Add one outgoing relation to an entity",
        description=RELATION_CREATE_DESCRIPTION,
        request=RelationWriteSerializer,
        responses={
            201: EntityRelationSerializer,
            400: CHILD_INVALID_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: PRIVATE_NOT_FOUND_RESPONSE,
        },
        examples=[RELATION_REQUEST_EXAMPLE],
    )
    @action(detail=True, methods=["post"], url_path="relations", url_name="relations")
    def create_relation(self, request: Request, **kwargs: Any) -> Response:
        """Create one outgoing relation from this record."""
        with self.locked_record() as entity:
            relation = self.saved_child(RelationWriteSerializer, from_entity=entity)
        return Response(
            EntityRelationSerializer(relation).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        methods=["PATCH"],
        operation_id="managed_entities_relations_partial_update",
        tags=["management"],
        summary="Update one outgoing relation of an entity",
        description=RELATION_UPDATE_DESCRIPTION,
        parameters=[RELATION_ID_PARAMETER],
        request=RelationWriteSerializer,
        responses={
            200: EntityRelationSerializer,
            400: CHILD_INVALID_RESPONSE,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: CHILD_NOT_FOUND_RESPONSE,
        },
        examples=[RELATION_REQUEST_EXAMPLE],
    )
    @extend_schema(
        methods=["DELETE"],
        operation_id="managed_entities_relations_destroy",
        tags=["management"],
        summary="Delete one outgoing relation of an entity",
        description=RELATION_DELETE_DESCRIPTION,
        parameters=[RELATION_ID_PARAMETER],
        request=None,
        responses={
            204: None,
            401: PRIVATE_UNAUTHENTICATED_RESPONSE,
            403: PRIVATE_NOT_EDITABLE_RESPONSE,
            404: CHILD_NOT_FOUND_RESPONSE,
        },
    )
    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"relations/(?P<relation_id>[0-9]+)",
        url_name="relation-detail",
    )
    def relation_detail(self, request: Request, **kwargs: Any) -> Response:
        """Update or delete one outgoing relation of this record."""
        with self.locked_record() as entity:
            relation = get_object_or_404(
                self.readable_relations(entity), pk=kwargs["relation_id"]
            )
            if request.method == "DELETE":
                relation.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            self.saved_child(RelationWriteSerializer, instance=relation)
        return Response(EntityRelationSerializer(relation).data)
