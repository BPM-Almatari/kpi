# Generated by Django 3.2.15 on 2023-04-19 18:44

from django.db import migrations
import kpi.fields.kpi_uid


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='id',
            field=kpi.fields.kpi_uid.KpiUidField(primary_key=True, serialize=False, uid_prefix='org'),
        ),
    ]