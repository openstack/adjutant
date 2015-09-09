from base.models import BaseAction
from serializers import NewClientSerializer
from django.conf import settings


class NewClient(BaseAction):
    """"""

    required = [
        'business_name',
        'billing_address',
        'billing_phone',
        'billing_email'
    ]

    def _pre_approve(self):
        self.action.valid = True
        self.action.need_token = False
        self.action.save()
        return []

    def _post_approve(self):
        self.action.valid = True
        self.action.need_token = False
        self.action.save()
        return []

    def _submit(self, token_data):
        pass


action_classes = {
    'NewClient': (NewClient, NewClientSerializer)
}

settings.ACTION_CLASSES.update(action_classes)
