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

from confspirator import groups
from confspirator import fields

from adjutant.config import CONF
from adjutant.common import user_store
from adjutant.actions.v1.base import (
    UserNameAction,
    UserIdAction,
    UserMixin,
    ProjectMixin,
)
from adjutant.actions.v1 import serializers
from adjutant.actions.utils import validate_steps


class NewUserAction(UserNameAction, ProjectMixin, UserMixin):
    """
    Setup a new user with a role on the given project.
    Creates the user if they don't exist, otherwise
    if the username and email for the request match the
    existing one, will simply add the project role.
    """

    required = [
        "username",
        "email",
        "project_id",
        "roles",
        "inherited_roles",
        "domain_id",
    ]

    serializer = serializers.NewUserSerializer

    def _validate_target_user(self):
        id_manager = user_store.IdentityManager()

        # check if user exists and is valid
        # this may mean we need a token.
        user = self._get_target_user()
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
            self.action.need_token = True
            # add to cache to use in template
            self.action.task.cache["user_state"] = "default"
            self.set_token_fields(["password"])
            return True
        if (
            not CONF.identity.username_is_email
            and getattr(user, "email", None) != self.email
        ):
            self.add_note(
                "Found matching username, but email did not match. "
                "Reporting as invalid."
            )
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
            self.action.need_token = True
            self.action.state = "disabled"
            # add to cache to use in template
            self.action.task.cache["user_state"] = "disabled"
            # as they are disabled we'll reset their password
            self.set_token_fields(["password"])
            return True

        # role_validation
        roles = id_manager.get_roles(user, self.project_id)
        role_names = {role.name for role in roles}
        missing = set(self.roles) - role_names
        if not missing:
            self.action.need_token = False
            self.action.state = "complete"
            self.add_note("Existing user already has roles.")
        else:
            self.roles = list(missing)
            self.action.need_token = True
            self.set_token_fields(["confirm"])
            self.action.state = "existing"
            # add to cache to use in template
            self.action.task.cache["user_state"] = "existing"
            self.add_note("Existing user with matching email missing roles.")

        return True

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_role_permissions,
                self._validate_keystone_user_domain_id,
                self._validate_keystone_user_project_id,
                self._validate_domain_id,
                self._validate_project_id,
                self._validate_target_user,
            ]
        )
        self.action.save()

    def _prepare(self):
        self._validate()
        self.set_auto_approve()

    def _approve(self):
        self._validate()

    def _submit(self, token_data, keystone_user=None):
        self._validate()

        if not self.valid:
            return

        if self.action.state == "default":
            # default action: Create a new user in the tenant and add roles
            user = self.create_user(token_data["password"])
            self.grant_roles(user, self.roles, self.project_id)
            self.grant_roles(user, self.inherited_roles, self.project_id, True)

            self.add_note(
                "User %s has been created, with roles %s in project %s."
                % (self.username, self.roles, self.project_id)
            )

        elif self.action.state == "disabled":
            # first re-enable user
            user = self.find_user()
            self.enable_user(user)
            self.grant_roles(user, self.roles, self.project_id)
            self.grant_roles(user, self.inherited_roles, self.project_id, True)
            self.update_password(token_data["password"])

            self.add_note("User %s password has been changed." % self.username)

            self.add_note(
                "Existing user %s has been re-enabled and given roles %s"
                " in project %s." % (self.username, self.roles, self.project_id)
            )

        elif self.action.state == "existing":
            # Existing action: only add roles.
            user = self.find_user()
            self.grant_roles(user, self.roles, self.project_id)
            self.grant_roles(user, self.inherited_roles, self.project_id, True)

            self.add_note(
                "Existing user %s has been given roles %s in project %s."
                % (self.username, self.roles, self.project_id)
            )
        elif self.action.state == "complete":
            # complete action: nothing to do.
            self.add_note(
                "Existing user %s already had roles %s in project %s."
                % (self.username, self.roles, self.project_id)
            )


class ResetUserPasswordAction(UserNameAction, UserMixin):
    """
    Simple action to reset a password for a given user.
    """

    required = ["domain_name", "username", "email"]

    serializer = serializers.ResetUserPasswordSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "blacklisted_roles",
                help_text="Users with these roles cannot reset their passwords.",
                default=[],
                sample_default=["admin"],
            ),
        ],
    )

    def __init__(self, *args, **kwargs):
        super(ResetUserPasswordAction, self).__init__(*args, **kwargs)

    def _validate_user_roles(self):
        id_manager = user_store.IdentityManager()

        roles = id_manager.get_all_roles(self.user)

        user_roles = []
        for roles in roles.values():
            user_roles.extend(role.name for role in roles)

        if set(self.config.blacklisted_roles) & set(user_roles):
            self.add_note("Cannot reset users with blacklisted roles.")
            return False

        return True

    def _validate_user_email(self):
        # NOTE(adriant): We only need to check the USERNAME_IS_EMAIL=False
        # case since '_validate_username_exists' will ensure the True case
        if not CONF.identity.username_is_email:
            if self.user and (
                getattr(self.user, "email", None).lower() != self.email.lower()
            ):
                self.add_note("Existing user with non-matching email.")
                return False

        self.action.need_token = True
        self.set_token_fields(["password"])
        self.add_note("Existing user with matching email.")
        return True

    def _validate(self):
        # Here, the order of validation matters
        # as each one adds new class variables
        self.action.valid = validate_steps(
            [
                self._validate_domain_name,
                self._validate_username_exists,
                self._validate_user_roles,
                self._validate_user_email,
            ]
        )
        self.action.save()

    def _prepare(self):
        self._validate()
        self.set_auto_approve()

    def _approve(self):
        self._validate()

    def _submit(self, token_data, keystone_user=None):
        self._validate()

        if not self.valid:
            return

        self.update_password(token_data["password"])
        self.add_note("User %s password has been changed." % self.username)


class EditUserRolesAction(UserIdAction, ProjectMixin, UserMixin):
    """
    A class for adding or removing roles
    on a user for the given project.
    """

    required = ["project_id", "user_id", "roles", "inherited_roles", "remove"]

    serializer = serializers.EditUserRolesSerializer

    def _validate_target_user(self):
        # Get target user
        user = self._get_target_user()
        if not user:
            self.add_note("No user present with user_id")
            return False
        return True

    def _validate_user_roles(self):
        id_manager = user_store.IdentityManager()
        user = self._get_target_user()
        project = id_manager.get_project(self.project_id)
        # user roles
        current_roles = id_manager.get_roles(user, project)
        current_inherited_roles = id_manager.get_roles(user, project, inherited=True)
        current_roles = {role.name for role in current_roles}
        current_inherited_roles = {role.name for role in current_inherited_roles}
        if self.remove:
            remaining = set(current_roles) & set(self.roles)
            remaining_inherited = set(current_inherited_roles) & set(
                self.inherited_roles
            )
            if not remaining and not remaining_inherited:
                self.action.state = "complete"
                self.add_note("User doesn't have roles to remove.")
            else:
                self.roles = list(remaining)
                self.inherited_roles = list(remaining_inherited)
                self.add_note("User has roles to remove.")
        else:
            missing = set(self.roles) - set(current_roles)
            missing_inherited = set(self.inherited_roles) - set(current_inherited_roles)
            if not missing and not missing_inherited:
                self.action.state = "complete"
                self.add_note("User already has roles.")
            else:
                self.roles = list(missing)
                self.inherited_roles = list(missing_inherited)
                self.add_note("User missing roles.")
        # All paths are valid here
        # We've just set state and roles that need to be changed.
        return True

    def _validate_role_permissions(self):

        id_manager = user_store.IdentityManager()

        current_user_roles = id_manager.get_roles(
            project=self.project_id, user=self.user_id
        )
        current_user_roles = [role.name for role in current_user_roles]

        current_roles_manageable = self.are_roles_manageable(
            self.action.task.keystone_user["roles"], current_user_roles
        )

        all_roles = set()
        all_roles.update(self.roles)
        all_roles.update(self.inherited_roles)
        new_roles_manageable = self.are_roles_manageable(
            self.action.task.keystone_user["roles"], all_roles
        )

        if new_roles_manageable and current_roles_manageable:
            self.add_note("All user roles are manageable.")
            return True
        self.add_note("Not all user roles are manageable.")
        return False

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_keystone_user_project_id,
                self._validate_role_permissions,
                self._validate_project_id,
                self._validate_target_user,
                self._validate_user_roles,
            ]
        )
        self.action.save()

    def _prepare(self):
        self._validate()
        self.set_auto_approve()

    def _approve(self):
        self._validate()

    def _submit(self, token_data, keystone_user=None):
        self._validate()

        if not self.valid:
            return

        if self.action.state == "default":
            user = self._get_target_user()
            self._user_roles_edit(user, self.roles, self.project_id, remove=self.remove)
            self._user_roles_edit(
                user,
                self.inherited_roles,
                self.project_id,
                remove=self.remove,
                inherited=True,
            )

            if self.remove and self.roles:
                self.add_note(
                    "User %s has had roles %s removed from project %s."
                    % (self.user_id, self.roles, self.project_id)
                )
            if self.remove and self.inherited_roles:
                self.add_note(
                    "User %s has had inherited roles %s "
                    "removed from project %s."
                    % (self.user_id, self.inherited_roles, self.project_id)
                )
            if self.roles:
                self.add_note(
                    "User %s has been given roles %s in project %s."
                    % (self.user_id, self.roles, self.project_id)
                )
            if self.inherited_roles:
                self.add_note(
                    "User %s has been given inherited roles %s in project %s."
                    % (self.user_id, self.inherited_roles, self.project_id)
                )
        elif self.action.state == "complete":
            if self.remove:
                self.add_note(
                    "User %s didn't have roles %s in project %s."
                    % (self.user_id, self.roles, self.project_id)
                )
            else:
                self.add_note(
                    "User %s already had roles %s in project %s."
                    % (self.user_id, self.roles, self.project_id)
                )


class UpdateUserEmailAction(UserIdAction, UserMixin):
    """
    Simple action to update a users email address for a given user.
    """

    required = [
        "user_id",
        "new_email",
    ]

    serializer = serializers.UpdateUserEmailSerializer

    def _get_email(self):
        # Sending to new email address
        return self.new_email

    def _validate(self):
        self.action.valid = validate_steps(
            [
                self._validate_user,
                self._validate_email_not_in_use,
            ]
        )
        self.action.save()

    def _validate_user(self):
        self.user = self._get_target_user()
        if self.user:
            return True
        self.add_note("Unable to find target user.")
        return False

    def _validate_email_not_in_use(self):
        if CONF.identity.username_is_email:
            self.domain_id = self.action.task.keystone_user["project_domain_id"]

            id_manager = user_store.IdentityManager()

            if id_manager.find_user(self.new_email, self.domain_id):
                self.add_note("User with same username already exists")
                return False
            self.add_note("No user with same username")
        return True

    def _prepare(self):
        self._validate()
        self.set_auto_approve(True)

    def _approve(self):
        self._validate()
        self.action.need_token = True
        self.set_token_fields(["confirm"])

    def _submit(self, token_data, keystone_user=None):
        self._validate()

        if not self.valid:
            return

        if token_data["confirm"]:
            self.old_username = str(self.user.name)
            self.update_email(self.new_email, user=self.user)

            if CONF.identity.username_is_email:
                self.update_user_name(self.new_email, user=self.user)

            self.add_note(
                "The email for user %s has been changed to %s."
                % (self.old_username, self.new_email)
            )
