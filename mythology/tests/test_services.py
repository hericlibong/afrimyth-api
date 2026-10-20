"""Tests de `create_entity_with_profile`.

Les factories existantes ne sont **pas** remplacées par le service : plusieurs
tests ont volontairement besoin d'entités sans profil ou de données invalides
pour vérifier des limites. Ce module teste le service lui-même.

Les données employées sont fictives. Chaque test vérifie l'état **stocké** —
après `refresh_from_db()` ou par une requête — et non le seul objet en
mémoire, ni la présence d'un décorateur `atomic`.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from mythology.models import (
    CreatureProfile,
    DivinityProfile,
    Entity,
    EntityStatus,
    EntityType,
    Gender,
    HeroProfile,
    ThreatLevel,
)
from mythology.services import create_entity_with_profile
from mythology.tests.factories import create_country, create_entity

pytestmark = pytest.mark.django_db


def entity_payload(**overrides: object) -> dict[str, object]:
    """Jeu minimal valide pour le tronc commun."""
    data: dict[str, object] = {
        "name": "Shango",
        "slug": "shango",
        "entity_type": EntityType.DIVINITY,
        "gender": Gender.MALE,
    }
    data.update(overrides)
    return data


# --- Les trois types ----------------------------------------------------


def test_creation_d_une_divinite_et_de_son_seul_profil() -> None:
    """Une divinité reçoit un `DivinityProfile`, et aucun des deux autres."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(),
        profile_data={"cult_offerings": ["Yam"], "cult_taboos": ["Lying"]},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.DIVINITY
    assert stored.divinity_profile.cult_offerings == ["Yam"]
    assert stored.divinity_profile.cult_taboos == ["Lying"]
    assert not hasattr(stored, "hero_profile")
    assert not hasattr(stored, "creature_profile")
    assert DivinityProfile.objects.count() == 1
    assert HeroProfile.objects.count() == 0
    assert CreatureProfile.objects.count() == 0


def test_creation_d_un_heros_et_de_son_seul_profil() -> None:
    """Un héros reçoit un `HeroProfile`, et aucun des deux autres."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(
            name="Soundiata", slug="soundiata", entity_type=EntityType.HERO
        ),
        profile_data={"titles": ["King of Mali"], "legacy": "Founded the empire."},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.HERO
    assert stored.hero_profile.titles == ["King of Mali"]
    assert stored.hero_profile.legacy == "Founded the empire."
    assert not hasattr(stored, "divinity_profile")
    assert not hasattr(stored, "creature_profile")
    assert HeroProfile.objects.count() == 1


def test_creation_d_une_creature_et_de_son_seul_profil() -> None:
    """Une créature reçoit un `CreatureProfile`, et aucun des deux autres."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(
            name="Mokele-mbembe",
            slug="mokele-mbembe",
            entity_type=EntityType.CREATURE,
            gender=Gender.NEUTRAL,
        ),
        profile_data={"habitat": ["Swamps"], "threat_level": ThreatLevel.HIGH},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.CREATURE
    assert stored.creature_profile.habitat == ["Swamps"]
    assert stored.creature_profile.threat_level == ThreatLevel.HIGH
    assert not hasattr(stored, "divinity_profile")
    assert not hasattr(stored, "hero_profile")
    assert CreatureProfile.objects.count() == 1


# --- Données conservées -------------------------------------------------


def test_les_donnees_du_tronc_commun_sont_conservees() -> None:
    """Les champs simples et les clés étrangères arrivent bien en base."""
    country = create_country()
    entity = create_entity_with_profile(
        entity_data=entity_payload(
            category="Orisha of Lightning",
            cultural_role="Thunder deity",
            story_description="Fictional narrative for tests.",
            symbols=["Double-headed axe"],
            primary_country=country,
        ),
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.category == "Orisha of Lightning"
    assert stored.cultural_role == "Thunder deity"
    assert stored.story_description == "Fictional narrative for tests."
    assert stored.symbols == ["Double-headed axe"]
    assert stored.primary_country == country


def test_cle_etrangere_acceptee_sous_sa_forme_id() -> None:
    """`primary_country_id` est accepté, forme utile à l'import."""
    country = create_country()

    entity = create_entity_with_profile(
        entity_data=entity_payload(primary_country_id=country.pk),
    )

    assert Entity.objects.get(pk=entity.pk).primary_country == country


def test_statut_par_defaut_reste_draft() -> None:
    """Le service ne publie rien et n'attribue aucun propriétaire."""
    entity = create_entity_with_profile(entity_data=entity_payload())

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.status == EntityStatus.DRAFT
    assert stored.created_by is None
    assert stored.submitted_at is None


# --- Profil absent ou vide ----------------------------------------------


def test_profil_absent_cree_un_profil_par_defaut() -> None:
    """Sans `profile_data`, le profil existe avec ses valeurs par défaut.

    Le point important : jamais une entité **sans** profil.
    """
    entity = create_entity_with_profile(entity_data=entity_payload())

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.divinity_profile.cult_offerings == []
    assert stored.divinity_profile.cult_festivals == []


def test_profil_vide_cree_un_profil_par_defaut() -> None:
    """Un dictionnaire vide est traité comme une absence."""
    entity = create_entity_with_profile(
        entity_data=entity_payload(entity_type=EntityType.CREATURE),
        profile_data={},
    )

    stored = Entity.objects.get(pk=entity.pk)

    assert stored.creature_profile.habitat == []
    assert stored.creature_profile.threat_level is None


# --- Type absent ou inconnu ---------------------------------------------


def test_type_absent_est_refuse() -> None:
    """Sans type, aucun profil ne peut être choisi : rien n'est créé."""
    data = entity_payload()
    del data["entity_type"]

    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=data)

    assert "entity_type" in excinfo.value.message_dict
    assert Entity.objects.count() == 0


def test_type_vide_est_refuse() -> None:
    """Une chaîne vide est traitée comme une absence de type."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(entity_type=""))

    assert "entity_type" in excinfo.value.message_dict
    assert Entity.objects.count() == 0


def test_type_inconnu_est_refuse() -> None:
    """Un type hors des trois valeurs est refusé avant toute écriture."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(entity_type="titan"))

    assert "entity_type" in excinfo.value.message_dict
    assert Entity.objects.count() == 0


# --- Champs refusés -----------------------------------------------------


def test_champ_de_profil_incompatible_est_refuse() -> None:
    """Un champ d'un autre profil ne passe pas, et rien n'est créé.

    `habitat` appartient au profil de créature : le demander pour une
    divinité est une erreur d'appel, pas une donnée à ignorer.
    """
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(
            entity_data=entity_payload(),
            profile_data={"habitat": ["Swamps"]},
        )

    assert "habitat" in str(excinfo.value)
    assert Entity.objects.count() == 0
    assert DivinityProfile.objects.count() == 0


def test_champ_d_entite_inconnu_est_refuse() -> None:
    """Un champ inexistant est signalé plutôt qu'écrit partiellement."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(pantheon="Orisha"))

    assert "pantheon" in str(excinfo.value)
    assert Entity.objects.count() == 0


@pytest.mark.parametrize(
    "champ",
    [
        "secondary_countries",
        "secondary_ethnicities",
        "secondary_cultural_areas",
        "domains",
        "sources",
        "relations_from",
    ],
)
def test_collections_hors_perimetre_sont_refusees(champ: str) -> None:
    """Les relations multiples sont explicitement hors périmètre.

    Elles exigent une entité déjà enregistrée : l'import les rattachera après
    l'appel, sans compromettre l'atomicité du couple entité/profil.
    """
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(**{champ: []}))

    assert champ in excinfo.value.message_dict
    assert Entity.objects.count() == 0


@pytest.mark.parametrize("champ", ["id", "pk"])
def test_identifiant_impose_est_refuse(champ: str) -> None:
    """Un identifiant fourni est refusé : la fonction crée, elle n'écrase pas."""
    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(entity_data=entity_payload(**{champ: 1}))

    assert champ in excinfo.value.message_dict
    assert Entity.objects.count() == 0


def test_identifiant_existant_ne_peut_pas_ecraser_une_fiche() -> None:
    """Réutiliser l'`id` d'une fiche existante ne l'écrase pas."""
    existante = create_entity(name="Existante", slug="existante")

    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(id=existante.pk))

    existante.refresh_from_db()
    assert existante.name == "Existante"
    assert Entity.objects.count() == 1


@pytest.mark.parametrize("champ", ["entity", "entity_id"])
def test_rattachement_du_profil_ne_peut_pas_etre_detourne(champ: str) -> None:
    """Le profil est rattaché à l'entité créée, jamais à une autre."""
    autre = create_entity(name="Autre", slug="autre")

    with pytest.raises(ValidationError) as excinfo:
        create_entity_with_profile(
            entity_data=entity_payload(),
            profile_data={champ: autre.pk if champ == "entity_id" else autre},
        )

    assert champ in excinfo.value.message_dict
    assert DivinityProfile.objects.count() == 0
    assert Entity.objects.count() == 1


# --- Atomicité ----------------------------------------------------------


def test_echec_du_profil_n_laisse_aucun_residu() -> None:
    """Si le profil échoue après l'entité, les deux créations sont annulées.

    C'est le cœur de la garantie : `threat_level` invalide est détecté par le
    `full_clean()` du profil, donc **après** l'enregistrement de l'entité.
    Sans transaction, une entité orpheline subsisterait.
    """
    with pytest.raises(ValidationError):
        create_entity_with_profile(
            entity_data=entity_payload(
                name="Mokele-mbembe",
                slug="mokele-mbembe",
                entity_type=EntityType.CREATURE,
            ),
            profile_data={"threat_level": "apocalyptic"},
        )

    assert Entity.objects.count() == 0
    assert CreatureProfile.objects.count() == 0


def test_echec_preserve_les_donnees_prealables() -> None:
    """Un échec ne touche pas les fiches déjà en base."""
    existante = create_entity(name="Existante", slug="existante")

    with pytest.raises(ValidationError):
        create_entity_with_profile(
            entity_data=entity_payload(entity_type=EntityType.CREATURE),
            profile_data={"threat_level": "apocalyptic"},
        )

    assert [e.slug for e in Entity.objects.all()] == [existante.slug]


def test_entite_invalide_ne_cree_ni_entite_ni_profil() -> None:
    """Un échec sur l'entité elle-même n'écrit rien non plus."""
    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(gender="plasma"))

    assert Entity.objects.count() == 0
    assert DivinityProfile.objects.count() == 0


# --- Contraintes d'unicité ---------------------------------------------


def test_slug_duplique_est_refuse() -> None:
    """L'unicité du slug reste appliquée, et rien ne subsiste."""
    create_entity_with_profile(entity_data=entity_payload())

    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(name="Autre nom"))

    assert Entity.objects.count() == 1
    assert DivinityProfile.objects.count() == 1


def test_couple_nom_type_duplique_est_refuse() -> None:
    """La contrainte `(name, entity_type)` reste appliquée."""
    create_entity_with_profile(entity_data=entity_payload())

    with pytest.raises(ValidationError):
        create_entity_with_profile(entity_data=entity_payload(slug="shango-2"))

    assert Entity.objects.count() == 1


def test_meme_nom_sous_deux_types_reste_possible() -> None:
    """La contrainte porte sur le couple, pas sur le nom seul."""
    create_entity_with_profile(entity_data=entity_payload())
    create_entity_with_profile(
        entity_data=entity_payload(
            slug="shango-creature",
            entity_type=EntityType.CREATURE,
        )
    )

    assert Entity.objects.filter(name="Shango").count() == 2


# --- Entrées de l'appelant ---------------------------------------------


def test_les_dictionnaires_fournis_ne_sont_pas_modifies() -> None:
    """Le service ne mute pas les données de l'appelant."""
    entity_data = entity_payload()
    profile_data: dict[str, object] = {"cult_offerings": ["Yam"]}
    attendu_entite = dict(entity_data)
    attendu_profil = dict(profile_data)

    create_entity_with_profile(entity_data=entity_data, profile_data=profile_data)

    assert entity_data == attendu_entite
    assert profile_data == attendu_profil


# --- Portée de la garantie ---------------------------------------------


def test_l_orm_direct_contourne_encore_le_service() -> None:
    """Documente la limite : le service ne couvre que ses propres appels.

    Un `objects.create()` direct — comme l'administration ou un import mal
    écrit — produit toujours une entité sans profil. Couvrir ces chemins
    relève de la phase 4 ; ce test fixe l'état réel afin qu'il ne soit pas
    confondu avec une garantie globale.
    """
    orpheline = Entity.objects.create(
        name="Orpheline",
        slug="orpheline",
        entity_type=EntityType.DIVINITY,
        gender=Gender.MALE,
    )

    assert not hasattr(orpheline, "divinity_profile")
    assert DivinityProfile.objects.count() == 0


def test_le_type_peut_encore_changer_apres_creation() -> None:
    """Autre limite : le service ne verrouille pas `entity_type`.

    Après création, modifier le type laisse le profil d'origine en place. La
    cohérence dans le temps n'est pas garantie par cette fonction.
    """
    entity = create_entity_with_profile(entity_data=entity_payload())

    entity.entity_type = EntityType.HERO
    entity.save()
    stored = Entity.objects.get(pk=entity.pk)

    assert stored.entity_type == EntityType.HERO
    # Le profil de divinité subsiste, désormais incohérent avec le type.
    assert hasattr(stored, "divinity_profile")
    assert not hasattr(stored, "hero_profile")


def test_un_second_profil_reste_impossible_par_le_onetoone() -> None:
    """Le `OneToOneField` empêche un second profil du même type."""
    entity = create_entity_with_profile(entity_data=entity_payload())

    with pytest.raises(IntegrityError), transaction.atomic():
        DivinityProfile.objects.create(entity=entity)
