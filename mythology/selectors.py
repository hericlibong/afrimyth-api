"""Public and role-based private read policies for mythology records."""

from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet

from accounts.roles import ADMINISTRATOR, CONTRIBUTOR, REVIEWER
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


def filter_entities(
    queryset: QuerySet[Entity],
    *,
    entity_type: str | None = None,
    country: str | None = None,
    cultural_area: str | None = None,
) -> QuerySet[Entity]:
    """Restrict an already-authorised queryset using normalised filters.

    Filters combine with AND; primary and secondary attachments use OR.
    Empty values do not filter. Validation belongs to the caller, and
    `distinct()` prevents M2M joins from duplicating results or counts.
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


#: Jointures du détail, partagées par les deux politiques. `variant_of` est
#: joint **sans condition** : la jointure ne décide pas de la visibilité,
#: c'est le serializer qui masque une référence interdite. Le joindre ici
#: permet à cette garde de s'exécuter sans requête supplémentaire.
#:
#: Les trois acteurs de la revue — `created_by`, `reviewed_by`, `deleted_by` —
#: sont absents volontairement : la représentation privée n'expose que leur
#: identifiant, que Django lit déjà dans la colonne `*_id` de la fiche. Les
#: joindre coûterait trois jointures pour aucune donnée supplémentaire.
DETAIL_SELECT_RELATED = (
    "divinity_profile",
    "hero_profile",
    "creature_profile",
    "primary_country",
    "primary_ethnicity",
    "primary_cultural_area",
    "variant_of",
)

#: Collections préchargées du détail, hors relations sortantes : celles-ci
#: dépendent de la politique et sont ajoutées par un `Prefetch` dédié.
DETAIL_PREFETCH_RELATED = (
    "secondary_countries",
    "secondary_ethnicities",
    "secondary_cultural_areas",
    "domains",
    "sources",
)


def public_entity_detail() -> QuerySet[Entity]:
    """Queryset du détail public : visibilité, jointures et préchargements.

    Les relations sortantes sont préchargées **déjà filtrées** par
    `public_relations()`, de sorte que la réponse ne puisse pas être
    construite depuis une collection non filtrée.
    """
    return (
        public_entities()
        .select_related(*DETAIL_SELECT_RELATED)
        .prefetch_related(
            *DETAIL_PREFETCH_RELATED,
            Prefetch("relations_from", queryset=public_relations()),
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


# --- Politique privée : rôle et propriété -------------------------------
#
# Traduction littérale de la matrice de l'ADR 0002, précisée par l'ADR 0004.
# Aucune nouvelle décision métier n'est prise ici.

#: Statuts qu'un contributeur lit sur ses **propres** fiches, en plus de
#: toutes les fiches publiées. Les trois valeurs sont énumérées plutôt que
#: déduites de « tout sauf publié » : un statut ajouté plus tard ne devrait pas
#: devenir lisible par simple effet de bord.
OWNED_PRIVATE_STATUSES = (
    EntityStatus.DRAFT,
    EntityStatus.SUBMITTED,
    EntityStatus.REJECTED,
)


def reads_every_record(roles: frozenset[str]) -> bool:
    """Return whether the roles allow reading every non-deleted record."""
    return bool(roles & {REVIEWER, ADMINISTRATOR})


def private_filter(
    *, roles: frozenset[str], caller_id: int | None, prefix: str = ""
) -> Q:
    """Select records readable by role and ownership, excluding deleted ones.

    Reviewers and administrators read all; contributors read published records
    and their own drafts, submissions and rejected records. Callers without
    a role read nothing. A missing caller ID never matches ownerless records.
    Use `prefix="to_entity__"` to apply this policy to a joined relation target.
    """

    def field(name: str) -> str:
        return f"{prefix}{name}"

    not_deleted = Q(**{field("deleted_at__isnull"): True})

    if reads_every_record(roles):
        return not_deleted
    if CONTRIBUTOR not in roles:
        return Q(**{field("pk__in"): []})

    published = Q(**{field("status"): EntityStatus.PUBLISHED})
    if caller_id is None:
        return not_deleted & published

    owned = Q(
        **{
            field("created_by_id"): caller_id,
            field("status__in"): OWNED_PRIVATE_STATUSES,
        }
    )
    return not_deleted & (published | owned)


def private_entities(
    *, roles: frozenset[str], caller_id: int | None
) -> QuerySet[Entity]:
    """Select privately readable records in stable name/id order."""
    return Entity.objects.filter(
        private_filter(roles=roles, caller_id=caller_id)
    ).order_by("name", "id")


def private_relations(
    *, roles: frozenset[str], caller_id: int | None
) -> QuerySet[EntityRelation]:
    """Keep unresolved links and links to targets readable by the caller.

    Omit forbidden resolved links entirely, without copying their target name.
    """
    return EntityRelation.objects.select_related("to_entity").filter(
        Q(to_entity__isnull=True)
        | private_filter(roles=roles, caller_id=caller_id, prefix="to_entity__")
    )


def private_entity_detail(
    *, roles: frozenset[str], caller_id: int | None
) -> QuerySet[Entity]:
    """Preload private detail fields and already-filtered outgoing relations."""
    return (
        private_entities(roles=roles, caller_id=caller_id)
        .select_related(*DETAIL_SELECT_RELATED)
        .prefetch_related(
            *DETAIL_PREFETCH_RELATED,
            Prefetch(
                "relations_from",
                queryset=private_relations(roles=roles, caller_id=caller_id),
            ),
        )
    )


def is_privately_readable(
    entity: Entity | None, *, roles: frozenset[str], caller_id: int | None
) -> bool:
    """Evaluate the private policy on a loaded target without querying.

    Used by serializer reference guards; missing roles never grant access.
    """
    if entity is None or entity.deleted_at is not None:
        return False
    if reads_every_record(roles):
        return True
    if CONTRIBUTOR not in roles:
        return False
    if entity.status == EntityStatus.PUBLISHED:
        return True
    return (
        caller_id is not None
        and entity.created_by_id == caller_id
        and entity.status in OWNED_PRIVATE_STATUSES
    )
