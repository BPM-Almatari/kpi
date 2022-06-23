# Generated by Django 2.2.7 on 2021-09-17 19:18

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('kpi', '0038_auto_20210917_1918'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('veritree_id', models.PositiveIntegerField()),
                ('org_type', models.CharField(choices=[('ngo', 'ngo'), ('organization', 'organization')], default='organization', max_length=100)),
                ('assets', models.ManyToManyField(related_name='organizations', to='kpi.Asset')),
            ],
        ),
    ]
