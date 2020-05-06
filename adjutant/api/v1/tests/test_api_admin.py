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

from datetime import timedelta
import json
from unittest import mock
from unittest import skip

from confspirator.tests import utils as conf_utils
from django.utils import timezone
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase

from adjutant.api.models import Task, Token, Notification
from adjutant.common.tests import fake_clients
from adjutant.common.tests.fake_clients import FakeManager, setup_identity_cache
from adjutant.config import CONF
from adjutant.tasks.v1.users import InviteUser
from adjutant.tasks.v1.manager import TaskManager


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
class AdminAPITests(APITestCase):
    """
    Tests to ensure the admin api endpoints work as expected within
    the context of the approval/token workflow.
    """

    def test_no_token_get(self):
        """
        Should be a 404.
        """
        url = "/v1/tokens/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(), {"errors": ["This token does not exist or has expired."]}
        )

    def test_no_token_post(self):
        """
        Should be a 404.
        """
        url = "/v1/tokens/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(), {"errors": ["This token does not exist or has expired."]}
        )

    def test_task_get(self):
        """
        Test the basic task detail view.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.get(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_no_task_get(self):
        """
        Should be a 404.
        """
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tasks/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"errors": ["No task with this id."]})

    def test_no_task_post(self):
        """
        Should be a 404.
        """
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tasks/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(),
            {
                "errors": [
                    "Task not found with uuid of: " "'e8b3f57f5da64bf3a6bf4f9bbd3a40b5'"
                ]
            },
        )

    def test_token_expired_post(self):
        """
        Expired token should do nothing, then delete itself.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/v1/tokens/" + new_token.token
        data = {"password": "new_test_password"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(), {"errors": ["This token does not exist or has expired."]}
        )
        self.assertEqual(0, Token.objects.count())

    def test_token_expired_get(self):
        """
        Expired token should do nothing, then delete itself.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/v1/tokens/" + new_token.token
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(), {"errors": ["This token does not exist or has expired."]}
        )
        self.assertEqual(0, Token.objects.count())

    def test_token_get(self):
        """
        Token should contain actions, task_type, required fields.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "actions": ["ResetUserPasswordAction"],
                "required_fields": ["password"],
                "task_type": "reset_user_password",
                "requires_authentication": False,
            },
        )
        self.assertEqual(1, Token.objects.count())

    def test_token_list_get(self):
        """
        Create two password resets, then confirm we can list tokens.
        """
        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="test2@example.com", password="123", email="test2@example.com"
        )

        setup_identity_cache(users=[user, user2])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        data = {"email": "test2@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tokens/"

        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["tokens"]), 2)

        task_ids = [t.uuid for t in Task.objects.all()]

        token_task_ids = [t["task"] for t in response.json()["tokens"]]

        self.assertEqual(sorted(task_ids), sorted(token_task_ids))

    def test_task_complete(self):
        """
        Can't approve a completed task.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        new_task = Task.objects.all()[0]
        new_task.completed = True
        new_task.save()
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {"errors": ["This task has already been completed."]}
        )

    def test_status_page(self):
        """
        Status page gives details of last_created_task, last_completed_task
        and error notifcations
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/status/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["last_created_task"]["actions"][0]["data"]["email"],
            "test@example.com",
        )
        self.assertEqual(response.json()["last_completed_task"], None)

        self.assertEqual(response.json()["error_notifications"], [])

        # Create a second task and ensure it is the new last_created_task
        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project_2", "email": "test_2@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        url = "/v1/status/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["last_created_task"]["actions"][0]["data"]["email"],
            "test_2@example.com",
        )
        self.assertEqual(response.json()["last_completed_task"], None)

        self.assertEqual(response.json()["error_notifications"], [])

        new_task = Task.objects.all()[0]
        new_task.completed = True
        new_task.save()

        url = "/v1/status/"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["last_completed_task"]["actions"][0]["data"]["email"],
            "test@example.com",
        )
        self.assertEqual(
            response.json()["last_created_task"]["actions"][0]["data"]["email"],
            "test_2@example.com",
        )

        self.assertEqual(response.json()["error_notifications"], [])

    def test_task_update(self):
        """
        Creates a invalid task.

        Updates it and attempts to reapprove.
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "project_name": "test_project2",
            "email": "test@example.com",
            "region": "RegionOne",
        }
        response = self.client.put(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"notes": ["Task successfully updated."]})

        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["created token"]})

    def test_notification_get(self):
        """
        Test that you can get details of an induvidual notfication.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_task = Task.objects.all()[0]

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        note = Notification.objects.first().uuid

        url = "/v1/notifications/%s" % note
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["task"], new_task.uuid)
        self.assertEqual(
            response.json()["notes"],
            {"notes": ["'create_project_and_user' task needs approval."]},
        )
        self.assertEqual(response.json()["error"], False)

    def test_notification_doesnt_exist(self):
        """
        Test that you get a 404 trying to access a non-existent notification.
        """
        setup_identity_cache()

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        note = "notarealnotifiactionuuid"

        url = "/v1/notifications/%s/" % note
        response = self.client.get(url, headers=headers, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"errors": ["No notification with this id."]})

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.task_defaults.notifications.standard_handlers": [
                {"operation": "override", "value": []},
            ],
        },
    )
    def test_notification_acknowledge(self):
        """
        Test that you can acknowledge a notification.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_task = Task.objects.all()[0]

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["notifications"][0]["task"], new_task.uuid)

        url = "/v1/notifications/%s/" % response.json()["notifications"][0]["uuid"]
        data = {"acknowledged": True}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.json(), {"notes": ["Notification acknowledged."]})

        url = "/v1/notifications"
        params = {"filters": json.dumps({"acknowledged": {"exact": False}})}
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.json(), {"notifications": []})

    def test_notification_acknowledge_doesnt_exist(self):
        """
        Test that you cant acknowledge a non-existent notification.
        """
        setup_identity_cache()

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/notifications/dasdaaaiooiiobksd/"
        response = self.client.post(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"errors": ["No notification with this id."]})

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.task_defaults.notifications.standard_handlers": [
                {"operation": "override", "value": []},
            ],
        },
    )
    def test_notification_re_acknowledge(self):
        """
        Test that you cant reacknowledge a notification.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        note_id = Notification.objects.first().uuid
        url = "/v1/notifications/%s/" % note_id
        data = {"acknowledged": True}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"notes": ["Notification acknowledged."]})

        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(), {"notes": ["Notification already acknowledged."]}
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.task_defaults.notifications.standard_handlers": [
                {"operation": "override", "value": []},
            ],
        },
    )
    def test_notification_acknowledge_no_data(self):
        """
        Test that you have to include 'acknowledged': True to the request.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        note_id = Notification.objects.first().uuid
        url = "/v1/notifications/%s/" % note_id
        data = {}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"acknowledged": ["this field is required."]})

    def test_notification_acknowledge_list(self):
        """
        Test that you can acknowledge a list of notifications.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = {"project_name": "test_project2", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = "/v1/notifications"
        notifications = response.json()["notifications"]
        data = {"notifications": [note["uuid"] for note in notifications]}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.json(), {"notes": ["Notifications acknowledged."]})

        url = "/v1/notifications"
        params = {"filters": json.dumps({"acknowledged": {"exact": False}})}
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.json(), {"notifications": []})

    def test_notification_acknowledge_list_empty_list(self):
        """
        Test that you cannot acknowledge an empty list of notifications.
        """
        setup_identity_cache()

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {"notifications": []}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {"notifications": ["this field is required and needs to be a list."]},
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.create_project_and_user.notifications": [
                {
                    "operation": "override",
                    "value": {
                        "standard_handlers": ["EmailNotification"],
                        "error_handlers": ["EmailNotification"],
                        "standard_handler_config": {
                            "EmailNotification": {
                                "emails": ["example@example.com"],
                                "reply": "no-reply@example.com",
                            }
                        },
                        "error_handler_config": {
                            "EmailNotification": {
                                "emails": ["example@example.com"],
                                "reply": "no-reply@example.com",
                            }
                        },
                    },
                },
            ],
            "adjutant.workflow.tasks.create_project_and_user.emails": [
                {
                    "operation": "override",
                    "value": {"initial": None, "token": None, "completed": None},
                },
            ],
        },
    )
    def test_notification_email(self):
        """
        Tests the email notification handler
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_task = Task.objects.all()[0]

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["notifications"][0]["task"], new_task.uuid)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "create_project_and_user notification")
        self.assertTrue(
            "'create_project_and_user' task needs approval." in mail.outbox[0].body
        )

    def test_token_expired_delete(self):
        """
        test deleting of expired tokens.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="test2@example.com", password="123", email="test2@example.com"
        )

        setup_identity_cache(users=[user, user2])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        data = {"email": "test2@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        tokens = Token.objects.all()

        self.assertEqual(len(tokens), 2)

        new_token = tokens[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tokens/"
        response = self.client.delete(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"notes": ["Deleted all expired tokens."]})
        self.assertEqual(Token.objects.count(), 1)

    def test_token_reissue(self):
        """
        test for reissue of tokens
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        task = Task.objects.all()[0]
        new_token = Token.objects.all()[0]

        uuid = new_token.token

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"notes": ["Token reissued."]})
        self.assertEqual(Token.objects.count(), 1)
        new_token = Token.objects.all()[0]
        self.assertNotEqual(new_token.token, uuid)

    def test_token_reissue_non_admin(self):
        """
        test for reissue of tokens for non-admin
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        task = Task.objects.all()[0]
        new_token = Token.objects.all()[0]

        uuid = new_token.token

        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"notes": ["Token reissued."]})
        self.assertEqual(Token.objects.count(), 1)
        new_token = Token.objects.all()[0]
        self.assertNotEqual(new_token.token, uuid)

        # Now confirm it is limited by project id properly.
        headers["project_id"] = "test_project_id2"
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"errors": ["No task with this id."]})

    def test_token_reissue_task_cancelled(self):
        """
        Tests that a cancelled task cannot have a token reissued
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        task = Task.objects.all()[0]
        task.cancelled = True
        task.save()
        self.assertEqual(Token.objects.count(), 1)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"errors": ["This task has been cancelled."]})

    def test_token_reissue_task_completed(self):
        """
        Tests that a completed task cannot have a token reissued
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        task = Task.objects.all()[0]
        task.completed = True
        task.save()
        self.assertEqual(Token.objects.count(), 1)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {"errors": ["This task has already been completed."]}
        )

    def test_token_reissue_task_not_approve(self):
        """
        Tests that an unapproved task cannot have a token reissued
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"email": "test@example.com", "project_name": "test_project"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json()["notes"], ["task created"])

        task = Task.objects.all()[0]

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tokens/"
        data = {"task": task.uuid}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {"errors": ["This task has not been approved."]}
        )

    def test_cancel_task(self):
        """
        Ensure the ability to cancel a task.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.delete(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.put(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_task_sent_token(self):
        """
        Ensure the ability to cancel a task after the token is sent.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_token = Token.objects.all()[0]

        response = self.client.delete(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(0, Token.objects.count())
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reapprove_task_delete_tokens(self):
        """
        Tests that a reapproved task will delete all of it's previous tokens.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(Token.objects.all()), 1)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Reapprove
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Old token no longer found
        url = "/v1/tokens/" + new_token.token
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.assertEqual(len(Token.objects.all()), 1)

    def test_task_update_unapprove(self):
        """
        Ensure task update doesn't work for approved actions.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        new_task = Task.objects.all()[0]
        self.assertEqual(new_task.approved, True)

        data = {"project_name": "test_project2", "email": "test2@example.com"}
        response = self.client.put(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_task_own(self):
        """
        Ensure the ability to cancel your own task.
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.delete(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers["roles"] = "admin"
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.put(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_task_own_fail(self):
        """
        Ensure the ability to cancel ONLY your own task.
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        headers["project_id"] = "fake_project_id"
        response = self.client.delete(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_task_list(self):
        """
        Create some user invite tasks, then make sure we can list them.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = {
            "email": "test2@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = {
            "email": "test3@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tasks"
        response = self.client.get(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["tasks"]), 3)

    def test_task_list_ordering(self):
        """
        Test that tasks returns in the default sort.
        The default sort is by created_on descending.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = {
            "email": "test2@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = {
            "email": "test3@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        url = "/v1/tasks"
        response = self.client.get(url, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sorted_list = sorted(
            response.json()["tasks"], key=lambda k: k["created_on"], reverse=True
        )

        for i, task in enumerate(sorted_list):
            self.assertEqual(task, response.json()["tasks"][i])

    def test_task_list_filter(self):
        """"""
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = {
            "email": "test2@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project2", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        params = {
            "filters": json.dumps({"task_type": {"exact": "create_project_and_user"}})
        }

        url = "/v1/tasks"
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["tasks"]), 1)

        params = {
            "filters": json.dumps({"task_type": {"exact": "invite_user_to_project"}})
        }
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["tasks"]), 2)

    # TODO(adriant): enable this test again when filters are properly
    # blacklisted.
    @skip("Does not apply yet.")
    def test_task_list_filter_cross_project(self):
        """
        Ensure you can't override the initial project_id filter if
        you are not admin.
        """

        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        project2 = mock.Mock()
        project2.id = "test_project_id_2"
        project2.name = "test_project_2"
        project2.domain = "default"
        project2.roles = {}

        setup_identity_cache({"test_project": project, "test_project_2": project2}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": project.name,
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "owner@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": "test_project_id",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            "project_name": project2.name,
            "project_id": project2.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        params = {
            "filters": json.dumps(
                {
                    "project_id": {"exact": "test_project_id"},
                    "task_type": {"exact": "invite_user_to_project"},
                }
            )
        }
        url = "/v1/tasks"
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["tasks"]), 0)

    def test_task_list_filter_formating(self):
        """
        Test error states for badly formatted filters.
        """

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        # not proper json
        params = {"filters": {"task_type": {"exact": "create_project"}}}
        url = "/v1/tasks"
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # inncorrect format
        params = {"filters": json.dumps("gibbberish")}
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # inncorrect format
        params = {"filters": json.dumps({"task_type": ["exact", "value"]})}
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid operation
        params = {"filters": json.dumps({"task_type": {"dont_find": "value"}})}
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # invalid field
        params = {"filters": json.dumps({"fake": {"exact": "value"}})}
        response = self.client.get(url, params, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.action_defaults.ResetUserPasswordAction.blacklisted_roles": [
                {"operation": "append", "value": "admin"},
            ],
        },
    )
    def test_reset_admin(self):
        """
        Ensure that you cannot issue a password reset for an
        admin user.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="admin",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )
        self.assertEqual(0, Token.objects.count())

    @mock.patch("adjutant.common.tests.fake_clients.FakeManager.find_project")
    def test_apiview_error_handler(self, mocked_find):
        """
        Ensure the handle_task_error function works as expected for APIViews.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        mocked_find.side_effect = KeyError("Forced key error for testing.")

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        data = {
            "project_name": "test_project2",
            "email": "test@example.com",
        }
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin,member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        response = self.client.put(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

        self.assertEqual(
            response.json()["errors"],
            ["Service temporarily unavailable, try again later."],
        )

        new_task = Task.objects.all()[0]
        new_notification = Notification.objects.all()[1]

        self.assertTrue(new_notification.error)
        self.assertEqual(
            new_notification.notes,
            {
                "errors": [
                    "Error: KeyError('Forced key error for testing.') while "
                    "setting up task. See task itself for details."
                ]
            },
        )
        self.assertEqual(new_notification.task, new_task)

    @mock.patch.object(InviteUser, "token_requires_authentication", True)
    def test_token_require_authenticated(self):
        """
        test for reissue of tokens
        """
        project = mock.Mock()
        project.id = "test_project_id"
        project.name = "test_project"
        project.domain = "default"
        project.roles = {}

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": project.name,
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "owner@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": "test_project_id",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_token = Token.objects.all()[0]

        url = "/v1/tokens/" + new_token.token
        data = {"confirm": True}
        response = self.client.post(url, data, format="json", headers={})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json(),
            {"errors": ["This token requires authentication to submit."]},
        )

        headers = {
            "project_name": project.name,
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "owner@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        submitted_keystone_user = {}

        def mocked_submit(self, task, token_data, keystone_user):
            submitted_keystone_user.update(keystone_user)

        with mock.patch.object(TaskManager, "submit", mocked_submit):
            response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {"notes": ["Token submitted successfully."]},
        )
        self.assertEqual(
            submitted_keystone_user,
            {
                "authenticated": True,
                "project_domain_id": "default",
                "project_id": "test_project_id",
                "project_name": "test_project",
                "roles": ["project_admin", "member", "project_mod"],
                "user_domain_id": "default",
                "user_id": "test_user_id",
                "username": "owner@example.com",
            },
        )
