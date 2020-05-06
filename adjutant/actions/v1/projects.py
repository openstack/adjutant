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

from uuid import uuid4

from django.utils import timezone

from confspirator import groups
from confspirator import fields

from adjutant.config import CONF
from adjutant.common import user_store
from adjutant.common.utils import str_datetime
from adjutant.actions.utils import validate_steps
from adjutant.actions.v1.base import BaseAction, UserNameAction, UserMixin, ProjectMixin
from adjutant.actions.v1 import serializers


class NewProjectAction(BaseAction, ProjectMixin, UserMixin):
    """
    Creates a new project for the current keystone_user.

    This action can only be used for an autheticated task.
    """

    required = [
        "domain_id",
        "parent_id",
        "project_name",
        "description",
    ]

    serializer = serializers.NewProjectSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "default_roles",
                help_text="Roles to be given on project to the creating user.",
                default=[],
                sample_default=["member", "project_admin"],
            ),
        ],
    )

    def __init__(self, *args, **kwargs):
        super(NewProjectAction, self).__init__(*args, **kwargs)

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_domain_id,
                self._validate_keystone_user_parent_project,
                self._validate_project_absent,
            ]
        )
        self.action.save()

    def _validate_domain_id(self):
        keystone_user = self.action.task.keystone_user

        if keystone_user["project_domain_id"] != self.domain_id:
            self.add_note("Domain id does not match keystone user domain.")
            return False

        return super(NewProjectAction, self)._validate_domain_id()

    def _validate_keystone_user_parent_project(self):
        if self.parent_id:
            keystone_user = self.action.task.keystone_user

            if self.parent_id != keystone_user["project_id"]:
                self.add_note("Parent id does not match keystone user project.")
                return False
            return self._validate_parent_project()
        return True

    def _prepare(self):
        self._validate()

    def _approve(self):
        project_id = self.get_cache("project_id")
        if project_id:
            self.action.task.cache["project_id"] = project_id
            self.add_note("Project already created.")
        else:
            self._validate()

            if not self.valid:
                return

            self._create_project()

        user_id = self.get_cache("user_id")
        if user_id:
            self.action.task.cache["user_id"] = user_id
            self.add_note("User already given roles.")
        else:
            default_roles = self.config.default_roles

            project_id = self.get_cache("project_id")
            keystone_user = self.action.task.keystone_user

            try:
                id_manager = user_store.IdentityManager()
                user = id_manager.get_user(keystone_user["user_id"])

                self.grant_roles(user, default_roles, project_id)
            except Exception as e:
                self.add_note(
                    (
                        "Error: '%s' while adding roles %s "
                        "to user '%s' on project '%s'"
                    )
                    % (e, default_roles, user.name, project_id)
                )
                raise

            # put user_id into action cache:
            self.action.task.cache["user_id"] = user.id
            self.set_cache("user_id", user.id)
            self.add_note(
                "Existing user '%s' attached to project %s with roles: %s"
                % (user.name, project_id, default_roles)
            )

    def _submit(self, token_data, keystone_user=None):
        """
        Nothing to do here. Everything is done at the approve step.
        """
        pass


class NewProjectWithUserAction(UserNameAction, ProjectMixin, UserMixin):
    """
    Makes a new project for the given username. Will create the user if it
    doesn't exists.
    """

    required = ["domain_id", "parent_id", "project_name", "username", "email"]

    serializer = serializers.NewProjectWithUserSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "default_roles",
                help_text="Roles to be given on project for the user.",
                default=[],
                sample_default=["member", "project_admin"],
            ),
        ],
    )

    def __init__(self, *args, **kwargs):
        super(NewProjectWithUserAction, self).__init__(*args, **kwargs)

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_domain_id,
                self._validate_parent_project,
                self._validate_project_absent,
                self._validate_user,
            ]
        )
        self.action.save()

    def _validate_user(self):
        id_manager = user_store.IdentityManager()
        user = id_manager.find_user(self.username, self.domain_id)

        if not user:
            self.add_note(
                "No user present with username '%s'. "
                "Need to create new user." % self.username
            )
            if not id_manager.can_edit_users:
                self.add_note(
                    "Identity backend does not support user editing, "
                    "cannot create new user."
                )
                return False
            # add to cache to use in template
            self.action.task.cache["user_state"] = "default"
            self.action.need_token = True
            self.set_token_fields(["password"])
            return True

        if (
            not CONF.identity.username_is_email
            and getattr(user, "email", None) != self.email
        ):
            self.add_note("Existing user '%s' with non-matching email." % self.username)
            return False

        if not user.enabled:
            self.add_note(
                "Existing disabled user '%s' with matching email." % self.email
            )
            if not id_manager.can_edit_users:
                self.add_note(
                    "Identity backend does not support user editing, "
                    "cannot renable user."
                )
                return False
            self.action.state = "disabled"
            # add to cache to use in template
            self.action.task.cache["user_state"] = "disabled"
            self.action.need_token = True
            # as they are disabled we'll reset their password
            self.set_token_fields(["password"])
            return True
        else:
            self.action.state = "existing"
            # add to cache to use in template
            self.action.task.cache["user_state"] = "existing"
            self.action.need_token = False
            self.add_note("Existing user '%s' with matching email." % self.email)
            return True

    def _validate_user_submit(self):
        user_id = self.get_cache("user_id")
        project_id = self.get_cache("project_id")

        id_manager = user_store.IdentityManager()

        user = id_manager.get_user(user_id)
        project = id_manager.get_project(project_id)

        if user and project:
            self.action.valid = True
        else:
            self.action.valid = False

        self.action.task.cache["user_state"] = self.action.state

        self.action.save()

    def _prepare(self):
        self._validate()

    def _approve(self):
        """
        Approving a new project means we set up the project itself,
        and if the user doesn't exist, create it right away. An existing
        user automatically gets added to the new project.
        """
        if not self.valid:
            return

        project_id = self.get_cache("project_id")
        if project_id:
            self.action.task.cache["project_id"] = project_id
            self.add_note("Project already created.")
        else:
            self.action.valid = (
                self._validate_domain_id()
                and self._validate_parent_project()
                and self._validate_project_absent()
            )
            self.action.save()

            if not self.valid:
                return

            self._create_project()

        # User validation and checks
        user_id = self.get_cache("user_id")
        roles_granted = self.get_cache("roles_granted")
        if user_id and roles_granted:
            self.action.task.cache["user_id"] = user_id
            self.action.task.cache["user_state"] = self.action.state
            self.add_note("User already setup.")
        elif not user_id:
            self.action.valid = self._validate_user()
            self.action.save()

            if not self.valid:
                return

            self._create_user_for_project()
        elif not roles_granted:
            self._create_user_for_project()

    def _create_user_for_project(self):
        id_manager = user_store.IdentityManager()
        default_roles = self.config.default_roles

        project_id = self.get_cache("project_id")

        if self.action.state == "default":
            try:
                # Generate a temporary password:
                password = uuid4().hex + uuid4().hex

                user_id = self.get_cache("user_id")
                if not user_id:
                    user = id_manager.create_user(
                        name=self.username,
                        password=password,
                        email=self.email,
                        domain=self.domain_id,
                        created_on=str_datetime(timezone.now()),
                    )
                    self.set_cache("user_id", user.id)
                else:
                    user = id_manager.get_user(user_id)
                # put user_id into action cache:
                self.action.task.cache["user_id"] = user.id

                self.grant_roles(user, default_roles, project_id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating user: %s with roles: %s"
                    % (e, self.username, default_roles)
                )
                raise

            self.set_cache("roles_granted", True)
            self.add_note(
                "New user '%s' created for project %s with roles: %s"
                % (self.username, project_id, default_roles)
            )
        elif self.action.state == "existing":
            try:
                user_id = self.get_cache("user_id")
                if not user_id:
                    user = id_manager.find_user(self.username, self.domain_id)
                    self.set_cache("user_id", user.id)
                else:
                    user = id_manager.get_user(user_id)
                self.action.task.cache["user_id"] = user.id

                self.grant_roles(user, default_roles, project_id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while granting roles: %s to user: %s"
                    % (e, default_roles, self.username)
                )
                raise

            self.set_cache("roles_granted", True)
            self.add_note(
                "Existing user '%s' setup on project %s  with roles: %s"
                % (self.username, project_id, default_roles)
            )
        elif self.action.state == "disabled":
            user_id = self.get_cache("user_id")
            if not user_id:
                # first re-enable user
                try:
                    user = id_manager.find_user(self.username, self.domain_id)
                    id_manager.enable_user(user)
                except Exception as e:
                    self.add_note(
                        "Error: '%s' while re-enabling user: %s" % (e, self.username)
                    )
                    raise

                # and now update their password
                # Generate a temporary password:
                password = uuid4().hex + uuid4().hex
                try:
                    id_manager.update_user_password(user, password)
                except Exception as e:
                    self.add_note(
                        "Error: '%s' while changing password for user: %s"
                        % (e, self.username)
                    )
                    raise
                self.add_note("User %s password has been changed." % self.username)

                self.set_cache("user_id", user.id)
            else:
                user = id_manager.get_user(user_id)
            self.action.task.cache["user_id"] = user.id

            # now add their roles
            roles_granted = self.get_cache("roles_granted")
            if not roles_granted:
                try:
                    self.grant_roles(user, default_roles, project_id)
                except Exception as e:
                    self.add_note(
                        "Error: '%s' while granting user: %s roles: %s"
                        % (e, self.username, default_roles)
                    )
                    raise
                self.set_cache("roles_granted", True)

            self.add_note(
                "Existing user '%s' setup on project %s with roles: %s"
                % (self.username, project_id, default_roles)
            )

    def _submit(self, token_data, keystone_user=None):
        """
        The submit action is performed when a token is submitted.
        This is done to set a user password only, and so should now only
        change the user password. The project and user themselves are created
        on approve.
        """

        self._validate_user_submit()

        if not self.valid:
            return

        project_id = self.get_cache("project_id")
        self.action.task.cache["project_id"] = project_id
        user_id = self.get_cache("user_id")
        self.action.task.cache["user_id"] = user_id
        id_manager = user_store.IdentityManager()

        if self.action.state in ["default", "disabled"]:
            user = id_manager.get_user(user_id)
            try:
                id_manager.update_user_password(user, token_data["password"])
            except Exception as e:
                self.add_note(
                    "Error: '%s' while changing password for user: %s"
                    % (e, self.username)
                )
                raise
            self.add_note("User %s password has been changed." % self.username)

        elif self.action.state == "existing":
            # do nothing, everything is already done.
            self.add_note(
                "Existing user '%s' already attached to project %s"
                % (user_id, project_id)
            )


class AddDefaultUsersToProjectAction(BaseAction, ProjectMixin, UserMixin):
    """
    The purpose of this action is to add a given set of users after
    the creation of a new Project. This is mainly for administrative
    purposes, and for users involved with migrations, monitoring, and
    general admin tasks that should be present by default.
    """

    required = [
        "domain_id",
    ]

    serializer = serializers.AddDefaultUsersToProjectSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "default_users",
                help_text="Users which this action should add to the project.",
                default=[],
            ),
            fields.ListConfig(
                "default_roles",
                help_text="Roles which those users should get.",
                default=[],
            ),
        ],
    )

    def __init__(self, *args, **kwargs):
        super(AddDefaultUsersToProjectAction, self).__init__(*args, **kwargs)
        self.users = self.config.default_users
        self.roles = self.config.default_roles

    def _validate_users(self):
        id_manager = user_store.IdentityManager()
        all_found = True
        for user in self.users:
            ks_user = id_manager.find_user(user, self.domain_id)
            if ks_user:
                self.add_note("User: %s exists." % user)
            else:
                self.add_note("ERROR: User: %s does not exist." % user)
                all_found = False

        return all_found

    def _pre_validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_users,
            ]
        )
        self.action.save()

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_users,
                self._validate_project_id,
            ]
        )
        self.action.save()

    def _prepare(self):
        self._pre_validate()

    def _approve(self):
        id_manager = user_store.IdentityManager()
        self.project_id = self.action.task.cache.get("project_id", None)
        self._validate()

        if self.valid and not self.action.state == "completed":
            try:
                for user in self.users:
                    ks_user = id_manager.find_user(user, self.domain_id)

                    self.grant_roles(ks_user, self.roles, self.project_id)
                    self.add_note(
                        'User: "%s" given roles: %s on project: %s.'
                        % (ks_user.name, self.roles, self.project_id)
                    )
            except Exception as e:
                self.add_note(
                    "Error: '%s' while adding users to project: %s"
                    % (e, self.project_id)
                )
                raise
            self.action.state = "completed"
            self.action.save()
            self.add_note("All users added.")

    def _submit(self, token_data, keystone_user=None):
        pass
