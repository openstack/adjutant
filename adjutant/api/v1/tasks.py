# Copyright (C) 2015 Catalyst IT Ltd
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from rest_framework.response import Response
from adjutant.actions.user_store import IdentityManager
from adjutant.api.models import Task
from django.utils import timezone
from adjutant.api import utils
from adjutant.api.v1.views import APIViewWithLogger
from adjutant.api.v1.utils import (
    send_stage_email, create_notification, create_token, create_task_hash,
    add_task_id_for_roles)
from adjutant.exceptions import SerializerMissingException


from django.conf import settings


class TaskView(APIViewWithLogger):
    """
    Base class for api calls that start a Task.
    'default_actions' is a required hardcoded field.

    The default_actions are considered the primary actions and
    will always run first (in the given order). Additional actions
    are defined in the settings file and will run in the order supplied,
    but after the default_actions.

    Default actions can be overridden in the settings file as well if
    needed.
    """

    default_actions = []

    def get(self, request):
        """
        The get method will return a json listing the actions this
        view will run, and the data fields that those actions require.
        """
        class_conf = settings.TASK_SETTINGS.get(
            self.task_type, settings.DEFAULT_TASK_SETTINGS)

        actions = (
            class_conf.get('default_actions', []) or
            self.default_actions[:])

        actions += class_conf.get('additional_actions', [])

        required_fields = []

        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]
            for field in action_class.required:
                if field not in required_fields:
                    required_fields.append(field)

        return Response({'actions': actions,
                         'required_fields': required_fields})

    def _instantiate_action_serializers(self, request, class_conf):
        action_serializer_list = []

        action_names = (
            class_conf.get('default_actions', []) or
            self.default_actions[:])
        action_names += class_conf.get('additional_actions', [])

        # instantiate all action serializers and check validity
        valid = True
        for action_name in action_names:
            action_class, serializer_class = \
                settings.ACTION_CLASSES[action_name]

            # instantiate serializer class
            if not serializer_class:
                raise SerializerMissingException(
                    "No serializer defined for action %s" % action_name)
            serializer = serializer_class(data=request.data)

            action_serializer_list.append({
                'name': action_name,
                'action': action_class,
                'serializer': serializer})

            if serializer and not serializer.is_valid():
                valid = False

        if not valid:
            errors = {}
            for action in action_serializer_list:
                if action['serializer']:
                    errors.update(action['serializer'].errors)
            return {'errors': errors}, 400

        return action_serializer_list

    def _handle_duplicates(self, class_conf, hash_key):
        duplicate_tasks = Task.objects.filter(
            hash_key=hash_key,
            completed=0,
            cancelled=0)

        if not duplicate_tasks:
            return False

        duplicate_policy = class_conf.get("duplicate_policy", "")
        if duplicate_policy == "cancel":
            self.logger.info(
                "(%s) - Task is a duplicate - Cancelling old tasks." %
                timezone.now())
            for task in duplicate_tasks:
                task.cancelled = True
                task.save()
            return False

        self.logger.info(
            "(%s) - Task is a duplicate - Ignoring new task." %
            timezone.now())
        return (
            {'errors': ['Task is a duplicate of an existing task']},
            409)

    def process_actions(self, request):
        """
        Will ensure the request data contains the required data
        based on the action serializer, and if present will create
        a Task and the linked actions, attaching notes
        based on running of the the pre_approve validation
        function on all the actions.

        If during the pre_approve step at least one of the actions
        sets auto_approve to True, and none of them set it to False
        the approval steps will also be run.
        """
        class_conf = settings.TASK_SETTINGS.get(
            self.task_type, settings.DEFAULT_TASK_SETTINGS)

        # Action serializers
        action_serializer_list = self._instantiate_action_serializers(
            request, class_conf)

        if isinstance(action_serializer_list, tuple):
            return action_serializer_list

        hash_key = create_task_hash(self.task_type, action_serializer_list)

        # Handle duplicates
        duplicate_error = self._handle_duplicates(class_conf, hash_key)
        if duplicate_error:
            return duplicate_error

        # Instantiate Task
        ip_address = request.META['REMOTE_ADDR']
        keystone_user = request.keystone_user
        try:
            task = Task.objects.create(
                ip_address=ip_address,
                keystone_user=keystone_user,
                project_id=keystone_user['project_id'],
                task_type=self.task_type,
                hash_key=hash_key)
        except KeyError:
            task = Task.objects.create(
                ip_address=ip_address,
                keystone_user=keystone_user,
                task_type=self.task_type,
                hash_key=hash_key)
        task.save()

        # Instantiate actions with serializers
        for i, action in enumerate(action_serializer_list):
            data = action['serializer'].validated_data

            # construct the action class
            action_instance = action['action'](
                data=data,
                task=task,
                order=i
            )

            try:
                action_instance.pre_approve()
            except Exception as e:
                import traceback
                trace = traceback.format_exc()
                self.logger.critical((
                    "(%s) - Exception escaped! %s\nTrace: \n%s") % (
                        timezone.now(), e, trace))
                notes = {
                    'errors':
                        [("Error: '%s' while setting up task. " +
                          "See task itself for details.") % e]
                }
                create_notification(task, notes, error=True)

                response_dict = {
                    'errors':
                        ["Error: Something went wrong on the server. " +
                         "It will be looked into shortly."]
                }
                return response_dict, 200

        # send initial confirmation email:
        email_conf = class_conf.get('emails', {}).get('initial', None)
        send_stage_email(task, email_conf)

        action_models = task.actions
        approve_list = [act.get_action().auto_approve for act in action_models]

        # TODO(amelia): It would be nice to explicitly test this, however
        #               currently we don't have the right combinations of
        #               actions to allow for it.
        if False in approve_list:
            can_auto_approve = False
        elif True in approve_list:
            can_auto_approve = True
        else:
            can_auto_approve = False

        if can_auto_approve:
            task_name = self.__class__.__name__
            self.logger.info("(%s) - AutoApproving %s request."
                             % (timezone.now(), task_name))
            approval_data, status = self.approve(request, task)
            # Additional information that would be otherwise expected
            approval_data['task'] = task
            approval_data['auto_approved'] = True
            return approval_data, status

        return {'task': task}, 200

    def _create_token(self, task):
        token = create_token(task)
        try:
            class_conf = settings.TASK_SETTINGS.get(
                self.task_type, settings.DEFAULT_TASK_SETTINGS)

            # will throw a key error if the token template has not
            # been specified
            email_conf = class_conf['emails']['token']
            send_stage_email(task, email_conf, token)
            return {'notes': ['created token']}, 200
        except KeyError as e:
            import traceback
            trace = traceback.format_exc()
            self.logger.critical((
                "(%s) - Exception escaped! %s\nTrace: \n%s") % (
                    timezone.now(), e, trace))
            notes = {
                'errors':
                    [("Error: '%s' while sending " +
                      "token. See task " +
                      "itself for details.") % e]
            }
            create_notification(task, notes, error=True)

            response_dict = {
                'errors':
                    ["Error: Something went wrong on the " +
                     "server. It will be looked into shortly."]
            }
            return response_dict, 500

    def approve(self, request, task):
        """
        Approves the task and runs the post_approve steps.
        Will create a token if required, otherwise will run the
        submit steps.
        """

        # We approve the task before running actions,
        # that way if something goes wrong we know if it was approved,
        # when it was approved, and who approved it.
        task.approved = True
        task.approved_on = timezone.now()
        task.approved_by = request.keystone_user
        task.save()

        action_models = task.actions
        actions = [act.get_action() for act in action_models]
        need_token = False

        valid = all([act.valid for act in actions])
        if not valid:
            return {'errors': ['actions invalid']}, 400

        # post_approve all actions
        for action in actions:
            try:
                action.post_approve()
            except Exception as e:
                import traceback
                trace = traceback.format_exc()
                self.logger.critical((
                    "(%s) - Exception escaped! %s\nTrace: \n%s") % (
                        timezone.now(), e, trace))
                notes = {
                    'errors':
                        [("Error: '%s' while approving task. " +
                          "See task itself for details.") % e]
                }
                create_notification(task, notes, error=True)

                response_dict = {
                    'errors':
                        ["Error: Something went wrong on the server. " +
                         "It will be looked into shortly."]
                }
                return response_dict, 500

        valid = all([act.valid for act in actions])
        if not valid:
            return {'errors': ['actions invalid']}, 400

        need_token = any([act.need_token for act in actions])
        if need_token:
            return self._create_token(task)

        # submit all actions
        for action in actions:
            try:
                action.submit({})
            except Exception as e:
                import traceback
                trace = traceback.format_exc()
                self.logger.critical((
                    "(%s) - Exception escaped! %s\nTrace: \n%s") % (
                        timezone.now(), e, trace))
                notes = {
                    'errors':
                        [("Error: '%s' while submitting " +
                          "task. See task " +
                          "itself for details.") % e]
                }
                create_notification(task, notes, error=True)

                response_dict = {
                    'errors':
                        ["Error: Something went wrong on the " +
                         "server. It will be looked into shortly."]
                }
                return response_dict, 500

        task.completed = True
        task.completed_on = timezone.now()
        task.save()

        # Sending confirmation email:
        class_conf = settings.TASK_SETTINGS.get(
            self.task_type, settings.DEFAULT_TASK_SETTINGS)
        email_conf = class_conf.get(
            'emails', {}).get('completed', None)
        send_stage_email(task, email_conf)
        return {'notes': ["Task completed successfully."]}, 200


# NOTE(adriant): We should deprecate these TaskViews properly and switch tests
# to work against the openstack ones. One option is making these abstract
# classes, so we retain the code here, but make them useless without extension.

class CreateProject(TaskView):

    task_type = "create_project"

    default_actions = ["NewProjectWithUserAction", ]

    def post(self, request, format=None):
        """
        Unauthenticated endpoint bound primarily to NewProjectWithUser.

        This process requires approval, so this will validate
        incoming data and create a task to be approved
        later.
        """
        self.logger.info("(%s) - Starting new project task." %
                         timezone.now())

        class_conf = settings.TASK_SETTINGS.get(self.task_type, {})

        # we need to set the region the resources will be created in:
        request.data['region'] = class_conf.get('default_region')

        # parent_id for new project, if null defaults to domain:
        request.data['parent_id'] = class_conf.get('default_parent_id')

        processed, status = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=status)

        notes = {
            'notes':
                ['New task for CreateProject.']
        }
        create_notification(processed['task'], notes)
        self.logger.info("(%s) - Task created." % timezone.now())

        response_dict = {'notes': ['task created']}

        add_task_id_for_roles(request, processed, response_dict, ['admin'])

        return Response(response_dict, status=status)


class InviteUser(TaskView):

    task_type = "invite_user"

    default_actions = ['NewUserAction', ]

    @utils.mod_or_admin
    def get(self, request):
        return super(InviteUser, self).get(request)

    @utils.mod_or_admin
    def post(self, request, format=None):
        """
        Invites a user to the current tenant.

        This endpoint requires either Admin access or the
        request to come from a project_admin|project_mod.
        As such this Task is considered pre-approved.
        """
        self.logger.info("(%s) - New AttachUser request." % timezone.now())

        # Default project_id to the keystone user's project
        if ('project_id' not in request.data or
                request.data['project_id'] is None):
            request.data['project_id'] = request.keystone_user['project_id']

        processed, status = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())

            if isinstance(errors, dict):
                return Response(errors, status=status)
            return Response({'errors': errors}, status=status)

        response_dict = {'notes': processed['notes']}

        add_task_id_for_roles(request, processed, response_dict, ['admin'])

        return Response(response_dict, status=status)


class ResetPassword(TaskView):

    task_type = "reset_password"

    default_actions = ['ResetUserPasswordAction', ]

    def post(self, request, format=None):
        """
        Unauthenticated endpoint bound to the password reset action.
        This will submit and approve a password reset request.
         ---
        parameters:
            - name: email
              required: true
              type: string
              description: The email of the user to reset
            - name: username
              required: false
              type: string
              description: The username of the user, not required if using
                           USERNAME_IS_PASSWORD

        responseMessages:
            - code: 400
              message: Validation Errors
            - code: 200
              message: Success. Does not indicate user exists.

        """
        self.logger.info("(%s) - New ResetUser request." % timezone.now())
        processed, status = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=status)

        task = processed['task']
        self.logger.info("(%s) - AutoApproving Resetuser request."
                         % timezone.now())

        # NOTE(amelia): Not using auto approve due to security implications
        # as it will return all errors including whether the user exists
        self.approve(request, task)
        response_dict = {'notes': [
            "If user with email exists, reset token will be issued."]}

        add_task_id_for_roles(request, processed, response_dict, ['admin'])

        return Response(response_dict, status=200)


class EditUser(TaskView):

    task_type = "edit_user"

    default_actions = ['EditUserRolesAction', ]

    @utils.mod_or_admin
    def get(self, request):
        class_conf = settings.TASK_SETTINGS.get(
            self.task_type, settings.DEFAULT_TASK_SETTINGS)

        action_names = (
            class_conf.get('default_actions', []) or
            self.default_actions[:])

        action_names += class_conf.get('additional_actions', [])
        role_blacklist = class_conf.get('role_blacklist', [])

        required_fields = set()

        for action_name in action_names:
            action_class, action_serializer = \
                settings.ACTION_CLASSES[action_name]
            required_fields |= action_class.required

        user_list = []
        id_manager = IdentityManager()
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)

        # todo: move to interface class
        for user in id_manager.list_users(project):
            skip = False
            roles = []
            for role in user.roles:
                if role.name in role_blacklist:
                    skip = True
                    continue
                roles.append(role.name)
            if skip:
                continue
            user_list.append({"username": user.username,
                              "email": user.username,
                              "roles": roles})

        return Response({'actions': action_names,
                         'required_fields': list(required_fields),
                         'users': user_list})

    @utils.mod_or_admin
    def post(self, request, format=None):
        """
        This endpoint requires either mod access or the
        request to come from a project_admin.
        As such this Task is considered pre-approved.
        Runs process_actions, then does the approve step and
        post_approve validation, and creates a Token if valid.
        """
        self.logger.info("(%s) - New EditUser request." % timezone.now())
        processed, status = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=status)

        response_dict = {'notes': processed.get('notes')}
        add_task_id_for_roles(request, processed, response_dict, ['admin'])

        return Response(response_dict, status=status)


class UpdateEmail(TaskView):
    task_type = "update_email"

    default_actions = ["UpdateUserEmailAction", ]

    @utils.authenticated
    def post(self, request, format=None):
        """
        Endpoint bound to the update email action.
        This will submit and approve an update email action.
        """

        request.data['user_id'] = request.keystone_user['user_id']

        processed, status = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=status)

        response_dict = {'notes': processed['notes']}
        return Response(response_dict, status=status)
