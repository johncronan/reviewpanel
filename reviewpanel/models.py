from django.db import models
from django.db.models import UniqueConstraint, Subquery
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, \
    GenericRelation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from formative.models import Program, Form, RankedModel
from formative.utils import MarkdownFormatter, remove_p


markdown = MarkdownFormatter()


class Template(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['program', 'name'],
                             name='unique_program_slug')
        ]
    
    program = models.ForeignKey(Program, models.CASCADE,
                                related_name='templates',
                                related_query_name='template')
    name = models.SlugField(max_length=32, allow_unicode=True,
                            verbose_name='identifier')
    min_width = models.PositiveIntegerField(default=0)
    max_width = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.name


class TemplateSection(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['template', 'name'],
                             name='unique_template_name')
        ]
    
    template = models.ForeignKey(Template, models.CASCADE,
                                 related_name='sections',
                                 related_query_name='section')
    name = models.SlugField(max_length=32, allow_unicode=32,
                            verbose_name='identifier')
    x = models.DecimalField(max_digits=7, decimal_places=3, default='0.000',
                            verbose_name='left %')
    y = models.DecimalField(max_digits=7, decimal_places=3, default='0.000',
                            verbose_name='top %')
    w = models.DecimalField(max_digits=7, decimal_places=3, default='100.000',
                            verbose_name='width %')
    h = models.DecimalField(max_digits=7, decimal_places=3,
                            null=True, blank=True, verbose_name='height')
    wrap = models.BooleanField(default=True)
    scroll = models.BooleanField(default=False) # vert, or horizontal if no wrap
    font = models.CharField(max_length=64, blank=True,
                            default='100% sans-serif')
    
    def __str__(self):
        return self.name


class Presentation(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['form', 'name'], name='unique_form_slug')
        ]
    
    form = models.ForeignKey(Form, models.CASCADE,
                             related_name='presentations',
                             related_query_name='presentation')
    template = models.ForeignKey(Template, models.CASCADE,
                                 null=True, blank=True,
                                 related_name='presentations',
                                 related_query_name='presentation')
    name = models.SlugField(max_length=32, allow_unicode=True,
                            verbose_name='identifier')
    no_input = models.BooleanField(default=False)
    min_seconds = models.PositiveIntegerField(default=0)
    options = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def inputs_section(self):
        if self.no_input: return None
        return 'inputs'
    
    def show_stats(self):
        if 'hide_stats' in self.options: return False
        return True


class Reference(RankedModel):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['presentation', '_rank'],
                             name='unique_presentation_rank')
        ]
        ordering = ['presentation', '_rank']
    
    presentation = models.ForeignKey(Presentation, models.CASCADE,
                                     related_name='references',
                                     related_query_name='reference')
    # if no collection, name identifies the (stock or custom) block
    collection = models.SlugField(max_length=32, allow_unicode=True, blank=True)
    # if no name, reference is to the item file for the specified collection
    name = models.SlugField(max_length=32, allow_unicode=True, blank=True)
    # if a composite block, can also give a field name (e.g., state for address)
    field = models.CharField(max_length=32, blank=True)
    
    section = models.ForeignKey(TemplateSection, models.SET_NULL,
                                null=True, blank=True, related_name='+')
    block_label = models.CharField(max_length=256, blank=True) # in markdown
    inline_label = models.CharField(max_length=128, blank=True)
    options = models.JSONField(default=dict, blank=True)
    
    # fields used when a collection is specified:
    block_combine = models.BooleanField(default=False)
    inline_combine = models.CharField(max_length=16, blank=True) # separator
    # if not combined, and no select section specified, it's added to the bottom
    select_section = models.ForeignKey(TemplateSection, models.SET_NULL,
                                       null=True, blank=True, related_name='+')
    
    def __str__(self):
        if self.collection:
            if self.name: return ' '.join((self.collection, self.name))
            return self.collection + ' file'
        if self.field: return ' '.join((self.name, self.field))
        return self.name
    
    def rank_group(self):
        return Reference.objects.filter(presentation=self.presentation)
    
    @property
    def is_file(self):
        return self.collection and not self.name
    
    @property
    def combined(self):
        if self.block_combine or self.inline_combine: return True
        return False
    
    def id_string(self):
        str = ''
        if self.collection: str += self.collection + '_'
        if self.name: str += self.name
        else: str += 'file'
        
        return str
    
    def block_label_html(self):
        return mark_safe(markdown.convert(self.block_label))
    
    def inline_label_html(self):
        return mark_safe(remove_p(markdown.convert(self.inline_label)))


class Input(RankedModel):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['form', '_rank'], name='unique_form_rank'),
            UniqueConstraint(fields=['form', 'name'], name='unique_input_name')
        ]
        ordering = ['form', '_rank']
    
    MAX_TEXT_MAXLEN = 1000
    
    class InputType(models.TextChoices):
        NUMERIC = 'num', _('numeric')
        BOOLEAN = 'bool', _('true/false')
        TEXT = 'text', _('text')
    
    form = models.ForeignKey(Form, models.CASCADE,
                             related_name='inputs', related_query_name='input')
    name = models.SlugField(max_length=32, allow_unicode=True)
    label = models.CharField(max_length=32, blank=True)
    type = models.CharField(max_length=16, choices=InputType.choices,
                            default=InputType.NUMERIC)
    min_num = models.PositiveIntegerField(null=True, blank=True)
    max_num = models.PositiveIntegerField(null=True, blank=True)
    max_chars = models.PositiveIntegerField(null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    def rank_group(self):
        return Input.objects.filter(form=self.form)


class Panel(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['program', 'name'],
                             name='unique_panel_name')
        ]
    
    program = models.ForeignKey(Program, models.CASCADE, related_name='panels',
                                related_query_name='panel')
    name = models.CharField(max_length=50)
    panelists = models.ManyToManyField(User, blank=True, related_name='panels',
                                       related_query_name='panel')
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Cohort(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['form', 'name'], name='unique_cohort_name')
        ]
    
    class Status(models.TextChoices):
        INACTIVE = 'inactive', _('inactive')
        ACTIVE = 'active', _('active')
        COMPLETED = 'completed', _('completed')
    
    form = models.ForeignKey(Form, models.CASCADE, # could remove and use
                             related_name='cohorts', # presentation.form?
                             related_query_name='cohort')
    name = models.CharField(max_length=50)
    message = models.TextField(blank=True)
    presentation = models.ForeignKey(Presentation, models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='cohorts',
                                     related_query_name='cohort')
    panel = models.ForeignKey(Panel, models.SET_NULL,
                               null=True, blank=True,
                               related_name='cohorts',
                               related_query_name='cohort')
    status = models.CharField(max_length=16, default=Status.INACTIVE,
                              choices=Status.choices)
    size = models.PositiveIntegerField(default=0, editable=False)
    panel_weight = models.FloatField(default=1.0)
    inputs = models.ManyToManyField(Input, blank=True, related_name='cohorts',
                                    related_query_name='cohort')
    allow_skip = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    activated = models.DateTimeField(null=True, blank=True, editable=False)
    completed = models.DateTimeField(null=True, blank=True, editable=False)
    
    def __str__(self):
        return self.name
    
    def members(self):
        cohort_members = Subquery(self.cohortmember_set.values('object_id'))
        return self.form.model.objects.filter(pk__in=cohort_members)


class CohortMember(models.Model):
    cohort = models.ForeignKey(Cohort, models.CASCADE)
    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.UUIDField()
    member = GenericForeignKey()
    
    def __str__(self):
        if self.cohort.form.validation_type == Form.Validation.EMAIL:
            return self.member._email
        
        return self.object_id


class ScoreManager(models.Manager):
    def create_for_cohort(self, user, cohort, **extra_fields):
        return self.model(panelist=user, form=cohort.form, cohort=cohort,
                          **extra_fields)


class Score(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=['panelist', 'object_id',
                                     'cohort', 'input'],
                             name='unique_panelist_submission_cohort_input')
        ]
    
    panelist = models.ForeignKey(User, models.SET_NULL, null=True, blank=True,
                                 related_name='scores',
                                 related_query_name='score')
    form = models.ForeignKey(Form, models.CASCADE, related_name='scores',
                             related_query_name='score')
    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.UUIDField()
    submission = GenericForeignKey()
    cohort = models.ForeignKey(Cohort, models.CASCADE, related_name='scores',
                               related_query_name='score')
    input = models.ForeignKey(Input, models.CASCADE, related_name='scores',
                              related_query_name='score')
    value = models.PositiveIntegerField(null=True, blank=True)
    text = models.CharField(max_length=Input.MAX_TEXT_MAXLEN, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    objects = ScoreManager()
    
    def __str__(self):
        name = f'{self.panelist.username} {self.input.name} '
        if self.value is None: return name + 'placeholder'
        elif not self.value: return name + 'skip'
        elif self.input.type == Input.InputType.TEXT: return name + 'score'
        return name + f'score={self.value}'
