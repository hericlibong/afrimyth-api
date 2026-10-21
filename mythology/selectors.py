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

from mythology.models import Entity, EntityRelation, EntityStatus

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
    """
    return Entity.objects.filter(PUBLIC_FILTER)


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
