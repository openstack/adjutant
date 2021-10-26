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

from adjutant.actions.v1.users import (
    EditUserRolesAction,
    NewUserAction,
    ResetUserPasswordAction,
    UpdateUserEmailAction,
)
from adjutant.api.models import Task
from adjutant.common.tests import fake_clients
from adjutant.common.tests.fake_clients import setup_identity_cache
from adjutant.common.tests.utils import AdjutantTestCase
from adjutant.config import CONF


@mock.patch("adjutant.common.user_store.IdentityManager", fake_clients.FakeManager)
@conf_utils.modify_conf(
    CONF,
    operations={
        "adjutant.identity.role_mapping": [
            {
                "operation": "override",
                "value": {
                    "admin": [
                        "project_admin",
                        "project_mod",
                        "member",
                        "heat_stack_owner",
                    ],
                    "project_admin": [
                        "project_mod",
                        "member",
                        "heat_stack_owner",
                        "project_admin",
                    ],
                    "project_mod": [
                        "member",
                        "heat_stack_owner",
                        "project_mod",
                    ],
                },
            },
        ],
    },
)
class UserActionTests(AdjutantTestCase):
    def test_new_user(self):
        """
        Test the default case, all valid.
        No existing user, valid tenant.
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)
        self.assertEqual(len(fake_clients.identity_cache["new_users"]), 1)

        fake_client = fake_clients.FakeManager()

        user = fake_client.find_user(name="test@example.com", domain="default")

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.password, "123456")

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    def test_new_user_existing(self):
        """
        Existing user, valid tenant, no role.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    def test_new_user_disabled(self):
        """
        Disabled user, valid existing tenant, no role.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com",
            password="123",
            email="test@example.com",
            enabled=False,
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)
        self.assertEqual(len(fake_clients.identity_cache["users"]), 2)

        fake_client = fake_clients.FakeManager()

        user = fake_client.find_user(name="test@example.com", domain="default")

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.password, "123456")
        self.assertTrue(user.enabled)

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    def test_new_user_existing_role(self):
        """
        Existing user, valid tenant, has role.

        Should complete the action as if no role,
        but actually do nothing.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="member",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)
        self.assertEqual(action.action.state, "complete")

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    def test_new_user_no_tenant(self):
        """
        No user, no tenant.
        """

        setup_identity_cache()

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": "test_project_id",
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, False)

    def test_new_user_wrong_project(self):
        """
        Existing user, valid project, project does not match keystone user.

        Action should be invalid.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": "test_project_id_1",
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

    def test_new_user_only_member(self):
        """
        Existing user, valid project, no edit permissions.

        Action should be invalid.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["member"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertFalse(action.valid)

    def test_new_user_invalid_roles(self):
        """
        Test that you can't add roles outside of managed roles.

        Action should be invalid.
        """

        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_admin"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["admin"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertFalse(action.valid)

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": [],
            "inherited_roles": ["admin"],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertFalse(action.valid)

    def test_new_user_wrong_domain(self):
        """
        Existing user, valid project, invalid domain.

        Action should be invalid.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="member",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_admin"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "not_default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertFalse(action.valid)

    def test_reset_user_password(self):
        """
        Base case, existing user.
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="gibberish", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_name": "Default",
            "email": "test@example.com",
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].password, "123456"
        )

    def test_reset_user_password_case_insensitive(self):
        """
        Existing user, ensure action is case insensitive.

        USERNAME_IS_EMAIL=True
        """

        user = fake_clients.FakeUser(
            name="test@example.com", password="gibberish", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_name": "Default",
            "email": "TEST@example.com",
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].password, "123456"
        )

    def test_reset_user_password_no_user(self):
        """
        Reset password for a non-existant user.
        """

        setup_identity_cache()

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_name": "Default",
            "email": "test@example.com",
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, False)

    def test_edit_user_roles_add(self):
        """
        Add roles to existing user.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        setup_identity_cache(projects=[project], users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["member", "project_mod"],
            "inherited_roles": [],
            "remove": False,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(sorted(roles), sorted(["member", "project_mod"]))

    def test_edit_user_roles_add_complete(self):
        """
        Add roles to existing user.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_mod",
                user={"id": user.id},
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=assignments
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["member", "project_mod"],
            "inherited_roles": [],
            "remove": False,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)
        self.assertEqual(action.action.state, "complete")

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member", "project_mod"])

    def test_edit_user_roles_remove(self):
        """
        Remove roles from existing user.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_mod",
                user={"id": user.id},
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=assignments
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["project_mod"],
            "inherited_roles": [],
            "remove": True,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    def test_edit_user_roles_remove_complete(self):
        """
        Remove roles from user that does not have them.
        """

        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="member",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["project_mod"],
            "inherited_roles": [],
            "remove": True,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)
        self.assertEqual(action.action.state, "complete")

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    def test_edit_user_roles_can_manage_all(self):
        """
        Confirm that you cannot edit a user unless all their roles
        can be managed by you.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignments = [
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user.id},
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="member",
                user={"id": user.id},
                inherited=True,
            ),
            fake_clients.FakeRoleAssignment(
                scope={"project": {"id": project.id}},
                role_name="project_admin",
                user={"id": user.id},
                inherited=True,
            ),
        ]

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=assignments
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["project_mod"],
            "inherited_roles": [],
            "remove": False,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member", "project_admin"])

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": [],
            "inherited_roles": ["project_mod"],
            "remove": False,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member", "project_admin"])

    def test_edit_user_roles_modified_config(self):
        """
        Tests that the role mappings do come from config and that they
        are enforced.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="project_mod",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["heat_stack_owner"],
            "inherited_roles": [],
            "remove": False,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        # Change config
        with conf_utils.modify_conf(
            CONF,
            operations={
                "adjutant.identity.role_mapping": [
                    {
                        "operation": "update",
                        "value": {
                            "project_mod": [
                                "member",
                                "project_mod",
                            ],
                        },
                    },
                ],
            },
        ):
            action.approve()
            self.assertEqual(action.valid, False)

            token_data = {}
            action.submit(token_data)
            self.assertEqual(action.valid, False)

        # After Settings Reset
        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["project_mod", "heat_stack_owner"])

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.role_mapping": [
                {
                    "operation": "update",
                    "value": {
                        "project_mod": [
                            "member",
                            "heat_stack_owner",
                            "project_mod",
                            "new_role",
                        ],
                    },
                },
            ],
        },
    )
    def test_edit_user_roles_modified_config_add(self):
        """
        Tests that the role mappings do come from config and a new role
        added there will be allowed.
        """
        project = fake_clients.FakeProject(name="test_project")

        user = fake_clients.FakeUser(
            name="test@example.com", password="123", email="test@example.com"
        )

        assignment = fake_clients.FakeRoleAssignment(
            scope={"project": {"id": project.id}},
            role_name="project_mod",
            user={"id": user.id},
        )

        setup_identity_cache(
            projects=[project], users=[user], role_assignments=[assignment]
        )

        new_role = fake_clients.FakeRole("new_role")

        fake_clients.identity_cache["roles"][new_role.id] = new_role

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_id": "default",
            "user_id": user.id,
            "project_id": project.id,
            "roles": ["new_role"],
            "inherited_roles": [],
            "remove": False,
        }

        action = EditUserRolesAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["project_mod", "new_role"])

    # Simple positive tests for when USERNAME_IS_EMAIL=False
    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_create_user_email_not_username(self):
        """
        Test the default case, all valid.
        No existing user, valid tenant.
        Different username from email address
        """
        project = fake_clients.FakeProject(name="test_project")

        setup_identity_cache(projects=[project])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": project.id,
                "project_domain_id": "default",
            }
        )

        data = {
            "username": "test_user",
            "email": "test@example.com",
            "project_id": project.id,
            "roles": ["member"],
            "inherited_roles": [],
            "domain_id": "default",
        }

        action = NewUserAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)
        self.assertEqual(len(fake_clients.identity_cache["users"]), 2)

        fake_client = fake_clients.FakeManager()

        user = fake_client.find_user(name="test_user", domain="default")

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.password, "123456")
        self.assertTrue(user.enabled)

        roles = fake_client._get_roles_as_names(user, project)
        self.assertEqual(roles, ["member"])

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_reset_user_email_not_username(self):
        """
        Base case, existing user.
        Username not email address
        """
        user = fake_clients.FakeUser(
            name="test_user", password="gibberish", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "username": "test_user",
            "domain_name": "Default",
            "email": "test@example.com",
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        fake_client = fake_clients.FakeManager()

        user = fake_client.find_user(name="test_user", domain="default")

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.password, "123456")

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_reset_user_password_case_insensitive_not_username(self):
        """
        Existing user, ensure action is case insensitive.

        USERNAME_IS_EMAIL=False
        """
        user = fake_clients.FakeUser(
            name="test_USER", password="gibberish", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["admin", "project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "domain_name": "Default",
            "username": "test_USER",
            "email": "TEST@example.com",
        }

        action = ResetUserPasswordAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"password": "123456"}
        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].password, "123456"
        )

    def test_update_email(self):
        """
        Base test case for user updating email address.
        """
        user = fake_clients.FakeUser(
            name="test@example.com", password="gibberish", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "new_email": "new_test@example.com",
            "user_id": user.id,
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        token_data = {"confirm": True}

        action.submit(token_data)
        self.assertEqual(action.valid, True)

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].email, "new_test@example.com"
        )

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].name, "new_test@example.com"
        )

    def test_update_email_invalid_user(self):
        """
        Test case for an invalid user being updated.
        """
        setup_identity_cache()

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "new_email": "new_test@example.com",
            "user_id": "non_user_id",
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, False)

        action.approve()
        self.assertEqual(action.valid, False)

        token_data = {"confirm": True}

        action.submit(token_data)
        self.assertEqual(action.valid, False)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.identity.username_is_email": [
                {"operation": "override", "value": False},
            ],
        },
    )
    def test_update_email_username_not_email(self):
        """
        Test case for a user attempting to update with an invalid email.
        """
        user = fake_clients.FakeUser(
            name="test_user", password="gibberish", email="test@example.com"
        )

        setup_identity_cache(users=[user])

        task = Task.objects.create(
            keystone_user={
                "roles": ["project_mod"],
                "project_id": "test_project_id",
                "project_domain_id": "default",
            }
        )

        data = {
            "new_email": "new_testexample.com",
            "user_id": user.id,
        }

        action = UpdateUserEmailAction(data, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        action.submit({"confirm": True})
        self.assertEqual(action.valid, True)

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].email, "new_testexample.com"
        )

        self.assertEqual(
            fake_clients.identity_cache["users"][user.id].name, "test_user"
        )
