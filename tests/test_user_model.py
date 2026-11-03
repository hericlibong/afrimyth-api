from django.contrib.auth import get_user_model
from django.db import models


def test_identifiant_est_le_username() -> None:
    """The model keeps `username` as the login identifier."""
    assert get_user_model().USERNAME_FIELD == "username"


def test_cle_primaire_est_un_bigautofield() -> None:
    """The primary key is a `BigAutoField`, set from the very first migration."""
    primary_key = get_user_model()._meta.pk

    assert isinstance(primary_key, models.BigAutoField)
