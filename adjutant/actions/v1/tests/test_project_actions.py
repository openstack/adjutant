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

from unittest import mock

from confspirator.tests import utils as conf_utils

from adjutant.actions.v1.projects import (
    NewProjectWithUserAction,
    AddDefaultUsersToProjectAction,
    NewProjectAction,
)
from adjutant.api.models import Task
from adjutant.common.tests import fake_clients
from adjutant.common.tests.fake_clients import FakeManager, setup_identity_cache
from adjutant.common.tests.utils import AdjutantTestCase
from adjutant.config import CONF


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
@conf_utils.modify_conf(
    CONF,
    operations={
        "adjutant.workflow.action_defaults.NewProjectWithUserAction.default_roles": [
            {
                "operation": "override",
                "value": ["member", "heat_stack_owner", "project_admin", "project_mod"],
            },
        ],
        "adjutant.workflow.action_defaults.NewProjectAction.default_roles": [
            {
                "operation": "override",
                "value": ["member", "heat_stack_owner", "project_admin", "project_mod"],
            },
        ],
        "adjutant.workflow.action_defaults.AddDefaultUsersToProjectAction.default_users": [
            {"operation": "override", "value": ["admin"]},
        ],
        "adjutant.workflow.action_defaults.AddDefaultUsersToProjectAction.default_roles": [
            {"operation": "override", "value": ["admin"]},
        ],
    },
)
class ProjectActionTests(AdjutantTestCase):
    def test_new_project(self):
        """
        Base case, no project, no user.

        Project and user created at approve step,
        user password at submit step.
        """

        setup_identity_cache()

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        new_user = fake_clients.identity_cache["new_users"][0]
        self.assertEqual(new_user.name, "test@example.com")
        self.assertEqual(new_user.email, "test@example.com")

        self.assertEqual(
            task.cache,
            {
                "project_id": new_project.id,
                "user_id": new_user.id,
                "user_state": "default",
            },
        )

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(new_user.password, "123456")

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(new_user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    def test_new_project_reapprove(self):
        """
        Project created at approve step,
        ensure reapprove does nothing.
        """

        setup_identity_cache()

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        new_user = fake_clients.identity_cache["new_users"][0]
        self.assertEqual(new_user.name, "test@example.com")
        self.assertEqual(new_user.email, "test@example.com")

        self.assertEqual(
            task.cache,
            {
                "project_id": new_project.id,
                "user_id": new_user.id,
                "user_state": "default",
            },
        )

        action.approve()
        self.assertEqual(action.valid, True)
        self.assertEqual(len(fake_clients.identity_cache["new_projects"]), 1)
        self.assertEqual(len(fake_clients.identity_cache["new_users"]), 1)
        self.assertEqual(
            task.cache,
            {
                "project_id": new_project.id,
                "user_id": new_user.id,
                "user_state": "default",
            },
        )

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(new_user.password, "123456")

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(new_user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    def test_new_project_reapprove_failure(self):
        """
        Project created at approve step, failure at role grant.

        Ensure reapprove correctly finishes.
        """

        setup_identity_cache()

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

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
        self.assertRaises(FakeException, action.approve)

        # No roles_granted yet, but user created
        self.assertTrue("user_id" in action.action.cache)
        self.assertFalse("roles_granted" in action.action.cache)
        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        new_user = fake_clients.identity_cache["new_users"][0]
        self.assertEqual(new_user.name, "test@example.com")
        self.assertEqual(new_user.email, "test@example.com")
        self.assertEqual(len(fake_clients.identity_cache["role_assignments"]), 0)

        # And then swap back the correct function
        action.grant_roles = old_grant_function
        # and try again, it should work this time
        action.approve()
        self.assertEqual(action.valid, True)
        # roles_granted in cache
        self.assertTrue("roles_granted" in action.action.cache)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(new_user.password, "123456")

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(new_user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    def test_new_project_existing_user(self):
        """
        Create a project for a user that already exists.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        self.assertEqual(len(fake_clients.identity_cache["new_users"]), 0)

        self.assertEqual(
            task.cache,
            {
                "project_id": new_project.id,
                "user_id": user.id,
                "user_state": "existing",
            },
        )

        # submit does nothing for existing
        action.submit({})
        self.assertEqual(action.valid, True)

        self.assertEqual(user.password, "123")

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_new_project_user_nonmatching_email(self):
        """
        Attempts to create a new project and a new user, where there is
        a user with the same name but different email address
        """

        user = fake_clients.FakeUser(
            name="test_user", password="123", email="different@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "username": "test_user",
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        self.assertEqual(
            fake_clients.identity_cache["projects"].get("test_project"), None
        )

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, False)

    def test_new_project_project_removed(self):
        """
        Tests when the project is removed after the post approve step.
        """

        setup_identity_cache()

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        fake_clients.identity_cache["projects"] = {}

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, False)

    def test_new_project_user_removed(self):
        """
        Tests when the user is removed after the post approve step.
        """

        setup_identity_cache()

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_user = fake_clients.identity_cache["new_users"][0]
        self.assertEqual(new_user.name, "test@example.com")
        self.assertEqual(new_user.email, "test@example.com")

        fake_clients.identity_cache["users"] = {}

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, False)

    def test_new_project_disabled_user(self):
        """
        Create a project for a user that is disabled.
        """

        user = fake_clients.FakeUser(
            name="test@example.com",
            password="123",
            email="test@example.com",
            enabled=False,
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        # Sign up, approve
        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        self.assertEqual(len(fake_clients.identity_cache["new_users"]), 0)

        self.assertEqual(
            task.cache,
            {
                "user_id": user.id,
                "project_id": new_project.id,
                "user_state": "disabled",
            },
        )
        self.assertEqual(action.action.cache["token_fields"], ["password"])

        # submit password reset
        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(user.password, "123456")

        # check that user has been enabled correctly
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.enabled, True)

        # Check user has correct roles in new project
        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    def test_new_project_user_disabled_during_signup(self):
        """
        Create a project for a user that is created and disabled during signup.

        This exercises the tasks ability to correctly act based on changed
        circumstances between two states.
        """

        # Start with nothing created
        setup_identity_cache()

        # Sign up for the project+user, validate.
        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        # Sign up
        action = NewProjectWithUserAction(data, task=task, order=1)
        action.prepare()
        self.assertEqual(action.valid, True)

        # Create the disabled user directly with the Identity Manager.
        fake_client = fake_clients.FakeManager()
        user = fake_client.create_user(
            name="test@example.com",
            password="origpass",
            email="test@example.com",
            created_on=None,
            domain="default",
            default_project=None,
        )
        fake_client.disable_user(user.id)

        # approve previous signup
        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        self.assertEqual(len(fake_clients.identity_cache["new_users"]), 1)

        self.assertEqual(
            task.cache,
            {
                "user_id": user.id,
                "project_id": new_project.id,
                "user_state": "disabled",
            },
        )

        # check that user has been re-enabled with a generated password.
        self.assertEqual(user.enabled, True)
        self.assertNotEqual(user.password, "origpass")

        # submit password reset
        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        # Ensure user has new password:
        self.assertEqual(user.password, "123456")

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    def test_new_project_existing_project(self):
        """
        Create a project that already exists.
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

    def test_new_project_invalid_domain_id(self):
        """Create a project using an invalid domain"""

        setup_identity_cache()

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "not_default_id",
            "parent_id": None,
            "email": "test@example.com",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_new_project_email_not_username(self):
        """
        Base case, no project, no user.

        Project and user created at approve step,
        user password at submit step.
        """

        setup_identity_cache()

        task = Task.objects.create(keystone_user={})

        data = {
            "domain_id": "default",
            "parent_id": None,
            "email": "test@example.com",
            "username": "test_user",
            "project_name": "test_project",
        }

        action = NewProjectWithUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")

        new_user = fake_clients.identity_cache["new_users"][0]
        self.assertEqual(new_user.name, "test_user")
        self.assertEqual(new_user.email, "test@example.com")

        self.assertEqual(
            task.cache,
            {
                "project_id": new_project.id,
                "user_id": new_user.id,
                "user_state": "default",
            },
        )

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(new_user.password, "123456")

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(new_user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

    def test_add_default_users(self):
        """
        Base case, adds admin user with admin role to project.

        NOTE(adriant): This test assumes the conf setting of:
        default_users = ['admin']
        default_roles = ['admin']
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        task.cache = {"project_id": project.id}

        action = AddDefaultUsersToProjectAction(
            {"domain_id": "default"}, task=task, order=1
        )

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()
        user = fake_client.find_user("admin", "default")
        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["admin"])

    def test_add_default_users_invalid_project(self):
        """Add default users to a project that doesn't exist.

        Action should become invalid at the approve state, it's ok if
        the project isn't created yet during prepare.
        """
        setup_identity_cache()

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        task.cache = {"project_id": "invalid_project_id"}

        action = AddDefaultUsersToProjectAction(
            {"domain_id": "default"}, task=task, order=1
        )
        action.prepare()
        # No need to test project yet - it's ok if it doesn't exist
        self.assertEqual(action.valid, True)

        action.approve()
        # Now the missing project should make the action invalid
        self.assertEqual(action.valid, False)

    def test_add_default_users_reapprove(self):
        """
        Ensure nothing happens or changes during rerun of approve.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        task = Task.objects.create(keystone_user={"roles": ["admin"]})

        task.cache = {"project_id": project.id}

        action = AddDefaultUsersToProjectAction(
            {"domain_id": "default"}, task=task, order=1
        )

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()
        user = fake_client.find_user("admin", "default")
        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["admin"])

        action.approve()
        self.assertEqual(action.valid, True)

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["admin"])

    def test_new_project_action(self):
        """
        Tests the new project action for an existing user.
        """

        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "user_id": user.id,
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "parent_id": project.id,
            "project_name": "test_project",
            "description": "",
        }

        action = NewProjectAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")
        self.assertEqual(new_project.parent_id, project.id)

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

        action.submit({})
        self.assertEqual(action.valid, True)

    def test_new_project_action_rerun_approve(self):
        """
        Tests the new project action for an existing user does
        nothing on reapproval.
        """

        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "user_id": user.id,
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "parent_id": project.id,
            "project_name": "test_project",
            "description": "",
        }

        action = NewProjectAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")
        self.assertEqual(new_project.parent_id, project.id)

        fake_client = fake_clients.FakeManager()
        roles = fake_client._get_roles_as_names(user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

        action.approve()
        # Nothing should change
        self.assertEqual(action.valid, True)

        self.assertEqual(new_project.name, "test_project")
        self.assertEqual(new_project.parent_id, project.id)

        roles = fake_client._get_roles_as_names(user, new_project)
        self.assertEqual(
            sorted(roles),
            sorted(["member", "project_admin", "project_mod", "heat_stack_owner"]),
        )

        action.submit({})
        self.assertEqual(action.valid, True)

    def test_new_project_action_wrong_parent_id(self):
        """
        New project action where specifed parent id is not the same
        as the current user's project id
        """

        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "user_id": user.id,
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "parent_id": "not_parent_project_id",
            "project_name": "test_project",
            "description": "",
        }

        action = NewProjectAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        action.submit({})
        self.assertEqual(action.valid, False)

    def test_new_project_action_wrong_domain_id(self):
        """
        New project action where specifed domain id is not the same
        as the current user's domain id
        """

        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "user_id": user.id,
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "notdefault",
            "parent_id": project.id,
            "project_name": "test_project",
            "description": "",
        }

        action = NewProjectAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        action.submit({})
        self.assertEqual(action.valid, False)

    def test_new_project_action_no_parent_id(self):
        """
        New project action where there is no specified parent id
        """

        project = fake_clients.FakeProject(name="parent_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "user_id": user.id,
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "parent_id": None,
            "project_name": "test_project",
            "description": "",
        }

        action = NewProjectAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        new_project = fake_clients.identity_cache["new_projects"][0]
        self.assertEqual(new_project.name, "test_project")
        self.assertEqual(new_project.parent_id, None)

        action.submit({})
        self.assertEqual(action.valid, True)
