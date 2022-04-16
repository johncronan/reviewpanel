from django import forms

from formative.forms import AdminJSONForm, ExportAdminForm
from formative.models import FormBlock
from .models import TemplateSection, Input, Cohort


class ReferenceForm(AdminJSONForm):
    class Meta:
        exclude = ('_rank',)
        json_fields = {'options': []}
        labels = {
            'section': 'template section',
            'select_section': 'section for selector'
        }
        help_texts = {
            'collection': 'Leave blank to reference a block.',
            'name': "Name of the block, or of the item field. " \
                    "Leave blank to reference the collection's file.",
            'select_section': 'If a separate section is not used, the ' \
                              'selector will be added below the content.'
        }
    
    def __init__(self, presentation=None, extra=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.presentation = presentation
        
        if extra:
            # these are set after the instance gets added, when applicable
            for n in ('field', 'block_combine', 'inline_combine',
                      'select_section'):
                self.fields[n].widget = forms.HiddenInput()
        else:
            self.fields['collection'].disabled = True
            
            if self.instance.combined or not self.instance.collection:
                self.fields['select_section'].widget = forms.HiddenInput()
            if not self.instance.collection:
                self.fields['block_combine'].widget = forms.HiddenInput()
                self.fields['inline_combine'].widget = forms.HiddenInput()
                
                form = presentation.form
                self.fields['name'].choices = [ (n, n) for n in 
                                                form.submission_blocks() ]
                try: block = form.blocks.get(name=self.instance.name)
                except FormBlock.DoesNotExist: return
                if block.block_type() != 'stock' or not block.stock.composite:
                    self.fields['field'].widget = forms.HiddenInput()
                    return
                
                self.fields['field'].choices = block.stock.render_choices()
            else:
                choices = []
                for block in presentation.form.collections():
                    for f in block.collection_fields():
                        if (f, f) not in choices: choices.append((f, f))
                self.fields['name'].choices = [('', '-')] + choices
                
                self.fields['field'].widget = forms.HiddenInput()


class ReferencesFormSet(forms.models.BaseInlineFormSet):
    def __init__(self, presentation=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.presentation = presentation
    
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['presentation'] = self.presentation
        return kwargs
        
    @property
    def empty_form(self):
        form = self.form(
            auto_id=self.auto_id,
            prefix=self.add_prefix('__prefix__'),
            empty_permitted=True,
            use_required_attribute=False,
            **self.get_form_kwargs(None),
            renderer=self.renderer,
            extra=True
        )
        self.add_fields(form, None)
        return form


class CohortForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data['status']
        if status == Cohort.Status.INACTIVE: return cleaned_data
        
        if not cleaned_data['panel']:
            self.add_error('panel',
                           'Must be specified, unless cohort is inactive.')
        if status == Cohort.Status.ACTIVE and not cleaned_data['presentation']:
            self.add_error('presentation',
                           'Must be specified for an active cohort.')
        if status == Cohort.Status.ACTIVE:
            if not cleaned_data['inputs']:
                self.add_error('inputs', 'There has to be a primary input.')
            else:
                inputs = cleaned_data['inputs']
                qs = Input.objects.filter(pk__in=inputs).order_by('_rank')
                primary = qs[:1]
                if not primary or primary[0].type == Input.InputType.TEXT:
                    self.add_error('inputs',
                                   "Primary input can't be a text input.")
        return cleaned_data


class MetricsExportForm(ExportAdminForm):
    def __init__(self, metrics=None, inputs=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for metric in metrics or []:
            name = f'metric_{metric.input.name}_{metric.name}'
            label = f'{metric.input.name} {metric.name}'
            self.fields[name] = forms.BooleanField(required=False, label=label,
                                                   initial=True)
        for input in inputs or []:
            name = 'input_' + input.name
            self.fields[name] = forms.ChoiceField(label=input.name,
                choices=[('no', 'not included'),
                         ('combine', 'in one column')]
            )


class ScoresForm(forms.Form):
    def __init__(self, inputs=None, allow_skip=False, *args, **kwargs):
        self.inputs, self.allow_skip = inputs, allow_skip
        super().__init__(*args, **kwargs)
        
        for i, input in enumerate(inputs):
            if input.type == Input.InputType.NUMERIC:
                field = forms.IntegerField(min_value=input.min_num,
                                           max_value=input.max_num)
                if allow_skip or i: field.required = False
            elif input.type == Input.InputType.BOOLEAN:
                field = forms.BooleanField()
            else:
                field = forms.CharField(max_length=input.max_chars)
                field.widget.attrs['placeholder'] = input.label
                if not input.min_num: field.required = False
            
            field.label = input.label
            if not i: field.widget.attrs['class'] = 'primary-input'
            self.fields[input.name] = field
    
    def clean(self):
        cleaned_data = super().clean()
        if not self.allow_skip: return cleaned_data
        
        for input in self.inputs:
            val = cleaned_data.get(input.name, None)
            if not val and input.type != Input.InputType.TEXT:
                cleaned_data[input.name] = 0 # zero for skipped
        
        return cleaned_data
