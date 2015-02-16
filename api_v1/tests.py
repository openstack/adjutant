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

from rest_framework import status
from rest_framework.test import APITestCase
from api_v1.models import Registration, Token
import mock
from django.utils import timezone
from datetime import timedelta


temp_cache = {}


class FakeManager(object):

    def find_user(self, name):
        global temp_cache
        return temp_cache['users'].get(name, None)

    def get_user(self, user_id):
        pass

    def create_user(self, name, password, email, project_id):
        global temp_cache
        user = mock.Mock()
        temp_cache['i'] += 1
        user.id = temp_cache['i']
        user.name = name
        user.password = password
        user.email = email
        user.default_project = project_id
        temp_cache['users'][name] = user
        return user

    def update_user_password(self, user, password):
        global temp_cache
        user = temp_cache['users'][user.name]
        user.password = password

    def find_role(self, name):
        global temp_cache
        temp_cache['roles'].get(name, None)

    def add_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        project.roles.append((user, role))

    def find_project(self, project_name):
        global temp_cache
        return temp_cache['projects'].get(project_name, None)

    def get_project(self, project_id):
        global temp_cache
        for project in temp_cache['projects'].values():
            if project.id == project_id:
                return project

    def create_project(self, project_name, p_id=None):
        global temp_cache
        project = mock.Mock()
        if p_id:
            project.id = p_id
        else:
            temp_cache['i'] += 1
            project.id = temp_cache['i']
        project.name = project_name
        project.roles = []
        temp_cache['projects'][project_name] = project
        return project


class APITests(APITestCase):
    """Tests to ensure the approval/token workflow does
       what is expected. These test don't check final
       results for actions, simply that the registrations,
       action, and tokens are created/updated.

       These tests also focus on authentication status
       and role prermissions."""

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create registration, create token, submit token.
        """
        global temp_cache

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = []

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {'test_project': project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'role': "Member",
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_no_project(self):
        """
        Can't create a user for a non-existent project.
        """
        global temp_cache

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'role': "Member",
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'notes': ['actions invalid']})

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_not_my_project(self):
        """
        Can't create a user for project that isn't mine.
        """
        global temp_cache

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'role': "Member",
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data,
            {'notes':
                [("Must have one of the following roles: " +
                  "['admin', 'project_owner']")]}
        )

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_not_my_project_admin(self):
        """
        Can create a user for project that isn't mine if admin.
        """
        global temp_cache

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = []

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {'test_project': project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'role': "Member",
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_not_authenticated(self):
        """
        Can't create a user if unauthenticated.
        """
        global temp_cache

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {}
        data = {'email': "test@example.com", 'role': "Member",
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data,
            {'notes':
                [("Must have one of the following roles: " +
                  "['admin', 'project_owner']")]}
        )

    @mock.patch('base.models.IdentityManager', FakeManager)
    @mock.patch('tenant_setup.models.IdentityManager', FakeManager)
    def test_new_project(self):
        """
        Ensure the new project workflow goes as expected.
        """
        global temp_cache
        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_registration = Registration.objects.all()[0]
        url = "/api_v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_token = Token.objects.all()[0]
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('base.models.IdentityManager', FakeManager)
    @mock.patch('tenant_setup.models.IdentityManager', FakeManager)
    def test_new_project_existing(self):
        """
        Test to ensure validation marks actions as invalid
        if project is already present.
        """
        global temp_cache

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = []

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {'test_project': project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/api_v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_registration = Registration.objects.all()[0]
        url = "/api_v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'notes': ['actions invalid']})

    @mock.patch('base.models.IdentityManager', FakeManager)
    @mock.patch('tenant_setup.models.IdentityManager', FakeManager)
    def test_new_project_existing_user(self):
        """
        Project created if not present, existing user attached.
        No token should be needed.
        """
        global temp_cache

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/api_v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_registration = Registration.objects.all()[0]
        url = "/api_v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': 'Registration completed successfully.'}
        )

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_reset_user(self):
        """
        Ensure the reset user workflow goes as expected.
        Create registration + create token, submit token.
        """
        global temp_cache

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password')

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_reset_user_no_existing(self):
        """
        Actions should be invalid.
        """
        global temp_cache

        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'notes': ['actions invalid']})

    def test_no_token_get(self):
        """
        Should be a 404.
        """
        url = "/api_v1/token/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'notes': ['This token does not exist.']})

    def test_no_token_post(self):
        """
        Should be a 404.
        """
        url = "/api_v1/token/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'notes': ['This token does not exist.']})

    def test_no_registration_get(self):
        """
        Should be a 404.
        """
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/api_v1/registration/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'notes': ['No registration with this id.']})

    def test_no_registration_post(self):
        """
        Should be a 404.
        """
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/api_v1/registration/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'notes': ['No registration with this id.']})

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_token_expired_post(self):
        """
        Expired token should do nothing, then delete itself.
        """
        global temp_cache

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/api_v1/token/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'notes': ['This token has expired.']})
        self.assertEqual(0, Token.objects.count())

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_token_expired_get(self):
        """
        Expired token should do nothing, then delete itself.
        """
        global temp_cache

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/api_v1/token/" + new_token.token
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'notes': ['This token has expired.']})
        self.assertEqual(0, Token.objects.count())

    @mock.patch('base.models.IdentityManager', FakeManager)
    @mock.patch('tenant_setup.models.IdentityManager', FakeManager)
    def test_registration_complete(self):
        """
        Can't approve a completed registration.
        """
        global temp_cache
        temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        url = "/api_v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        new_registration = Registration.objects.all()[0]
        new_registration.completed = True
        new_registration.save()
        url = "/api_v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'notes': ['This registration has already been completed.']})
