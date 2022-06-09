# Generated by Django 2.2.7 on 2020-12-23 20:15

from django.db import migrations
import kpi.fields.lazy_default_jsonb
import kpi.models.import_export_task


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0038_auto_20210917_1918'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='data_sharing',
            field=kpi.fields.lazy_default_jsonb.LazyDefaultJSONBField(default=dict),
        ),
        migrations.AddField(
            model_name='asset',
            name='paired_data',
            field=kpi.fields.lazy_default_jsonb.LazyDefaultJSONBField(default=dict),
        ),
    ]
