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

from django.test.utils import override_settings

from adjutant.actions.v1.users import (
    EditUserRolesAction, NewUserAction, ResetUserPasswordAction,
    UpdateUserEmailAction)
from adjutant.api.models import Task
from adjutant.api.v1 import tests
from adjutant.api.v1.tests import (FakeManager, setup_temp_cache,
                                   modify_dict_settings, AdjutantTestCase)


@mock.patch('adjutant.actions.user_store.IdentityManager',
            FakeManager)
class UserActionTests(AdjutantTestCase):

    def test_new_user(self):
        """
        Test the default case, all valid.
        No existing user, valid tenant.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

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

    def test_new_user_existing(self):
        """
        Existing user, valid tenant, no role.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    def test_new_user_disabled(self):
        """
        Disabled user, valid existing tenant, no role.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.enabled = False

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

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
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].enabled,
            True)

        self.assertEquals(project.roles["user_id_1"], ['_member_'])

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
        user.domain = 'default'

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['_member_']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(action.action.state, 'complete')

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    def test_new_user_no_tenant(self):
        """
        No user, no tenant.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, False)

    def test_new_user_wrong_project(self):
        """
        Existing user, valid project, project does not match keystone user.

        Action should be invalid.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        project = mock.Mock()
        project.id = 'test_project_id_1'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {user.id: ['_member_']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id_1',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

    def test_new_user_only_member(self):
        """
        Existing user, valid project, no edit permissions.

        Action should be invalid.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['_member_'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertFalse(action.valid)

    def test_new_user_wrong_domain(self):
        """
        Existing user, valid project, invalid domain.

        Action should be invalid.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['_member_'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'not_default',
        }

        action = NewUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertFalse(action.valid)

    def test_reset_user_password(self):
        """
        Base case, existing user.
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "gibberish"

        setup_temp_cache({}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_name': 'Default',
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

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

    def test_reset_user_password_no_user(self):
        """
        Reset password for a non-existant user.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_name': 'Default',
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, False)

    def test_edit_user_roles_add(self):
        """
        Add roles to existing user.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['_member_', 'project_mod'],
            'remove': False
        }

        action = EditUserRolesAction(data, task=task, order=1)

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

    def test_edit_user_roles_add_complete(self):
        """
        Add roles to existing user.
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
        project.roles = {user.id: ['_member_', 'project_mod']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['_member_', 'project_mod'],
            'remove': False
        }

        action = EditUserRolesAction(data, task=task, order=1)

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

    def test_edit_user_roles_remove(self):
        """
        Remove roles from existing user.
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
        project.roles = {user.id: ['_member_', 'project_mod']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['project_mod'],
            'remove': True
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    def test_edit_user_roles_remove_complete(self):
        """
        Remove roles from user that does not have them.
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

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['project_mod'],
            'remove': True
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(action.action.state, "complete")

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(project.roles[user.id], ['_member_'])

    def test_edit_user_roles_can_manage_all(self):
        """
        Confirm that you cannot edit a user unless all their roles
        can be managed by you.
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
        project.roles = {user.id: ['_member_', 'project_admin']}

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['project_mod'],
            'remove': False
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        self.assertEquals(
            project.roles[user.id], ['_member_', 'project_admin'])

    def test_edit_user_roles_modified_settings(self):
        """
        Tests that the role mappings do come from settings and that they
        are enforced.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {'user_id': ['project_mod']}

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['heat_stack_owner'],
            'remove': False
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        # Change settings
        with self.modify_dict_settings(ROLES_MAPPING={
                'key_list': ['project_mod'],
                'operation': "remove",
                'value': 'heat_stack_owner'}):
            action.post_approve()
            self.assertEquals(action.valid, False)

            token_data = {}
            action.submit(token_data)
            self.assertEquals(action.valid, False)

        # After Settings Reset
        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(len(project.roles[user.id]), 2)
        self.assertEquals(set(project.roles[user.id]),
                          set(['project_mod', 'heat_stack_owner']))

    @modify_dict_settings(ROLES_MAPPING={'key_list': ['project_mod'],
                          'operation': "append", 'value': 'new_role'})
    def test_edit_user_roles_modified_settings_add(self):
        """
        Tests that the role mappings do come from settings and a new role
        added there will be allowed.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {'user_id': ['project_mod']}

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {user.id: user})

        tests.temp_cache['roles']['new_role'] = 'new_role'

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'user_id': 'user_id',
            'project_id': 'test_project_id',
            'roles': ['new_role'],
            'remove': False
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(len(project.roles[user.id]), 2)
        self.assertEquals(set(project.roles[user.id]),
                          set(['project_mod', 'new_role']))

    # Simple positive tests for when USERNAME_IS_EMAIL=False
    @override_settings(USERNAME_IS_EMAIL=False)
    def test_create_user_email_not_username(self):
        """
        Test the default case, all valid.
        No existing user, valid tenant.
        Different username from email address
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'username': 'test_user',
            'email': 'test@example.com',
            'project_id': 'test_project_id',
            'roles': ['_member_'],
            'domain_id': 'default',
        }

        action = NewUserAction(data, task=task, order=1)

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
            tests.temp_cache['users']["user_id_1"].name,
            'test_user')
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].password,
            '123456')

        self.assertEquals(project.roles["user_id_1"], ['_member_'])

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_reset_user_email_not_username(self):
        """
        Base case, existing user.
        Username not email address
        """

        user = mock.Mock()
        user.id = 'user_id'
        user.name = "test_user"
        user.email = "test@example.com"
        user.domain = 'default'
        user.password = "gibberish"

        setup_temp_cache({}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'username': "test_user",
            'domain_name': 'Default',
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

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
        self.assertEquals(
            tests.temp_cache['users'][user.id].name,
            'test_user')
        self.assertEquals(
            tests.temp_cache['users'][user.id].email,
            'test@example.com')

    @override_settings(USERNAME_IS_EMAIL=True)
    def test_update_email(self):
        """
        Base test case for user updating email address.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'new_email': 'new_test@example.com',
            'user_id': user.id,
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        token_data = {'confirm': True}

        action.submit(token_data)
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'new_test@example.com')

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].name,
            'new_test@example.com')

    @override_settings(USERNAME_IS_EMAIL=True)
    def test_update_email_invalid_user(self):
        """
        Test case for an invalid user being updated.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'new_email': 'new_test@example.com',
            'user_id': "non_user_id",
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        token_data = {'confirm': True}

        action.submit(token_data)
        self.assertEquals(action.valid, False)

    @override_settings(USERNAME_IS_EMAIL=True)
    def test_update_email_invalid_email(self):
        """
        Test case for a user attempting to update with an invalid email.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'new_email': 'new_testexample.com',
            'user_id': "non_user_id",
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        action.submit({'confirm': True})
        self.assertEquals(action.valid, False)

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'test@example.com')
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].name,
            'test@example.com')

    @override_settings(USERNAME_IS_EMAIL=False)
    def test_update_email_username_not_email(self):
        """
        Test case for a user attempting to update with an invalid email.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test_user"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({'test_project': project}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'new_email': 'new_testexample.com',
            'user_id': "user_id_1",
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        action.submit({'confirm': True})
        self.assertEquals(action.valid, True)

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'new_testexample.com')

        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].name,
            'test_user')
