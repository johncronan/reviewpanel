from django import forms

from formative.forms import AdminJSONForm
from .models import TemplateSection


class ReferenceForm(AdminJSONForm):
    class Meta:
        exclude = ('_rank',)
        json_fields = {'options': []}
        labels = {
            'select_section': 'section for selector'
        }
        help_texts = {
            'collection': 'Leave blank to reference a block.',
            'name': "Name of the block, or of the item field. " \
                    "Leave blank to reference the collection's file.",
            'select_section': 'If not used, ...'
        }
    
    def __init__(self, presentation=None, extra=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if presentation.template:
            self.fields['section'].queryset = TemplateSection.objects.filter(
                template=presentation.template
            )
        else: self.fields['section'].queryset = TemplateSection.objects.none()
        
        if extra:
            self.fields['field'].widget = forms.HiddenInput()
            self.fields['select_section'].widget = forms.HiddenInput()


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
