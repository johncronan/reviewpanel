from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from . import __version__


class ReviewPanelConfig(AppConfig):
    name = 'reviewpanel'
    verbose_name = 'reviewpanel'
    
    class FormativePluginMeta:
        name = 'reviewpanel'
        author = 'John Kyle Cronan'
        description = _('Review and score application form submissions')
        version = __version__
    
    def ready(self):
        from . import signals
