from django.db import migrations

ROLES = ["RSSI", "DSI", "Référent interne", "Référent applicatif", "Référent technique"]


def creer_groupes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nom in ROLES:
        Group.objects.get_or_create(name=nom)


class Migration(migrations.Migration):
    dependencies = [("comptes", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(creer_groupes, migrations.RunPython.noop)]
