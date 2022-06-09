# Generated by Django 2.2.7 on 2022-03-09 02:18

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import kpi.fields.kpi_uid
import kpi.models.asset_file
import kpi.models.import_export_task
import private_storage.fields
import private_storage.storage.files


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('kpi', '0040_add_support_paired_data_to_asset_file'),
    ]

    operations = [
        migrations.CreateModel(
            name='SynchronousExport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', django.contrib.postgres.fields.jsonb.JSONField()),
                ('messages', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('status', models.CharField(choices=[('created', 'created'), ('processing', 'processing'), ('error', 'error'), ('complete', 'complete')], default='created', max_length=32)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('uid', kpi.fields.kpi_uid.KpiUidField(uid_prefix='e')),
                ('last_submission_time', models.DateTimeField(null=True)),
                ('result', private_storage.fields.PrivateFileField(max_length=380, storage=private_storage.storage.files.PrivateFileSystemStorage(), upload_to=kpi.models.import_export_task.export_upload_to)),
                ('format_type', models.CharField(choices=[('csv', 'csv'), ('xlsx', 'xlsx')], max_length=32)),
                ('asset_export_settings', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='kpi.AssetExportSettings')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'asset_export_settings', 'format_type')},
            },
        ),
    ]
