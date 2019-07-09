##############################
Creating Plugins for Adjutant
##############################

As Adjutant is built on top of Django, we've used parts of Django's installed
apps system to allow us a plugin mechanism that allows additional actions and
views to be brought in via external sources. This allows company specific or
deployer specific changes to easily live outside of the core service and simply
extend the core service where and when need.

An example of such a plugin is here:
https://github.com/catalyst/adjutant-odoo

Building DelegateAPIs
=====================

New DelegateAPIs should inherit from adjutant.api.v1.base.BaseDelegateAPI
can be registered as such::

    from adjutant.plugins import register_plugin_delegate_api,

    from myplugin import apis

    register_plugin_delegate_api(r'^my-plugin/some-action/?$', apis.MyAPIView)

A DelegateAPI must both be registered with a valid URL and specified in
ACTIVE_DELEGATE_APIS in the configuration to be accessible.

A new DelegateAPI from a plugin can effectively 'override' a default
DelegateAPI by registering with the same URL. However it must have
a different class name and the previous DelegateAPI must be removed from
ACTIVE_DELEGATE_APIS.

Examples of DelegateAPIs can be found in adjutant.api.v1.openstack

Minimally they can look like this::

    class NewCreateProject(BaseDelegateAPI):

        @utils.authenticated
        def post(self, request):
            self.task_manager.create_from_request('my_custom_task', request)

            return Response({'notes': ['task created']}, status=202)

Access can be restricted with the decorators mod_or_admin, project_admin and
admin decorators found in adjutant.api.utils. The request handlers are fairly
standard django view handlers and can execute any needed code. Additional
information for the task should be placed in request.data.


Building Tasks
==============

Tasks must be derived from adjutant.tasks.v1.base.BaseTask and can be
registered as such::

     from adjutant.plugins import register_plugin_task

    register_plugin_task(MyPluginTask)

Examples of tasks can be found in `adjutant.tasks.v1`

Minimally task should define their required fields::

    class My(MyPluginTask):
        task_type = "my_custom_task"
        default_actions = [
            "MyCustomAction",
        ]
        duplicate_policy = "cancel" # default is cancel


Building Actions
================

Actions must be derived from adjutant.actions.v1.base.BaseAction and are
registered alongside their serializer::

    from adjutant.plugins import register_plugin_action

    register_action_class(MyCustomAction, MyCustomActionSerializer)

Serializers can inherit from either rest_framework.serializers.Serializer, or
the current serializers in adjutant.actions.v1.serializers.

Examples of actions can be found in `adjutant.actions.v1`

Minimally actions should define their required fields and implement 3
functions::

    class MyCustomAction(BaseAction):

        required = [
            'user_id',
            'value1',
        ]

        def _prepare(self):
            # Do some validation here
            pass

        def _approve(self):
            # Do some logic here
            self.action.task.cache['value'] = self.value1

        def _submit(self, data):
            # Do some logic here
            self.add_note("Submit action performed")

Information set in the action task cache is available in email templates under
task.cache.value, and the action data is available in action.ActionName.value.

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

All fields required for an action must be placed through the serializer
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

        settings_group = groups.DynamicNameConfigGroup(
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


    register_notification_handler(NewNotificationHandler)

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
