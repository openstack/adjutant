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

import mock

from rest_framework import status
from rest_framework.test import APITestCase

from stacktask.api.models import Task, Token
from stacktask.api.v1.tests import FakeManager, setup_temp_cache


class TaskViewTests(APITestCase):
    """
    Tests to ensure the approval/token workflow does what is
    expected with the given TaskViews. These test don't check
    final results for actions, simply that the tasks, action,
    and tokens are created/updated.
    """

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create task, create token, submit token.
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
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
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

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
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

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
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

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_add_user_existing(self):
        """
        Adding existing user to project.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

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

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
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

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
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
            {'notes': 'Task completed successfully.'})

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
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

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    def test_new_project_existing(self):
        """
        Test to ensure validation marks actions as invalid
        if project is already present.
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
        self.assertEqual(response.data, {'errors': ['actions invalid']})

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
    def test_new_project_existing_user(self):
        """
        Project created if not present, existing user attached.
        No token should be needed.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/InviteUser"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_admin,_member_,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
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
            {'notes': 'Task completed successfully.'}
        )

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_reset_user(self):
        """
        Ensure the reset user workflow goes as expected.
        Create task + create token, submit token.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password')

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_reset_user_duplicate(self):
        """
        Request password reset twice in a row
        The first token should become invalid, with the second replacing it.

        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        setup_temp_cache({}, {user.id: user})

        # Submit password reset
        url = "/v1/actions/ResetPassword"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)

        # Submit password reset again
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)

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

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_reset_user_no_existing(self):
        """
        Actions should be successful, so usernames are not exposed.
        """

        setup_temp_cache({}, {})

        url = "/v1/actions/ResetPassword"
        data = {'email': "test@exampleinvalid.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    @mock.patch('stacktask.actions.tenant_setup.models.IdentityManager',
                FakeManager)
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

    @mock.patch(
        'stacktask.actions.models.user_store.IdentityManager', FakeManager)
    @mock.patch(
        'stacktask.actions.tenant_setup.models.IdentityManager', FakeManager)
    def test_duplicate_tasks_new_project(self):
        """
        Ensure we can't submit duplicate tasks
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({}, {})

        url = "/v1/actions/CreateProject"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {'project_name': "test_project_2", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch(
        'stacktask.actions.models.user_store.IdentityManager', FakeManager)
    def test_duplicate_tasks_new_user(self):
        """
        Ensure we can't submit duplicate tasks
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
        data = {'email': "test@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
