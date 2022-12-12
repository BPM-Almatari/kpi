from django.conf import settings
from django.core.management import call_command
from django.db import migrations


def standarize_fields(apps, schema_editor):
    if settings.SKIP_HEAVY_MIGRATIONS:
        print(
            """
            !!! ATTENTION !!!
            If you have existing projects you need to run this management command:

               > python manage.py standarize_searcheable_jsonb_fields

            Otherwise, search with query parser will not be accurate.
            """
        )
    else:
        print(
            """
            This might take a while. If it is too slow, you may want to re-run the
            migration with SKIP_HEAVY_MIGRATIONS=True and run the management command
            (populate_assetversions) to prepare the versions.
            """
        )
        call_command('standardize_searchable_fields')


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0044_project_view_export_task'),
    ]

    # allow this command to be run backwards
    def noop(apps, schema_editor):
        pass

    operations = [
        migrations.RunPython(
            standarize_fields,
            noop,
        ),
    ]
