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

from decorator import decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from stacktask.base.user_store import IdentityManager
from stacktask.api.models import Task, Token, Notification
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from logging import getLogger
from django.core.mail import send_mail
from smtplib import SMTPException


from django.conf import settings
from django.template import loader, Context


def require_roles(roles, func, *args, **kwargs):
    """
    endpoints setup with this decorator require the defined roles.
    """
    request = args[1]
    req_roles = set(roles)
    if not request.keystone_user.get('authenticated', False):
        return Response({'errors': ["Credentials incorrect or none given."]},
                        401)

    roles = set(request.keystone_user.get('roles', []))

    if roles & req_roles:
        return func(*args, **kwargs)

    return Response({'errors': ["Must have one of the following roles: %s" %
                                list(req_roles)]},
                    403)


@decorator
def mod_or_owner(func, *args, **kwargs):
    return require_roles(
        {'project_owner', 'project_mod'}, func, *args, **kwargs)


@decorator
def mod_or_owner_or_admin(func, *args, **kwargs):
    return require_roles(
        {'project_owner', 'project_mod', 'admin'}, func, *args, **kwargs)


@decorator
def admin(func, *args, **kwargs):
    """
    endpoints setup with this decorator require the admin role.
    """
    request = args[1]
    if not request.keystone_user.get('authenticated', False):
        return Response({'errors': ["Credentials incorrect or none given."]},
                        401)

    roles = request.keystone_user.get('roles', [])
    if "admin" in roles:
        return func(*args, **kwargs)

    return Response({'errors': ["Must be admin."]}, 403)


def create_token(task):
    # expire needs to be made configurable.
    expire = timezone.now() + timedelta(hours=24)

    # is this a good way to create tokens?
    uuid = uuid4().hex
    token = Token.objects.create(
        task=task,
        token=uuid,
        expires=expire
    )
    token.save()
    return token


def send_email(task, email_conf, token=None):
    if email_conf:
        template = loader.get_template(email_conf['template'])
        html_template = loader.get_template(email_conf['html_template'])

        emails = set()
        actions = []
        for action in task.actions:
            act = action.get_action()
            email = act.get_email()
            if email:
                emails.add(email)
                actions.append(unicode(act))

        if len(emails) > 1:
            notes = {
                'notes':
                    (("Error: Unable to send token, More than one email for" +
                     " task: %s") % task.uuid)
            }
            create_notification(task, notes)
            return
            # TODO(adriant): raise some error?
            # and surround calls to this function with try/except

        if token:
            context = {'task': task, 'actions': actions,
                       'token': token.token}
        else:
            context = {'task': task, 'actions': actions}

        try:
            message = template.render(Context(context))
            html_message = html_template.render(Context(context))
            send_mail(
                email_conf['subject'], message, email_conf['reply'],
                [emails.pop()], fail_silently=False, html_message=html_message)
        except SMTPException as e:
            notes = {
                'notes':
                    ("Error: '%s' while emailing token for task: %s" %
                     (e, task.uuid))
            }
            create_notification(task, notes)
            # TODO(adriant): raise some error?
            # and surround calls to this function with try/except


def create_notification(task, notes):
    notification = Notification.objects.create(
        task=task,
        notes=notes
    )
    notification.save()


class APIViewWithLogger(APIView):
    """
    APIView with a logger.
    """
    def __init__(self, *args, **kwargs):
        super(APIViewWithLogger, self).__init__(*args, **kwargs)
        self.logger = getLogger('django.request')


class NotificationList(APIViewWithLogger):

    @admin
    def get(self, request, format=None):
        """
        A list of unacknowledged Notification objects as dicts.
        """
        notifications = Notification.objects.filter(acknowledged__exact=False)
        note_list = []
        for notification in notifications:
            note_list.append(notification.to_dict())
        return Response(note_list, status=200)

    @admin
    def post(self, request, format=None):
        """
        Acknowledge notifications.
        """
        note_list = request.data.get('notifications', None)
        if note_list and isinstance(note_list, list):
            notifications = Notification.objects.filter(pk__in=note_list)
            for notification in notifications:
                notification.acknowledged = True
                notification.save()
            return Response({'notes': ['Notifications acknowledged.']},
                            status=200)
        else:
            return Response({'notifications': ["this field is required" +
                                               "needs to be a list."]},
                            status=400)


class NotificationDetail(APIViewWithLogger):

    @admin
    def get(self, request, pk, format=None):
        """
        Dict notification of a Notification object
        and its related actions.
        """
        try:
            notification = Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return Response(
                {'errors': ['No notification with this id.']},
                status=404)
        return Response(notification.to_dict())

    @admin
    def post(self, request, pk, format=None):
        """
        Acknowledge notification.
        """
        try:
            notification = Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return Response(
                {'errors': ['No notification with this id.']},
                status=404)

        if request.data.get('acknowledged', False) is True:
            notification.acknowledged = True
            notification.save()
            return Response({'notes': ['Notification acknowledged.']},
                            status=200)
        else:
            return Response({'acknowledged': ["this field is required."]},
                            status=400)


class TaskList(APIViewWithLogger):

    @mod_or_owner_or_admin
    def get(self, request, format=None):
        """
        A list of dict representations of Task objects
        and their related actions.
        """

        if 'admin' in request.keystone_user['roles']:
            tasks = Task.objects.all()
            reg_list = []
            for task in tasks:
                reg_list.append(task.to_dict())
            return Response(reg_list, status=200)
        else:
            tasks = Task.objects.filter(
                project_id__exact=request.keystone_user['project_id'])
            reg_list = []
            for task in tasks:
                reg_list.append(task.to_dict())
            return Response(reg_list, status=200)


class TaskDetail(APIViewWithLogger):

    @mod_or_owner_or_admin
    def get(self, request, uuid, format=None):
        """
        Dict representation of a Task object
        and its related actions.
        """
        try:
            if 'admin' in request.keystone_user['roles']:
                task = Task.objects.get(uuid=uuid)
            else:
                task = Task.objects.get(
                    uuid=uuid, project_id=request.keystone_user['project_id'])
        except Task.DoesNotExist:
            return Response(
                {'errors': ['No task with this id.']},
                status=404)
        return Response(task.to_dict())

    @admin
    def put(self, request, uuid, format=None):
        """
        Allows the updating of action data and retriggering
        of the pre_approve step.

        Will undo task approval, and clear tokens for the task.
        """
        try:
            task = Task.objects.get(uuid=uuid)
        except Task.DoesNotExist:
            return Response(
                {'errors': ['No task with this id.']},
                status=404)

        if task.completed:
            return Response(
                {'errors':
                    ['This task has already been completed.']},
                status=400)

        if task.cancelled:
            # NOTE(adriant): If we can uncancel a task, that should happen
            # at this endpoint.
            return Response(
                {'errors':
                    ['This task has been cancelled.']},
                status=400)

        if task.approved:
            return Response(
                {'errors':
                    ['This task has already been approved.']},
                status=400)

        act_list = []

        valid = True
        for action in task.actions:
            action_serializer = settings.ACTION_CLASSES[action.action_name][1]

            if action_serializer is not None:
                serializer = action_serializer(data=request.data)
            else:
                serializer = None

            act_list.append({
                'name': action.action_name,
                'action': action,
                'serializer': serializer})

            if serializer is not None and not serializer.is_valid():
                valid = False

        if valid:
            for act in act_list:
                if act['serializer'] is not None:
                    data = act['serializer'].validated_data
                else:
                    data = {}
                act['action'].action_data = data
                act['action'].save()

                try:
                    act['action'].get_action().pre_approve()
                except Exception as e:
                    notes = {
                        'errors':
                            [("Error: '%s' while updating task. " +
                              "See task itself for details.") % e],
                        'task': task.uuid
                    }
                    create_notification(task, notes)

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

            return Response(
                {'notes': ["Task successfully updated."]},
                status=200)
        else:
            errors = {}
            for act in act_list:
                if act['serializer'] is not None:
                    errors.update(act['serializer'].errors)
            return Response({'errors': errors}, status=400)

    @admin
    def post(self, request, uuid, format=None):
        """
        Will approve the Task specified,
        followed by running the post_approve actions
        and if valid will setup and create a related token.
        """
        try:
            task = Task.objects.get(uuid=uuid)
        except Task.DoesNotExist:
            return Response(
                {'errors': ['No task with this id.']},
                status=404)

        if request.data.get('approved', False) is True:

            if task.completed:
                return Response(
                    {'errors':
                        ['This task has already been completed.']},
                    status=400)

            if task.cancelled:
                return Response(
                    {'errors':
                        ['This task has been cancelled.']},
                    status=400)

            need_token = False
            valid = True

            actions = []

            for action in task.actions:
                act_model = action.get_action()
                actions.append(act_model)
                try:
                    act_model.post_approve()
                except Exception as e:
                    notes = {
                        'errors':
                            [("Error: '%s' while approving task. " +
                              "See task itself for details.") % e],
                        'task': task.uuid
                    }
                    create_notification(task, notes)

                    import traceback
                    trace = traceback.format_exc()
                    self.logger.critical(("(%s) - Exception escaped! %s\n" +
                                          "Trace: \n%s") %
                                         (timezone.now(), e, trace))

                    return Response(notes, status=500)

                if not action.valid:
                    valid = False
                if action.need_token:
                    need_token = True

            if valid:
                task.approved = True
                task.approved_on = timezone.now()
                task.save()
                if need_token:
                    token = create_token(task)
                    try:
                        class_conf = settings.ACTIONVIEW_SETTINGS[
                            task.action_view]

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
                                  "itself for details.") % e],
                            'task': task.uuid
                        }
                        create_notification(task, notes)

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
                                      "itself for details.") % e],
                                'task': task.uuid
                            }
                            create_notification(task, notes)

                            import traceback
                            trace = traceback.format_exc()
                            self.logger.critical(("(%s) - Exception escaped!" +
                                                  " %s\n Trace: \n%s") %
                                                 (timezone.now(), e, trace))

                            return Response(notes, status=500)

                    task.completed = True
                    task.completed_on = timezone.now()
                    task.save()

                    # Sending confirmation email:
                    class_conf = settings.ACTIONVIEW_SETTINGS.get(
                        task.action_view, {})
                    email_conf = class_conf.get(
                        'emails', {}).get('completed', None)
                    send_email(task, email_conf)

                    return Response(
                        {'notes': "Task completed successfully."},
                        status=200)
            return Response({'errors': ['actions invalid']}, status=400)
        else:
            return Response({'approved': ["this field is required."]},
                            status=400)

    @admin
    def delete(self, request, uuid, format=None):
        """
        Cancel the Task.
        """
        try:
            task = Task.objects.get(uuid=uuid)
        except Task.DoesNotExist:
            return Response(
                {'errors': ['No task with this id.']},
                status=404)

        if task.completed:
            return Response(
                {'errors':
                    ['This task has already been completed.']},
                status=400)

        if task.cancelled:
            return Response(
                {'errors':
                    ['This task has already been cancelled.']},
                status=400)

        task.cancelled = True
        task.save()

        return Response(
            {'notes': "Task cancelled successfully."},
            status=200)


class TokenList(APIViewWithLogger):
    """
    Admin functionality for managing/monitoring tokens.
    """

    @admin
    def get(self, request, format=None):
        """
        A list of dict representations of Token objects.
        """
        tokens = Token.objects.all()
        token_list = []
        for token in tokens:
            token_list.append(token.to_dict())
        return Response(token_list)

    @admin
    def post(self, request, format=None):
        """
        Reissue a token for an approved task.

        Clears other tokens for it.
        """
        uuid = request.data.get('task', None)
        if uuid is None:
            return Response(
                {'task': ["This field is required.", ]},
                status=400)
        try:
            task = Task.objects.get(uuid=uuid)
        except Task.DoesNotExist:
            return Response(
                {'errors': ['No task with this id.']},
                status=404)

        if task.completed:
            return Response(
                {'errors':
                    ['This task has already been completed.']},
                status=400)

        if task.cancelled:
            return Response(
                {'errors':
                    ['This task has been cancelled.']},
                status=400)

        if not task.approved:
            return Response(
                {'errors': ['This task has not been approved.']},
                status=400)

        for token in task.tokens:
            token.delete()

        token = create_token(task)
        try:
            class_conf = settings.ACTIONVIEW_SETTINGS[
                task.action_view]

            # will throw a key error if the token template has not
            # been specified
            email_conf = class_conf['emails']['token']
            send_email(task, email_conf, token)
        except KeyError as e:
            notes = {
                'errors':
                    [("Error: '%s' while sending " +
                      "token. See task " +
                      "itself for details.") % e],
                'task': task.uuid
            }
            create_notification(task, notes)

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
        return Response(
            {'notes': ['Token reissued.']}, status=200)

    @admin
    def delete(self, request, format=None):
        """
        Delete all expired tokens.
        """
        now = timezone.now()
        Token.objects.filter(expires__lt=now).delete()
        return Response(
            {'notes': ['Deleted all expired tokens.']}, status=200)


class TokenDetail(APIViewWithLogger):

    def get(self, request, id, format=None):
        """
        Returns a response with the list of required fields
        and what actions those go towards.
        """
        try:
            token = Token.objects.get(token=id)
        except Token.DoesNotExist:
            return Response(
                {'errors': ['This token does not exist.']}, status=404)

        if token.task.completed:
            return Response(
                {'errors':
                    ['This task has already been completed.']},
                status=400)

        if token.task.cancelled:
            return Response(
                {'errors':
                    ['This task has been cancelled.']},
                status=400)

        if token.expires < timezone.now():
            token.delete()
            return Response({'errors': ['This token has expired.']},
                            status=400)

        required_fields = []
        actions = []

        for action in token.task.actions:
            action = action.get_action()
            actions.append(action)
            for field in action.token_fields:
                if field not in required_fields:
                    required_fields.append(field)

        return Response({'actions': [unicode(act) for act in actions],
                         'required_fields': required_fields})

    def post(self, request, id, format=None):
        """
        Ensures the required fields are present,
        will then pass those to the actions via the submit
        function.
        """
        try:
            token = Token.objects.get(token=id)
        except Token.DoesNotExist:
            return Response(
                {'errors': ['This token does not exist.']}, status=404)

        if token.task.completed:
            return Response(
                {'errors':
                    ['This task has already been completed.']},
                status=400)

        if token.task.cancelled:
            return Response(
                {'errors':
                    ['This task has been cancelled.']},
                status=400)

        if token.expires < timezone.now():
            token.delete()
            return Response({'errors': ['This token has expired.']},
                            status=400)

        required_fields = set()
        actions = []

        for action in token.task.actions:
            action = action.get_action()
            actions.append(action)
            for field in action.token_fields:
                required_fields.add(field)

        errors = {}
        data = {}

        for field in required_fields:
            try:
                data[field] = request.data[field]
            except KeyError:
                errors[field] = ["This field is required.", ]

        if errors:
            return Response(errors, status=400)

        for action in actions:
            try:
                action.submit(data)
            except Exception as e:
                notes = {
                    'errors':
                        [("Error: '%s' while submitting task. " +
                          "See task itself for details.") % e],
                    'task': token.task.uuid
                }
                create_notification(token.task, notes)

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

        token.task.completed = True
        token.task.completed_on = timezone.now()
        token.task.save()
        token.delete()

        # Sending confirmation email:
        class_conf = settings.ACTIONVIEW_SETTINGS.get(
            token.task.action_view, {})
        email_conf = class_conf.get(
            'emails', {}).get('completed', None)
        send_email(token.task, email_conf)

        return Response(
            {'notes': "Token submitted successfully."},
            status=200)


class ActionView(APIViewWithLogger):
    """
    Base class for api calls that start a Task.
    Until it is moved to settings, 'default_action' is a
    required hardcoded field.

    The default_action is considered the primary action and
    will always run first. Addtional actions are defined in
    the settings file and will run in the order supplied, but
    after the default_action.
    """

    def get(self, request):
        """
        The get method will return a json listing the actions this
        view will run, and the data fields that those actons require.
        """
        class_conf = settings.ACTIONVIEW_SETTINGS.get(self.__class__.__name__,
                                                      {})

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

        class_conf = settings.ACTIONVIEW_SETTINGS.get(self.__class__.__name__,
                                                      {})

        actions = [self.default_action, ]

        actions += class_conf.get('actions', [])

        act_list = []

        valid = True
        for action in actions:
            action_class, action_serializer = settings.ACTION_CLASSES[action]

            if action_serializer is not None:
                serializer = action_serializer(data=request.data)
            else:
                serializer = None

            act_list.append({
                'name': action,
                'action': action_class,
                'serializer': serializer})

            if serializer is not None and not serializer.is_valid():
                valid = False

        if valid:
            ip_addr = request.META['REMOTE_ADDR']
            keystone_user = request.keystone_user

            try:
                task = Task.objects.create(
                    ip_address=ip_addr, keystone_user=keystone_user,
                    project_id=keystone_user['project_id'],
                    action_view=self.__class__.__name__)
            except KeyError:
                task = Task.objects.create(
                    ip_address=ip_addr, keystone_user=keystone_user,
                    action_view=self.__class__.__name__)
            task.save()

            for i, act in enumerate(act_list):
                if act['serializer'] is not None:
                    data = act['serializer'].validated_data
                else:
                    data = {}
                action = act['action'](
                    data=data, task=task,
                    order=i
                )

                try:
                    action.pre_approve()
                except Exception as e:
                    notes = {
                        'errors':
                            [("Error: '%s' while setting up task. " +
                              "See task itself for details.") % e],
                        'task': task.uuid
                    }
                    create_notification(task, notes)

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
        else:
            errors = {}
            for act in act_list:
                if act['serializer'] is not None:
                    errors.update(act['serializer'].errors)
            return {'errors': errors}

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
                              "See task itself for details.") % e],
                        'task': task.uuid
                    }
                    create_notification(task, notes)

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
                        class_conf = settings.ACTIONVIEW_SETTINGS[
                            self.__class__.__name__]

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
                                  "itself for details.") % e],
                            'task': task.uuid
                        }
                        create_notification(task, notes)

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
                                      "itself for details.") % e],
                                'task': task.uuid
                            }
                            create_notification(task, notes)

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
                    class_conf = settings.ACTIONVIEW_SETTINGS.get(
                        self.__class__.__name__, {})
                    email_conf = class_conf.get(
                        'emails', {}).get('completed', None)
                    send_email(task, email_conf)
                    return Response(
                        {'notes': "Task completed successfully."},
                        status=200)
            return Response({'errors': ['actions invalid']}, status=400)
        return Response({'errors': ['actions invalid']}, status=400)


class CreateProject(ActionView):

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


class AttachUser(ActionView):

    default_action = 'NewUser'

    @mod_or_owner
    def get(self, request):
        return super(AttachUser, self).get(request)

    @mod_or_owner
    def post(self, request, format=None):
        """
        This endpoint requires either Admin access or the
        request to come from a project_owner.
        As such this Task is considered pre-approved.
        Runs process_actions, then does the approve step and
        post_approve validation, and creates a Token if valid.
        """
        self.logger.info("(%s) - New AttachUser request." % timezone.now())
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


class ResetPassword(ActionView):

    default_action = 'ResetUser'

    def post(self, request, format=None):
        """
        Unauthenticated endpoint bound to the password reset action.
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
        return self.approve(task)


class EditUser(ActionView):

    default_action = 'EditUser'

    @mod_or_owner
    def get(self, request):
        class_conf = settings.ACTIONVIEW_SETTINGS.get(self.__class__.__name__,
                                                      {})

        actions = [self.default_action, ]

        actions += class_conf.get('actions', [])
        filters = class_conf.get('filters', [])

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
                if role.name in filters:
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

    @mod_or_owner
    def post(self, request, format=None):
        """
        This endpoint requires either mod access or the
        request to come from a project_owner.
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
