from django import forms

from formative.forms import AdminJSONForm
from formative.models import FormBlock
from .models import TemplateSection, Input


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
            if self.instance.combined or not self.instance.collection:
                self.fields['select_section'].widget = forms.HiddenInput()
            if not self.instance.collection:
                self.fields['block_combine'].widget = forms.HiddenInput()
                self.fields['inline_combine'].widget = forms.HiddenInput()
                
                form = presentation.form
                try: block = form.blocks.get(name=self.instance.name)
                except FormBlock.DoesNotExist: return
                if block.block_type() != 'stock' or not block.stock.composite:
                    self.fields['field'].widget = forms.HiddenInput()
                    return
                
                self.fields['field'].choices = block.stock.render_choices()
            else: self.fields['field'].widget = forms.HiddenInput()
    
    # TODO: clean method


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
        if not self.allow_skip: return
        
        for input in self.inputs:
            val = cleaned_data.get(input.name, None)
            if not val and input.type != Input.InputType.TEXT:
                cleaned_data[input.name] = 0 # zero for skipped
        
        return cleaned_data
