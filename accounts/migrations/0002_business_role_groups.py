"""Create the three business role groups of ADR 0002 and ADR 0004."""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

# Les noms sont recopiés ici volontairement plutôt qu'importés depuis
# `accounts.roles` : une migration doit rester lisible et rejouable telle
# qu'elle a été écrite, même si le code applicatif renomme ses constantes plus
# tard. Un test garde l'égalité entre les deux listes.
BUSINESS_ROLE_NAMES = ("contributor", "reviewer", "administrator")


def create_business_role_groups(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Create the three groups, reusing any that already exists.

    Only the groups are created. No Django permission is attached to them:
    the rights of this project are the business rules of ADR 0002, evaluated
    server-side from group membership, not the model-level permissions of the
    admin. Attaching unused permissions would suggest rights that no code
    reads.

    No account is added to any group, and no demonstration account is
    created: assignments are explicit, made by a human in the administration.
    """
    group_model = apps.get_model("auth", "Group")
    for name in BUSINESS_ROLE_NAMES:
        group_model.objects.get_or_create(name=name)


def keep_business_role_groups(
    apps: Apps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Deliberately do nothing when migrating backwards.

    Rolling back must stay reversible without destroying data. The groups may
    already have existed before this migration ran, and humans may have been
    assigned to them since. Deleting them here would silently drop those
    assignments, which a schema rollback has no mandate to do.

    Removing a group is therefore a deliberate administrative act, not a side
    effect of `migrate accounts 0001`.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        # Le modèle `Group` appartient à `django.contrib.auth` : sa dernière
        # migration doit être appliquée avant que l'on écrive dans sa table.
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            create_business_role_groups,
            keep_business_role_groups,
        ),
    ]
