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

import mock

from django.test.utils import override_settings
from django.core import mail

from rest_framework import status

from adjutant.api.models import Task, Token
from adjutant.common.tests.fake_clients import (
    FakeManager, setup_identity_cache)
from adjutant.common.tests import fake_clients
from adjutant.common.tests.utils import (AdjutantAPITestCase,
                                         modify_dict_settings)


@mock.patch('adjutant.common.user_store.IdentityManager',
            FakeManager)
class TaskViewTests(AdjutantAPITestCase):
    """
    Tests to ensure the approval/token workflow does what is
    expected with the given TaskViews. These test don't check
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
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'wrong_email_field': "test@example.com", 'roles': ["_member_"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(),
                         {'email': ['This field is required.']})

        data = {'email': "not_a_valid_email", 'roles': ["not_a_valid_role"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(), {
                'email': ['Enter a valid email address.'],
                'roles': ['"not_a_valid_role" is not a valid choice.']})

    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create task, create token, submit token.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'invite_user')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            fake_clients.identity_cache['new_users'][0].name,
            'test@example.com')

    def test_new_user_no_project(self):
        """
        Can't create a user for a non-existent project.
        """
        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'errors': ['actions invalid']})

    def test_new_user_not_my_project(self):
        """
        Can't create a user for project that user isn't'
        project admin or mod on.
        """
        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_new_user_not_authenticated(self):
        """
        Can't create a user if unauthenticated.
        """

        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {}
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json(),
            {'errors': ["Credentials incorrect or none given."]}
        )

    def test_add_user_existing(self):
        """
        Adding existing user to project.
        """
        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(projects=[project], users=[user])

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_user_existing_with_role(self):
        """
        Adding existing user to project.
        Already has role.
        Should 'complete' anyway but do nothing.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        assignment = fake_clients.FakeRoleAssignment(
            scope={'project': {'id': project.id}},
            role_name="_member_",
            user={'id': user.id}
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment])

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {'notes': ['Task completed successfully.']})

    def test_new_project(self):
        """
        Ensure the new project workflow goes as expected.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {'notes': ['created token']}
        )

        new_project = fake_clients.identity_cache['new_projects'][0]
        self.assertEqual(new_project.name, 'test_project')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_new_project_invalid_on_submit(self):
        """
        Ensures that when a project becomes invalid at the submit stage
        that the a 400 is recieved and no final emails are sent.
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': ['created token']}
        )
        self.assertEqual(len(mail.outbox), 3)

        fake_clients.identity_cache['projects'] = {}

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 3)

    def test_new_project_existing(self):
        """
        Test to ensure validation marks actions as invalid
        if project is already present.
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'errors': ['Cannot approve an invalid task. ' +
                        'Update data and rerun pre_approve.']})

    def test_new_project_existing_user(self):
        """
        Project created if not present, existing user attached.
        No token should be needed.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        # unauthenticated sign up as existing user
        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': user.email}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # approve the sign-up as admin
        headers = {
            'project_name': "admin_project",
            'project_id': "admin_project_id",
            'roles': "admin,_member_",
            'username': "admin",
            'user_id': "admin_id",
            'authenticated': True
        }
        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {'notes': ['Task completed successfully.']}
        )

    def test_new_project_existing_project_new_user(self):
        """
        Project already exists but new user attempting to create it.
        """
        setup_identity_cache()

        # create signup#1 - project1 with user 1
        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Create signup#2 - project1 with user 2
        data = {'project_name': "test_project", 'email': "test2@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "admin_project",
            'project_id': "admin_project_id",
            'roles': "admin,_member_",
            'username': "admin",
            'user_id': "admin_id",
            'authenticated': True
        }
        # approve signup #1
        new_task1 = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task1.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {'notes': ['created token']}
        )

        # Attempt to approve signup #2
        new_task2 = Task.objects.all()[1]
        url = "/v1/tasks/" + new_task2.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {'errors': ['actions invalid']}
        )

    def test_reset_user(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['notes'],
            ['If user with email exists, reset token will be issued.'])

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password')

    def test_reset_user_duplicate(self):
        """
        Request password reset twice in a row
        The first token should become invalid, with the second replacing it.

        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        # Submit password reset
        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['notes'],
            ['If user with email exists, reset token will be issued.'])

        # Submit password reset again
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['notes'],
            ['If user with email exists, reset token will be issued.'])

        # Verify the first token doesn't work
        first_token = Token.objects.all()[0]
        url = "/v1/tokens/" + first_token.token
        data = {'password': 'new_test_password1'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(user.password, '123')

        # Now reset with the second token
        second_token = Token.objects.all()[1]
        url = "/v1/tokens/" + second_token.token
        data = {'password': 'new_test_password2'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password2')

    def test_reset_user_no_existing(self):
        """
        Actions should be successful, so usernames are not exposed.
        """

        setup_identity_cache()

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@exampleinvalid.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['notes'],
            ['If user with email exists, reset token will be issued.'])

    def test_notification_createproject(self):
        """
        CreateProject should create a notification.
        We should be able to grab it.
        """
        setup_identity_cache()

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_task = Task.objects.all()[0]

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        url = "/v1/notifications"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['notifications'][0]['task'],
            new_task.uuid)

    def test_duplicate_tasks_new_project(self):
        """
        Ensure we can't submit duplicate tasks
        """

        setup_identity_cache()

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {'project_name': "test_project_2", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_duplicate_tasks_new_user(self):
        """
        Ensure we can't submit duplicate tasks
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_return_task_id_if_admin(self):
        """
        Confirm that the task id is returned when admin.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # make sure the task is actually valid
        new_task = Task.objects.all()[0]
        self.assertTrue(all([a.valid for a in new_task.actions]))

        self.assertEqual(
            response.json()['task'],
            new_task.uuid)

    def test_return_task_id_if_admin_fail(self):
        """
        Confirm that the task id is not returned unless admin.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "_member_",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # make sure the task is actually valid
        new_task = Task.objects.all()[0]
        self.assertTrue(all([a.valid for a in new_task.actions]))

        self.assertFalse(response.json().get('task'))

    def test_update_email_task(self):
        """
        Ensure the update email workflow goes as expected.
        Create task, create token, submit token.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': user.id,
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.name, 'new_test@example.com')

    @modify_dict_settings(TASK_SETTINGS=[
        {'key_list': ['update_email', 'additional_actions'],
         'operation': 'append',
         'value': ['SendAdditionalEmailAction']},
        {'key_list': ['update_email', 'action_settings',
                      'SendAdditionalEmailAction', 'initial'],
         'operation': 'update',
         'value': {
            'subject': 'email_update_additional',
            'template': 'email_update_started.txt',
            'email_roles': [],
            'email_current_user': True,
        }
        }
    ])
    def test_update_email_task_send_email_to_current_user(self):
        """
        Tests the email update workflow, and ensures that when setup
        to send a confirmation email to the old email address it does.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': user.id,
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['test@example.com'])
        self.assertEqual(mail.outbox[0].subject, 'email_update_additional')

        self.assertEqual(mail.outbox[1].to, ['new_test@example.com'])
        self.assertEqual(mail.outbox[1].subject, 'email_update_token')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.name, 'new_test@example.com')

        self.assertEqual(len(mail.outbox), 3)

    @modify_dict_settings(TASK_SETTINGS=[
        {'key_list': ['update_email', 'additional_actions'],
         'operation': 'append',
         'value': ['SendAdditionalEmailAction']},
        {'key_list': ['update_email', 'action_settings',
                      'SendAdditionalEmailAction', 'initial'],
         'operation': 'update',
         'value': {
            'subject': 'email_update_additional',
            'template': 'email_update_started.txt',
            'email_roles': [],
            'email_current_user': True}
         }
    ])
    @override_settings(USERNAME_IS_EMAIL=False)
    def test_update_email_task_send_email_current_name_not_email(self):
        """
        Tests the email update workflow when USERNAME_IS_EMAIL=False, and
        ensures that when setup to send a confirmation email to the old
        email address it does.
        """

        user = fake_clients.FakeUser(
            name="nkdfslnkls", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "nkdfslnkls",
            'user_id': user.id,
            'authenticated': True,
            'email': 'test@example.com',
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['test@example.com'])
        self.assertEqual(mail.outbox[0].subject, 'email_update_additional')

        self.assertEqual(mail.outbox[1].to, ['new_test@example.com'])
        self.assertEqual(mail.outbox[1].subject, 'email_update_token')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(mail.outbox), 3)

    def test_update_email_task_invalid_email(self):

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': user.id,
            'authenticated': True
        }

        data = {'new_email': "new_test@examplecom"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(),
                         {'new_email': [u'Enter a valid email address.']})

    @override_settings(USERNAME_IS_EMAIL=True)
    def test_update_email_pre_existing_user_with_email(self):

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        user2 = fake_clients.FakeUser(
            name="new_test@example.com", password="123",
            email="new_test@example.com")

        setup_identity_cache(users=[user, user2])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True,
            'project_domain_id': 'default',
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), ['actions invalid'])
        self.assertEqual(len(Token.objects.all()), 0)

        self.assertEqual(len(mail.outbox), 0)

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_update_email_user_with_email_username_not_email(self):

        user = fake_clients.FakeUser(
            name="test", password="123", email="test@example.com")

        user2 = fake_clients.FakeUser(
            name="new_test", password="123",
            email="new_test@example.com")

        setup_identity_cache(users=[user, user2])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': user.id,
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.email, 'new_test@example.com')

    def test_update_email_task_not_authenticated(self):
        """
        Ensure that an unauthenticated user cant access the endpoint.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
        }

        data = {'new_email': "new_test@examplecom"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_update_email_task_username_not_email(self):

        user = fake_clients.FakeUser(
            name="test_user", password="123", email="test@example.com")

        setup_identity_cache(users=[user])

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test_user",
            'user_id': user.id,
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.name, "test_user")
        self.assertEqual(user.email, 'new_test@example.com')

    # Tests for USERNAME_IS_EMAIL=False
    @override_settings(USERNAME_IS_EMAIL=False)
    def test_invite_user_email_not_username(self):
        """
        Invites a user where the email is different to the username.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "user",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'username': 'new_user', 'email': "new@example.com",
                'roles': ["_member_"], 'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'invite_user')
        self.assertEqual(mail.outbox[0].to[0], 'new@example.com')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(
            fake_clients.identity_cache['new_users'][0].name,
            'new_user')

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_reset_user_username_not_email(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
        """

        user = fake_clients.FakeUser(
            name="test_user", password="123", email="test@example.com")

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
        data = {'email': "test@example.com", 'username': 'test_user'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()['notes'],
            ['If user with email exists, reset token will be issued.'])

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject,
                         'Password Reset for OpenStack')
        self.assertEqual(mail.outbox[0].to[0], 'test@example.com')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password')

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_new_project_username_not_email(self):
        setup_identity_cache()

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com",
                'username': 'test'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {'email': "new_test@example.com", 'username': "new",
                'project_name': 'new_project'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['task created']})

        new_task = Task.objects.all()[0]
        url = "/v1/tasks/" + new_task.uuid

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin",
            'username': "test",
            'user_id': "test_user_id",
            'email': "test@example.com",
            'authenticated': True
        }
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True, 'password': '1234'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @modify_dict_settings(
        TASK_SETTINGS=[
            {'key_list': ['invite_user', 'additional_actions'],
             'operation': 'append',
             'value': ['SendAdditionalEmailAction']},
            {'key_list': ['invite_user', 'action_settings',
                          'SendAdditionalEmailAction', 'initial'],
             'operation': 'update',
             'value': {
                'subject': 'email_update_additional',
                'template': 'email_update_started.txt',
                'email_roles': ['project_admin'],
                'email_current_user': False,
            }
            }
        ])
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
            name="test@example.com", password="123", email="test@example.com")

        user2 = fake_clients.FakeUser(
            name="test2@example.com", password="123",
            email="test2@example.com")

        user3 = fake_clients.FakeUser(
            name="test3@example.com", password="123",
            email="test2@example.com")

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="_member_",
                user={'id': user.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="project_admin",
                user={'id': user.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="_member_",
                user={'id': user2.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="project_admin",
                user={'id': user2.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="_member_",
                user={'id': user3.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="project_mod",
                user={'id': user3.id}
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user, user2, user3],
            role_assignments=assignments)

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'email': "new_test@example.com",
                'roles': ['_member_'], 'project_id': project.id}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(len(mail.outbox[0].to), 2)
        self.assertEqual(set(mail.outbox[0].to),
                         set([user.email, user2.email]))
        self.assertEqual(mail.outbox[0].subject, 'email_update_additional')

        # Test that the token email gets sent to the other addresses
        self.assertEqual(mail.outbox[1].to[0], 'new_test@example.com')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True, 'password': '1234'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @modify_dict_settings(
        TASK_SETTINGS=[
            {'key_list': ['invite_user', 'additional_actions'],
             'operation': 'append',
             'value': ['SendAdditionalEmailAction']},
            {'key_list': ['invite_user', 'action_settings',
                          'SendAdditionalEmailAction', 'initial'],
             'operation': 'update',
             'value': {
                'subject': 'email_update_additional',
                'template': 'email_update_started.txt',
                'email_roles': ['project_admin'],
                'email_current_user': False,
            }
            }
        ])
    def test_additional_emails_role_no_email(self):
        """
        Tests that setting email roles to something that has no people to
        send to that the update action doesn't fall over
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        assignment = fake_clients.FakeRoleAssignment(
            scope={'project': {'id': project.id}},
            role_name="_member_",
            user={'id': user.id}
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment])

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'email': "new_test@example.com",
                'roles': ['_member_']}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)

        # Test that the token email gets sent to the other addresses
        self.assertEqual(mail.outbox[0].to[0], 'new_test@example.com')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True, 'password': '1234'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @modify_dict_settings(
        TASK_SETTINGS=[
            {'key_list': ['invite_user', 'additional_actions'],
             'operation': 'override',
             'value': ['SendAdditionalEmailAction']},
            {'key_list': ['invite_user', 'action_settings',
                          'SendAdditionalEmailAction', 'initial'],
             'operation': 'update',
             'value':{
                'subject': 'invite_user_additional',
                'template': 'email_update_started.txt',
                'email_additional_addresses': ['admin@example.com'],
                'email_current_user': False,
            }
            }
        ])
    def test_email_additional_addresses(self):
        """
        Tests the sending of additional emails an admin email set in
        the conf
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com")

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="_member_",
                user={'id': user.id}
            ),
            fake_clients.FakeRoleAssignment(
                scope={'project': {'id': project.id}},
                role_name="project_admin",
                user={'id': user.id}
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=assignments)

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': project.id,
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'email': "new_test@example.com", 'roles': ['_member_']}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 2)

        self.assertEqual(set(mail.outbox[0].to),
                         set(['admin@example.com']))
        self.assertEqual(mail.outbox[0].subject, 'invite_user_additional')

        # Test that the token email gets sent to the other addresses
        self.assertEqual(mail.outbox[1].to[0], 'new_test@example.com')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @modify_dict_settings(
        TASK_SETTINGS=[
            {'key_list': ['invite_user', 'additional_actions'],
             'operation': 'override',
             'value': ['SendAdditionalEmailAction']},
            {'key_list': ['invite_user', 'action_settings',
                          'SendAdditionalEmailAction', 'initial'],
             'operation': 'update',
             'value':{
                'subject': 'invite_user_additional',
                'template': 'email_update_started.txt',
                'email_additional_addresses': ['admin@example.com'],
                'email_current_user': False,
            }
            }
        ])
    def test_email_additional_action_invalid(self):
        """
        The additional email actions should not send an email if the
        action is invalid.
        """

        setup_identity_cache()

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'errors': ['actions invalid']})
        self.assertEqual(len(mail.outbox), 0)
