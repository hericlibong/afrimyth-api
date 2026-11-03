"""Models of the mythological domain.

Current content: the `Entity` common trunk - with its possible variant
(`variant_of`) -, its three business profiles (`DivinityProfile`,
`HeroProfile`, `CreatureProfile`), the four validated reference models
(`CulturalArea`, `Country`, `Ethnicity`, `Domain`) and the links between
figures (`EntityRelation`).

To these are added the documentary references (`Source`) and the platform
fields of `Entity`: ownership, editorial state, review and logical
deletion.

Those platform fields are **declared, not driven**: status transitions,
automatic owner assignment, roles, permissions and restoration belong to
phase 4. Visual rendering data is out of V1 scope, as stated in section 8
of ADR 0002.
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
    """Type of a mythological figure.

    The type governs the expected business profile. It stays distinct from
    `Entity.category`, which is a free editorial subtitle.
    """

    DIVINITY = "divinity", "Divinity"
    HERO = "hero", "Hero"
    CREATURE = "creature", "Creature"


class Gender(models.TextChoices):
    """Gender of the figure, limited to the values observed in the corpus."""

    MALE = "male", "Male"
    FEMALE = "female", "Female"
    NEUTRAL = "neutral", "Neutral"
    ANDROGYNOUS = "androgynous", "Androgynous"
    FLUID = "fluid", "Fluid"


class ThreatLevel(models.TextChoices):
    """Threat level of a creature, optional."""

    LOW = "low", "Low"
    MEDIUM = "medium", "Moderate"
    HIGH = "high", "High"
    MYTHIC = "mythic", "Mythic"


class CulturalAreaKind(models.TextChoices):
    """Nature of a cultural area.

    The three values describe distinct phenomena, as stated by decision 3 of
    ADR 0002: an area internal to the continent, a transregional scope, and a
    transmission outside Africa.
    """

    AFRICAN_REGION = "african_region", "African region"
    TRANSREGIONAL = "transregional", "Transregional"
    DIASPORIC = "diasporic", "Diasporic"


class RelationKind(models.TextChoices):
    """Nature of a link between two figures.

    The label always qualifies the **target** of the link, read from the
    source: `parent` means that the target is a parent of the source.
    """

    PARENT = "parent", "Parent"
    CHILD = "child", "Child"
    CONSORT = "consort", "Consort"
    ALLY = "ally", "Ally"
    ENEMY = "enemy", "Enemy"


class EntityStatus(models.TextChoices):
    """Editorial state of a record, as defined by decision 7 of ADR 0002.

    There is no `deleted` status: logical deletion is carried separately by
    `Entity.deleted_at`, so that a deleted record keeps the editorial state it
    had. A single field mixing both notions would force a choice between was
    published and is deleted.
    """

    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


class ActiveEntityManager(models.Manager["Entity"]):
    """Manager restricted to records that are not logically deleted.

    Filters **only** on `deleted_at`: the editorial status plays no part here,
    filtering on `published` being a matter for phase 3.
    """

    def get_queryset(self) -> models.QuerySet[Entity]:
        return super().get_queryset().filter(deleted_at__isnull=True)


class SourceKind(models.TextChoices):
    """Nature of a documentary reference."""

    BOOK = "book", "Book"
    ARTICLE = "article", "Article"
    ENCYCLOPEDIA = "encyclopedia", "Encyclopedia"
    MUSEUM = "museum", "Museum"
    ORAL = "oral", "Oral tradition or testimony"
    OTHER = "other", "Other"


def string_array() -> ArrayField[list[str], list[str]]:
    """Build an `ArrayField` of short strings, empty by default.

    The symbolic lists of `Entity` and the lists of the three profiles share
    exactly the same definition; factoring it out avoids about twenty
    repetitions without introducing a model abstraction.
    """
    return ArrayField(models.CharField(max_length=100), default=list, blank=True)


def wrong_entity_type_error(profile_label: str, expected: str) -> ValidationError:
    """Build the validation error shared by the three profiles.

    Only the message is factored out: each profile keeps its own explicit
    `clean()`, so that the rule stays readable where it applies.
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
    """Cultural area: African region, transregional scope or diaspora.

    Reference data, and never an entity type nor a business profile. This is
    where values such as `Congo Basin`, `Pan-African` or a diasporic
    destination are classified, which decision 2 of ADR 0002 refuses to
    record in `Country`.
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
        """Forbid an area from being its own direct parent.

        The rule is also enforced in the database by
        `cultural_area_parent_is_not_self`; this `clean()` exists only to produce
        a readable message in forms rather than an `IntegrityError`.

        No detection of indirect cycles - A to B to A - is attempted: that would
        be a tree engine, out of the scope of this increment.
        """
        super().clean()
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError(
                {"parent": "A cultural area cannot be its own parent."}
            )


class Country(models.Model):
    """Real country, identified by its name and its optional ISO alpha-2 code.

    Holds genuine countries only: `Pan-African`, `Congo Basin` and `Diaspora`
    belong to `CulturalArea`, as stated by decision 2 of ADR 0002.
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
        """Normalise the ISO code when saving through `save()`.

        Placed here rather than in `clean()` alone, so that the normalisation also
        applies to a direct `objects.create()`. `update()` and bulk operations
        bypass this method.
        """
        self.iso_code = self.normalized_iso_code()
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def normalized_iso_code(self) -> str:
        """Return the ISO code without stray spaces and in upper case."""
        return self.iso_code.strip().upper()

    def clean_fields(self, exclude: Collection[str] | None = None) -> None:
        """Normalise the code before the field and length validators."""
        if not exclude or "iso_code" not in exclude:
            self.iso_code = self.normalized_iso_code()
        super().clean_fields(exclude=exclude)

    def clean(self) -> None:
        """Normalise the ISO code, then validate its format.

        The normalisation is repeated here so that a code typed in lower case in a
        form is accepted instead of being rejected by the check that follows. The
        format check itself is only applied by `full_clean()`:
        `objects.create(iso_code='X1')` would pass, the only database barrier
        being the maximum length of two characters.
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
    """Ethnicity, the main cultural anchor of a figure.

    `primary_cultural_area` situates the ethnicity without duplicating the
    areas carried by the entity itself.
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
    """Domain of attribution, shared by the three entity types.

    The single location for domains, as stated by decision 4 of ADR 0002: no
    duplicate inside the type-specific profiles.
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
    """Common trunk of every mythological figure.

    Carries the facts that are reusable whatever the type: identification,
    narrative, appearance and symbolic attributes. Type-specific data lives in
    a profile linked through a `OneToOne`.

    **Rule not enforced yet.** ADR 0002 requires that one value not be both a
    primary anchor and a secondary attachment - for instance a country present
    in `primary_country` and in `secondary_countries`. That rule is
    deliberately enforced nowhere here. A `Model.clean()` would not cover it:
    the many-to-many selections of the admin are saved after the instance is
    validated, so a new secondary value would escape the check. No global
    signal is added for that purpose either. Enforcing it will belong to the
    import and write services, before CRUD is opened.
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
        """Forbid an entity from being its own reference figure.

        The rule is guaranteed in the database by
        `entity_variant_of_is_not_self`; this `clean()` exists only to produce a
        readable message in a form rather than an `IntegrityError`.

        Indirect cycles - A a variant of B, B a variant of A - are **not**
        detected: that would require a recursive traversal, out of the scope of
        this increment.
        """
        super().clean()
        if self.variant_of_id is not None and self.variant_of_id == self.pk:
            raise ValidationError(
                {"variant_of": "An entity cannot be a variant of itself."}
            )


class DivinityProfile(models.Model):
    """Data specific to divinities.

    Holds the cult only: the shared symbolic attributes stay on `Entity`, as
    stated by decision 4 of ADR 0002, which imposes a single location for
    shared domains and attributes.
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
        """Forbid attaching this profile to an entity of another type.

        This rule cannot become a database constraint: it bears on a column of
        another table. It is therefore enforced by `full_clean()`, and so by the
        admin and by forms. A direct call to `objects.create()` does not trigger
        it - the full guarantee that an entity owns exactly the profile of its
        type will come with the business creation services.
        """
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.DIVINITY
        ):
            raise wrong_entity_type_error("divinity profile", EntityType.DIVINITY)


class HeroProfile(models.Model):
    """Data specific to heroes.

    Allies and enemies are not here: those are relations between entities,
    which will be carried by `EntityRelation` in a later increment of
    phase 2.
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
        """Forbid attaching this profile to an entity of another type."""
        super().clean()
        if self.entity_id is not None and self.entity.entity_type != EntityType.HERO:
            raise wrong_entity_type_error("hero profile", EntityType.HERO)


class CreatureProfile(models.Model):
    """Data specific to creatures."""

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
        """Forbid attaching this profile to an entity of another type."""
        super().clean()
        if (
            self.entity_id is not None
            and self.entity.entity_type != EntityType.CREATURE
        ):
            raise wrong_entity_type_error("creature profile", EntityType.CREATURE)


class EntityRelation(models.Model):
    """Directed link from one figure to another, resolved or merely cited.

    **Reading direction.** The link always reads from `from_entity`, and
    `kind` qualifies the target:

    - `A - parent -> B` means that B is a parent of A;
    - `A - child -> B` means that B is a child of A.

    That direction must be respected at import time: reversing it would turn
    an ascent into a descent. A distant descendant is never converted into a
    direct child; ambiguous cases are reported by the import summary.

    **Resolved or cited target.** Across the 44 entities of the V2 corpus, the
    names cited in `relations` often designate absent figures. Requiring an
    existing target would lose that information; `to_name` therefore keeps the
    raw name. Once the record exists, the link can be resolved explicitly. No
    matching by name is attempted: names are culturally ambiguous and an
    automatic merge of records would be a loss of data.

    **No inverse relation is created.** `parent` does not generate a `child`,
    and an alliance does not generate its counterpart: a single row is
    written, the one that was entered.
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
        """Validate the target, mirroring the constraints with a readable message.

        The three rules below are guaranteed in the database by the
        `CheckConstraint`s; this `clean()` replays them so that the admin shows a
        form error instead of an `IntegrityError`. The fourth one - a name made of
        spaces only - exists here only: a blank-filled string is not the empty
        string, so the database constraint would let it through.
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
    """Documentary reference attached to a record.

    A source belongs to **one single** entity; an entity owns zero or several.
    The same bibliographic reference can therefore be entered for several
    entities: there is deliberately neither a shared catalogue nor a
    many-to-many relation at this stage. Sharing references would require a
    stable bibliographic identity - edition, pagination, print run - that the
    corpus does not provide.

    `label` stays free: a book title, a site name, a museum reference number
    or the description of a testimony. Details that do not fit in that label -
    author, pages, edition, context of an interview - go into `notes`. No
    extra bibliographic field is created: the V2 corpus currently holds **no**
    source at all, and inventing a complete bibliographic model before having
    a single real record would be premature.

    A source without a URL stays valid: a book or an oral tradition has none.
    `accessed_at` is a **consultation** date, not a publication date; it can
    be filled in without a URL, for instance the date of an interview or of a
    visit. No value is filled in automatically.

    No network check is performed: neither URL availability, nor a list of
    allowed domains. The format alone is validated.
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
        """Refuse a reference made of spaces only.

        Exact scope: this rule exists here only, so it applies to `full_clean()`,
        to forms and to the admin. A blank-filled string is not the empty string,
        and no PostgreSQL constraint intercepts it - a direct create with a
        blank-filled label would be accepted. Likewise, the mandatory nature of
        `label` and `kind`, as well as the URL format, are checked by Django
        validation and not by the database.
        """
        super().clean()
        self.label = self.label.strip()
        if not self.label:
            raise ValidationError({"label": "Provide a non-empty source label."})
