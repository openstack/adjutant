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

New TaskViews should inherit from adjutant.api.v1.tasks.TaskView
can be registered as such::

  from adjutant.api.v1.models import register_taskview_class,

  from myplugin import tasks

  register_taskview_class(r'^openstack/sign-up/?$', tasks.OpenStackSignUp)

Actions must be derived from adjutant.actions.v1.base.BaseAction and are
registered alongside their serializer::

  from adjutant.actions.v1.models import register_action_class

  register_action_class(NewClientSignUpAction, NewClientSignUpActionSerializer)

Serializers can inherit from either rest_framework.serializers.Serializer, or
the current serializers in adjutant.actions.v1.serializers.

A task must both be registered with a valid URL and specified in
ACTIVE_TASKVIEWS in the configuration to be accessible.

A new task from a plugin can effectively 'override' a default task by
registering with the same URL, and sharing the task type. However it must have
a different class name and the previous task must be removed from
ACTIVE_TASKVIEWS.


**********************
Building Taskviews
**********************

Examples of taskviews can be found in adjutant.api.v1.openstack

Minimally they can look like this::

    class NewCreateProject(TaskView):

        task_type = "new_create_project"

        default_actions = ["NewProjectWithUserAction", ]

        def post(self, request, format=None):
            processed, status = self.process_actions(request)

            errors = processed.get('errors', None)
            if errors:
                self.logger.info("(%s) - Validation errors with task." %
                                 timezone.now())
                return Response(errors, status=status)

            return Response(response_dict, status=status)

Access can be restricted with the decorators mod_or_admin, project_admin and
admin decorators found in adjutant.api.utils. The request handlers are fairly
standard django view handlers and can execute any needed code. Additional
information for the actions should be placed in request.data.


*********************
Building Actions
*********************

Examples of actions can be found in adjutant.actions.v1.

Minimally actions should define their required fields and implement 3
functions::

    required = [
        'user_id',
        'value1',
    ]

    def _pre_approve(self):
        self.perform_action('initial')

    def _post_approve(self):
        self.perform_action('token')
        self.action.task.cache['value'] = self.value1

    def _submit(self, data):
        self.perform_action('completed')
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

    class NewActionSerializer(BaseUserIdSerializer):
        value_1 = serializers.CharField()

******************************
Building Notification Engines
******************************

Notification Engines can also be added through a plugin::

    from adjutant.notifcations.models import NotificationEngine
    from django.conf import settings

    class NewNotificationEngine(NotificationEngine):

        def _notify(self, task, notification):
            if self.conf.get('do_this_thing'):
              # do something with the task and notification


    settings.NOTIFICATION_ENGINES.update(
      {'NewNotificationEngine': NewNotificationEngine})

They should be then refered to in conf.yaml::

    TASK_SETTINGS:
        signup:
            notifications:
                NewNotificationEngine:
                    standard:
                        do_this_thing: True
                    error:
                        do_this_thing: False


*************************************************
Using the Identity Manager, and Openstack Clients
*************************************************

The Identity Manager is designed to replace access to the Keystone Client. It
can be imported from ``adjutant.actions.user_store.IdentityManager`` .
Functions for access to some of the other Openstack Clients are in
``adjutant.actions.openstack_clients``.
