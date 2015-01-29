from base.models import BaseAction
from serializers import NewNetworkSerializer, NewRouterSerializer
from django.conf import settings


class NewNetwork(BaseAction):
    """"""

    required = [
        'network_name'
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
        print "Network Created"


class NewRouter(BaseAction):
    """"""

    required = [
        'router_name'
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
        print "router Created"


action_classes = {
    'NewNetwork': (NewNetwork, NewNetworkSerializer),
    'NewRouter': (NewRouter, NewRouterSerializer)
}


settings.ACTION_CLASSES.update(action_classes)
