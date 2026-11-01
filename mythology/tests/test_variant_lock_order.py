"""Crossed `variant_of` assignments must not deadlock.

One genuinely concurrent scenario, on two database connections, bounded by a
PostgreSQL `lock_timeout` and by join timeouts so a regression fails fast
instead of hanging. It is **not** a stress battery, and it does not prove that
every possible interleaving is safe: it exercises the case the review
identified — two simultaneous writes needing the same two rows — and would
fail if those rows were acquired in opposite orders again.

This module runs with a real transactional database, so it keeps its own
`django_db(transaction=True)` marker instead of the module-wide marker used by
the other suites.
"""

import threading
from typing import Any

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from mythology.models import Entity
from mythology.tests.factories import create_divinity_profile, create_entity

PASSWORD = "synthetic-test-passphrase-7261"

#: Bornes du scénario : la base rend la main plutôt que d'attendre une ligne
#: indéfiniment, et le test échoue au lieu de bloquer la session.
LOCK_TIMEOUT = "5s"
JOIN_TIMEOUT = 30.0


def detail_url(slug: str) -> str:
    return reverse("managed-entity-detail", kwargs={"slug": slug})


def record(slug: str, name: str) -> Entity:
    """Create a consistent divinity record with its profile."""
    entity = create_entity(name=name, slug=slug)
    create_divinity_profile(entity)
    return entity


@pytest.mark.django_db(transaction=True)
def test_deux_patch_croises_ne_s_interbloquent_pas() -> None:
    """Patch two records into each other's variant, from two connections.

    Both requests need the same two rows. Acquiring them in one statement
    ordered by primary key is what keeps each from holding the row the other
    is waiting for.
    """
    # Un superutilisateur plutôt qu'un groupe : une base transactionnelle est
    # vidée, donc les groupes créés par la migration de données n'y sont pas.
    admin = User.objects.create_user(
        username="administratrice-verrous",
        password=PASSWORD,
        is_staff=True,
        is_superuser=True,
    )
    premiere = record("lock-one", "Lock One")
    seconde = record("lock-two", "Lock Two")

    barrier = threading.Barrier(2, timeout=JOIN_TIMEOUT)
    outcomes: dict[str, Any] = {}

    def patch_into_variant(key: str, slug: str, reference: Entity) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
            client = APIClient()
            client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(admin)}"
            )
            barrier.wait()
            response = client.patch(
                detail_url(slug), {"variant_of": str(reference.pk)}, format="json"
            )
            outcomes[key] = response.status_code
        except BaseException as error:  # noqa: BLE001
            # Un interblocage remonte ici en `OperationalError` ; le consigner
            # plutôt que le laisser tuer le thread silencieusement.
            outcomes[key] = repr(error)
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=patch_into_variant,
            args=("premiere", premiere.slug, seconde),
            daemon=True,
        ),
        threading.Thread(
            target=patch_into_variant,
            args=("seconde", seconde.slug, premiere),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_TIMEOUT)

    assert not any(thread.is_alive() for thread in threads), "requête bloquée"
    assert outcomes == {"premiere": 200, "seconde": 200}
    assert Entity.objects.get(pk=premiere.pk).variant_of_id == seconde.pk
    assert Entity.objects.get(pk=seconde.pk).variant_of_id == premiere.pk
