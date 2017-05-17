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

from logging import getLogger

from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView

from adjutant.api import utils
from adjutant.api.models import Notification, Task, Token
from adjutant.api.v1.utils import (
    create_notification, create_token, parse_filters, send_stage_email)


class APIViewWithLogger(APIView):
    """
    APIView with a logger.
    """
    def __init__(self, *args, **kwargs):
        super(APIViewWithLogger, self).__init__(*args, **kwargs)
        self.logger = getLogger('adjutant')


class StatusView(APIViewWithLogger):

    @utils.admin
    def get(self, request, filters=None, format=None):
        """
        Simple status endpoint.

        Returns a list of unacknowledged error notifications,
        and both the last created and last completed tasks.

        Can returns None, if there are no tasks.
        """
        notifications = Notification.objects.filter(
            error=1,
            acknowledged=0
        )

        try:
            last_created_task = Task.objects.filter(
                completed=0).order_by("-created_on")[0].to_dict()
        except IndexError:
            last_created_task = None
        try:
            last_completed_task = Task.objects.filter(
                completed=1).order_by("-completed_on")[0].to_dict()
        except IndexError:
            last_completed_task = None

        status = {
            "error_notifications": [note.to_dict() for note in notifications],
            "last_created_task": last_created_task,
            "last_completed_task": last_completed_task
        }

        return Response(status, status=200)


class NotificationList(APIViewWithLogger):

    @utils.admin
    @parse_filters
    def get(self, request, filters=None, format=None):
        """
        A list of Notification objects as dicts.
        """
        if filters:
            notifications = Notification.objects.filter(
                **filters).order_by("-created_on")
        else:
            notifications = Notification.objects.all().order_by("-created_on")
        note_list = []
        for notification in notifications:
            note_list.append(notification.to_dict())
        return Response({"notifications": note_list}, status=200)

    @utils.admin
    def post(self, request, format=None):
        """
        Acknowledge notifications.
        """
        note_list = request.data.get('notifications', None)
        if note_list and isinstance(note_list, list):
            notifications = Notification.objects.filter(uuid__in=note_list)
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

    @utils.admin
    def get(self, request, uuid, format=None):
        """
        Dict notification of a Notification object
        and its related actions.
        """
        try:
            notification = Notification.objects.get(uuid=uuid)
        except Notification.DoesNotExist:
            return Response(
                {'errors': ['No notification with this id.']},
                status=404)
        return Response(notification.to_dict())

    @utils.admin
    def post(self, request, uuid, format=None):
        """
        Acknowledge notification.
        """
        try:
            notification = Notification.objects.get(uuid=uuid)
        except Notification.DoesNotExist:
            return Response(
                {'errors': ['No notification with this id.']},
                status=404)

        if notification.acknowledged:
            return Response({'notes': ['Notification already acknowledged.']},
                            status=200)
        if request.data.get('acknowledged', False) is True:
            notification.acknowledged = True
            notification.save()
            return Response({'notes': ['Notification acknowledged.']},
                            status=200)
        else:
            return Response({'acknowledged': ["this field is required."]},
                            status=400)


class TaskList(APIViewWithLogger):

    @utils.admin
    @parse_filters
    def get(self, request, filters=None, format=None):
        """
        A list of dict representations of Task objects
        and their related actions.
        """

        page = request.GET.get('page', 1)
        tasks_per_page = request.GET.get('tasks_per_page', None)

        if 'admin' in request.keystone_user['roles']:
            if filters:
                tasks = Task.objects.filter(**filters).order_by("-created_on")
            else:
                tasks = Task.objects.all().order_by("-created_on")

            if tasks_per_page:
                paginator = Paginator(tasks, tasks_per_page)
                try:
                    tasks = paginator.page(page)
                except EmptyPage:
                    return Response({'tasks': [],
                                     'pages': paginator.num_pages,
                                     'has_more': False,
                                     'has_prev': False}, status=200)
                    # NOTE(amelia): 'has_more'and 'has_prev' names are
                    # based on the horizon pagination table pagination names
                except PageNotAnInteger:
                    return Response({'error': 'Page not an integer'},
                                    status=400)

            task_list = []
            for task in tasks:
                task_list.append(task._to_dict())
            if tasks_per_page:
                return Response({'tasks': task_list,
                                 'pages': paginator.num_pages,
                                 'has_more': tasks.has_next(),
                                 'has_prev': tasks.has_previous()}, status=200)
            else:
                return Response({'tasks': task_list})
        else:
            if filters:
                # Ignore any filters with project_id in them
                for field_filter in filters.keys():
                    if "project_id" in field_filter:
                        filters.pop(field_filter)

                tasks = Task.objects.filter(
                    project_id__exact=request.keystone_user['project_id'],
                    **filters).order_by("-created_on")
            else:
                tasks = Task.objects.filter(
                    project_id__exact=request.keystone_user['project_id']
                ).order_by("-created_on")

            paginator = Paginator(tasks, tasks_per_page)
            tasks = paginator.page(page)

            task_list = []
            for task in tasks:
                task_list.append(task.to_dict())
            return Response({'tasks': task_list,
                             'pages': paginator.num_pages}, status=200)


class TaskDetail(APIViewWithLogger):

    @utils.mod_or_admin
    def get(self, request, uuid, format=None):
        """
        Dict representation of a Task object
        and its related actions.
        """
        try:
            if 'admin' in request.keystone_user['roles']:
                task = Task.objects.get(uuid=uuid)
                return Response(task._to_dict())
            else:
                task = Task.objects.get(
                    uuid=uuid, project_id=request.keystone_user['project_id'])
                return Response(task.to_dict())
        except Task.DoesNotExist:
            return Response(
                {'errors': ['No task with this id.']},
                status=404)

    @utils.admin
    def put(self, request, uuid, format=None):
        """
        Allows the updating of action data and retriggering
        of the pre_approve step.
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

    @utils.admin
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

        try:
            if request.data.get('approved') is not True:
                return Response(
                    {'approved': ["this is a required boolean field."]},
                    status=400)
        except ParseError:
            return Response(
                {'approved': ["this is a required boolean field."]},
                status=400)

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

        # we check that the task is valid before approving it:
        valid = True
        for action in task.actions:
            if not action.valid:
                valid = False

        if not valid:
            return Response(
                {'errors':
                    ['Cannot approve an invalid task. ' +
                     'Update data and rerun pre_approve.']},
                status=400)

        # We approve the task before running actions,
        # that way if something goes wrong we know if it was approved,
        # when it was approved, and who approved it last. Subsequent
        # reapproval attempts overwrite previous approved_by/on.
        task.approved = True
        task.approved_by = request.keystone_user
        task.approved_on = timezone.now()
        task.save()

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
            if need_token:
                token = create_token(task)
                try:
                    class_conf = settings.TASK_SETTINGS.get(
                        task.task_type, settings.DEFAULT_TASK_SETTINGS)

                    # will throw a key error if the token template has not
                    # been specified
                    email_conf = class_conf['emails']['token']
                    send_stage_email(task, email_conf, token)
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
                class_conf = settings.TASK_SETTINGS.get(
                    task.task_type, settings.DEFAULT_TASK_SETTINGS)
                email_conf = class_conf.get(
                    'emails', {}).get('completed', None)
                send_stage_email(task, email_conf)

                return Response(
                    {'notes': ["Task completed successfully."]},
                    status=200)
        return Response({'errors': ['actions invalid']}, status=400)

    @utils.mod_or_admin
    def delete(self, request, uuid, format=None):
        """
        Cancel the Task.

        Project Admins and Project Mods can only cancel tasks
        associated with their project.
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
            {'notes': ["Task cancelled successfully."]},
            status=200)


class TokenList(APIViewWithLogger):
    """
    Admin functionality for managing/monitoring tokens.
    """

    @utils.admin
    @parse_filters
    def get(self, request, filters=None, format=None):
        """
        A list of dict representations of Token objects.
        """
        if filters:
            tokens = Token.objects.filter(**filters).order_by("-created_on")
        else:
            tokens = Token.objects.all().order_by("-created_on")
        token_list = []
        for token in tokens:
            token_list.append(token.to_dict())
        return Response({"tokens": token_list})

    @utils.mod_or_admin
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
            if 'admin' in request.keystone_user['roles']:
                task = Task.objects.get(uuid=uuid)
            else:
                task = Task.objects.get(
                    uuid=uuid, project_id=request.keystone_user['project_id'])
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
            class_conf = settings.TASK_SETTINGS.get(
                task.task_type, settings.DEFAULT_TASK_SETTINGS)

            # will throw a key error if the token template has not
            # been specified
            email_conf = class_conf['emails']['token']
            send_stage_email(task, email_conf, token)
        except KeyError as e:
            notes = {
                'errors': [
                    ("Error: '%(error)s' while sending token. " +
                     "See registration itself for details.") % {'error': e}
                ],
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

    @utils.admin
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
            if token.expires < timezone.now():
                token.delete()
                token = Token.objects.get(token=id)
        except Token.DoesNotExist:
            return Response(
                {'errors': ['This token does not exist or has expired.']},
                status=404)

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

        return Response({'actions': [str(act) for act in actions],
                         'required_fields': required_fields})

    def post(self, request, id, format=None):
        """
        Ensures the required fields are present,
        will then pass those to the actions via the submit
        function.
        """
        try:
            token = Token.objects.get(token=id)
            if token.expires < timezone.now():
                token.delete()
                token = Token.objects.get(token=id)
        except Token.DoesNotExist:
            return Response(
                {'errors': ['This token does not exist or has expired.']},
                status=404)

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
            a = action.get_action()
            actions.append(a)
            for field in a.token_fields:
                required_fields.add(field)

        errors = {}
        data = {}

        for field in required_fields:
            try:
                data[field] = request.data[field]
            except KeyError:
                errors[field] = ["This field is required.", ]
            except TypeError:
                errors = ["Improperly formated json. " +
                          "Should be a key-value object.", ]
                break

        if errors:
            return Response({"errors": errors}, status=400)

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
        class_conf = settings.TASK_SETTINGS.get(
            token.task.task_type, settings.DEFAULT_TASK_SETTINGS)
        email_conf = class_conf.get(
            'emails', {}).get('completed', None)
        send_stage_email(token.task, email_conf)

        return Response(
            {'notes': ["Token submitted successfully."]},
            status=200)
