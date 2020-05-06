##################################
Creating Feature Sets for Adjutant
##################################

Adjutant supports the introduction of new Actions, Tasks, and DelegateAPIs
via additional feature sets. A feature set is a bundle of these elements
with maybe some feature set specific extra config. This allows company specific
or deployer specific changes to easily live outside of the core service and
simply extend the core service where and when need.

An example of such a plugin is here (although it may not yet be using the new
'feature set' plugin mechanism):
https://github.com/catalyst-cloud/adjutant-odoo


Once you have all the Actions, Tasks, DelegateAPIs, or Notification Handlers
that you want to include in a feature set, you register them by making a
feature set class::

    from adjutant.feature_set import BaseFeatureSet

    from myplugin.actions import MyCustonAction
    from myplugin.tasks import MyCustonTask
    from myplugin.apis import MyCustonAPI
    from myplugin.handlers import MyCustonNotificationHandler

    class MyFeatureSet(BaseFeatureSet):

        actions = [
            MyCustonAction,
        ]

        tasks = [
            MyCustonTask,
        ]

        delegate_apis = [
            MyCustonAPI,
        ]

        notification_handlers = [
            MyCustonNotificationHandler,
        ]


Then adding it to the library entrypoints::

    adjutant.feature_sets =
        custom_thing = myplugin.features:MyFeatureSet


If you need custom config for your plugin that should be accessible
and the same across all your Actions, Tasks, APIs, or Notification Handlers
then you can register config to the feature set itself::

    from confspirator import groups

    ....

    class MyFeatureSet(BaseFeatureSet):

        .....

        config = groups.DynamicNameConfigGroup(
            children=[
                fields.StrConfig(
                    'myconfig',
                    help_text="Some custom config.",
                    required=True,
                    default="Stuff",
                ),
            ]
        )

Which will be accessible via Adjutant's config at:
``CONF.feature_sets.MyFeatureSet.myconfig``

Building DelegateAPIs
=====================

New DelegateAPIs should inherit from ``adjutant.api.v1.base.BaseDelegateAPI``

A new DelegateAPI from a plugin can effectively 'override' a default
DelegateAPI by registering with the same URL. However it must have
a different class name and the previous DelegateAPI must be removed from
ACTIVE_DELEGATE_APIS.

Examples of DelegateAPIs can be found in adjutant.api.v1.openstack

Minimally they can look like this::

    class MyCustomAPI(BaseDelegateAPI):

        url = r'^custom/mycoolstuff/?$'

        @utils.authenticated
        def post(self, request):
            self.task_manager.create_from_request('my_custom_task', request)

            return Response({'notes': ['task created']}, status=202)

Access can be restricted with the decorators mod_or_admin, project_admin and
admin decorators found in adjutant.api.utils. The request handlers are fairly
standard django view handlers and can execute any needed code. Additional
information for the task should be placed in request.data.

You can also add customer config for the DelegateAPI by setting a
config_group::

    class MyCustomAPI(BaseDelegateAPI):

        url = r'^custom/mycoolstuff/?$'

        config_group = groups.DynamicNameConfigGroup(
            children=[
                fields.StrConfig(
                    'myconfig',
                    help_text="Some custom config.",
                    required=True,
                    default="Stuff",
                ),
            ]
        )


Building Tasks
==============

Tasks must be derived from ``adjutant.tasks.v1.base.BaseTask``. Examples
of tasks can be found in ``adjutant.tasks.v1``

Minimally task should define their required fields::

    class My(MyPluginTask):
        task_type = "my_custom_task"
        default_actions = [
            "MyCustomAction",
        ]
        duplicate_policy = "cancel" # default is cancel

Then there are other optional values you can set::

    class My(MyPluginTask):
        ....

        # previous task_types
        deprecated_task_types = ['create_project']

        # config defaults for the task (used to generate default config):
        allow_auto_approve = True
        additional_actions = None
        token_expiry = None
        action_config = None
        email_config = None
        notification_config = None


Building Actions
================

Actions must be derived from ``adjutant.actions.v1.base.BaseAction``.

Serializers can inherit from either rest_framework.serializers.Serializer, or
the current serializers in adjutant.actions.v1.serializers.

Examples of actions can be found in ``adjutant.actions.v1``

Minimally actions should define their required fields and implement 3
functions::

    class MyCustomAction(BaseAction):

        required = [
            'user_id',
            'value1',
        ]

        serializer = MyCustomActionSerializer

        def _prepare(self):
            # Do some validation here
            pass

        def _approve(self):
            # Do some logic here
            self.action.task.cache['value'] = self.value1

        def _submit(self, token_data, keystone_user=None):
            # Do some logic here
            self.add_note("Submit action performed")

Information set in the action task cache is available in email templates under
``task.cache.value``, and the action data is available in
``action.ActionName.value``.

If a token email is needed to be sent the action should also implement::

    def _get_email(self):
        return self.keystone_user.email

If an action does not require outside approval this function should be run at
the pre-approval stage::

    self.set_auto_approve(True)

If an action requires a token this should be set at the post approval stage::

    self.action.need_token = True
    self.set_token_fields(["confirm"])

All actions must be paired with a serializer to do basic data structure
checking, but should also check data validity during the action. Serializers
are django-rest-framework serializers, but there are also two base serializers
available in adjutant.actions.v1.serializers, BaseUserNameSerializer and
BaseUserIdSerializer.

All fields required for an action must be plassed through the serializer
otherwise they will be inaccessible to the action.

Example::

    from adjutant.actions.v1.serializers import BaseUserIdSerializer
    from rest_framework import serializers

    class MyCustomActionSerializer(BaseUserIdSerializer):
        value_1 = serializers.CharField()

******************************
Building Notification Handlers
******************************

Notification Handlers can also be added through a plugin::

    from adjutant.notifications.models import BaseNotificationHandler
    from adjutant.plugins import register_notification_handler

    class NewNotificationHandler(BaseNotificationHandler):

        config_group = groups.DynamicNameConfigGroup(
            children=[
                fields.BoolConfig(
                    "do_this_thing",
                    help_text="Should we do the thing?",
                    default=False,
                ),
            ]
        )

        def _notify(self, task, notification):
            conf = self.settings(task, notification)
            if conf.do_this_thing:
              # do something with the task and notification

You then need to setup the handler to be used either by default for a task,
or for a specific task::

    workflow:
        task_defaults:
            notifications:
                standard_handlers:
                    - NewNotificationHandler
                standard_handler_settings:
                    NewNotificationHandler:
                        do_this_thing: true
        tasks:
            some_task:
                notifications:
                    standard_handlers: null
                    error_handlers:
                        - NewNotificationHandler
                    error_handler_settings:
                        NewNotificationHandler:
                            do_this_thing: true


*************************************************
Using the Identity Manager, and Openstack Clients
*************************************************

The Identity Manager is designed to replace access to the Keystone Client. It
can be imported from ``adjutant.actions.user_store.IdentityManager`` .
Functions for access to some of the other Openstack Clients are in
``adjutant.actions.openstack_clients``.

This will be expanded on in future, with the IdentityManager itself also
becoming pluggable.
