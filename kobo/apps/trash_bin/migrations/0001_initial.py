# Generated by Django 3.2.15 on 2023-03-07 16:10

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import kpi.fields.kpi_uid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_celery_beat', '0015_edit_solarschedule_events_choices'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectTrash',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('in_progress', 'IN PROGRESS'), ('pending', 'PENDING'), ('retry', 'RETRY'), ('failed', 'FAILED')], db_index=True, default='pending', max_length=11)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('date_modified', models.DateTimeField(default=django.utils.timezone.now)),
                ('metadata', models.JSONField(default=dict)),
                ('empty_manually', models.BooleanField(default=False)),
                ('delete_all', models.BooleanField(default=False)),
                ('uid', kpi.fields.kpi_uid.KpiUidField(uid_prefix='pt')),
                ('asset', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='trash', to='kpi.asset')),
                ('periodic_task', models.OneToOneField(null=True, on_delete=django.db.models.deletion.RESTRICT, to='django_celery_beat.periodictask')),
                ('request_author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'project',
                'verbose_name_plural': 'projects',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AccountTrash',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('in_progress', 'IN PROGRESS'), ('pending', 'PENDING'), ('retry', 'RETRY'), ('failed', 'FAILED')], db_index=True, default='pending', max_length=11)),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('date_modified', models.DateTimeField(default=django.utils.timezone.now)),
                ('metadata', models.JSONField(default=dict)),
                ('empty_manually', models.BooleanField(default=False)),
                ('delete_all', models.BooleanField(default=False)),
                ('uid', kpi.fields.kpi_uid.KpiUidField(uid_prefix='at')),
                ('periodic_task', models.OneToOneField(null=True, on_delete=django.db.models.deletion.RESTRICT, to='django_celery_beat.periodictask')),
                ('request_author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='trash', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
        ),
    ]