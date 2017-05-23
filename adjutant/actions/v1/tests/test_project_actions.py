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
from django.test.utils import override_settings

import mock

from adjutant.actions.v1.projects import (
    NewProjectWithUserAction, AddDefaultUsersToProjectAction)
from adjutant.api.models import Task
from adjutant.api.v1 import tests
from adjutant.api.v1.tests import (FakeManager, setup_temp_cache,
                                   modify_dict_settings)


@mock.patch('adjutant.actions.user_store.IdentityManager',
            FakeManager)
class ProjectActionTests(TestCase):

    def test_new_project(self):
        """
        Base case, no project, no user.

        Project and user created at post_approve step,
        user password at submit step.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={}
        )

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(
            task.cache,
            {'project_id': 'project_id_1', 'user_id': 'user_id_1',
             'user_state': 'default'})

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

    def test_new_project_reapprove(self):
        """
        Project created at post_approve step,
        ensure reapprove does nothing.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={}
        )

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(
            task.cache,
            {'project_id': 'project_id_1', 'user_id': 'user_id_1',
             'user_state': 'default'})

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(
            task.cache,
            {'project_id': 'project_id_1', 'user_id': 'user_id_1',
             'user_state': 'default'})

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

    def test_new_project_reapprove_failure(self):
        """
        Project created at post_approve step, failure at role grant.

        Ensure reapprove correctly finishes.
        """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={}
        )

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        # NOTE(adrian): We need the code to fail at the
        # grant roles step so we can attempt reapproving it
        class FakeException(Exception):
            pass

        def fail_grant(user, default_roles, project_id):
            raise FakeException
        # We swap out the old grant function and keep
        # it for later.
        old_grant_function = action.grant_roles
        action.grant_roles = fail_grant

        # Now we expect the failure
        self.assertRaises(FakeException, action.post_approve)

        # No roles_granted yet, but user created
        self.assertTrue("user_id" in action.action.cache)
        self.assertFalse("roles_granted" in action.action.cache)
        self.assertEquals(
            tests.temp_cache['users']["user_id_1"].email,
            'test@example.com')
        project = tests.temp_cache['projects']['test_project']
        self.assertFalse("user_id_1" in project.roles)

        # And then swap back the correct function
        action.grant_roles = old_grant_function
        # and try again, it should work this time
        action.post_approve()
        self.assertEquals(action.valid, True)
        # roles_granted in cache
        self.assertTrue("roles_granted" in action.action.cache)

        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            sorted(project.roles["user_id_1"]),
            sorted(['_member_', 'project_admin',
                    'project_mod', 'heat_stack_owner']))

    def test_new_project_existing_user(self):
        """
        Create a project for a user that already exists.
        """

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'

        setup_temp_cache({}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={}
        )

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(
            task.cache,
            {'user_id': 'user_id_1', 'project_id': 'project_id_1',
             'user_state': 'existing'})

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

    def test_new_project_disabled_user(self):
        """
        Create a project for a user that is disabled.
        """

        user = mock.Mock()
        user.id = 'user_id_1'
        user.name = "test@example.com"
        user.email = "test@example.com"
        user.domain = 'default'
        user.enabled = False

        # create disabled user
        setup_temp_cache({}, {user.id: user})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={}
        )

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        # Sign up, approve
        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)
        self.assertEquals(
            tests.temp_cache['projects']['test_project'].name,
            'test_project')
        self.assertEquals(
            task.cache,
            {'user_id': 'user_id_1',
             'project_id': 'project_id_1',
             'user_state': 'disabled'})
        self.assertEquals(
            action.action.cache["token_fields"],
            ['password'])

        # submit password reset
        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        # check that user has been created correctly
        self.assertEquals(
            tests.temp_cache['users'][user.id].email,
            'test@example.com')
        self.assertEquals(
            tests.temp_cache['users'][user.id].enabled,
            True)

        # Check user has correct roles in new project
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            sorted(project.roles[user.id]),
            sorted(['_member_', 'project_admin',
                    'project_mod', 'heat_stack_owner']))

    def test_new_project_user_disabled_during_signup(self):
        """
        Create a project for a user that is created and disabled during signup.

        This exercises the tasks ability to correctly act based on changed
        circumstances between two states.
        """

        # Start with nothing created
        setup_temp_cache({}, {})

        # Sign up for the project+user, validate.
        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={}
        )

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        # Sign up
        action = NewProjectWithUserAction(data, task=task, order=1)
        action.pre_approve()
        self.assertEquals(action.valid, True)

        # Create the disabled user directly with the Identity Manager.
        fm = FakeManager()
        user = fm.create_user(
            name="test@example.com",
            password='origpass',
            email="test@example.com",
            created_on=None,
            domain='default',
            default_project=None
        )
        fm.disable_user(user.id)

        # approve previous signup
        action.post_approve()
        self.assertEquals(action.valid, True)
        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(
            project.name,
            'test_project')
        self.assertEquals(
            task.cache,
            {'user_id': user.id,
             'project_id': project.id,
             'user_state': 'disabled'})

        # check that user has been re-enabled with a generated password.
        self.assertEquals(user.enabled, True)
        self.assertNotEquals(user.password, 'origpass')

        # submit password reset
        token_data = {'password': '123456'}
        action.submit(token_data)
        self.assertEquals(action.valid, True)

        # Ensure user has new password:
        self.assertEquals(user.password, '123456')

    def test_new_project_existing_project(self):
        """
        Create a project that already exists.
        """

        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({project.name: project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'default',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

    def test_new_project_invalid_domain_id(self):
        """ Create a project using an invalid domain """

        setup_temp_cache({}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0",
            keystone_user={
                'roles': ['admin', 'project_mod'],
                'project_id': 'test_project_id',
                'project_domain_id': 'default',
            })

        data = {
            'domain_id': 'not_default_id',
            'parent_id': None,
            'email': 'test@example.com',
            'project_name': 'test_project',
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, False)

        action.post_approve()
        self.assertEquals(action.valid, False)

        @override_settings(USERNAME_IS_EMAIL=False)
        def test_new_project_email_not_username(self):
            """
            Base case, no project, no user.

            Project and user created at post_approve step,
            user password at submit step.
            """

            setup_temp_cache({}, {})

            task = Task.objects.create(
                ip_address="0.0.0.0",
                keystone_user={}
            )

            data = {
                'domain_id': 'default',
                'parent_id': None,
                'email': 'test@example.com',
                'username': 'test_user',
                'project_name': 'test_project',
            }

            action = NewProjectWithUserAction(data, task=task, order=1)

            action.pre_approve()
            self.assertEquals(action.valid, True)

            action.post_approve()
            self.assertEquals(action.valid, True)
            self.assertEquals(
                tests.temp_cache['projects']['test_project'].name,
                'test_project')
            self.assertEquals(
                task.cache,
                {'project_id': 'project_id_1', 'user_id': 'user_id_1',
                 'user_state': 'default'})

            token_data = {'password': '123456'}
            action.submit(token_data)
            self.assertEquals(action.valid, True)
            self.assertEquals(
                tests.temp_cache['users']["user_id_1"].email,
                'test@example.com')
            self.assertEquals(
                tests.temp_cache['users']["user_id_1"].name,
                'test_user')
            project = tests.temp_cache['projects']['test_project']
            self.assertEquals(
                sorted(project.roles["user_id_1"]),
                sorted(['_member_', 'project_admin',
                        'project_mod', 'heat_stack_owner']))

    @modify_dict_settings(DEFAULT_ACTION_SETTINGS={
                          'key_list': ['AddDefaultUsersToProjectAction'],
                          'operation': 'override',
                          'value': {'default_users': ['admin', ],
                                    'default_roles': ['admin', ]}})
    def test_add_default_users(self):
        """
        Base case, adds admin user with admin role to project.

        NOTE(adriant): both the lists of users, and the roles to add
        come from test_settings. This test assumes the conf setting of:
        default_users = ['admin']
        default_roles = ['admin']
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = AddDefaultUsersToProjectAction(
            {'domain_id': 'default'}, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(project.roles['user_id_0'], ['admin'])

    def test_add_default_users_invalid_project(self):
        """Add default users to a project that doesn't exist.

        Action should become invalid at the post_approve state, it's ok if
        the project isn't created yet during pre_approve.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "invalid_project_id"}

        action = AddDefaultUsersToProjectAction(
            {'domain_id': 'default'}, task=task, order=1)
        action.pre_approve()
        # No need to test project yet - it's ok if it doesn't exist
        self.assertEquals(action.valid, True)

        action.post_approve()
        # Now the missing project should make the action invalid
        self.assertEquals(action.valid, False)

    @modify_dict_settings(DEFAULT_ACTION_SETTINGS={
                          'key_list': ['AddDefaultUsersToProjectAction'],
                          'operation': 'override',
                          'value': {'default_users': ['admin', ],
                                    'default_roles': ['admin', ]}})
    def test_add_default_users_reapprove(self):
        """
        Ensure nothing happens or changes during rerun of approve.
        """
        project = mock.Mock()
        project.id = 'test_project_id'
        project.name = 'test_project'
        project.domain = 'default'
        project.roles = {}

        setup_temp_cache({'test_project': project}, {})

        task = Task.objects.create(
            ip_address="0.0.0.0", keystone_user={'roles': ['admin']})

        task.cache = {'project_id': "test_project_id"}

        action = AddDefaultUsersToProjectAction(
            {'domain_id': 'default'}, task=task, order=1)

        action.pre_approve()
        self.assertEquals(action.valid, True)

        action.post_approve()
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(project.roles['user_id_0'], ['admin'])

        action.post_approve()
        self.assertEquals(action.valid, True)

        project = tests.temp_cache['projects']['test_project']
        self.assertEquals(project.roles['user_id_0'], ['admin'])
