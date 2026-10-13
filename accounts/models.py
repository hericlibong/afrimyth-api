from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Modèle utilisateur du projet.

    Volontairement minimal à ce stade : il hérite de `AbstractUser` sans champ
    supplémentaire. Son seul rôle dans cet incrément est d'être déclaré via
    `AUTH_USER_MODEL` dès la première migration, afin que les champs et les
    profils métier ajoutés plus tard n'imposent pas de migration d'un modèle
    utilisateur déjà en production.

    La clé primaire est un `BigAutoField`, fixé par `DEFAULT_AUTO_FIELD` et par
    `AccountsConfig.default_auto_field`.
    """
