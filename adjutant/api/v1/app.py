from django.apps import AppConfig
from adjutant.api.views import build_version_details


class APIV1Config(AppConfig):
    name = "adjutant.api.v1"
    label = 'api_v1'

    def ready(self):
        build_version_details('1.0', 'CURRENT', relative_endpoint='v1/')
