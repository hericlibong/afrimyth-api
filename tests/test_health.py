from django.test import Client
from django.urls import reverse


def test_health_est_public_et_repond_ok(client: Client) -> None:
    """L'endpoint de santé répond 200 sans authentification."""
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
