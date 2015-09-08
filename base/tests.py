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

from django.test import TestCase
from api_v1.models import Registration
from api_v1.tests import FakeManager
from api_v1 import tests
from base.models import NewUser, NewProject, ResetUser
import mock


class BaseActionTests(TestCase):

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user(self):
        """
        Test the base case, all valid.
        No existing user, valid tenant.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        tests.temp_cache = {
            'i': 0,
            'users': {},
            'projects': {'test_project': project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'role': 'Member'
        }

        action = NewUser(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)
        self.assertEquals(len(tests.temp_cache['users']), 1)
        self.assertEquals(
            tests.temp_cache['users']['test@example.com'].email,
            'test@example.com')
        self.assertEquals(
            tests.temp_cache['users']['test@example.com'].password,
            '123456')

        self.assertEquals(project.roles['test@example.com'], ['Member'])

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_existing(self):
        """
        Existing user, valid tenant, no role.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        tests.temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {'test_project': project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'role': 'Member'
        }

        action = NewUser(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.name], ['Member'])

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_existing_role(self):
        """
        Existing user, valid tenant, has role.

        Should complete the action as if no role,
        but actually do nothing.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {user.name: ['Member']}

        tests.temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {'test_project': project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'role': 'Member'
        }

        action = NewUser(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(action.action.state, 'complete')

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.name], ['Member'])

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_user_no_tenant(self):
        """
        No user, no tenant.
        """

        tests.temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'role': 'Member'
        }

        action = NewUser(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, False)

        self.assertEquals(tests.temp_cache['users'], {})

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_project(self):
        """
        Base case, no project, no user.

        Project created at post_approve step,
        user at submit step.
        """

        tests.temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(tests.temp_cache['users'], {})
        self.assertEquals(registration.cache, {'project_id': 1})

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users']['test@example.com'].email,
            'test@example.com')
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            project.roles['test@example.com'],
            ['Member', 'project_owner'])

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_project_existing_user(self):
        """
        no project, existing user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        tests.temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(registration.cache, {'project_id': 1})

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users']['test@example.com'].email,
            'test@example.com')
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            project.roles['test@example.com'],
            ['Member', 'project_owner'])

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_new_project_existing(self):
        """
        Existing project.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        tests.temp_cache = {
            'i': 0,
            'users': {},
            'projects': {project.name: project},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_reset_user(self):
        """
        Base case, existing user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "gibberish"

        tests.temp_cache = {
            'i': 0,
            'users': {user.name: user},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUser(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users']['test@example.com'].password,
            '123456')

    @mock.patch('base.models.IdentityManager', FakeManager)
    def test_reset_user_no_user(self):
        """
        No user.
        """

        tests.temp_cache = {
            'i': 0,
            'users': {},
            'projects': {},
            'roles': {
                'Member': 'Member', 'admin': 'admin',
                'project_owner': 'project_owner'
            }
        }
        registration = Registration.objects.create(
            reg_ip="0.0.0.0", keystone_user={'roles': ['admin']})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUser(data, registration=registration, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, False)
