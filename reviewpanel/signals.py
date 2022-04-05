from django.dispatch import receiver

from formative.admin import site
from formative.models import Program, Form
from formative.signals import form_published_changed, register_user_actions
from .admin import add_to_panel, ProgramFormsAdmin, FormSubmissionsAdmin


programs_registered, forms_registered = {}, {}

def create_proxy_model(base, name, **kwargs):
    class Meta:
        proxy = True
        app_label = 'reviewpanel'
    
    model = type(name, (base,), {'__module__': 'reviewpanel', 'Meta': Meta})
    for k, v in kwargs.items(): setattr(model._meta, k, v)
    return model

@receiver(form_published_changed, dispatch_uid='reviewpanel_published_changed')
def form_published_changed(sender, **kwargs):
    for model in programs_registered: site.unregister(model)
    programs_registered.clear()
    for model in forms_registered: site.unregister(model)
    forms_registered.clear()
    
    queryset = Form.objects.exclude(status=Form.Status.DRAFT)
    for form in queryset.select_related('program'):
        slug = form.program.slug
        if slug not in [ p._meta.program_slug for p in programs_registered ]:
            model = create_proxy_model(Form, form.program.db_slug + '_forms',
                                       program_slug=slug,
                                       verbose_name=slug+' form',
                                       verbose_name_plural=slug+' forms')
            site.register(model, ProgramFormsAdmin)
            programs_registered[model] = True
        
        model = create_proxy_model(form.model,
                                   form.program.db_slug + '_' + form.db_slug,
                                   program_slug=slug, form_slug=form.slug,
                                   verbose_name=form.slug+' submission',
                                   verbose_name_plural=form.slug+' submissions')
        site.register(model, FormSubmissionsAdmin)
        forms_registered[model] = True


@receiver(register_user_actions, dispatch_uid='reviewpanel_user_action')
def register_user_actions(sender, **kwargs):
    return {'add_to_panel': add_to_panel}
