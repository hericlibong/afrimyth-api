from django.test import Client
from django.urls import reverse


def test_health_est_public_et_repond_ok(client: Client) -> None:
    """The health endpoint answers 200 without authentication."""
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
