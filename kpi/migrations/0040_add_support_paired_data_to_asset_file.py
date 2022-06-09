# Generated by Django 2.2.7 on 2021-01-07 16:41

from django.db import migrations, models
import django.utils.timezone
import kpi.models.import_export_task
import private_storage.fields
import private_storage.storage.s3boto3


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0039_add_data_sharing_to_asset'),
    ]

    operations = [
        migrations.AddField(
            model_name='assetfile',
            name='date_modified',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='assetfile',
            name='file_type',
            field=models.CharField(choices=[('map_layer', 'map_layer'), ('form_media', 'form_media'), ('paired_data', 'paired_data')], max_length=32),
        ),
    ]
