# Generated by Django 4.0.3 on 2022-03-24 01:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviewpanel', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='input',
            options={'ordering': ['form', '_rank']},
        ),
        migrations.AddField(
            model_name='cohort',
            name='allow_skip',
            field=models.BooleanField(default=True),
        ),
    ]
