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
from stacktask.api.models import Registration, Token
import mock
from django.utils import timezone
from datetime import timedelta


temp_cache = {}


def setup_temp_cache(projects, users):
    admin_user = mock.Mock()
    admin_user.id = 0
    admin_user.name = 'admin'
    admin_user.password = 'password'
    admin_user.email = 'admin@example.com'

    users.update({admin_user.name: admin_user})

    global temp_cache

    temp_cache = {
        'i': 1,
        'users': users,
        'projects': projects,
        'roles': {
            'Member': 'Member', 'admin': 'admin',
            'project_owner': 'project_owner',
            'project_mod': 'project_mod'
        }
    }


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
        return temp_cache['roles'].get(name, None)

    def get_roles(self, user, project):
        global temp_cache
        try:
            roles = []
            for role in project.roles[user.name]:
                r = mock.Mock()
                r.name = role
                roles.append(r)
            return roles
        except KeyError:
            return []

    def add_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        try:
            project.roles[user.name].append(role)
        except KeyError:
            project.roles[user.name] = [role]

    def remove_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        try:
            project.roles[user.name].remove(role)
        except KeyError:
            pass

    def find_project(self, project_name):
        global temp_cache
        return temp_cache['projects'].get(project_name, None)

    def get_project(self, project_id):
        global temp_cache
        for project in temp_cache['projects'].values():
            if project.id == project_id:
                return project

    def create_project(self, project_name, created_on, p_id=None):
        global temp_cache
        project = mock.Mock()
        if p_id:
            project.id = p_id
        else:
            temp_cache['i'] += 1
            project.id = temp_cache['i']
        project.name = project_name
        project.roles = {}
        temp_cache['projects'][project_name] = project
        return project


class APITests(APITestCase):
    """Tests to ensure the approval/token workflow does
       what is expected. These test don't check final
       results for actions, simply that the registrations,
       action, and tokens are created/updated.

       These tests also focus on authentication status
       and role prermissions."""

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_new_user(self):
        """
        Ensure the new user workflow goes as expected.
        Create registration, create token, submit token.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["Member"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_new_user_no_project(self):
        """
        Can't create a user for a non-existent project.
        """
        setup_temp_cache({}, {})

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["Member"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'errors': ['actions invalid']})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_new_user_not_my_project(self):
        """
        Can't create a user for project that isn't mine.
        """
        setup_temp_cache({}, {})

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["Member"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_new_user_not_authenticated(self):
        """
        Can't create a user if unauthenticated.
        """

        setup_temp_cache({}, {})

        url = "/v1/user"
        headers = {}
        data = {'email': "test@example.com", 'roles': ["Member"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data,
            {'errors': ["Credentials incorrect or none given."]}
        )

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
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

        setup_temp_cache({'test_project': project}, {user.name: user})

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["Member"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': 'Registration completed successfully.'})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
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
        project.roles = {user.name: ['Member']}

        setup_temp_cache({'test_project': project}, {user.name: user})

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        data = {'email': "test@example.com", 'roles': ["Member"],
                'project_id': 'test_project_id'}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': 'Registration completed successfully.'})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_new_project(self):
        """
        Ensure the new project workflow goes as expected.
        """

        setup_temp_cache({}, {})

        url = "/v1/project"
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
        url = "/v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_token = Token.objects.all()[0]
        url = "/v1/token/" + new_token.token
        data = {'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
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

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/project"
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
        url = "/v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'errors': ['actions invalid']})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_new_project_existing_user(self):
        """
        Project created if not present, existing user attached.
        No token should be needed.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        setup_temp_cache({}, {user.name: user})

        url = "/v1/user"
        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "project_owner,Member,project_mod",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/project"
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
        url = "/v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': 'Registration completed successfully.'}
        )

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_reset_user(self):
        """
        Ensure the reset user workflow goes as expected.
        Create registration + create token, submit token.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        setup_temp_cache({}, {user.name: user})

        url = "/v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        url = "/v1/token/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password, 'new_test_password')

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_reset_user_no_existing(self):
        """
        Actions should be invalid.
        """

        setup_temp_cache({}, {})

        url = "/v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'errors': ['actions invalid']})

    def test_no_token_get(self):
        """
        Should be a 404.
        """
        url = "/v1/token/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'errors': ['This token does not exist.']})

    def test_no_token_post(self):
        """
        Should be a 404.
        """
        url = "/v1/token/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'errors': ['This token does not exist.']})

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
        url = "/v1/registration/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.get(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'errors': ['No registration with this id.']})

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
        url = "/v1/registration/e8b3f57f5da64bf3a6bf4f9bbd3a40b5"
        response = self.client.post(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data, {'errors': ['No registration with this id.']})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_token_expired_post(self):
        """
        Expired token should do nothing, then delete itself.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        setup_temp_cache({}, {user.name: user})

        url = "/v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/v1/token/" + new_token.token
        data = {'password': 'new_test_password'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'errors': ['This token has expired.']})
        self.assertEqual(0, Token.objects.count())

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_token_expired_get(self):
        """
        Expired token should do nothing, then delete itself.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        setup_temp_cache({}, {user.name: user})

        url = "/v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        new_token = Token.objects.all()[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()
        url = "/v1/token/" + new_token.token
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'errors': ['This token has expired.']})
        self.assertEqual(0, Token.objects.count())

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_registration_complete(self):
        """
        Can't approve a completed registration.
        """
        setup_temp_cache({}, {})

        url = "/v1/project"
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
        url = "/v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data,
            {'errors': ['This registration has already been completed.']})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_registration_update(self):
        """
        Creates a invalid registration.

        Updates it and attempts to reapprove.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        url = "/v1/project"
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
        url = "/v1/registration/" + new_registration.uuid
        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {'project_name': "test_project2", 'email': "test@example.com"}
        response = self.client.put(url, data, format='json',
                                   headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': ['Registration successfully updated.']})

        response = self.client.post(url, {'approved': True}, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {'notes': ['created token']})

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_notification_createproject(self):
        """
        CreateProject should create a notification.
        We should be able to grab it.
        """
        setup_temp_cache({}, {})

        url = "/v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_registration = Registration.objects.all()[0]

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        url = "/v1/notification"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data[0]['registration'],
            new_registration.uuid)

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_notification_acknowledge(self):
        """
        Test that you can acknowledge a notification.
        """
        setup_temp_cache({}, {})

        url = "/v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_registration = Registration.objects.all()[0]

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }

        url = "/v1/notification"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data[0]['registration'],
            new_registration.uuid)

        url = "/v1/notification/%s/" % response.data[0]['pk']
        data = {'acknowledged': True}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.data,
                         {'notes': ['Notification acknowledged.']})

        url = "/v1/notification"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.data, [])

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    @mock.patch('stacktask.tenant_setup.models.IdentityManager', FakeManager)
    def test_notification_acknowledge_list(self):
        """
        Test that you can acknowledge a list of notifications.
        """
        setup_temp_cache({}, {})

        url = "/v1/project"
        data = {'project_name': "test_project", 'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {'project_name': "test_project2", 'email': "test@example.com"}
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

        url = "/v1/notification"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = "/v1/notification"
        data = {'notifications': [note['pk'] for note in response.data]}
        response = self.client.post(url, data, format='json', headers=headers)
        self.assertEqual(response.data,
                         {'notes': ['Notifications acknowledged.']})

        url = "/v1/notification"
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.data, [])

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_token_expired_delete(self):
        """
        test deleting of expired tokens.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        user2 = mock.Mock()
        user2.id = 'user_id2'
        user2.name = "test2@example.com"
        user2.email = "test2@example.com"
        user2.password = "test_password"

        setup_temp_cache({}, {user.name: user, user2.name: user2})

        url = "/v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        url = "/v1/reset"
        data = {'email': "test2@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        tokens = Token.objects.all()

        self.assertEqual(len(tokens), 2)

        new_token = tokens[0]
        new_token.expires = timezone.now() - timedelta(hours=24)
        new_token.save()

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/token/"
        response = self.client.delete(url, format='json', headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data,
                         {'notes': ['Deleted all expired tokens.']})
        self.assertEqual(Token.objects.count(), 1)

    @mock.patch('stacktask.base.models.IdentityManager', FakeManager)
    def test_token_reissue(self):
        """
        test for reissue of tokens
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "test_password"

        setup_temp_cache({}, {user.name: user})

        url = "/v1/reset"
        data = {'email': "test@example.com"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'notes': ['created token']})

        registration = Registration.objects.all()[0]
        new_token = Token.objects.all()[0]

        uuid = new_token.token

        headers = {
            'project_name': "test_project",
            'project_id': "test_project_id",
            'roles': "admin,Member",
            'username': "test@example.com",
            'user_id': "test_user_id",
            'authenticated': True
        }
        url = "/v1/token/"
        data = {"registration": registration.uuid}
        response = self.client.post(url, data, format='json',
                                    headers=headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data,
                         {'notes': ['Token reissued.']})
        self.assertEqual(Token.objects.count(), 1)
        new_token = Token.objects.all()[0]
        self.assertNotEquals(new_token.token, uuid)
