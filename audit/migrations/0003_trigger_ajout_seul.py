"""Sous PostgreSQL, interdit UPDATE et DELETE sur le journal d'audit au niveau de la base."""

from django.db import migrations

FONCTION = """
CREATE OR REPLACE FUNCTION audit_ajout_seul() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Le journal d''audit est en ajout seul';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_entreeaudit_ajout_seul
  BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_entreeaudit
  FOR EACH STATEMENT EXECUTE FUNCTION audit_ajout_seul();
"""

SUPPRESSION = """
DROP TRIGGER IF EXISTS audit_entreeaudit_ajout_seul ON audit_entreeaudit;
DROP FUNCTION IF EXISTS audit_ajout_seul();
"""


def creer(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FONCTION)


def supprimer(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SUPPRESSION)


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_initial")]
    operations = [migrations.RunPython(creer, supprimer)]
