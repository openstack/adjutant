#  Copyright (C) 2015 Catalyst IT Ltd
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

from unittest import mock

from confspirator.tests import utils as conf_utils
from django.core import mail
from rest_framework import status

from adjutant.api.models import Token, Notification
from adjutant.tasks.models import Task
from adjutant.tasks.v1.projects import CreateProjectAndUser
from adjutant.common.tests.fake_clients import FakeManager, setup_identity_cache
from adjutant.common.tests import fake_clients
from adjutant.common.tests.utils import AdjutantAPITestCase
from adjutant.config import CONF


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
class DelegateAPITests(AdjutantAPITestCase):
    """
    Tests to ensure the approval/token workflow does what is
    expected with the given DelegateAPIs. These test don't check
    final results for actions, simply that the tasks, action,
    and tokens are created/updated.
    """

    def test_bad_data(self):
        """
        Simple test to confirm the serializers are correctly processing
        wrong data or missing fields.
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
            "wrong_email_field": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {"errors": {"email": ["This field is required."]}}
        )

        data = {
            "email": "not_a_valid_email",
            "roles": ["not_a_valid_role"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {
                "errors": {
                    "email": ["Enter a valid email address."],
                    "roles": ['"not_a_valid_role" is not a valid choice.'],
                }
            },
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.invite_user_to_project.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "invite_user_to_project"},
                    },
                },
            ],
        },
    )
    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create task, create token, submit token.
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

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "invite_user_to_project")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            fake_clients.identity_cache["new_users"][0].name, "test@example.com"
        )

    def test_new_user_no_project(self):
        """
        Can't create a user for a non-existent project.
        """
        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": "test_project_id",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"errors": ["actions invalid"]})

    def test_new_user_not_my_project(self):
        """
        Can't create a user for project that user isn't'
        project admin or mod on.
        """
        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "member",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": "test_project_id",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_user_not_authenticated(self):
        """
        Can't create a user if unauthenticated.
        """

        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {}
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": "test_project_id",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json(), {"errors": ["Credentials incorrect or none given."]}
        )

    def test_add_user_existing(self):
        """
        Adding existing user to project.
        """
        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

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

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"confirm": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_user_existing_with_role(self):
        """
        Adding existing user to project.
        Already has role.
        Should 'complete' anyway but do nothing.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="member",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

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

        tasks = Task.objects.all()
        self.assertEqual(1, len(tasks))
        self.assertTrue(tasks[0].completed)

    def test_new_project(self):
        """
        Ensure the new project workflow goes as expected.
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
        self.assertEqual(response.json(), {"notes": ["created token"]})

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.create_project_and_user.notifications": [
                {
                    "operation": "override",
                    "value": {
                        "standard_handler_config": {
                            "EmailNotification": {
                                "emails": ["example_notification@example.com"],
                                "reply": "no-reply@example.com",
                            }
                        }
                    },
                },
            ],
        },
    )
    def test_new_project_invalid_on_submit(self):
        """
        Ensures that when a project becomes invalid at the submit stage
        that the a 400 is recieved and no final emails are sent.
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
        self.assertEqual(response.data, {"notes": ["created token"]})
        self.assertEqual(len(mail.outbox), 3)

        fake_clients.identity_cache["projects"] = {}

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 3)

    def test_new_project_existing(self):
        """
        Test to ensure validation marks actions as invalid
        if project is already present.
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
        self.assertEqual(response.json(), {"errors": ["actions invalid"]})

    def test_new_project_existing_user(self):
        """
        Project created if not present, existing user attached.
        No token should be needed.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        # unauthenticated sign up as existing user
        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": user.email}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # approve the sign-up as admin
        headers = {
            "project_name": "admin_project",
            "project_id": "admin_project_id",
            "roles": "admin,member",
            "username": "admin",
            "user_id": "admin_id",
            "authenticated": True,
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"notes": ["Task completed successfully."]})

    def test_new_project_existing_project_new_user(self):
        """
        Project already exists but new user attempting to create it.
        """
        setup_identity_cache()

        # create signup#1 - project1 with user 1
        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Create signup#2 - project1 with user 2
        data = {"project_name": "test_project", "email": "test2@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        headers = {
            "project_name": "admin_project",
            "project_id": "admin_project_id",
            "roles": "admin,member",
            "username": "admin",
            "user_id": "admin_id",
            "authenticated": True,
        }
        # approve signup #1
        new_task1 = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task1.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["created token"]})

        # Attempt to approve signup #2
        new_task2 = Task.objects.all()[1]
        url = "/v1/tasks/" + new_task2.uuid
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"errors": ["actions invalid"]})

    def test_reset_user(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
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
        data = {"password": "new_test_password"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, "new_test_password")

    def test_reset_user_duplicate(self):
        """
        Request password reset twice in a row
        The first token should become invalid, with the second replacing it.

        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        # Submit password reset
        url = "/v1/actions/ResetPassword"
        data = {"email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        # Verify the first token doesn't work
        first_token = Token.objects.all()[0]

        # Submit password reset again
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        # confirm the old toke has been cleared:
        second_token = Token.objects.all()[0]
        self.assertNotEqual(first_token.token, second_token.token)

        # Now reset with the second token
        url = "/v1/tokens/" + second_token.token
        data = {"password": "new_test_password2"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, "new_test_password2")

    def test_reset_user_no_existing(self):
        """
        Actions should be successful, so usernames are not exposed.
        """

        setup_identity_cache()

        url = "/v1/actions/ResetPassword"
        data = {"email": "test@exampleinvalid.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        self.assertFalse(len(Token.objects.all()))

    def test_notification_CreateProjectAndUser(self):
        """
        CreateProjectAndUser should create a notification.
        We should be able to grab it.
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

    def test_duplicate_tasks_new_project(self):
        """
        Ensure we can't submit duplicate tasks
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {"project_name": "test_project_2", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_duplicate_tasks_new_user(self):
        """
        Ensure we can't submit duplicate tasks
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
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {
            "email": "test2@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_update_email_task(self):
        """
        Ensure the update email workflow goes as expected.
        Create task, create token, submit token.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": user.id,
            "authenticated": True,
        }

        data = {"new_email": "new_test@example.com"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.name, "new_test@example.com")

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.update_user_email.additional_actions": [
                {"operation": "append", "value": "SendAdditionalEmailAction"},
            ],
            "adjutant.workflow.tasks.update_user_email.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "update_user_email_token"},
                    },
                },
            ],
            "adjutant.workflow.tasks.update_user_email.actions": [
                {
                    "operation": "update",
                    "value": {
                        "SendAdditionalEmailAction": {
                            "prepare": {
                                "subject": "update_user_email_additional",
                                "template": "update_user_email_started.txt",
                                "email_roles": [],
                                "email_current_user": True,
                            }
                        }
                    },
                },
            ],
        },
    )
    def test_update_email_task_send_email_to_current_user(self):
        """
        Tests the email update workflow, and ensures that when setup
        to send a confirmation email to the old email address it does.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": user.id,
            "authenticated": True,
        }

        data = {"new_email": "new_test@example.com"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data, {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertEqual(mail.outbox[0].subject, "update_user_email_additional")

        self.assertEqual(mail.outbox[1].to, ["new_test@example.com"])
        self.assertEqual(mail.outbox[1].subject, "update_user_email_token")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.name, "new_test@example.com")

        self.assertEqual(len(mail.outbox), 3)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.update_user_email.additional_actions": [
                {"operation": "append", "value": "SendAdditionalEmailAction"},
            ],
            "adjutant.workflow.tasks.update_user_email.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "update_user_email_token"},
                    },
                },
            ],
            "adjutant.workflow.tasks.update_user_email.actions": [
                {
                    "operation": "update",
                    "value": {
                        "SendAdditionalEmailAction": {
                            "prepare": {
                                "subject": "update_user_email_additional",
                                "template": "update_user_email_started.txt",
                                "email_roles": [],
                                "email_current_user": True,
                            }
                        }
                    },
                },
            ],
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_update_email_task_send_email_current_name_not_email(self):
        """
        Tests the email update workflow when USERNAME_IS_EMAIL=False, and
        ensures that when setup to send a confirmation email to the old
        email address it does.
        """

        user = fake_clients.FakeUser(
            name="nkdfslnkls", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "nkdfslnkls",
            "user_id": user.id,
            "authenticated": True,
            "email": "test@example.com",
        }

        data = {"new_email": "new_test@example.com"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data, {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["test@example.com"])
        self.assertEqual(mail.outbox[0].subject, "update_user_email_additional")

        self.assertEqual(mail.outbox[1].to, ["new_test@example.com"])
        self.assertEqual(mail.outbox[1].subject, "update_user_email_token")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(mail.outbox), 3)

    def test_update_email_task_invalid_email(self):

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": user.id,
            "authenticated": True,
        }

        data = {"new_email": "new_test@examplecom"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {"errors": {"new_email": ["Enter a valid email address."]}}
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
            "adjutant.workflow.tasks.update_user_email.emails": [
                {"operation": "update", "value": {"initial": None}},
            ],
        },
    )
    def test_update_email_pre_existing_user_with_email(self):

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="new_test@example.com", password="123", email="new_test@example.com"
        )

        setup_identity_cache(users=[user, user2])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
            "project_domain_id": "default",
        }

        data = {"new_email": "new_test@example.com"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"errors": ["actions invalid"]})
        self.assertEqual(len(Token.objects.all()), 0)

        self.assertEqual(len(mail.outbox), 0)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
            "adjutant.workflow.tasks.update_user_email.emails": [
                {"operation": "update", "value": {"initial": None}},
            ],
        },
    )
    def test_update_email_user_with_email_username_not_email(self):

        user = fake_clients.FakeUser(
            name="test", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="new_test", password="123", email="new_test@example.com"
        )

        setup_identity_cache(users=[user, user2])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": user.id,
            "authenticated": True,
        }

        data = {"new_email": "new_test@example.com"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 2)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.email, "new_test@example.com")
        self.assertEqual(len(mail.outbox), 3)

    def test_update_email_task_not_authenticated(self):
        """
        Ensure that an unauthenticated user cant access the endpoint.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {}

        data = {"new_email": "new_test@examplecom"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_update_email_task_username_not_email(self):

        user = fake_clients.FakeUser(
            name="test_user", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test_user",
            "user_id": user.id,
            "authenticated": True,
        }

        data = {"new_email": "new_test@example.com"}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.name, "test_user")
        self.assertEqual(user.email, "new_test@example.com")

    # Tests for USERNAME_IS_EMAIL=False
    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "invite_user_to_project"},
                    },
                },
            ],
        },
    )
    def test_invite_user_to_project_email_not_username(self):
        """
        Invites a user where the email is different to the username.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "user",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "username": "new_user",
            "email": "new@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "invite_user_to_project")
        self.assertEqual(mail.outbox[0].to[0], "new@example.com")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(fake_clients.identity_cache["new_users"][0].name, "new_user")

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
            "adjutant.workflow.tasks.reset_user_password.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "Password Reset for OpenStack"},
                    },
                },
            ],
        },
    )
    def test_reset_user_username_not_email(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
        """

        user = fake_clients.FakeUser(
            name="test_user", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        # NOTE(amelia): Requiring both username and email here may be
        #               a slight issue for various UIs as typically a
        #               forgotten password screen only asks for the
        #               email address, however there isn't a very
        #               good way to address this as keystone doesn't
        #               store emails in their own field
        #               Currently this is an issue for the forked adjutant
        #               horizon
        data = {"email": "test@example.com", "username": "test_user"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.json()["notes"],
            ["If user with email exists, reset token will be issued."],
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Password Reset for OpenStack")
        self.assertEqual(mail.outbox[0].to[0], "test@example.com")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "new_test_password"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, "new_test_password")

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_new_project_username_not_email(self):
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {
            "project_name": "test_project",
            "email": "test@example.com",
            "username": "test",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        data = {
            "email": "new_test@example.com",
            "username": "new",
            "project_name": "new_project",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid

        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "admin",
            "username": "test",
            "user_id": "test_user_id",
            "email": "test@example.com",
            "authenticated": True,
        }
        response = self.client.post(
            url, {"approved": True}, format="json", headers=headers
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True, "password": "1234"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.invite_user_to_project.additional_actions": [
                {"operation": "append", "value": "SendAdditionalEmailAction"},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.emails": [
                {"operation": "update", "value": {"initial": None}},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.actions": [
                {
                    "operation": "update",
                    "value": {
                        "SendAdditionalEmailAction": {
                            "prepare": {
                                "subject": "invite_user_to_project_additional",
                                "template": "update_user_email_started.txt",
                                "email_roles": ["project_admin"],
                            }
                        }
                    },
                },
            ],
        },
    )
    def test_additional_emails_roles(self):
        """
        Tests the sending of additional emails to a set of roles in a project
        """

        # NOTE(amelia): sending this email here is probably not the intended
        # case. It would be more useful in utils such as a quota update or a
        # child project being created that all the project admins should be
        # notified of

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        user2 = fake_clients.FakeUser(
            name="test2@example.com", password="123", email="test2@example.com"
        )

        user3 = fake_clients.FakeUser(
            name="test3@example.com", password="123", email="test2@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user2.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user2.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user3.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_mod",
                user={"id": user3.id},
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user, user2, user3], role_assignments=assignments
        )

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
            "email": "new_test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(len(mail.outbox[0].to), 2)
        self.assertEqual(set(mail.outbox[0].to), set([user.email, user2.email]))
        self.assertEqual(mail.outbox[0].subject, "invite_user_to_project_additional")

        # Test that the token email gets sent to the other addresses
        self.assertEqual(mail.outbox[1].to[0], "new_test@example.com")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True, "password": "1234"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.invite_user_to_project.additional_actions": [
                {"operation": "append", "value": "SendAdditionalEmailAction"},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "invite_user_to_project_token"},
                    },
                },
            ],
            "adjutant.workflow.tasks.invite_user_to_project.actions": [
                {
                    "operation": "update",
                    "value": {
                        "SendAdditionalEmailAction": {
                            "prepare": {
                                "subject": "invite_user_to_project_additional",
                                "template": "update_user_email_started.txt",
                                "email_roles": ["project_admin"],
                            }
                        }
                    },
                },
            ],
        },
    )
    def test_additional_emails_role_no_email(self):
        """
        Tests that setting email roles to something that has no people to
        send to that the update action doesn't fall over
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="member",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        data = {"email": "new_test@example.com", "roles": ["member"]}
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data, {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 1)

        # Test that the token email gets sent to the other addresses
        self.assertEqual(mail.outbox[0].to[0], "new_test@example.com")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {"confirm": True, "password": "1234"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.invite_user_to_project.additional_actions": [
                {"operation": "append", "value": "SendAdditionalEmailAction"},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.emails": [
                {"operation": "update", "value": {"initial": None}},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.actions": [
                {
                    "operation": "update",
                    "value": {
                        "SendAdditionalEmailAction": {
                            "prepare": {
                                "subject": "invite_user_to_project_additional",
                                "template": "update_user_email_started.txt",
                                "email_additional_addresses": ["admin@example.com"],
                            }
                        }
                    },
                },
            ],
        },
    )
    def test_email_additional_addresses(self):
        """
        Tests the sending of additional emails an admin email set in
        the conf
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user.id},
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=assignments
        )

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }

        data = {"email": "new_test@example.com", "roles": ["member"]}
        response = self.client.post(url, data, format="json", headers=headers)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(set(mail.outbox[0].to), set(["admin@example.com"]))
        self.assertEqual(mail.outbox[0].subject, "invite_user_to_project_additional")

        # Test that the token email gets sent to the other addresses
        self.assertEqual(mail.outbox[1].to[0], "new_test@example.com")

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {"password": "testpassword"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.tasks.invite_user_to_project.additional_actions": [
                {"operation": "append", "value": "SendAdditionalEmailAction"},
            ],
            "adjutant.workflow.tasks.invite_user_to_project.emails": [
                {
                    "operation": "update",
                    "value": {
                        "initial": None,
                        "token": {"subject": "invite_user_to_project_token"},
                    },
                },
            ],
            "adjutant.workflow.tasks.invite_user_to_project.actions": [
                {
                    "operation": "update",
                    "value": {
                        "SendAdditionalEmailAction": {
                            "prepare": {
                                "subject": "invite_user_to_project_additional",
                                "template": "update_user_email_started.txt",
                                "email_additional_addresses": ["admin@example.com"],
                            }
                        }
                    },
                },
            ],
        },
    )
    def test_email_additional_action_invalid(self):
        """
        The additional email actions should not send an email if the
        action is invalid.
        """

        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": "test_project_id",
            "roles": "project_admin,member,project_mod",
            "username": "test@example.com",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": "test_project_id",
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"errors": ["actions invalid"]})
        self.assertEqual(len(mail.outbox), 0)

    @mock.patch("adjutant.common.tests.fake_clients.FakeManager.find_project")
    def test_all_actions_setup(self, mocked_find):
        """
        Ensures that all actions have been setup before prepare is
        run on any actions, even if we have a prepare failure.

        Deals with: bug/1745053
        """

        setup_identity_cache()

        mocked_find.side_effect = KeyError("Error forced for testing")

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

        new_task = Task.objects.all()[0]

        class_conf = new_task.config
        expected_action_names = CreateProjectAndUser.default_actions[:]
        expected_action_names += class_conf.additional_actions

        actions = new_task.actions
        observed_action_names = [a.action_name for a in actions]
        self.assertEqual(observed_action_names, expected_action_names)

    @mock.patch("adjutant.common.tests.fake_clients.FakeManager.find_project")
    def test_task_error_handler(self, mocked_find):
        """
        Ensure the _handle_task_error function works as expected.
        """

        setup_identity_cache()

        mocked_find.side_effect = KeyError("Error forced for testing")

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

        self.assertEqual(
            response.json(),
            {"errors": ["Service temporarily unavailable, try again later."]},
        )

        new_task = Task.objects.all()[0]
        new_notification = Notification.objects.all()[0]

        self.assertTrue(new_notification.error)
        self.assertEqual(
            new_notification.notes,
            {
                "errors": [
                    "Error: KeyError('Error forced for testing') while setting up "
                    "task. See task itself for details."
                ]
            },
        )
        self.assertEqual(new_notification.task, new_task)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.can_edit_users": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_user_invite_cant_edit_users(self):
        """
        When can_edit_users is false, and a new user is invited,
        the task should be marked as invalid if the user doesn't
        already exist.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "user",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "username": "new_user",
            "email": "new@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"errors": ["actions invalid"]})

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.can_edit_users": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_user_invite_cant_edit_users_existing_user(self):
        """
        When can_edit_users is false, and a new user is invited,
        the task should be marked as valid if the user exists.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(name="test@example.com")

        setup_identity_cache(projects=[project], users=[user])

        url = "/v1/actions/InviteUser"
        headers = {
            "project_name": "test_project",
            "project_id": project.id,
            "roles": "project_admin,member,project_mod",
            "username": "user",
            "user_id": "test_user_id",
            "authenticated": True,
        }
        data = {
            "username": "new_user",
            "email": "test@example.com",
            "roles": ["member"],
            "project_id": project.id,
        }
        response = self.client.post(url, data, format="json", headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.can_edit_users": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_project_create_cant_edit_users(self):
        """
        When can_edit_users is false, and a new signup comes in,
        the task should be marked as invalid if it needs to
        create a new user.

        Will return OK (as task doesn't auto_approve), but task will
        actually be invalid.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})
        task = Task.objects.all()[0]
        action_models = task.actions
        actions = [act.get_action() for act in action_models]
        self.assertFalse(all([act.valid for act in actions]))

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.can_edit_users": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_project_create_cant_edit_users_existing_user(self):
        """
        When can_edit_users is false, and a new signup comes in,
        the task should be marked as valid if the user already
        exists.

        Will return OK (as task doesn't auto_approve), but task will
        actually be valid.
        """
        user = fake_clients.FakeUser(name="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/CreateProjectAndUser"
        data = {"project_name": "test_project", "email": "test@example.com"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.json(), {"notes": ["task created"]})
        task = Task.objects.all()[0]
        action_models = task.actions
        actions = [act.get_action() for act in action_models]
        self.assertTrue(all([act.valid for act in actions]))
