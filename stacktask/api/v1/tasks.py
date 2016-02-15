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
from stacktask.actions.user_store import IdentityManager
from stacktask.api.models import Task
from django.utils import timezone
from stacktask.api import utils
from stacktask.api.v1.views import APIViewWithLogger
from stacktask.api.v1.utils import (
    send_email, create_notification, create_token, create_task_hash)


from django.conf import settings


class TaskView(APIViewWithLogger):
    """
    Base class for api calls that start a Task.
    Until it is moved to settings, 'default_action' is a
    required hardcoded field.

    The default_action is considered the primary action and
    will always run first. Additional actions are defined in
    the settings file and will run in the order supplied, but
    after the default_action.
    """

    def get(self, request):
        """
        The get method will return a json listing the actions this
        view will run, and the data fields that those actions require.
        """
        class_conf = settings.TASK_SETTINGS.get(self.task_type, {})

        actions = [self.default_action, ]

        actions += class_conf.get('actions', [])

        required_fields = []

        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]
            for field in action_class.required:
                if field not in required_fields:
                    required_fields.append(field)

        return Response({'actions': actions,
                         'required_fields': required_fields})

    def process_actions(self, request):
        """
        Will ensure the request data contains the required data
        based on the action serializer, and if present will create
        a Task and the linked actions, attaching notes
        based on running of the the pre_approve validation
        function on all the actions.
        """

        class_conf = settings.TASK_SETTINGS.get(self.task_type, {})

        actions = [self.default_action, ]

        actions += class_conf.get('actions', [])

        action_list = []

        valid = True
        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]

            # instantiate serializer class
            if action_serializer is not None:
                serializer = action_serializer(data=request.data)
            else:
                serializer = None

            action_list.append({
                'name': action,
                'action': action_class,
                'serializer': serializer})

            if serializer is not None and not serializer.is_valid():
                valid = False

        if not valid:
            errors = {}
            for action in action_list:
                if action['serializer'] is not None:
                    errors.update(action['serializer'].errors)
            return {'errors': errors}

        hash_key = create_task_hash(self.task_type, action_list)
        duplicate_tasks = Task.objects.filter(
            hash_key=hash_key,
            completed=0,
            cancelled=0)

        if duplicate_tasks:
            duplicate_policy = class_conf.get("handle_duplicates", "")
            if duplicate_policy == "cancel":
                self.logger.info(
                    "(%s) - Task is a duplicate - Cancelling old tasks." %
                    timezone.now())
                for task in duplicate_tasks:
                    task.cancelled = True
                    task.save()
            else:
                self.logger.info(
                    "(%s) - Task is a duplicate - Ignoring new task." %
                    timezone.now())
                return {'errors': ['Task is a duplicate of an existing task']}

        ip_address = request.META['REMOTE_ADDR']
        keystone_user = request.keystone_user

        try:
            task = Task.objects.create(
                ip_address=ip_address, keystone_user=keystone_user,
                project_id=keystone_user['project_id'],
                task_type=self.task_type,
                hash_key=hash_key)
        except KeyError:
            task = Task.objects.create(
                ip_address=ip_address, keystone_user=keystone_user,
                task_type=self.task_type,
                hash_key=hash_key)
        task.save()

        for i, action in enumerate(action_list):
            if action['serializer'] is not None:
                data = action['serializer'].validated_data
            else:
                data = {}

            # construct the action class
            action_instance = action['action'](
                data=data, task=task,
                order=i
            )

            try:
                action_instance.pre_approve()
            except Exception as e:
                notes = {
                    'errors':
                        [("Error: '%s' while setting up task. " +
                          "See task itself for details.") % e]
                }
                create_notification(task, notes, error=True)

                import traceback
                trace = traceback.format_exc()
                self.logger.critical(("(%s) - Exception escaped! %s\n" +
                                      "Trace: \n%s") %
                                     (timezone.now(), e, trace))

                response_dict = {
                    'errors':
                        ["Error: Something went wrong on the server. " +
                         "It will be looked into shortly."]
                }
                return response_dict

        # send initial conformation email:
        email_conf = class_conf.get('emails', {}).get('initial', None)
        send_email(task, email_conf)

        return {'task': task}

    def approve(self, task):
        """
        Approves the task and runs the post_approve steps.
        Will create a token if required, otherwise will run the
        submit steps.
        """
        task.approved = True
        task.approved_on = timezone.now()
        task.save()

        action_models = task.actions
        actions = []

        valid = True
        need_token = False
        for action in action_models:
            act = action.get_action()
            actions.append(act)

            if not act.valid:
                valid = False

        if valid:
            for action in actions:
                try:
                    action.post_approve()
                except Exception as e:
                    notes = {
                        'errors':
                            [("Error: '%s' while approving task. " +
                              "See task itself for details.") % e]
                    }
                    create_notification(task, notes, error=True)

                    import traceback
                    trace = traceback.format_exc()
                    self.logger.critical(("(%s) - Exception escaped! %s\n" +
                                          "Trace: \n%s") %
                                         (timezone.now(), e, trace))

                    response_dict = {
                        'errors':
                            ["Error: Something went wrong on the server. " +
                             "It will be looked into shortly."]
                    }
                    return Response(response_dict, status=500)

                if not action.valid:
                    valid = False
                if action.need_token:
                    need_token = True

            if valid:
                if need_token:
                    token = create_token(task)
                    try:
                        class_conf = settings.TASK_SETTINGS[self.task_type]

                        # will throw a key error if the token template has not
                        # been specified
                        email_conf = class_conf['emails']['token']
                        send_email(task, email_conf, token)
                        return Response({'notes': ['created token']},
                                        status=200)
                    except KeyError as e:
                        notes = {
                            'errors':
                                [("Error: '%s' while sending " +
                                  "token. See task " +
                                  "itself for details.") % e]
                        }
                        create_notification(task, notes, error=True)

                        import traceback
                        trace = traceback.format_exc()
                        self.logger.critical(("(%s) - Exception escaped!" +
                                              " %s\n Trace: \n%s") %
                                             (timezone.now(), e, trace))

                        response_dict = {
                            'errors':
                                ["Error: Something went wrong on the " +
                                 "server. It will be looked into shortly."]
                        }
                        return Response(response_dict, status=500)
                else:
                    for action in actions:
                        try:
                            action.submit({})
                        except Exception as e:
                            notes = {
                                'errors':
                                    [("Error: '%s' while submitting " +
                                      "task. See task " +
                                      "itself for details.") % e]
                            }
                            create_notification(task, notes, error=True)

                            import traceback
                            trace = traceback.format_exc()
                            self.logger.critical(("(%s) - Exception escaped!" +
                                                  " %s\n Trace: \n%s") %
                                                 (timezone.now(), e, trace))

                            response_dict = {
                                'errors':
                                    ["Error: Something went wrong on the " +
                                     "server. It will be looked into shortly."]
                            }
                            return Response(response_dict, status=500)

                    task.completed = True
                    task.completed_on = timezone.now()
                    task.save()

                    # Sending confirmation email:
                    class_conf = settings.TASK_SETTINGS.get(
                        self.task_type, {})
                    email_conf = class_conf.get(
                        'emails', {}).get('completed', None)
                    send_email(task, email_conf)
                    return Response(
                        {'notes': "Task completed successfully."},
                        status=200)
            return Response({'errors': ['actions invalid']}, status=400)
        return Response({'errors': ['actions invalid']}, status=400)


class CreateProject(TaskView):

    task_type = "create_project"

    default_action = "NewProject"

    def post(self, request, format=None):
        """
        Unauthenticated endpoint bound primarily to NewProject.

        This process requires approval, so this will validate
        incoming data and create a task to be approved
        later.
        """
        self.logger.info("(%s) - Starting new project task." %
                         timezone.now())
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=400)

        notes = {
            'notes':
                ['New task for CreateProject.']
        }
        create_notification(processed['task'], notes)
        self.logger.info("(%s) - Task created." % timezone.now())
        return Response({'notes': ['task created']}, status=200)


class InviteUser(TaskView):

    task_type = "invite_user"

    default_action = 'NewUser'

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

        # TODO: First check if the user already exists or is pending
        # We should not allow duplicate invites.

        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=400)

        task = processed['task']
        self.logger.info("(%s) - AutoApproving AttachUser request."
                         % timezone.now())
        return self.approve(task)


class ResetPassword(TaskView):

    task_type = "reset_password"

    default_action = 'ResetUser'

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
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=400)

        task = processed['task']
        self.logger.info("(%s) - AutoApproving Resetuser request."
                         % timezone.now())
        self.approve(task)
        return Response(status=200)


class EditUser(TaskView):

    task_type = "edit_user"

    default_action = 'EditUser'

    @utils.mod_or_admin
    def get(self, request):
        class_conf = settings.TASK_SETTINGS.get(self.task_type, {})

        actions = [self.default_action, ]

        actions += class_conf.get('actions', [])
        role_blacklist = class_conf.get('role_blacklist', [])

        required_fields = []

        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]
            for field in action_class.required:
                if field not in required_fields:
                    required_fields.append(field)

        user_list = []
        id_manager = IdentityManager()
        project_id = request.keystone_user['project_id']
        project = id_manager.get_project(project_id)

        for user in project.list_users():
            skip = False
            self.logger.info(user)
            roles = []
            for role in id_manager.get_roles(user, project):
                if role.name in role_blacklist:
                    skip = True
                    continue
                roles.append(role.name)
            if skip:
                continue
            user_list.append({"username": user.username,
                              "email": user.username,
                              "roles": roles})

        return Response({'actions': actions,
                         'required_fields': required_fields,
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
        processed = self.process_actions(request)

        errors = processed.get('errors', None)
        if errors:
            self.logger.info("(%s) - Validation errors with task." %
                             timezone.now())
            return Response(errors, status=400)

        task = processed['task']
        self.logger.info("(%s) - AutoApproving EditUser request."
                         % timezone.now())
        return self.approve(task)
