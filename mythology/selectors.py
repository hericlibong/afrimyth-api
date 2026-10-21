"""Sélections de lecture du domaine mythologique.

Un seul endroit définit ce qu'« être publiquement visible » signifie, afin que
la liste, le détail, les références imbriquées et les futures vues partagent
la même règle. La roadmap de phase 3 demande explicitement cette
centralisation, pour que la phase 4 puisse ajouter une sélection privée sans
réécrire les serializers de lecture.

Ce module ne contient ni moteur de permissions ni repository générique : des
fonctions nommées, qui retournent des `QuerySet`.
"""

from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet

from mythology.models import CulturalArea, Entity, EntityRelation, EntityStatus

#: Condition de visibilité publique, exprimée une seule fois. Elle porte sur
#: deux champs indépendants : l'état éditorial et la suppression logique.
#: Une fiche supprimée reste `published` — c'est voulu, décision 7 de
#: l'ADR 0002 — donc les deux conditions sont nécessaires.
PUBLIC_FILTER = Q(status=EntityStatus.PUBLISHED, deleted_at__isnull=True)


def public_entities() -> QuerySet[Entity]:
    """Fiches visibles publiquement : publiées et non supprimées.

    Part de `Entity.objects`, le manager complet, et applique la règle
    éditoriale ici plutôt que dans un manager : `Entity.active` garde sa
    portée — la seule suppression logique — et l'administration conserve son
    queryset complet.

    La règle est la même pour tous les appelants, anonymes comme connectés,
    superutilisateur compris : ces routes sont publiques, pas des routes
    privées de gestion.

    **Ordre déterministe** : `name` puis `id`, ce dernier départageant deux
    figures homonymes. Sans lui, deux fiches de même nom pourraient changer de
    page d'une requête à l'autre, et la pagination deviendrait instable.
    L'ordre est posé ici plutôt que dans `Meta.ordering`, afin de ne pas
    modifier l'ordre par défaut du modèle ni générer de migration.
    """
    return Entity.objects.filter(PUBLIC_FILTER).order_by("name", "id")


def descendant_area_ids(slug: str) -> set[int]:
    """Identifiants d'une aire culturelle et de tous ses descendants.

    La hiérarchie est lue dans `parent`, telle qu'elle est **réellement
    enregistrée** : aucun nom de région n'est codé en dur, et la traversée
    fonctionne sur autant de niveaux que la base en contient.

    La descente est itérative, niveau par niveau — une requête par niveau —
    et chaque identifiant déjà vu est exclu des suivants. Un cycle
    accidentel dans `parent` ne provoque donc pas de boucle infinie, sans
    qu'il soit nécessaire de modifier le modèle pour l'interdire.

    Retourne un ensemble vide si le slug ne correspond à aucune aire : c'est
    ce qui fait qu'un slug inconnu donne une liste vide plutôt qu'une erreur.
    """
    root = CulturalArea.objects.filter(slug=slug).values_list("pk", flat=True).first()
    if root is None:
        return set()

    seen = {root}
    frontier = [root]
    while frontier:
        children = list(
            CulturalArea.objects.filter(parent_id__in=frontier)
            .exclude(pk__in=seen)
            .values_list("pk", flat=True)
        )
        if not children:
            break
        seen.update(children)
        frontier = children
    return seen


def filter_public_entities(
    queryset: QuerySet[Entity],
    *,
    entity_type: str | None = None,
    country: str | None = None,
    cultural_area: str | None = None,
) -> QuerySet[Entity]:
    """Applique les filtres de la collection publique.

    Les trois paramètres se combinent par **ET**. À l'intérieur d'un filtre,
    les rattachements principal et secondaire se combinent par **OU** : une
    fiche correspond si l'un ou l'autre convient.

    Un paramètre absent ou vide ne filtre rien. La validation des valeurs
    — type inconnu, code pays mal formé — relève de l'appelant : cette
    fonction suppose des valeurs déjà normalisées.

    Le `distinct()` final est nécessaire : joindre une relation multiple
    multiplie les lignes quand plusieurs rattachements correspondent, ce qui
    produirait des doublons dans `results` **et** gonflerait `count`.
    """
    joined_many_to_many = False

    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)

    if country:
        queryset = queryset.filter(
            Q(primary_country__iso_code=country)
            | Q(secondary_countries__iso_code=country)
        )
        joined_many_to_many = True

    if cultural_area:
        area_ids = descendant_area_ids(cultural_area)
        if not area_ids:
            # Slug inconnu : aucune fiche, sans erreur ni divulgation.
            return queryset.none()
        queryset = queryset.filter(
            Q(primary_cultural_area_id__in=area_ids)
            | Q(secondary_cultural_areas__id__in=area_ids)
        )
        joined_many_to_many = True

    if joined_many_to_many:
        queryset = queryset.distinct()
    return queryset


def public_relations() -> QuerySet[EntityRelation]:
    """Relations sortantes exposables dans une fiche publique.

    Deux cas sont conservés :

    - les liens **non résolus**, qui ne citent qu'un nom (`to_entity` nul) ;
    - les liens dont la cible résolue est elle-même publique.

    Un lien vers une cible résolue non publique est **entièrement omis** :
    ni son identifiant, ni son type, ni ses notes ne sont exposés, et son nom
    n'est pas recopié dans `to_name` — ce qui reviendrait à republier la cible
    masquée sous une autre forme.
    """
    return EntityRelation.objects.select_related("to_entity").filter(
        Q(to_entity__isnull=True)
        | Q(
            to_entity__status=EntityStatus.PUBLISHED,
            to_entity__deleted_at__isnull=True,
        )
    )


def public_entity_detail() -> QuerySet[Entity]:
    """Queryset du détail public : visibilité, jointures et préchargements.

    Les relations sortantes sont préchargées **déjà filtrées** par
    `public_relations()`, de sorte que la réponse ne puisse pas être
    construite depuis une collection non filtrée.

    `variant_of` est joint sans condition : la jointure ne décide pas de la
    visibilité, c'est le serializer qui masque une référence non publique. Le
    joindre ici permet à cette garde de s'exécuter sans requête
    supplémentaire.
    """
    return (
        public_entities()
        .select_related(
            "divinity_profile",
            "hero_profile",
            "creature_profile",
            "primary_country",
            "primary_ethnicity",
            "primary_cultural_area",
            "variant_of",
        )
        .prefetch_related(
            "secondary_countries",
            "secondary_ethnicities",
            "secondary_cultural_areas",
            "domains",
            Prefetch("relations_from", queryset=public_relations()),
            "sources",
        )
    )


def is_publicly_visible(entity: Entity | None) -> bool:
    """Indique si une instance déjà chargée est publiquement visible.

    Même règle que `PUBLIC_FILTER`, évaluée en Python. Sert de garde au
    serializer pour les références déjà jointes — `variant_of`, cible d'une
    relation — sans déclencher de requête supplémentaire.
    """
    if entity is None:
        return False
    return entity.status == EntityStatus.PUBLISHED and entity.deleted_at is None
