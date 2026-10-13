from django.contrib.auth import get_user_model
from django.db import models


def test_identifiant_est_le_username() -> None:
    """Le modèle conserve `username` comme identifiant de connexion."""
    assert get_user_model().USERNAME_FIELD == "username"


def test_cle_primaire_est_un_bigautofield() -> None:
    """La clé primaire est un `BigAutoField`, fixé dès la première migration."""
    primary_key = get_user_model()._meta.pk

    assert isinstance(primary_key, models.BigAutoField)
