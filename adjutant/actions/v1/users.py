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

from django.conf import settings
from django.db import models

from adjutant.actions import user_store
from adjutant.actions.v1.base import (
    UserNameAction, UserIdAction, UserMixin, ProjectMixin)


class NewUserAction(UserNameAction, ProjectMixin, UserMixin):
    """
    Setup a new user with a role on the given project.
    Creates the user if they don't exist, otherwise
    if the username and email for the request match the
    existing one, will simply add the project role.
    """

    required = [
        'username',
        'email',
        'project_id',
        'roles',
        'domain_id',
    ]

    def _validate_target_user(self):
        id_manager = user_store.IdentityManager()

        # check if user exists and is valid
        # this may mean we need a token.
        user = self._get_target_user()
        if not user:
            self.action.need_token = True
            # add to cache to use in template
            self.action.task.cache['user_state'] = "default"
            self.set_token_fields(["password"])
            self.add_note(
                'No user present with username. Need to create new user.')
            return True
        if user.email != self.email:
            self.add_note(
                'Found matching username, but email did not match.' +
                'Reporting as invalid.')
            return False

        if not user.enabled:
            self.action.need_token = True
            self.action.state = "disabled"
            # add to cache to use in template
            self.action.task.cache['user_state'] = "disabled"
            # as they are disabled we'll reset their password
            self.set_token_fields(["password"])
            self.add_note(
                'Existing disabled user with matching email.')
            return True

        # role_validation
        roles = id_manager.get_roles(user, self.project_id)
        role_names = {role.name for role in roles}
        missing = set(self.roles) - role_names
        if not missing:
            self.action.need_token = False
            self.action.state = "complete"
            self.add_note(
                'Existing user already has roles.'
            )
        else:
            self.roles = list(missing)
            self.action.need_token = True
            self.set_token_fields(["confirm"])
            self.action.state = "existing"
            # add to cache to use in template
            self.action.task.cache['user_state'] = "existing"
            self.add_note(
                'Existing user with matching email missing roles.')

        return True

    def _validate(self):
        self.action.valid = (
            self._validate_role_permissions() and
            self._validate_keystone_user() and
            self._validate_domain_id() and
            self._validate_project_id() and
            self._validate_target_user()
        )
        self.action.save()

    def _pre_approve(self):
        self._validate()
        self.set_auto_approve()

    def _post_approve(self):
        self._validate()

    def _submit(self, token_data):
        self._validate()

        if not self.valid:
            return

        if self.action.state == "default":
            # default action: Create a new user in the tenant and add roles
            user = self.create_user(token_data['password'])
            self.grant_roles(user, self.roles, self.project_id)

            self.add_note(
                'User %s has been created, with roles %s in project %s.'
                % (self.username, self.roles, self.project_id))

        elif self.action.state == "disabled":
            # first re-enable user
            user = self.find_user()
            self.enable_user(user)
            self.grant_roles(user, self.roles, self.project_id)
            self.update_password(token_data['password'])

            self.add_note('User %s password has been changed.' % self.username)

            self.add_note(
                'Existing user %s has been re-enabled and given roles %s'
                ' in project %s.'
                % (self.username, self.roles, self.project_id))

        elif self.action.state == "existing":
            # Existing action: only add roles.
            user = self.find_user()
            self.grant_roles(user, self.roles, self.project_id)

            self.add_note(
                'Existing user %s has been given roles %s in project %s.'
                % (self.username, self.roles, self.project_id))
        elif self.action.state == "complete":
            # complete action: nothing to do.
            self.add_note(
                'Existing user %s already had roles %s in project %s.'
                % (self.username, self.roles, self.project_id))


class ResetUserPasswordAction(UserNameAction, UserMixin):
    """
    Simple action to reset a password for a given user.
    """

    username = models.CharField(max_length=200)
    email = models.EmailField()

    required = [
        'domain_name',
        'username',
        'email'
    ]

    def __init__(self, *args, **kwargs):
        super(ResetUserPasswordAction, self).__init__(*args, **kwargs)
        self.blacklist = self.settings.get("blacklisted_roles", {})

    def _validate_user_roles(self):
        id_manager = user_store.IdentityManager()

        self.user = id_manager.find_user(self.username, self.domain.id)
        roles = id_manager.get_all_roles(self.user)

        user_roles = []
        for roles in roles.itervalues():
            user_roles.extend(role.name for role in roles)

        if set(self.blacklist) & set(user_roles):
            self.add_note('Cannot reset users with blacklisted roles.')
            return False

        if self.user.email == self.email:
            self.action.need_token = True
            self.set_token_fields(["password"])
            self.add_note('Existing user with matching email.')
            return True
        else:
            self.add_note('Existing user with non-matching email.')
            return False

    def _validate(self):
        # Here, the order of validation matters
        # as each one adds new class variables
        self.action.valid = (
            self._validate_domain_name() and
            self._validate_username_exists() and
            self._validate_user_roles()
        )
        self.action.save()

    def _pre_approve(self):
        self._validate()

    def _post_approve(self):
        self._validate()

    def _submit(self, token_data):
        self._validate()

        if not self.valid:
            return

        self.update_password(token_data['password'])
        self.add_note('User %s password has been changed.' % self.username)


class EditUserRolesAction(UserIdAction, ProjectMixin, UserMixin):
    """
    A class for adding or removing roles
    on a user for the given project.
    """

    required = [
        'domain_id',
        'project_id',
        'user_id',
        'roles',
        'remove'
    ]

    def _validate_target_user(self):
        # Get target user
        user = self._get_target_user()
        if not user:
            self.add_note('No user present with user_id')
            return False
        return True

    def _validate_user_roles(self):
        id_manager = user_store.IdentityManager()
        user = self._get_target_user()
        project = id_manager.get_project(self.project_id)
        # user roles
        current_roles = id_manager.get_roles(user, project)
        current_role_names = {role.name for role in current_roles}

        # NOTE(adriant): Only allow someone to edit roles if all roles from
        # the target user can be managed by editor.
        can_manage_roles = user_store.get_managable_roles(
            self.action.task.keystone_user['roles'])
        if not set(can_manage_roles).issuperset(current_role_names):
            self.add_note(
                'Not all target user roles are manageable.')
            return False

        if self.remove:
            remaining = set(current_role_names) & set(self.roles)
            if not remaining:
                self.action.state = "complete"
                self.add_note(
                    "User doesn't have roles to remove.")
            else:
                self.roles = list(remaining)
                self.add_note(
                    'User has roles to remove.')
        else:
            missing = set(self.roles) - set(current_role_names)
            if not missing:
                self.action.state = "complete"
                self.add_note(
                    'User already has roles.')
            else:
                self.roles = list(missing)
                self.add_note(
                    'User user missing roles.')
        # All paths are valid here
        # We've just set state and roles that need to be changed.
        return True

    def _validate(self):
        self.action.valid = (
            self._validate_keystone_user() and
            self._validate_role_permissions() and
            self._validate_domain_id() and
            self._validate_project_id() and
            self._validate_target_user() and
            self._validate_user_roles()
        )
        self.action.save()

    def _pre_approve(self):
        self._validate()
        self.set_auto_approve()

    def _post_approve(self):
        self._validate()

    def _submit(self, token_data):
        self._validate()

        if not self.valid:
            return

        if self.action.state == "default":
            user = self._get_target_user()
            self._user_roles_edit(user, self.roles, self.project_id,
                                  remove=self.remove)

            if self.remove:
                self.add_note(
                    'User %s has had roles %s removed from project %s.'
                    % (self.user_id, self.roles, self.project_id))
            else:
                self.add_note(
                    'User %s has been given roles %s in project %s.'
                    % (self.user_id, self.roles, self.project_id))
        elif self.action.state == "complete":
            if self.remove:
                self.add_note(
                    'User %s already had roles %s in project %s.'
                    % (self.user_id, self.roles, self.project_id))
            else:
                self.add_note(
                    "User %s didn't have roles %s in project %s."
                    % (self.user_id, self.roles, self.project_id))


class UpdateUserEmailAction(UserIdAction, UserMixin):
    """
    Simple action to update a users email address for a given user.
    """

    required = [
        'user_id',
        'new_email',
    ]

    def _get_email(self):
        # Sending to new email address
        return self.new_email

    def _validate(self):
        self.action.valid = (self._validate_user() and
                             self._validate_email_not_in_use())
        self.action.save()

    def _validate_user(self):
        self.user = self._get_target_user()
        if self.user:
            return True
        return False

    def _validate_email_not_in_use(self):
        if settings.USERNAME_IS_EMAIL:
            self.domain_id = self.action.task.keystone_user[
                'project_domain_id']

            id_manager = user_store.IdentityManager()

            if id_manager.find_user(self.new_email, self.domain_id):
                self.add_note("User with same username already exists")
                return False
            self.add_note("No user with same username")
        return True

    def _pre_approve(self):
        self._validate()
        self.set_auto_approve(True)

    def _post_approve(self):
        self._validate()
        self.action.need_token = True
        self.set_token_fields(["confirm"])

    def _submit(self, token_data):
        self._validate()

        if not self.valid:
            return

        if token_data["confirm"]:
            self.old_username = str(self.user.name)
            self.update_email(self.new_email, user=self.user)

            if settings.USERNAME_IS_EMAIL:
                self.update_user_name(self.new_email, user=self.user)

            self.add_note('The email for user %s has been changed to %s.'
                          % (self.old_username, self.new_email))
