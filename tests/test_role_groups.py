"""Business role groups: the data migration, and the roles read from them."""

from importlib import import_module
from typing import Any

import pytest
from django.apps import apps as global_apps
from django.contrib.auth.models import AnonymousUser, Group

from accounts.models import User
from accounts.roles import (
    ADMINISTRATOR,
    BUSINESS_ROLE_NAMES,
    CONTRIBUTOR,
    REVIEWER,
    business_roles,
)

pytestmark = pytest.mark.django_db

PASSWORD = "synthetic-test-passphrase-3517"

# Le nom du module commence par un chiffre : il ne peut pas être importé par
# une instruction `import`, d'où le chargement dynamique.
role_groups_migration = import_module("accounts.migrations.0002_business_role_groups")


def account(username: str, *, groups: tuple[str, ...] = (), **flags: Any) -> User:
    """Create a synthetic account, optionally in the given groups."""
    user = User.objects.create_user(username=username, password=PASSWORD, **flags)
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


# --- The migration ------------------------------------------------------


def test_la_migration_a_cree_les_trois_groupes() -> None:
    """Create all three groups when migrating the database."""
    assert set(
        Group.objects.filter(name__in=BUSINESS_ROLE_NAMES).values_list(
            "name", flat=True
        )
    ) == set(BUSINESS_ROLE_NAMES)


def test_la_migration_et_le_code_nomment_les_memes_groupes() -> None:
    """Keep runtime role names consistent with the historical migration."""
    assert role_groups_migration.BUSINESS_ROLE_NAMES == BUSINESS_ROLE_NAMES


def test_la_migration_n_attache_aucune_permission_django() -> None:
    """Do not attach unused Django model permissions to business groups."""
    for group in Group.objects.filter(name__in=BUSINESS_ROLE_NAMES):
        assert group.permissions.count() == 0, group.name


def test_la_migration_n_affecte_aucun_compte() -> None:
    """Do not automatically assign roles when creating an account."""
    user = account("sans-groupe-apres-migration")

    assert user.groups.count() == 0


def test_rejouer_la_migration_reutilise_les_groupes_existants() -> None:
    """Preserve group identifiers when rerunning the migration."""
    before = dict(
        Group.objects.filter(name__in=BUSINESS_ROLE_NAMES).values_list("name", "id")
    )

    role_groups_migration.create_business_role_groups(global_apps, None)

    after = dict(
        Group.objects.filter(name__in=BUSINESS_ROLE_NAMES).values_list("name", "id")
    )
    assert after == before


def test_la_marche_arriere_ne_supprime_ni_groupe_ni_affectation() -> None:
    """Preserve groups and human assignments when migrating backwards."""
    user = account("relecteur-affecte", groups=(REVIEWER,))

    role_groups_migration.keep_business_role_groups(global_apps, None)

    assert Group.objects.filter(name__in=BUSINESS_ROLE_NAMES).count() == 3
    assert set(user.groups.values_list("name", flat=True)) == {REVIEWER}


# --- Roles read from the groups -----------------------------------------


def test_un_appelant_anonyme_ou_absent_n_a_aucun_role() -> None:
    assert business_roles(AnonymousUser()) == frozenset()
    assert business_roles(None) == frozenset()


def test_un_compte_sans_groupe_n_a_aucun_role() -> None:
    assert business_roles(account("ordinaire")) == frozenset()


def test_is_staff_seul_n_accorde_aucun_role_metier() -> None:
    """Do not equate staff status with a business role."""
    assert business_roles(account("staff", is_staff=True)) == frozenset()


def test_un_groupe_etranger_est_sans_effet() -> None:
    assert business_roles(account("etranger", groups=("newsletter",))) == frozenset()


def test_les_groupes_metier_se_cumulent_et_ignorent_les_etrangers() -> None:
    user = account("cumul", groups=(CONTRIBUTOR, REVIEWER, "newsletter"))

    assert business_roles(user) == frozenset({CONTRIBUTOR, REVIEWER})


def test_un_superutilisateur_sans_groupe_est_administrateur() -> None:
    """Treat active superusers as administrators, as specified in ADR 0004."""
    user = account("secours", is_staff=True, is_superuser=True)

    assert business_roles(user) == frozenset({ADMINISTRATOR})


def test_un_superutilisateur_conserve_ses_autres_groupes() -> None:
    user = account("super-contributeur", groups=(CONTRIBUTOR,), is_superuser=True)

    assert business_roles(user) == frozenset({CONTRIBUTOR, ADMINISTRATOR})


def test_un_compte_desactive_n_a_aucun_role() -> None:
    user = account("desactive", groups=(REVIEWER,), is_active=False)

    assert business_roles(user) == frozenset()


def test_les_roles_sont_relus_a_chaque_appel() -> None:
    """Apply group changes without a persistent role cache."""
    user = account("promu")
    assert business_roles(user) == frozenset()

    user.groups.add(Group.objects.get(name=REVIEWER))

    assert business_roles(user) == frozenset({REVIEWER})
