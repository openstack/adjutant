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

import mock

from stacktask.actions.models import (
    EditUserRoles, NewProject, NewUser, ResetUser)
from stacktask.api.models import Task
from stacktask.api.v1 import tests
from stacktask.api.v1.tests import FakeManager, setup_temp_cache


class ActionTests(TestCase):

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_user(self):
        """
        Test the default case, all valid.
        No existing user, valid tenant.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_']
        }

        action = NewUser(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)
        self.assertEquals(len(tests.temp_cache['users']), 2)
        # The new user id in this case will be "user_id_1"
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'test@example.com')
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].password,
            '123456')

        self.assertEquals(project.roles["user_id_1"], ['_member_'])

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
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

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_']
        }

        action = NewUser(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
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
        project.roles = {user.id: ['_member_']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_']
        }

        action = NewUser(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(action.action.state, 'complete')

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_user_no_tenant(self):
        """
        No user, no tenant.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_']
        }

        action = NewUser(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, False)

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_project(self):
        """
        Base case, no project, no user.

        Project created at post_approve step,
        user at submit step.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(task.cache, {'project_id': "project_id_1"})

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'test@example.com')
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            sorted(project.roles["user_id_1"]),
            sorted(['_member_', 'project_admin',
                    'project_mod', 'heat_stack_owner']))

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_project_reapprove(self):
        """
        Project created at post_approve step,
        ensure reapprove does nothing.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(task.cache, {'project_id': "project_id_1"})

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(task.cache, {'project_id': "project_id_1"})

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'test@example.com')
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            sorted(project.roles["user_id_1"]),
            sorted(['_member_', 'project_admin',
                    'project_mod', 'heat_stack_owner']))

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_project_existing_user(self):
        """
        no project, existing user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        setup_temp_cache({}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(task.cache, {'project_id': "project_id_1"})

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users'][user.id].email,
            'test@example.com')
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            sorted(project.roles[user.id]),
            sorted(['_member_', 'project_admin',
                    'project_mod', 'heat_stack_owner']))

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_new_project_existing(self):
        """
        Existing project.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {}

        setup_temp_cache({project.name: project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProject(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_reset_user(self):
        """
        Base case, existing user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.password = "gibberish"

        setup_temp_cache({}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUser(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users'][user.id].password,
            '123456')

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_reset_user_no_user(self):
        """
        No user.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id'})

        data = {
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUser(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, False)

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_edit_user_add(self):
        """
        Add roles to existing user.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={'roles': ['admin', 'project_mod'],
                           'project_id': 'test_project_id'})

        data = {
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['_member_', 'project_mod'],
            'remove': False
        }

        action = EditUserRoles(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(len(project.roles[user.id]), 2)
        self.assertEquals(set(project.roles[user.id]),
                          set(['_member_', 'project_mod']))

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_edit_user_add_complete(self):
        """
        Add roles to existing user.
        """
        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {user.id: ['_member_', 'project_mod']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={'roles': ['admin', 'project_mod'],
                           'project_id': 'test_project_id'})

        data = {
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['_member_', 'project_mod'],
            'remove': False
        }

        action = EditUserRoles(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(action.action.state, "complete")

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(len(project.roles[user.id]), 2)
        self.assertEquals(set(project.roles[user.id]),
                          set(['_member_', 'project_mod']))

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_edit_user_remove(self):
        """
        Remove roles from existing user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.roles = {user.id: ['_member_', 'project_mod']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={'roles': ['admin', 'project_mod'],
                           'project_id': 'test_project_id'})

        data = {
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['project_mod'],
            'remove': True
        }

        action = EditUserRoles(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    @mock.patch('stacktask.actions.models.user_store.IdentityManager',
                FakeManager)
    def test_edit_user_remove_complete(self):
        """
        Remove roles from existing user.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={'roles': ['admin', 'project_mod'],
                           'project_id': 'test_project_id'})

        data = {
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['project_mod'],
            'remove': True
        }

        action = EditUserRoles(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(action.action.state, "complete")

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])
