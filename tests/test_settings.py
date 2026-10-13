from django.conf import settings


def test_modele_utilisateur_personnalise_est_actif() -> None:
    """Le projet utilise bien le modèle utilisateur de l'app `accounts`."""
    assert settings.AUTH_USER_MODEL == "accounts.User"
