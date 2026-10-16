"""Modèles du domaine mythologique.

Contenu actuel : le tronc commun `Entity`, ses trois profils métier
(`DivinityProfile`, `HeroProfile`, `CreatureProfile`) et les quatre
référentiels validés (`CulturalArea`, `Country`, `Ethnicity`, `Domain`).

Restent à venir : `variant_of`, `EntityRelation`, `Source`, le workflow
éditorial et les champs de suppression logique. Les données de rendu visuel
sont hors V1, conformément à la section 8 de l'ADR 0002.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class EntityType(models.TextChoices):
    """Type d'une figure mythologique.

    Le type gouverne le profil métier attendu. Il reste distinct de
    `Entity.category`, qui est un sous-titre éditorial libre.
    """

    DIVINITY = "divinity", "Divinité"
    HERO = "hero", "Héros"
    CREATURE = "creature", "Créature"


class Gender(models.TextChoices):
    """Genre de la figure, limité aux valeurs observées dans le corpus."""

    MALE = "male", "Masculin"
    FEMALE = "female", "Féminin"
    NEUTRAL = "neutral", "Neutre"
    ANDROGYNOUS = "androgynous", "Androgyne"
    FLUID = "fluid", "Fluide"


class ThreatLevel(models.TextChoices):
    """Niveau de menace d'une créature, facultatif."""

    LOW = "low", "Faible"
    MEDIUM = "medium", "Modéré"
    HIGH = "high", "Élevé"
    MYTHIC = "mythic", "Mythique"


class CulturalAreaKind(models.TextChoices):
    """Nature d'une aire culturelle.

    Les trois valeurs décrivent des phénomènes distincts, conformément à la
    décision 3 de l'ADR 0002 : une aire interne au continent, une portée
    transrégionale, et une transmission hors d'Afrique.
    """

    AFRICAN_REGION = "african_region", "African region"
    TRANSREGIONAL = "transregional", "Transregional"
    DIASPORIC = "diasporic", "Diasporic"


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
                f"Un {profile_label} ne peut être rattaché qu'à une entité "
                f"de type « {expected} »."
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
        verbose_name = "aire culturelle"
        verbose_name_plural = "aires culturelles"
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
        verbose_name = "pays"
        verbose_name_plural = "pays"
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
        verbose_name = "ethnie"
        verbose_name_plural = "ethnies"

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
        verbose_name = "domaine"
        verbose_name_plural = "domaines"

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
        help_text="Sous-titre éditorial libre, par exemple « Orisha of Lightning ».",
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "entité"
        verbose_name_plural = "entités"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "entity_type"],
                name="unique_entity_name_per_type",
            )
        ]
        indexes = [models.Index(fields=["entity_type"], name="entity_type_idx")]

    def __str__(self) -> str:
        return self.name


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
        verbose_name = "profil de divinité"
        verbose_name_plural = "profils de divinité"

    def __str__(self) -> str:
        return f"Profil de divinité — {self.entity.name}"

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
            raise wrong_entity_type_error("profil de divinité", EntityType.DIVINITY)


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
        verbose_name = "profil de héros"
        verbose_name_plural = "profils de héros"

    def __str__(self) -> str:
        return f"Profil de héros — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type."""
        super().clean()
        if self.entity_id is not None and self.entity.entity_type != EntityType.HERO:
            raise wrong_entity_type_error("profil de héros", EntityType.HERO)


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
        verbose_name = "profil de créature"
        verbose_name_plural = "profils de créatures"

    def __str__(self) -> str:
        return f"Profil de créature — {self.entity.name}"

    def clean(self) -> None:
        """Interdit de rattacher ce profil à une entité d'un autre type."""
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.CREATURE
        ):
            raise wrong_entity_type_error("profil de créature", EntityType.CREATURE)
