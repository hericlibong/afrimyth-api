"""Tests de la navigation dans la collection publique.

Pagination, recherche et filtres. Toutes les fiches sont **synthétiques et
publiées dans la base de test** : les brouillons réels du corpus ne sont
jamais publiés pour illustrer ces fonctions.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mythology.models import CulturalAreaKind, Entity, EntityStatus, EntityType
from mythology.selectors import descendant_area_ids
from mythology.tests.factories import (
    create_country,
    create_cultural_area,
    create_entity,
    create_published_entity,
    create_source,
)

pytestmark = pytest.mark.django_db

LIST_URL = reverse("entity-list")


def slugs_of(response_json: dict[str, object]) -> list[str]:
    """Extrait les slugs de `results`, dans l'ordre de la réponse."""
    results = response_json["results"]
    assert isinstance(results, list)
    return [item["slug"] for item in results]


def publish_many(count: int, *, prefix: str = "figure") -> None:
    """Crée `count` fiches publiées, nommées de façon ordonnable."""
    for index in range(count):
        create_published_entity(
            name=f"{prefix} {index:03d}", slug=f"{prefix}-{index:03d}"
        )


# --- Pagination ---------------------------------------------------------


def test_enveloppe_de_pagination(client: Client) -> None:
    """La liste renvoie l'enveloppe DRF, non plus un tableau brut.

    Changement assumé du contrat de liste.
    """
    create_published_entity()

    payload = client.get(LIST_URL).json()

    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert payload["next"] is None
    assert payload["previous"] is None


def test_collection_vide(client: Client) -> None:
    """Sans fiche publiée, l'enveloppe reste présente et cohérente."""
    create_entity(name="Brouillon", slug="brouillon")

    payload = client.get(LIST_URL).json()

    assert payload == {"count": 0, "next": None, "previous": None, "results": []}


def test_pagination_sur_plusieurs_pages(client: Client) -> None:
    """Vingt fiches par page, et les liens de navigation suivent."""
    publish_many(45)

    premiere = client.get(LIST_URL).json()
    assert premiere["count"] == 45
    assert len(premiere["results"]) == 20
    assert premiere["previous"] is None
    assert premiere["next"] is not None

    deuxieme = client.get(LIST_URL, {"page": 2}).json()
    assert len(deuxieme["results"]) == 20
    assert deuxieme["previous"] is not None

    troisieme = client.get(LIST_URL, {"page": 3}).json()
    assert len(troisieme["results"]) == 5
    assert troisieme["next"] is None


def test_les_pages_ne_se_chevauchent_pas(client: Client) -> None:
    """Les trois pages couvrent l'ensemble, sans doublon ni manque."""
    publish_many(45)

    collectes: list[str] = []
    for page in (1, 2, 3):
        collectes += slugs_of(client.get(LIST_URL, {"page": page}).json())

    assert len(collectes) == 45
    assert len(set(collectes)) == 45
    assert collectes == sorted(collectes)


def test_page_inexistante_renvoie_404(client: Client) -> None:
    """Comportement standard de DRF, conservé tel quel."""
    publish_many(3)

    response = client.get(LIST_URL, {"page": 99})

    assert response.status_code == 404


def test_page_invalide_renvoie_404(client: Client) -> None:
    publish_many(3)

    assert client.get(LIST_URL, {"page": "abc"}).status_code == 404


def test_ordre_stable_avec_des_noms_egaux(client: Client) -> None:
    """Deux figures homonymes gardent un ordre déterministe.

    `name` seul ne suffirait pas : l'`id` départage, sans quoi une fiche
    pourrait changer de page d'une requête à l'autre.
    """
    for index, entity_type in enumerate(
        [EntityType.DIVINITY, EntityType.HERO, EntityType.CREATURE]
    ):
        create_published_entity(
            name="Homonyme", slug=f"homonyme-{index}", entity_type=entity_type
        )

    premier = slugs_of(client.get(LIST_URL).json())
    second = slugs_of(client.get(LIST_URL).json())

    assert premier == second
    attendu = sorted(Entity.objects.values_list("id", flat=True))
    assert premier == [Entity.objects.get(id=identifier).slug for identifier in attendu]


def test_les_parametres_sont_conserves_dans_les_liens(client: Client) -> None:
    """Filtres et recherche survivent à la navigation entre pages."""
    publish_many(25, prefix="hero")
    for entity in Entity.objects.all():
        entity.entity_type = EntityType.HERO
        entity.save(update_fields=["entity_type"])

    filtres: dict[str, str] = {"entity_type": EntityType.HERO, "search": "hero"}
    payload = client.get(LIST_URL, filtres).json()

    assert payload["next"] is not None
    assert "entity_type=hero" in payload["next"]
    assert "search=hero" in payload["next"]

    page2 = client.get(LIST_URL, {**filtres, "page": "2"}).json()
    assert page2["previous"] is not None
    assert "entity_type=hero" in page2["previous"]


# --- Recherche ----------------------------------------------------------


@pytest.mark.parametrize(
    ("champ", "valeur", "terme"),
    [
        ("name", "Anansi", "anansi"),
        ("category", "Trickster Spirit", "trickster"),
        ("cultural_role", "Master Weaver", "weaver"),
        ("story_description", "The clever son of the sky god", "clever"),
    ],
)
def test_recherche_dans_les_quatre_champs(
    client: Client, champ: str, valeur: str, terme: str
) -> None:
    """La recherche couvre les quatre champs publics, sans casse."""
    champs: dict[str, str] = {"name": "Cible", "slug": "cible"}
    champs[champ] = valeur
    create_published_entity(**champs)
    create_published_entity(name="Autre", slug="autre")

    payload = client.get(LIST_URL, {"search": terme}).json()

    assert slugs_of(payload) == ["cible"]
    assert payload["count"] == 1


def test_recherche_sans_resultat(client: Client) -> None:
    """Aucun résultat donne une enveloppe vide, pas une erreur."""
    create_published_entity()

    payload = client.get(LIST_URL, {"search": "introuvable"}).json()

    assert payload["count"] == 0
    assert payload["results"] == []


def test_recherche_vide_ne_filtre_pas(client: Client) -> None:
    create_published_entity()

    assert client.get(LIST_URL, {"search": ""}).json()["count"] == 1


def test_la_recherche_ignore_les_champs_non_publics(client: Client) -> None:
    """Notes de revue, sources et fiches liées ne sont pas interrogées.

    Une recherche ne doit pas devenir un chemin d'accès indirect vers des
    données que l'API n'expose pas.
    """
    entity = create_published_entity(review_notes="motcledinterne")
    create_source(entity, label="motcledesource")

    assert client.get(LIST_URL, {"search": "motcledinterne"}).json()["count"] == 0
    assert client.get(LIST_URL, {"search": "motcledesource"}).json()["count"] == 0


def test_la_recherche_ne_voit_pas_les_fiches_privees(client: Client) -> None:
    """Les fiches non publiées restent hors des résultats **et** du compte."""
    create_entity(name="Anansi brouillon", slug="anansi-brouillon")
    supprimee = create_published_entity(name="Anansi supprimé", slug="anansi-supprime")
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    payload = client.get(LIST_URL, {"search": "anansi"}).json()

    assert payload["count"] == 0
    assert payload["results"] == []


# --- Filtre entity_type ------------------------------------------------


def test_filtre_entity_type(client: Client) -> None:
    create_published_entity(name="Une divinité", slug="divinite")
    create_published_entity(name="Un héros", slug="heros", entity_type=EntityType.HERO)
    create_published_entity(
        name="Une créature", slug="creature", entity_type=EntityType.CREATURE
    )

    payload = client.get(LIST_URL, {"entity_type": EntityType.HERO}).json()

    assert slugs_of(payload) == ["heros"]
    assert payload["count"] == 1


def test_entity_type_vide_ne_filtre_pas(client: Client) -> None:
    create_published_entity()

    assert client.get(LIST_URL, {"entity_type": ""}).json()["count"] == 1


def test_entity_type_inconnu_renvoie_400(client: Client) -> None:
    """Un type hors des trois valeurs est une erreur d'appel."""
    response = client.get(LIST_URL, {"entity_type": "titan"})

    assert response.status_code == 400
    message = response.json()["entity_type"][0]
    assert message == (
        "Unknown entity type 'titan'. Expected one of: divinity, hero, creature."
    )


# --- Filtre country ----------------------------------------------------


def test_filtre_country_sur_le_pays_principal(client: Client) -> None:
    nigeria = create_country()
    create_published_entity(name="Au Nigeria", slug="nigeria", primary_country=nigeria)
    create_published_entity(name="Ailleurs", slug="ailleurs")

    payload = client.get(LIST_URL, {"country": "NG"}).json()

    assert slugs_of(payload) == ["nigeria"]


def test_filtre_country_sur_un_pays_secondaire(client: Client) -> None:
    """Le filtre couvre aussi les rattachements secondaires."""
    benin = create_country(name="Benin", slug="benin", iso_code="BJ")
    entity = create_published_entity(name="Composite", slug="composite")
    entity.secondary_countries.add(benin)

    payload = client.get(LIST_URL, {"country": "BJ"}).json()

    assert slugs_of(payload) == ["composite"]


def test_filtre_country_est_insensible_a_la_casse(client: Client) -> None:
    """Le code est normalisé en majuscules avant comparaison."""
    create_published_entity(
        name="Au Nigeria", slug="nigeria", primary_country=create_country()
    )

    assert client.get(LIST_URL, {"country": "ng"}).json()["count"] == 1


def test_aucun_doublon_quand_les_deux_rattachements_correspondent(
    client: Client,
) -> None:
    """Une fiche liée deux fois au même pays n'apparaît qu'une fois.

    Sans `distinct()`, la jointure multiple dupliquerait la ligne dans
    `results` **et** gonflerait `count`.
    """
    nigeria = create_country()
    entity = create_published_entity(
        name="Deux fois", slug="deux-fois", primary_country=nigeria
    )
    entity.secondary_countries.add(nigeria)
    # Le pays principal correspond : les deux lignes de jointure secondaire
    # passent le OU. Sans distinct(), la fiche serait réellement dupliquée.
    entity.secondary_countries.add(
        create_country(name="Ghana", slug="ghana", iso_code="GH")
    )

    payload = client.get(LIST_URL, {"country": "NG"}).json()

    assert payload["count"] == 1
    assert slugs_of(payload) == ["deux-fois"]


def test_country_bien_forme_mais_absent_donne_une_liste_vide(client: Client) -> None:
    """Un code inconnu ne révèle pas quels pays sont enregistrés."""
    create_published_entity(primary_country=create_country())

    payload = client.get(LIST_URL, {"country": "ZZ"}).json()

    assert payload["count"] == 0
    assert payload["results"] == []


@pytest.mark.parametrize("valeur", ["N", "NGA", "N1", "12"])
def test_country_mal_forme_renvoie_400(client: Client, valeur: str) -> None:
    response = client.get(LIST_URL, {"country": valeur})

    assert response.status_code == 400
    assert "ISO 3166-1 alpha-2" in response.json()["country"][0]


def test_country_vide_ne_filtre_pas(client: Client) -> None:
    create_published_entity()

    assert client.get(LIST_URL, {"country": ""}).json()["count"] == 1


# --- Filtre cultural_area ----------------------------------------------


def test_filtre_cultural_area_sur_l_aire_principale(client: Client) -> None:
    area = create_cultural_area()
    create_published_entity(
        name="En Afrique de l'Ouest", slug="ouest", primary_cultural_area=area
    )
    create_published_entity(name="Ailleurs", slug="ailleurs")

    payload = client.get(LIST_URL, {"cultural_area": "west-africa"}).json()

    assert slugs_of(payload) == ["ouest"]


def test_filtre_cultural_area_sur_une_aire_secondaire(client: Client) -> None:
    diaspora = create_cultural_area(
        name="Diaspora", slug="diaspora", kind=CulturalAreaKind.DIASPORIC
    )
    entity = create_published_entity(name="Diasporique", slug="diasporique")
    entity.secondary_cultural_areas.add(diaspora)

    payload = client.get(LIST_URL, {"cultural_area": "diaspora"}).json()

    assert slugs_of(payload) == ["diasporique"]


def test_filtre_cultural_area_inclut_les_descendants(client: Client) -> None:
    """`central-africa` inclut une fiche rattachée à `congo-basin`.

    La hiérarchie est lue dans `parent`, sans qu'aucun nom de région soit
    codé en dur.
    """
    centrale = create_cultural_area(name="Central Africa", slug="central-africa")
    bassin = create_cultural_area(
        name="Congo Basin", slug="congo-basin", parent=centrale
    )
    create_published_entity(
        name="Dans le bassin", slug="bassin", primary_cultural_area=bassin
    )

    payload = client.get(LIST_URL, {"cultural_area": "central-africa"}).json()

    assert slugs_of(payload) == ["bassin"]


def test_filtre_cultural_area_descend_sur_plusieurs_niveaux(client: Client) -> None:
    """La traversée fonctionne à trois niveaux, et au-delà."""
    niveau1 = create_cultural_area(name="Level 1", slug="level-1")
    niveau2 = create_cultural_area(name="Level 2", slug="level-2", parent=niveau1)
    niveau3 = create_cultural_area(name="Level 3", slug="level-3", parent=niveau2)
    niveau4 = create_cultural_area(name="Level 4", slug="level-4", parent=niveau3)
    create_published_entity(
        name="Tout en bas", slug="tout-en-bas", primary_cultural_area=niveau4
    )

    payload = client.get(LIST_URL, {"cultural_area": "level-1"}).json()

    assert slugs_of(payload) == ["tout-en-bas"]


def test_filtre_cultural_area_ne_remonte_pas_la_hierarchie(client: Client) -> None:
    """Demander une sous-région n'inclut pas sa région parente."""
    centrale = create_cultural_area(name="Central Africa", slug="central-africa")
    bassin = create_cultural_area(
        name="Congo Basin", slug="congo-basin", parent=centrale
    )
    create_published_entity(
        name="Région", slug="region", primary_cultural_area=centrale
    )
    create_published_entity(
        name="Sous-région", slug="sous-region", primary_cultural_area=bassin
    )

    payload = client.get(LIST_URL, {"cultural_area": "congo-basin"}).json()

    assert slugs_of(payload) == ["sous-region"]


def test_aucun_doublon_avec_une_aire_principale_et_secondaire(client: Client) -> None:
    """Deux rattachements dans la même hiérarchie ne dupliquent pas la fiche."""
    centrale = create_cultural_area(name="Central Africa", slug="central-africa")
    bassin = create_cultural_area(
        name="Congo Basin", slug="congo-basin", parent=centrale
    )
    entity = create_published_entity(
        name="Deux rattachements", slug="deux", primary_cultural_area=centrale
    )
    entity.secondary_cultural_areas.add(bassin)
    autre_bassin = create_cultural_area(
        name="Other Basin", slug="other-basin", parent=centrale
    )
    entity.secondary_cultural_areas.add(autre_bassin)

    payload = client.get(LIST_URL, {"cultural_area": "central-africa"}).json()

    assert payload["count"] == 1
    assert slugs_of(payload) == ["deux"]


def test_cultural_area_absente_donne_une_liste_vide(client: Client) -> None:
    """Un slug inconnu ne produit ni erreur ni divulgation."""
    create_published_entity(primary_cultural_area=create_cultural_area())

    payload = client.get(LIST_URL, {"cultural_area": "atlantide"}).json()

    assert payload["count"] == 0
    assert payload["results"] == []


def test_cultural_area_vide_ne_filtre_pas(client: Client) -> None:
    create_published_entity()

    assert client.get(LIST_URL, {"cultural_area": ""}).json()["count"] == 1


def test_un_cycle_de_hierarchie_ne_boucle_pas() -> None:
    """Un cycle accidentel dans `parent` ne provoque pas de boucle infinie.

    La contrainte de base interdit l'auto-parentage direct, mais pas un cycle
    A → B → A. La traversée exclut les identifiants déjà vus, ce qui suffit
    sans modifier le modèle.
    """
    a = create_cultural_area(name="Area A", slug="area-a")
    b = create_cultural_area(name="Area B", slug="area-b", parent=a)
    a.parent = b
    a.save()

    identifiants = descendant_area_ids("area-a")

    assert identifiants == {a.pk, b.pk}


def test_aucun_pays_n_est_deduit_d_une_aire(client: Client) -> None:
    """Filtrer par aire ne renseigne aucun pays : les filtres sont distincts."""
    bassin = create_cultural_area(name="Congo Basin", slug="congo-basin")
    create_published_entity(
        name="Sans pays", slug="sans-pays", primary_cultural_area=bassin
    )

    par_aire = client.get(LIST_URL, {"cultural_area": "congo-basin"}).json()
    par_pays = client.get(LIST_URL, {"country": "CD"}).json()

    assert par_aire["count"] == 1
    assert par_pays["count"] == 0
    assert Entity.objects.get(slug="sans-pays").primary_country is None


# --- Combinaisons -------------------------------------------------------


def test_les_filtres_se_combinent_par_et(client: Client) -> None:
    """Trois filtres et une recherche, tous appliqués simultanément."""
    nigeria = create_country()
    ouest = create_cultural_area()
    attendue = create_published_entity(
        name="Anansi cible",
        slug="cible",
        entity_type=EntityType.HERO,
        primary_country=nigeria,
        primary_cultural_area=ouest,
    )
    # Chaque leurre ne diffère que par un seul critère.
    create_published_entity(
        name="Anansi mauvaise aire",
        slug="mauvaise-aire",
        entity_type=EntityType.HERO,
        primary_country=nigeria,
        primary_cultural_area=create_cultural_area(
            name="East Africa", slug="east-africa"
        ),
    )
    create_published_entity(
        name="Anansi mauvais type",
        slug="mauvais-type",
        primary_country=nigeria,
        primary_cultural_area=ouest,
    )
    create_published_entity(
        name="Anansi mauvais pays",
        slug="mauvais-pays",
        entity_type=EntityType.HERO,
        primary_country=create_country(name="Ghana", slug="ghana", iso_code="GH"),
        primary_cultural_area=ouest,
    )
    create_published_entity(
        name="Autre nom",
        slug="autre-nom",
        entity_type=EntityType.HERO,
        primary_country=nigeria,
        primary_cultural_area=ouest,
    )

    payload = client.get(
        LIST_URL,
        {
            "search": "anansi",
            "entity_type": EntityType.HERO,
            "country": "NG",
            "cultural_area": "west-africa",
        },
    ).json()

    assert slugs_of(payload) == [attendue.slug]
    assert payload["count"] == 1


def test_une_combinaison_sans_correspondance_donne_une_liste_vide(
    client: Client,
) -> None:
    create_published_entity(
        name="Divinité", slug="divinite", primary_country=create_country()
    )

    payload = client.get(
        LIST_URL, {"entity_type": EntityType.HERO, "country": "NG"}
    ).json()

    assert payload["count"] == 0


def test_la_pagination_compte_apres_filtrage(client: Client) -> None:
    """`count` ne compte que les fiches publiques correspondant aux filtres."""
    publish_many(25, prefix="hero")
    for entity in Entity.objects.all():
        entity.entity_type = EntityType.HERO
        entity.save(update_fields=["entity_type"])
    publish_many(5, prefix="divinity")

    total = client.get(LIST_URL).json()
    heros = client.get(LIST_URL, {"entity_type": EntityType.HERO}).json()

    assert total["count"] == 30
    assert heros["count"] == 25
    assert len(heros["results"]) == 20


@pytest.mark.parametrize(
    "parametres",
    [
        {"search": "cachee"},
        {"entity_type": EntityType.DIVINITY},
        {"country": "NG"},
        {"cultural_area": "west-africa"},
    ],
)
def test_aucun_filtre_ne_divulgue_une_fiche_privee(
    client: Client, parametres: dict[str, str]
) -> None:
    """Les fiches privées et supprimées restent hors des résultats et du compte.

    La règle de visibilité s'applique **avant** les filtres : aucun paramètre
    ne peut servir de contournement.
    """
    nigeria = create_country()
    ouest = create_cultural_area()
    for status in (EntityStatus.DRAFT, EntityStatus.SUBMITTED, EntityStatus.REJECTED):
        create_entity(
            name=f"Cachee {status}",
            slug=f"cachee-{status}",
            status=status,
            primary_country=nigeria,
            primary_cultural_area=ouest,
        )
    supprimee = create_published_entity(
        name="Cachee supprimee",
        slug="cachee-supprimee",
        primary_country=nigeria,
        primary_cultural_area=ouest,
    )
    supprimee.deleted_at = timezone.now()
    supprimee.save()

    payload = client.get(LIST_URL, parametres).json()

    assert payload["count"] == 0
    assert payload["results"] == []
    assert "cachee" not in client.get(LIST_URL, parametres).content.decode().lower()


# --- Portée : la liste seulement ---------------------------------------


@pytest.mark.parametrize(
    "parametres",
    [
        {"search": "introuvable"},
        {"entity_type": EntityType.CREATURE},
        {"country": "ZZ"},
        {"cultural_area": "atlantide"},
        {"page": "99"},
    ],
)
def test_les_parametres_de_liste_n_affectent_pas_le_detail(
    client: Client, parametres: dict[str, str]
) -> None:
    """Le détail ne dépend que de la visibilité publique du slug demandé."""
    entity = create_published_entity(name="Shango", slug="shango")

    response = client.get(
        reverse("entity-detail", kwargs={"slug": entity.slug}), parametres
    )

    assert response.status_code == 200
    assert response.json()["slug"] == "shango"


def test_le_detail_n_est_pas_pagine(client: Client) -> None:
    """La forme du détail est inchangée : pas d'enveloppe de pagination."""
    entity = create_published_entity()

    payload = client.get(reverse("entity-detail", kwargs={"slug": entity.slug})).json()

    assert "results" not in payload
    assert "count" not in payload
    assert payload["slug"] == entity.slug


def test_l_endpoint_de_sante_est_inchange(client: Client) -> None:
    """La santé ne prend ni pagination ni filtre."""
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_les_ecritures_restent_refusees(client: Client, method: str) -> None:
    """La navigation n'ouvre aucune écriture."""
    response = getattr(client, method)(LIST_URL, {"search": "x"})

    assert response.status_code == 405


# --- Coût en requêtes ---------------------------------------------------


def test_cout_de_la_liste_sans_filtre(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Deux requêtes : le comptage de la pagination, puis la page.

    Le coût ne dépend **pas** du nombre de fiches : la liste n'expose ni
    profil, ni référentiel, ni relation, donc aucune requête par entité.
    """
    publish_many(30)

    with django_assert_num_queries(2):
        client.get(LIST_URL)


def test_cout_de_la_liste_filtree_par_aire(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Le filtre d'aire ajoute le coût de la traversée de la hiérarchie.

    Décompte : 1 requête pour la racine de l'aire, puis 1 par niveau de
    descendants — ici deux niveaux, dont le dernier vide —, puis le comptage
    et la page. Ce coût dépend de la profondeur de la hiérarchie, jamais du
    nombre de fiches.
    """
    centrale = create_cultural_area(name="Central Africa", slug="central-africa")
    bassin = create_cultural_area(
        name="Congo Basin", slug="congo-basin", parent=centrale
    )
    for index in range(25):
        create_published_entity(
            name=f"Figure {index:03d}",
            slug=f"figure-{index:03d}",
            primary_cultural_area=bassin,
        )

    with django_assert_num_queries(5):
        response = client.get(LIST_URL, {"cultural_area": "central-africa"})

    assert response.json()["count"] == 25


def test_le_cout_ne_croit_pas_avec_le_nombre_de_fiches(
    client: Client,
    django_assert_num_queries: Callable[[int], AbstractContextManager[None]],
) -> None:
    """Même budget pour 5 et pour 30 fiches : aucune requête par entité."""
    publish_many(5)
    with django_assert_num_queries(2):
        client.get(LIST_URL)

    publish_many(25, prefix="autre")
    with django_assert_num_queries(2):
        client.get(LIST_URL)
