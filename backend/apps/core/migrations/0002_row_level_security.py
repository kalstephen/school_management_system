"""PostgreSQL row-level security on every table that carries school_id.

The application sets `app.current_school` for each request (SchoolContextMiddleware).
When it is set, PostgreSQL only returns and accepts rows of that school, so a query that
forgets its school filter still cannot leak another school's data. When it is empty
(login, the public report-card check, platform administration) the policy allows the
query and the application's own filters apply.

Policies only bind a role that does not own the tables: run migrations as the owner and
the app as a separate role (DB_USER=sms_app). Does nothing on SQLite.
"""

from django.apps import apps as global_apps
from django.db import migrations

POLICY = """
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS school_isolation ON {table};
CREATE POLICY school_isolation ON {table}
    USING (
        coalesce(current_setting('app.current_school', true), '') = ''
        OR school_id = current_setting('app.current_school', true)::bigint
    )
    WITH CHECK (
        coalesce(current_setting('app.current_school', true), '') = ''
        OR school_id = current_setting('app.current_school', true)::bigint
    );
"""


def school_tables():
    for model in global_apps.get_models():
        if model._meta.app_label in ("admin", "auth", "contenttypes", "sessions"):
            continue
        if any(f.attname == "school_id" for f in model._meta.concrete_fields):
            yield model._meta.db_table


def enable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in school_tables():
        schema_editor.execute(POLICY.format(table=schema_editor.quote_name(table)))


def disable(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in school_tables():
        quoted = schema_editor.quote_name(table)
        schema_editor.execute(f"DROP POLICY IF EXISTS school_isolation ON {quoted}; ALTER TABLE {quoted} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        *[(label, "0001_initial") for label in (
            "accounts", "admissions", "assessment", "attendance", "communication", "curriculum", "discipline",
            "finance", "learners", "library", "promotion", "schoolsetup", "sickbay", "staff", "stores",
            "subscriptions", "sync", "timetable",
        )],
    ]

    operations = [migrations.RunPython(enable, disable)]
