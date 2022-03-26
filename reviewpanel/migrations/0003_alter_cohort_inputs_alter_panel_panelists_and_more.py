# Generated by Django 4.0.3 on 2022-03-26 16:25

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reviewpanel', '0002_alter_input_options_cohort_allow_skip'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cohort',
            name='inputs',
            field=models.ManyToManyField(blank=True, related_name='cohorts', related_query_name='cohort', to='reviewpanel.input'),
        ),
        migrations.AlterField(
            model_name='panel',
            name='panelists',
            field=models.ManyToManyField(blank=True, related_name='panels', related_query_name='panel', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='templatesection',
            name='scroll',
            field=models.BooleanField(default=False),
        ),
    ]
