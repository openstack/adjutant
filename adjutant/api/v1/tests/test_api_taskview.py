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
from adjutant.api.v1.tests import (FakeManager, setup_temp_cache,
                                   AdjutantAPITestCase, modify_dict_settings)
from adjutant.api.v1 import tests


@mock.patch('adjutant.actions.user_store.IdentityManager',
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
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'wrong_email_field': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'email': ['This field is required.']})

        data = {'email': "not_a_valid_email", 'roles': ["not_a_valid_role"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data, {
                'email': ['Enter a valid email address.'],
                'roles': ['"not_a_valid_role" is not a valid choice.']})

    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create task, create token, submit token.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'invite_user')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].name,
            'test@example.com')

    def test_new_user_no_project(self):
        """
        Can't create a user for a non-existent project.
        """
        setup_temp_cache({}, {})

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
        self.assertEqual(response.data, {'errors': ['actions invalid']})

    def test_new_user_not_my_project(self):
        """
        Can't create a user for project that isn't mine.
        """
        setup_temp_cache({}, {})

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

        setup_temp_cache({}, {})

        url = "/v1/actions/InviteUser"
        headers = {}
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data,
            {'errors': ["Credentials incorrect or none given."]}
        )

    def test_add_user_existing(self):
        """
        Adding existing user to project.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {user.id: user})

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

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
        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['_member_']}

        setup_temp_cache({'test_project': project}, {user.id: user})

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': ['Task completed successfully.']})

    def test_new_project(self):
        """
        Ensure the new project workflow goes as expected.
        """

        setup_temp_cache({}, {})

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

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_new_project_existing(self):
        """
        Test to ensure validation marks actions as invalid
        if project is already present.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

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
            response.data,
            {'errors': ['Cannot approve an invalid task. ' +
                        'Update data and rerun pre_approve.']})

    def test_new_project_existing_user(self):
        """
        Project created if not present, existing user attached.
        No token should be needed.
        """

        # pre-create user
        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache(
            projects={},
            users={user.id: user})

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
            response.data,
            {'notes': ['Task completed successfully.']}
        )

    def test_new_project_existing_project_new_user(self):
        """
        Project already exists but new user attempting to create it.
        """
        setup_temp_cache({}, {})

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
            response.data,
            {'notes': ['created token']}
        )

        # Attempt to approve signup #2
        new_task2 = Task.objects.all()[1]
        url = "/v1/tasks/" + new_task2.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'errors': ['actions invalid']}
        )

    def test_reset_user(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
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

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        # Submit password reset
        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        # Submit password reset again
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

        # Verify the first token doesn't work
        first_token = Token.objects.all()[0]
        url = "/v1/tokens/" + first_token.token
        data = {'password': 'new_test_password1'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(user.password, 'test_password')

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

        setup_temp_cache({}, {})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@exampleinvalid.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['notes'],
            ['If user with email exists, reset token will be issued.'])

    def test_notification_createproject(self):
        """
        CreateProject should create a notification.
        We should be able to grab it.
        """
        setup_temp_cache({}, {})

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
            response.data['notifications'][0]['task'],
            new_task.uuid)

    def test_duplicate_tasks_new_project(self):
        """
        Ensure we can't submit duplicate tasks
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({}, {})

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
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

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
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_return_task_id_if_admin(self):
        """
        Confirm that the task id is returned when admin.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

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

        new_task = Task.objects.all()[0]
        self.assertEqual(
            response.data['task'],
            new_task.uuid)

    def test_return_task_id_if_admin_fail(self):
        """
        Confirm that the task id is not returned unless admin.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

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

        self.assertFalse(response.data.get('task'))

    def test_update_email_task(self):
        """
        Ensure the update email workflow goes as expected.
        Create task, create token, submit token.
        """

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEquals(user.name, 'new_test@example.com')

    def test_update_email_task_invalid_email(self):

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'new_email': "new_test@examplecom"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data,
                         {'new_email': [u'Enter a valid email address.']})

    @override_settings(USERNAME_IS_EMAIL=True)
    def test_update_email_pre_existing_user_with_email(self):

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        user2 = mock.Mock()
        user2.id = 'new_user_id'
        user2.name = "new_test@example.com"
        user2.email = "new_test@example.com"
        user2.domain = 'default'

        setup_temp_cache({}, {user.id: user, user2.id: user2})

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
        self.assertEqual(response.data, ['actions invalid'])
        self.assertEqual(len(Token.objects.all()), 0)

        self.assertEqual(len(mail.outbox), 0)

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_update_email_user_with_email_username_not_email(self):

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test"
        user.email = "test@example.com"
        user.domain = 'Default'

        user2 = mock.Mock()
        user2.id = 'new_user_id'
        user2.name = "new_test"
        user2.email = "new_test@example.com"
        user2.domain = 'Default'

        setup_temp_cache({}, {user.id: user, user2.id: user})

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEquals(user.email, 'new_test@example.com')

    def test_update_email_task_not_authenticated(self):
        """
        Ensure that an unauthenticated user cant access the endpoint.
        """

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/UpdateEmail"
        headers = {
        }

        data = {'new_email': "new_test@examplecom"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_update_email_task_username_not_email(self):

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test_user"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/UpdateEmail"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test_user",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'new_email': "new_test@example.com"}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token

        data = {'confirm': True}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEquals(user.name, "test_user")
        self.assertEquals(user.email, 'new_test@example.com')

    # Tests for USERNAME_IS_EMAIL=False
    @override_settings(USERNAME_IS_EMAIL=False)
    def test_invite_user_email_not_username(self):
        """
        Invites a user where the email is different to the username.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "user",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'username': 'new_user', 'email': "new@example.com",
                'roles': ["_member_"], 'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEquals(mail.outbox[0].subject, 'invite_user')
        self.assertEquals(mail.outbox[0].to[0], 'new@example.com')

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 2)

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].name,
            'new_user')

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_reset_user_username_not_email(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test_user"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

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
            response.data['notes'],
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
        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com",
                'username': 'test'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {'email': "new_test@example.com", 'username': "new",
                'project_name': 'new_project'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['task created']})

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
        # case. It would be more useful in cases such as a quota update or a
        # child project being created that all the project admins should be
        # notified of

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        user2 = mock.Mock()
        user2.id = 'test_user_id_2'
        user2.name = "test2@example.com"
        user2.email = "test2@example.com"
        user2.domain = 'default'

        user3 = mock.Mock()
        user3.id = 'test_user_id_3'
        user3.name = "test3@example.com"
        user3.email = "test3@example.com"
        user3.domain = 'default'

        project.roles = {user.id: ['project_admin', '_member_'],
                         user2.id: ['project_admin', '_member_'],
                         user3.id: ['project_mod', '_member_']}

        setup_temp_cache({'test_project': project},
                         {user.id: user, user2.id: user2, user3.id: user3})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
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

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'

        user = mock.Mock()
        user.id = 'test_user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        project.roles = {user.id: ['project_admin', '_member_']}
        setup_temp_cache({'test_project': project}, {user.id: user, })

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        data = {'email': "new_test@example.com", 'roles': ['_member_']}
        response = self.client.post(url, data, format='json', headers=headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

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

        setup_temp_cache({}, {})

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
        self.assertEqual(response.data, {'errors': ['actions invalid']})
        self.assertEqual(len(mail.outbox), 0)
