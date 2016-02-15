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

from stacktask.api.models import Token
from stacktask.api.v1.tests import FakeManager, setup_temp_cache


class OpenstackAPITests(APITestCase):
    """
    TaskView tests specific to the openstack style urls.
    Many of the original TaskView tests are valid and need
    not be repeated here, but some additional features in the
    unique TaskViews need testing.
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

        url = "/v1/openstack/users"
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
    def test_user_list(self):
        """
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/openstack/users"
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

        url = "/v1/openstack/users"
        data = {'email': "test2@example.com", 'roles': ["_member_"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch(
        'stacktask.actions.models.user_store.IdentityManager', FakeManager)
    def test_force_reset_password(self):
        """
        Ensure the force password endpoint works as expected,
        and only for admin.

        Should also check if template can be rendered.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
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

        url = "/v1/openstack/users/password-set"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        headers["roles"] = "admin,_member_"
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, None)

        new_token = Token.objects.all()[0]
        url = "/v1/tokens/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password')
