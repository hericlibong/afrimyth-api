"""Modèles du domaine mythologique.

Contenu actuel : le tronc commun `Entity` — avec sa variante éventuelle
(`variant_of`) —, ses trois profils métier (`DivinityProfile`, `HeroProfile`,
`CreatureProfile`), les quatre référentiels validés (`CulturalArea`,
`Country`, `Ethnicity`, `Domain`) et les liens entre figures
(`EntityRelation`).

S'y ajoutent les références documentaires (`Source`) et les champs de
plateforme de `Entity` : propriété, état éditorial, revue et suppression
logique.

Ces champs de plateforme sont **posés, non pilotés** : les transitions de
statut, l'attribution automatique du propriétaire, les rôles, les permissions
et la restauration appartiennent à la phase 4. Les données de rendu visuel
sont hors V1, conformément à la section 8 de l'ADR 0002.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class EntityType(models.TextChoices):
    """Type d'une figure mythologique.

    Le type gouverne le profil métier attendu. Il reste distinct de
    `Entity.category`, qui est un sous-titre éditorial libre.
    """

    DIVINITY = "divinity", "Divinity"
    HERO = "hero", "Hero"
    CREATURE = "creature", "Creature"


class Gender(models.TextChoices):
    """Genre de la figure, limité aux valeurs observées dans le corpus."""

    MALE = "male", "Male"
    FEMALE = "female", "Female"
    NEUTRAL = "neutral", "Neutral"
    ANDROGYNOUS = "androgynous", "Androgynous"
    FLUID = "fluid", "Fluid"


class ThreatLevel(models.TextChoices):
    """Niveau de menace d'une créature, facultatif."""

    LOW = "low", "Low"
    MEDIUM = "medium", "Moderate"
    HIGH = "high", "High"
    MYTHIC = "mythic", "Mythic"


class CulturalAreaKind(models.TextChoices):
    """Nature d'une aire culturelle.

    Les trois valeurs décrivent des phénomènes distincts, conformément à la
    décision 3 de l'ADR 0002 : une aire interne au continent, une portée
    transrégionale, et une transmission hors d'Afrique.
    """

    AFRICAN_REGION = "african_region", "African region"
    TRANSREGIONAL = "transregional", "Transregional"
    DIASPORIC = "diasporic", "Diasporic"


class RelationKind(models.TextChoices):
    """Nature d'un lien entre deux figures.

    Le libellé qualifie toujours la **cible** du lien, lu depuis la source :
    `parent` signifie « la cible est un parent de la source ».
    """

    PARENT = "parent", "Parent"
    CHILD = "child", "Child"
    CONSORT = "consort", "Consort"
    ALLY = "ally", "Ally"
    ENEMY = "enemy", "Enemy"


class EntityStatus(models.TextChoices):
    """État éditorial d'une fiche, au sens de la décision 7 de l'ADR 0002.

    Aucun statut `deleted` : la suppression logique est portée séparément par
    `Entity.deleted_at`, de sorte qu'une fiche supprimée conserve l'état
    éditorial qu'elle avait. Un champ unique mêlant les deux notions
    obligerait à choisir entre « était publiée » et « est supprimée ».
    """

    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


class ActiveEntityManager(models.Manager["Entity"]):
    """Manager restreint aux fiches non supprimées logiquement.

    Ne filtre **que** `deleted_at` : le statut éditorial n'entre pas en jeu,
    le filtrage sur `published` relevant de la phase 3.
    """

    def get_queryset(self) -> models.QuerySet[Entity]:
        return super().get_queryset().filter(deleted_at__isnull=True)


class SourceKind(models.TextChoices):
    """Nature d'une référence documentaire."""

    BOOK = "book", "Book"
    ARTICLE = "article", "Article"
    ENCYCLOPEDIA = "encyclopedia", "Encyclopedia"
    MUSEUM = "museum", "Museum"
    ORAL = "oral", "Oral tradition or testimony"
    OTHER = "other", "Other"


def string_array() -> ArrayField[list[str], list[str]]:
    """Construit un `ArrayField` de courtes chaînes, vide par défaut.

    Les listes symboliques de `Entity` et les listes des trois profils
    partagent exactement la même définition ; la factoriser évite une
    vingtaine de répétitions sans introduire d'abstraction de modèle.
    """
    return ArrayField(models.CharField(max_length=100), default=list, blank=True)


def wrong_entity_type_error(profile_label: str, expected: str) -> ValidationError:
    """Construit l'erreur de validation commune aux trois profils.

    Seul le message est factorisé : chaque profil garde son propre `clean()`
    explicite, afin que la règle reste lisible à l'endroit où elle s'applique.
    """
    return ValidationError(
        {
            "entity": (
                f"A {profile_label} can only be attached to an entity of type "
                f"'{expected}'."
            )
        }
    )


class CulturalArea(models.Model):
    """Aire culturelle : région africaine, portée transrégionale ou diaspora.

    Référentiel, et jamais un type d'entité ni un profil métier. C'est ici que
    sont classées les valeurs comme `Congo Basin`, `Pan-African` ou une
    destination diasporique, que la décision 2 de l'ADR 0002 refuse d'inscrire
    dans `Country`.
    """

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    kind = models.CharField(max_length=20, choices=CulturalAreaKind.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "cultural area"
        verbose_name_plural = "cultural areas"
        constraints = [
            models.CheckConstraint(
                condition=~Q(parent=F("id")),
                name="cultural_area_parent_is_not_self",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Interdit qu'une aire soit son propre parent direct.

        La règle est aussi posée en base par `cultural_area_parent_is_not_self`
        ; ce `clean()` n'existe que pour produire un message lisible dans les
        formulaires plutôt qu'une `IntegrityError`.

        Aucune détection des cycles indirects — A → B → A — n'est tentée : ce
        serait un moteur d'arbre, hors du périmètre de cet incrément.
        """
        super().clean()
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError(
                {"parent": "A cultural area cannot be its own parent."}
            )


class Country(models.Model):
    """Pays réel, identifié par son nom et son code ISO alpha-2 facultatif.

    Ne contient que de véritables pays : `Pan-African`, `Congo Basin` et
    `Diaspora` relèvent de `CulturalArea`, conformément à la décision 2 de
    l'ADR 0002.
    """

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    # Code facultatif représenté par la chaîne vide plutôt que par `NULL` :
    # une seule représentation de l'absence, et pas de `null=True` sur un
    # champ textuel. L'unicité est donc portée par une contrainte
    # conditionnelle qui ignore les codes non renseignés, ce qui autorise
    # autant de pays sans code que nécessaire.
    iso_code = models.CharField(max_length=2, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "country"
        verbose_name_plural = "countries"
        constraints = [
            models.UniqueConstraint(
                fields=["iso_code"],
                condition=~Q(iso_code=""),
                name="unique_country_iso_code_when_set",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        """Normalise le code ISO lors d'un enregistrement par `save()`.

        Placé ici plutôt que dans `clean()` seul, afin que la normalisation
        s'applique aussi à un `objects.create()` direct.
        `update()` et les opérations en masse contournent cette méthode.
        """
        self.iso_code = self.normalized_iso_code()
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def normalized_iso_code(self) -> str:
        """Retourne le code ISO sans espaces superflus et en majuscules."""
        return self.iso_code.strip().upper()

    def clean_fields(self, exclude: Collection[str] | None = None) -> None:
        """Normalise le code avant les validateurs de champ et de longueur."""
        if not exclude or "iso_code" not in exclude:
            self.iso_code = self.normalized_iso_code()
        super().clean_fields(exclude=exclude)

    def clean(self) -> None:
        """Normalise le code ISO puis en valide le format.

        La normalisation est répétée ici pour qu'un code saisi en minuscules
        dans un formulaire soit accepté au lieu d'être rejeté par le contrôle
        qui suit. Le contrôle de format, lui, n'est appliqué que par
        `full_clean()` : `objects.create(iso_code="X1")` passerait, la seule
        barrière de base étant la longueur maximale de deux caractères.
        """
        super().clean()
        self.iso_code = self.normalized_iso_code()
        if self.iso_code and (
            len(self.iso_code) != 2
            or not all("A" <= letter <= "Z" for letter in self.iso_code)
        ):
            raise ValidationError(
                {"iso_code": "ISO code must be exactly two letters from A to Z."}
            )


class Ethnicity(models.Model):
    """Ethnie, ancrage culturel principal d'une figure.

    `primary_cultural_area` situe l'ethnie sans dupliquer les aires portées
    par l'entité elle-même.
    """

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    primary_cultural_area = models.ForeignKey(
        CulturalArea,
        on_delete=models.PROTECT,
        related_name="ethnicities",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "ethnicity"
        verbose_name_plural = "ethnicities"

    def __str__(self) -> str:
        return self.name


class Domain(models.Model):
    """Domaine d'attribution, partagé par les trois types d'entités.

    Emplacement unique des domaines, conformément à la décision 4 de
    l'ADR 0002 : aucun doublon dans les profils propres aux types.
    """

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "domain"
        verbose_name_plural = "domains"

    def __str__(self) -> str:
        return self.name


class Entity(models.Model):
    """Tronc commun à toutes les figures mythologiques.

    Porte les faits réutilisables quel que soit le type : identification,
    récit, apparence et attributs symboliques. Les données propres à un type
    vivent dans un profil relié en `OneToOne`.

    **Règle non encore appliquée.** L'ADR 0002 veut qu'une même valeur ne soit
    pas à la fois ancrage principal et rattachement secondaire — par exemple
    un pays présent dans `primary_country` et dans `secondary_countries`.
    Cette règle n'est volontairement imposée nulle part ici. Un
    `Model.clean()` ne la couvrirait pas : les sélections plusieurs-à-plusieurs
    de l'administration sont enregistrées après la validation de l'instance,
    si bien qu'une nouvelle valeur secondaire échapperait au contrôle. Aucun
    signal global n'est ajouté pour autant. Son application appartiendra aux
    services d'import et d'écriture, avant l'ouverture du CRUD.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    category = models.CharField(
        max_length=255,
        blank=True,
        help_text="Free editorial subtitle, for example 'Orisha of Lightning'.",
    )
    gender = models.CharField(max_length=20, choices=Gender.choices)
    cultural_role = models.CharField(max_length=255, blank=True)
    alignment = models.CharField(max_length=100, blank=True)
    story_description = models.TextField(blank=True)
    characteristics = string_array()
    physical_signs = string_array()
    symbols = string_array()
    power_objects = string_array()
    symbolic_animals = string_array()
    manifestations = models.TextField(blank=True)

    # --- Rattachements aux référentiels ---------------------------------
    #
    # Chaque dimension géographique ou culturelle se décline en un ancrage
    # principal facultatif et une collection de rattachements secondaires,
    # conformément aux décisions 1, 2 et 3 de l'ADR 0002. `PROTECT` sur les
    # clés principales empêche de supprimer un référentiel encore utilisé
    # comme ancrage.
    #
    # Les clés étrangères sont indexées par Django : aucun index manuel n'est
    # ajouté. Aucune table de liaison explicite non plus, les relations
    # multiples ne portant aucune donnée propre.
    primary_country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="entities_as_primary_country",
        null=True,
        blank=True,
    )
    secondary_countries = models.ManyToManyField(
        Country,
        related_name="entities_as_secondary_country",
        blank=True,
    )
    primary_ethnicity = models.ForeignKey(
        Ethnicity,
        on_delete=models.PROTECT,
        related_name="entities_as_primary_ethnicity",
        null=True,
        blank=True,
    )
    secondary_ethnicities = models.ManyToManyField(
        Ethnicity,
        related_name="entities_as_secondary_ethnicity",
        blank=True,
    )
    primary_cultural_area = models.ForeignKey(
        CulturalArea,
        on_delete=models.PROTECT,
        related_name="entities_as_primary_area",
        null=True,
        blank=True,
    )
    secondary_cultural_areas = models.ManyToManyField(
        CulturalArea,
        related_name="entities_as_secondary_area",
        blank=True,
    )
    domains = models.ManyToManyField(Domain, related_name="entities", blank=True)

    # Variante culturelle d'une figure de référence, au sens de la décision 3
    # de l'ADR 0002. La variante reste une entité autonome : rien n'est hérité
    # ni recopié depuis la référence, et son `entity_type` peut différer du
    # sien — une forme régionale peut être une créature là où la référence est
    # une divinité. Aucune contrainte d'égalité des types n'est donc posée.
    #
    # `PROTECT` interdit la suppression physique d'une figure encore citée
    # comme référence.
    variant_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="variants",
        null=True,
        blank=True,
    )

    # --- Champs de plateforme -------------------------------------------
    #
    # Propriété, état éditorial, revue et suppression logique, au sens de la
    # décision 7 de l'ADR 0002. Ces champs sont **posés**, non pilotés :
    # aucun `save()` surchargé, aucun signal, aucune machine à états. Les
    # transitions, l'attribution automatique du propriétaire et la matrice de
    # permissions appartiennent à la phase 4.
    #
    # `SET_NULL` sur les trois acteurs : supprimer un compte ne doit jamais
    # supprimer une fiche, et une date historique peut légitimement subsister
    # avec un acteur devenu nul. Aucune contrainte ne lie donc acteur, date et
    # statut.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_entities",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=EntityStatus.choices,
        default=EntityStatus.DRAFT,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_entities",
        null=True,
        blank=True,
    )
    review_notes = models.TextField(blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="deleted_entities",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # `objects` est déclaré en premier, donc manager par défaut : il voit
    # **toutes** les lignes, y compris celles supprimées logiquement. C'est ce
    # que veut la décision 7 de l'ADR 0002 — l'administration et une future
    # restauration doivent pouvoir les atteindre, et le parcours des relations
    # ne doit jamais masquer de lignes silencieusement.
    objects = models.Manager()
    active = ActiveEntityManager()

    class Meta:
        ordering = ["name"]
        verbose_name = "entity"
        verbose_name_plural = "entities"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "entity_type"],
                name="unique_entity_name_per_type",
            ),
            models.CheckConstraint(
                condition=~Q(variant_of=F("id")),
                name="entity_variant_of_is_not_self",
            ),
        ]
        indexes = [models.Index(fields=["entity_type"], name="entity_type_idx")]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Interdit qu'une entité soit sa propre figure de référence.

        La règle est garantie en base par `entity_variant_of_is_not_self` ; ce
        `clean()` n'existe que pour produire un message lisible dans un
        formulaire plutôt qu'une `IntegrityError`.

        Les cycles indirects — A variante de B, B variante de A — ne sont
        **pas** détectés : il faudrait un parcours récursif, hors du périmètre
        de cet incrément.
        """
        super().clean()
        if self.variant_of_id is not None and self.variant_of_id == self.pk:
            raise ValidationError(
                {"variant_of": "An entity cannot be a variant of itself."}
            )


class DivinityProfile(models.Model):
    """Données propres aux divinités.

    Ne contient que le culte : les attributs symboliques communs restent sur
    `Entity`, conformément à la décision 4 de l'ADR 0002 qui impose un
    emplacement unique pour les domaines et les attributs partagés.
    """

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="divinity_profile",
    )
    cult_offerings = string_array()
    cult_taboos = string_array()
    cult_rituals = string_array()
    cult_places = string_array()
    cult_festivals = string_array()

    class Meta:
        verbose_name = "divinity profile"
        verbose_name_plural = "divinity profiles"

    def __str__(self) -> str:
        return f"Divinity profile — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type.

        Cette règle ne peut pas devenir une contrainte de base : elle porte sur
        une colonne d'une autre table. Elle est donc appliquée par
        `full_clean()`, donc par l'administration et par les formulaires. Un
        appel direct à `objects.create()` ne la déclenche pas — la garantie
        complète « une entité possède exactement le profil de son type »
        viendra avec les services de création métier.
        """
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.DIVINITY
        ):
            raise wrong_entity_type_error("divinity profile", EntityType.DIVINITY)


class HeroProfile(models.Model):
    """Données propres aux héros.

    Les alliés et les ennemis ne sont pas ici : ce sont des relations entre
    entités, qui seront portées par `EntityRelation` dans un incrément
    ultérieur de la phase 2.
    """

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="hero_profile",
    )
    titles = string_array()
    achievements = string_array()
    quests = string_array()
    weapons_or_artifacts = string_array()
    legacy = models.TextField(blank=True)
    historical_context = models.TextField(blank=True)

    class Meta:
        verbose_name = "hero profile"
        verbose_name_plural = "hero profiles"

    def __str__(self) -> str:
        return f"Hero profile — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type."""
        super().clean()
        if self.entity_id is not None and self.entity.entity_type != EntityType.HERO:
            raise wrong_entity_type_error("hero profile", EntityType.HERO)


class CreatureProfile(models.Model):
    """Données propres aux créatures."""

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="creature_profile",
    )
    habitat = string_array()
    powers = string_array()
    strengths = string_array()
    weaknesses = string_array()
    encounter_omens = string_array()
    encounter_rules = string_array()
    known_sightings = string_array()
    diet = models.CharField(max_length=255, blank=True)
    size = models.CharField(max_length=255, blank=True)
    appearance_notes = models.TextField(blank=True)
    # `null=True` sur un champ textuel est signalé par Ruff (DJ001) parce
    # qu'il ouvre deux représentations de l'absence, `NULL` et `""`.
    # L'écart est délibéré, mais il n'est pas sans effet : il est seulement
    # borné pour l'instant.
    #
    # Ce qui est garanti : pour un champ à `choices` nullable,
    # `Field.formfield()` impose `empty_value=None`, donc un choix laissé vide
    # dans un formulaire ou dans l'administration est enregistré `NULL`.
    # Ce qui ne l'est pas : un appel ORM direct — `objects.create(
    # threat_level="")` — ou un futur serializer d'écriture peut toujours
    # stocker `""`. L'API étant en lecture seule, ce cas n'est pas exposé
    # aujourd'hui. La normalisation de `""` vers `None` sera imposée dans les
    # serializers ou services d'écriture de la phase 4 ; aucune contrainte ni
    # abstraction n'est ajoutée maintenant.
    threat_level = models.CharField(  # noqa: DJ001
        max_length=10,
        choices=ThreatLevel.choices,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "creature profile"
        verbose_name_plural = "creature profiles"

    def __str__(self) -> str:
        return f"Creature profile — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type."""
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.CREATURE
        ):
            raise wrong_entity_type_error("creature profile", EntityType.CREATURE)


class EntityRelation(models.Model):
    """Lien orienté entre une figure et une autre, résolue ou simplement citée.

    **Sens de lecture.** Le lien se lit toujours depuis `from_entity`, et
    `kind` qualifie la cible :

    - `A — parent → B` signifie « B est un parent de A » ;
    - `A — child → B` signifie « B est un enfant de A ».

    Ce sens doit être respecté à l'import : l'inverser transformerait une
    ascendance en descendance. Un descendant lointain n'est jamais converti en
    enfant direct ; les cas ambigus seront signalés par le rapport d'import.

    **Cible résolue ou citée.** Sur les 44 entités du corpus V2, les noms
    cités dans `relations` désignent souvent des figures absentes. Exiger une
    cible existante perdrait l'information ; `to_name` conserve donc le nom
    brut. Une fois la fiche créée, le lien pourra être résolu explicitement. Aucun
    rapprochement par nom n'est tenté : les noms sont culturellement ambigus
    et une fusion automatique de fiches serait une perte de donnée.

    **Aucune relation inverse n'est créée.** `parent` n'engendre pas de
    `child`, et une alliance n'engendre pas sa réciproque : une seule ligne
    est écrite, celle que l'on a saisie.
    """

    from_entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name="relations_from",
    )
    to_entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name="relations_to",
        null=True,
        blank=True,
    )
    to_name = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=20, choices=RelationKind.choices)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["kind", "to_name", "id"]
        verbose_name = "entity relation"
        verbose_name_plural = "entity relations"
        constraints = [
            # Exactement une cible : soit la fiche, soit le nom, jamais les
            # deux ni aucune.
            models.CheckConstraint(
                condition=(
                    Q(to_entity__isnull=False, to_name="")
                    | Q(to_entity__isnull=True) & ~Q(to_name="")
                ),
                name="entity_relation_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=~Q(to_entity=F("from_entity")),
                name="entity_relation_target_is_not_source",
            ),
            # Deux unicités complémentaires : l'une pour les liens résolus,
            # l'autre pour les liens cités. Une paire de figures peut porter
            # plusieurs types de relation, seul le triplet est unique.
            models.UniqueConstraint(
                fields=["from_entity", "to_entity", "kind"],
                condition=Q(to_entity__isnull=False),
                name="unique_resolved_relation",
            ),
            models.UniqueConstraint(
                fields=["from_entity", "to_name", "kind"],
                condition=Q(to_entity__isnull=True),
                name="unique_unresolved_relation",
            ),
        ]

    def __str__(self) -> str:
        target = self.to_entity.name if self.to_entity is not None else self.to_name
        return f"{self.from_entity.name} — {self.kind} → {target}"

    def clean(self) -> None:
        """Valide la cible, en doublant les contraintes d'un message lisible.

        Les trois règles ci-dessous sont garanties en base par les
        `CheckConstraint` ; ce `clean()` les rejoue pour que l'administration
        affiche une erreur de formulaire au lieu d'une `IntegrityError`. La
        quatrième — un nom composé uniquement d'espaces — n'existe qu'ici :
        `"   "` n'est pas la chaîne vide, donc la contrainte de base le
        laisserait passer.
        """
        super().clean()
        self.to_name = self.to_name.strip()

        if self.to_entity_id is not None and self.to_name:
            raise ValidationError(
                {
                    "to_name": (
                        "Leave the target name empty when a target entity is "
                        "selected."
                    )
                }
            )
        if self.to_entity_id is None and not self.to_name:
            raise ValidationError(
                {"to_name": ("Provide either a target entity or a target name.")}
            )
        if self.to_entity_id is not None and self.to_entity_id == self.from_entity_id:
            raise ValidationError(
                {"to_entity": "An entity cannot be related to itself."}
            )


class Source(models.Model):
    """Référence documentaire rattachée à une fiche.

    Une source appartient à **une seule** entité ; une entité en possède zéro
    ou plusieurs. La même référence bibliographique peut donc être saisie pour
    plusieurs entités : il n'y a volontairement ni catalogue partagé ni
    relation plusieurs-à-plusieurs à ce stade. Mutualiser les références
    supposerait une identité bibliographique stable — édition, pagination,
    tirage — que le corpus ne fournit pas.

    `label` reste libre : titre d'ouvrage, nom de site, cote de musée ou
    description d'un témoignage. Les précisions qui ne tiennent pas dans ce
    libellé — auteur, pages, édition, contexte d'un entretien — vont dans
    `notes`. Aucun champ bibliographique supplémentaire n'est créé : le corpus
    V2 ne contient aujourd'hui **aucune** source, et inventer un modèle
    bibliographique complet avant d'avoir une seule donnée réelle serait
    prématuré.

    Une source sans URL reste valide : un livre ou une tradition orale n'en a
    pas. `accessed_at` est une date de **consultation**, non de publication ;
    elle peut être renseignée sans URL, par exemple la date d'un entretien ou
    d'une visite. Aucune valeur n'est remplie automatiquement.

    Aucune vérification réseau n'est effectuée : ni disponibilité de l'URL, ni
    liste de domaines autorisés. Le format seul est validé.
    """

    entity = models.ForeignKey(
        Entity,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    label = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=SourceKind.choices)
    url = models.URLField(max_length=2048, blank=True)
    accessed_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        # Aucune unicité sur `label`, `url` ou leur combinaison : deux
        # éditions, deux pages ou deux usages d'une même référence sont
        # légitimes. Écarter les doublons relève du contrôle éditorial, pas de
        # la structure de la base.
        ordering = ["label", "id"]
        verbose_name = "documentary source"
        verbose_name_plural = "documentary sources"

    def __str__(self) -> str:
        return f"{self.label} ({self.kind}) — {self.entity.name}"

    def clean(self) -> None:
        """Refuse une référence composée uniquement d'espaces.

        Portée exacte : cette règle n'existe qu'ici, donc elle ne s'applique
        qu'à `full_clean()`, aux formulaires et à l'administration. `"   "`
        n'est pas la chaîne vide, et aucune contrainte PostgreSQL ne
        l'intercepte — `objects.create(label="   ")` serait accepté. De même,
        le caractère obligatoire de `label` et de `kind` ainsi que le format
        de l'URL sont vérifiés par la validation Django, et non par la base.
        """
        super().clean()
        self.label = self.label.strip()
        if not self.label:
            raise ValidationError({"label": "Provide a non-empty source label."})
