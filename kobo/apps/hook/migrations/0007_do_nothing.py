# Generated by Django 3.2.15 on 2023-04-07 23:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hook', '0006_rename_instance_id_to_submission_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hooklog',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[[0, 'Failed'], [1, 'Pending'], [2, 'Success']], default=1),
        ),
    ]
