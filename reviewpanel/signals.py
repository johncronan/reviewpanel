from django.dispatch import receiver

from formative.signals import register_user_actions
from .admin import add_to_panel


@receiver(register_user_actions, dispatch_uid='reviewpanel_user_action')
def register_user_actions(sender, **kwargs):
    return {'add_to_panel': add_to_panel}
