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

from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView

from adjutant.api import utils
from adjutant.api.views import SingleVersionView
from adjutant.api.models import Notification, Token
from adjutant.api.v1.utils import parse_filters
from adjutant import exceptions
from adjutant.tasks.v1.manager import TaskManager
from adjutant.tasks.models import Task


class V1VersionEndpoint(SingleVersionView):
    version = "1.0"


class APIViewWithLogger(APIView):
    """
    APIView with a logger.
    """

    def __init__(self, *args, **kwargs):
        super(APIViewWithLogger, self).__init__(*args, **kwargs)
        self.logger = getLogger("adjutant")
        self.task_manager = TaskManager()


class StatusView(APIViewWithLogger):
    @utils.admin
    def get(self, request, filters=None, format=None):
        """
        Simple status endpoint.

        Returns a list of unacknowledged error notifications,
        and both the last created and last completed tasks.

        Can returns None, if there are no tasks.
        """
        notifications = Notification.objects.filter(error=1, acknowledged=0)

        try:
            last_created_task = (
                Task.objects.filter(completed=0).order_by("-created_on")[0].to_dict()
            )
        except IndexError:
            last_created_task = None
        try:
            last_completed_task = (
                Task.objects.filter(completed=1).order_by("-completed_on")[0].to_dict()
            )
        except IndexError:
            last_completed_task = None

        status = {
            "error_notifications": [note.to_dict() for note in notifications],
            "last_created_task": last_created_task,
            "last_completed_task": last_completed_task,
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
            notifications = Notification.objects.filter(**filters).order_by(
                "-created_on"
            )
        else:
            notifications = Notification.objects.all().order_by("-created_on")

        page = request.GET.get("page", 1)
        notifs_per_page = request.GET.get("notifications_per_page", None)

        if notifs_per_page:
            paginator = Paginator(notifications, notifs_per_page)
            try:
                notifications = paginator.page(page)
            except EmptyPage:
                return Response({"errors": ["Empty page"]}, status=400)
            except PageNotAnInteger:
                return Response({"errors": ["Page not an integer"]}, status=400)

        note_list = []
        for notification in notifications:
            note_list.append(notification.to_dict())
        if notifs_per_page:
            return Response(
                {
                    "notifications": note_list,
                    "pages": paginator.num_pages,
                    "has_more": notifications.has_next(),
                    "has_prev": notifications.has_previous(),
                },
                status=200,
            )

        return Response({"notifications": note_list}, status=200)

    @utils.admin
    def post(self, request, format=None):
        """
        Acknowledge notifications.
        """
        note_list = request.data.get("notifications", None)
        if note_list and isinstance(note_list, list):
            notifications = Notification.objects.filter(uuid__in=note_list)
            for notification in notifications:
                notification.acknowledged = True
                notification.save()
            return Response({"notes": ["Notifications acknowledged."]}, status=200)
        else:
            return Response(
                {"notifications": ["this field is required and needs to be a list."]},
                status=400,
            )


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
            return Response({"errors": ["No notification with this id."]}, status=404)
        return Response(notification.to_dict())

    @utils.admin
    def post(self, request, uuid, format=None):
        """
        Acknowledge notification.
        """
        try:
            notification = Notification.objects.get(uuid=uuid)
        except Notification.DoesNotExist:
            return Response({"errors": ["No notification with this id."]}, status=404)

        if notification.acknowledged:
            return Response(
                {"notes": ["Notification already acknowledged."]}, status=200
            )
        if request.data.get("acknowledged", False) is True:
            notification.acknowledged = True
            notification.save()
            return Response({"notes": ["Notification acknowledged."]}, status=200)
        else:
            return Response({"acknowledged": ["this field is required."]}, status=400)


class TaskList(APIViewWithLogger):
    @utils.admin
    @parse_filters
    def get(self, request, filters=None, format=None):
        """
        A list of dict representations of Task objects
        and their related actions.
        """

        page = request.GET.get("page", 1)
        tasks_per_page = request.GET.get("tasks_per_page", None)

        if not filters:
            filters = {}

        # TODO(adriant): better handle this bit of incode policy
        if "admin" not in request.keystone_user["roles"]:
            # Ignore any filters with project_id in them
            for field_filter in filters.keys():
                if "project_id" in field_filter:
                    filters.pop(field_filter)

            filters["project_id__exact"] = request.keystone_user["project_id"]

        tasks = Task.objects.filter(**filters).order_by("-created_on")

        if tasks_per_page:
            paginator = Paginator(tasks, tasks_per_page)
            try:
                tasks = paginator.page(page)
            except EmptyPage:
                return Response({"errors": ["Empty page"]}, status=400)
            except PageNotAnInteger:
                return Response({"errors": ["Page not an integer"]}, status=400)
        task_list = []
        for task in tasks:
            task_list.append(task.to_dict())

        if tasks_per_page:
            return Response(
                {
                    "tasks": task_list,
                    "pages": paginator.num_pages,
                    "has_more": tasks.has_next(),
                    "has_prev": tasks.has_previous(),
                },
                status=200,
            )
            # NOTE(amelia): 'has_more'and 'has_prev' names are
            # based on the horizon pagination table pagination names
        else:
            return Response({"tasks": task_list})


class TaskDetail(APIViewWithLogger):
    @utils.mod_or_admin
    def get(self, request, uuid, format=None):
        """
        Dict representation of a Task object
        and its related actions.
        """
        try:
            # TODO(adriant): better handle this bit of incode policy
            if "admin" in request.keystone_user["roles"]:
                task = Task.objects.get(uuid=uuid)
            else:
                task = Task.objects.get(
                    uuid=uuid, project_id=request.keystone_user["project_id"]
                )
            return Response(task.to_dict())
        except Task.DoesNotExist:
            return Response({"errors": ["No task with this id."]}, status=404)

    @utils.admin
    def put(self, request, uuid, format=None):
        """
        Allows the updating of action data and retriggering
        of the prepare step.
        """
        self.task_manager.update(uuid, request.data)

        return Response({"notes": ["Task successfully updated."]}, status=200)

    @utils.admin
    def post(self, request, uuid, format=None):
        """
        Will approve the Task specified,
        followed by running the approve actions
        and if valid will setup and create a related token.
        """
        try:
            if request.data.get("approved") is not True:
                raise exceptions.TaskSerializersInvalid(
                    {"approved": ["this is a required boolean field."]}
                )
        except ParseError:
            raise exceptions.TaskSerializersInvalid(
                {"approved": ["this is a required boolean field."]}
            )

        task = self.task_manager.approve(uuid, request.keystone_user)

        if task.completed:
            return Response({"notes": ["Task completed successfully."]}, status=200)
        else:
            return Response({"notes": ["created token"]}, status=202)

    @utils.mod_or_admin
    def delete(self, request, uuid, format=None):
        """
        Cancel the Task.

        Project Admins and Project Mods can only cancel tasks
        associated with their project.
        """
        try:
            # TODO(adriant): better handle this bit of incode policy
            if "admin" in request.keystone_user["roles"]:
                task = Task.objects.get(uuid=uuid)
            else:
                task = Task.objects.get(
                    uuid=uuid, project_id=request.keystone_user["project_id"]
                )
        except Task.DoesNotExist:
            return Response({"errors": ["No task with this id."]}, status=404)

        self.task_manager.cancel(task)

        return Response({"notes": ["Task cancelled successfully."]}, status=200)


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
        uuid = request.data.get("task", None)
        if uuid is None:
            return Response(
                {
                    "errors": {
                        "task": [
                            "This field is required.",
                        ]
                    }
                },
                status=400,
            )
        try:
            # TODO(adriant): better handle this bit of incode policy
            if "admin" in request.keystone_user["roles"]:
                task = Task.objects.get(uuid=uuid)
            else:
                task = Task.objects.get(
                    uuid=uuid, project_id=request.keystone_user["project_id"]
                )
        except Task.DoesNotExist:
            return Response({"errors": ["No task with this id."]}, status=404)

        self.task_manager.reissue_token(task)
        return Response({"notes": ["Token reissued."]}, status=200)

    @utils.admin
    def delete(self, request, format=None):
        """
        Delete all expired tokens.
        """
        now = timezone.now()
        Token.objects.filter(expires__lt=now).delete()
        return Response({"notes": ["Deleted all expired tokens."]}, status=200)


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
                {"errors": ["This token does not exist or has expired."]}, status=404
            )

        if token.task.completed:
            return Response(
                {"errors": ["This task has already been completed."]}, status=400
            )

        if token.task.cancelled:
            return Response({"errors": ["This task has been cancelled."]}, status=400)

        required_fields = []
        actions = []

        for action in token.task.actions:
            action = action.get_action()
            actions.append(action)
            for field in action.token_fields:
                if field not in required_fields:
                    required_fields.append(field)

        return Response(
            {
                "actions": [str(act) for act in actions],
                "required_fields": required_fields,
                "task_type": token.task.task_type,
                "requires_authentication": token.task.get_task().token_requires_authentication,
            }
        )

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
                {"errors": ["This token does not exist or has expired."]}, status=404
            )

        task = self.task_manager.get(token.task)
        if task.token_requires_authentication and not request.keystone_user.get(
            "authenticated", False
        ):
            return Response(
                {"errors": ["This token requires authentication to submit."]}, 401
            )

        self.task_manager.submit(task, request.data, request.keystone_user)

        return Response({"notes": ["Token submitted successfully."]}, status=200)
