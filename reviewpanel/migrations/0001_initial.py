# Generated by Django 4.0.3 on 2022-03-22 17:55

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('formative', '0006_alter_formblock__rank'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cohort',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('message', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('inactive', 'inactive'), ('active', 'active'), ('completed', 'completed')], default='inactive', max_length=16)),
                ('panel_weight', models.FloatField(default=1.0)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('activated', models.DateTimeField(blank=True, editable=False, null=True)),
                ('completed', models.DateTimeField(blank=True, editable=False, null=True)),
                ('form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohorts', related_query_name='cohort', to='formative.form')),
            ],
        ),
        migrations.CreateModel(
            name='Input',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_rank', models.IntegerField(verbose_name='')),
                ('name', models.SlugField(allow_unicode=True, max_length=32)),
                ('label', models.CharField(blank=True, max_length=32)),
                ('type', models.CharField(choices=[('num', 'numeric'), ('bool', 'true/false'), ('text', 'text')], default='num', max_length=16)),
                ('min_num', models.PositiveIntegerField(blank=True, null=True)),
                ('max_num', models.PositiveIntegerField(blank=True, null=True)),
                ('max_chars', models.PositiveIntegerField(blank=True, null=True)),
                ('form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inputs', related_query_name='input', to='formative.form')),
            ],
        ),
        migrations.CreateModel(
            name='Presentation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(allow_unicode=True, max_length=32, verbose_name='identifier')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='presentations', related_query_name='presentation', to='formative.form')),
            ],
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(allow_unicode=True, max_length=32, verbose_name='identifier')),
                ('max_width', models.PositiveIntegerField(default=0)),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', related_query_name='template', to='formative.program')),
            ],
        ),
        migrations.CreateModel(
            name='TemplateSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(allow_unicode=32, max_length=32, verbose_name='identifier')),
                ('x', models.DecimalField(decimal_places=3, default='0.000', max_digits=7, verbose_name='left %')),
                ('y', models.DecimalField(decimal_places=3, default='0.000', max_digits=7, verbose_name='top %')),
                ('w', models.DecimalField(decimal_places=3, default='100.000', max_digits=7, verbose_name='width %')),
                ('h', models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True, verbose_name='height')),
                ('wrap', models.BooleanField(default=True)),
                ('scroll', models.BooleanField(default=True)),
                ('font', models.CharField(blank=True, default='100% sans-serif', max_length=64)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', related_query_name='section', to='reviewpanel.template')),
            ],
        ),
        migrations.CreateModel(
            name='Score',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.UUIDField()),
                ('value', models.PositiveIntegerField(blank=True, null=True)),
                ('text', models.CharField(blank=True, max_length=1000)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('cohort', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', related_query_name='score', to='reviewpanel.cohort')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', related_query_name='score', to='formative.form')),
                ('input', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', related_query_name='score', to='reviewpanel.input')),
                ('panelist', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scores', related_query_name='score', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Reference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_rank', models.IntegerField(verbose_name='')),
                ('collection', models.SlugField(allow_unicode=True, blank=True, max_length=32)),
                ('name', models.SlugField(allow_unicode=True, blank=True, max_length=32)),
                ('field', models.CharField(blank=True, max_length=32)),
                ('block_label', models.CharField(blank=True, max_length=256)),
                ('inline_label', models.CharField(blank=True, max_length=128)),
                ('options', models.JSONField(blank=True, default=dict)),
                ('block_combine', models.BooleanField(default=False)),
                ('inline_combine', models.CharField(blank=True, max_length=16)),
                ('presentation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refereneces', related_query_name='reference', to='reviewpanel.presentation')),
                ('section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='reviewpanel.templatesection')),
                ('select_section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='reviewpanel.templatesection')),
            ],
            options={
                'ordering': ['presentation', '_rank'],
            },
        ),
        migrations.AddField(
            model_name='presentation',
            name='template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='presentations', related_query_name='presentation', to='reviewpanel.template'),
        ),
        migrations.CreateModel(
            name='Panel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('panelists', models.ManyToManyField(related_name='panels', related_query_name='panel', to=settings.AUTH_USER_MODEL)),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='panels', related_query_name='panel', to='formative.program')),
            ],
        ),
        migrations.CreateModel(
            name='CohortMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.UUIDField()),
                ('cohort', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='reviewpanel.cohort')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
        ),
        migrations.AddField(
            model_name='cohort',
            name='inputs',
            field=models.ManyToManyField(related_name='cohorts', related_query_name='cohort', to='reviewpanel.input'),
        ),
        migrations.AddField(
            model_name='cohort',
            name='panel',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cohorts', related_query_name='cohort', to='reviewpanel.panel'),
        ),
        migrations.AddField(
            model_name='cohort',
            name='presentation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cohorts', related_query_name='cohort', to='reviewpanel.presentation'),
        ),
        migrations.AddConstraint(
            model_name='templatesection',
            constraint=models.UniqueConstraint(fields=('template', 'name'), name='unique_template_name'),
        ),
        migrations.AddConstraint(
            model_name='template',
            constraint=models.UniqueConstraint(fields=('program', 'name'), name='unique_program_slug'),
        ),
        migrations.AddConstraint(
            model_name='score',
            constraint=models.UniqueConstraint(fields=('panelist', 'object_id', 'cohort', 'input'), name='unique_panelist_submission_cohort_input'),
        ),
        migrations.AddConstraint(
            model_name='reference',
            constraint=models.UniqueConstraint(fields=('presentation', '_rank'), name='unique_presentation_rank'),
        ),
        migrations.AddConstraint(
            model_name='presentation',
            constraint=models.UniqueConstraint(fields=('form', 'name'), name='unique_form_slug'),
        ),
        migrations.AddConstraint(
            model_name='panel',
            constraint=models.UniqueConstraint(fields=('program', 'name'), name='unique_panel_name'),
        ),
        migrations.AddConstraint(
            model_name='input',
            constraint=models.UniqueConstraint(fields=('form', '_rank'), name='unique_form_rank'),
        ),
        migrations.AddConstraint(
            model_name='input',
            constraint=models.UniqueConstraint(fields=('form', 'name'), name='unique_input_name'),
        ),
        migrations.AddConstraint(
            model_name='cohort',
            constraint=models.UniqueConstraint(fields=('form', 'name'), name='unique_cohort_name'),
        ),
    ]
