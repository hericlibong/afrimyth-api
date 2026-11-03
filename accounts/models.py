from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model.

    Deliberately minimal at this stage: it inherits `AbstractUser` without any
    extra field. Its only role in this increment is to be declared through
    `AUTH_USER_MODEL` from the very first migration, so that the business
    fields and profiles added later do not force a migration of an already
    deployed user model.

    The primary key is a `BigAutoField`, set by `DEFAULT_AUTO_FIELD` and by
    `AccountsConfig.default_auto_field`.
    """
