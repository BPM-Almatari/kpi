# Generated by Django 2.2.27 on 2022-07-26 16:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('code', models.CharField(max_length=10)),
                ('featured', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'language',
                'ordering': ['-featured', 'name'],
            },
        ),
        migrations.CreateModel(
            name='LanguageRegion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('code', models.CharField(max_length=20, unique=True)),
                ('language', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regions', to='languages.Language')),
            ],
            options={
                'verbose_name': 'region',
                'ordering': ['code', 'name'],
            },
        ),
        migrations.CreateModel(
            name='TranscriptionService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(max_length=10, unique=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TranslationService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(max_length=10, unique=True)),
            ],
            options={
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TranslationServiceLanguageM2M',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mapping_code', models.CharField(blank=True, max_length=10, null=True)),
                ('language', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='languages.Language')),
                ('region', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='regions', to='languages.LanguageRegion')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', to='languages.TranslationService')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TranscriptionServiceLanguageM2M',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mapping_code', models.CharField(blank=True, max_length=10, null=True)),
                ('language', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='languages.Language')),
                ('region', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='languages.LanguageRegion')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', to='languages.TranscriptionService')),
            ],
            options={
                'unique_together': {('language', 'service', 'region')},
            },
        ),
        migrations.AddField(
            model_name='language',
            name='transcription_services',
            field=models.ManyToManyField(through='languages.TranscriptionServiceLanguageM2M', to='languages.TranscriptionService'),
        ),
        migrations.AddField(
            model_name='language',
            name='translation_services',
            field=models.ManyToManyField(through='languages.TranslationServiceLanguageM2M', to='languages.TranslationService'),
        ),
    ]