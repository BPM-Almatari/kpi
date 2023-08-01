import json

from constance import config
from django.db import migrations


def reset_free_tier_thresholds(apps, schema_editor):
    # The constance defaults for FREE_TIER_THRESHOLDS changed, so we set existing config to the new default value
    thresholds = {
        'storage': None,
        'data': None,
        'transcription_minutes': None,
        'translation_chars': None,
    }
    setattr(config, 'FREE_TIER_THRESHOLDS', json.dumps(thresholds))


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0050_add_indexes_to_import_and_export_tasks'),
    ]

    operations = [
        migrations.RunPython(
            reset_free_tier_thresholds,
            migrations.RunPython.noop,
        )
    ]
