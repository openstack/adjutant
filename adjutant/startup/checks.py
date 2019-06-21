from django.apps import AppConfig
from django.conf import settings

from adjutant.exceptions import ActionNotRegistered, DelegateAPINotRegistered


def check_expected_delegate_apis():
    missing_delegate_apis = list(
        set(settings.ACTIVE_DELEGATE_APIS)
        - set(settings.DELEGATE_API_CLASSES.keys()))

    if missing_delegate_apis:
        raise DelegateAPINotRegistered(
            message=(
                "Expected DelegateAPIs are unregistered: %s"
                % missing_delegate_apis))


def check_configured_actions():
    """Check that all the expected actions have been registered."""
    configured_actions = []

    for task in settings.TASK_CLASSES:
        task_class = settings.TASK_CLASSES.get(task)

        configured_actions += task_class.default_actions
        configured_actions += settings.TASK_SETTINGS.get(
            task_class.task_type, {}).get('additional_actions', [])

    missing_actions = list(
        set(configured_actions) - set(settings.ACTION_CLASSES.keys()))

    if missing_actions:
        raise ActionNotRegistered(
            "Configured actions are unregistered: %s" % missing_actions)


class StartUpConfig(AppConfig):
    name = "adjutant.startup"

    def ready(self):
        """A pre-startup function for the api

        Code run here will occur before the API is up and active but after
        all models have been loaded.

        Useful for any start up checks.
        """

        # First check that all expect DelegateAPIs are present
        check_expected_delegate_apis()

        # Now check if all the actions those views expecte are present.
        check_configured_actions()
