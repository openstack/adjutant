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

from logging import getLogger

from django.conf import settings
from django.db import models
from django.utils import timezone

from jsonfield import JSONField

from stacktask.actions import serializers
from stacktask.actions import user_store


class Action(models.Model):
    """
    Database model representation of an action.
    """
    action_name = models.CharField(max_length=200)
    action_data = JSONField(default={})
    cache = JSONField(default={})
    state = models.CharField(max_length=200, default="default")
    valid = models.BooleanField(default=False)
    need_token = models.BooleanField(default=False)
    task = models.ForeignKey('api.Task')

    order = models.IntegerField()

    created = models.DateTimeField(default=timezone.now)

    def get_action(self):
        """Returns self as the appropriate action wrapper type."""
        data = self.action_data
        return settings.ACTION_CLASSES[self.action_name][0](
            data=data, action_model=self)


class BaseAction(object):
    """
    Base class for the object wrapping around the database model.
    Setup to allow multiple action types and different internal logic
    per type but built from a single database type.
    - 'required' defines what fields to setup from the data.

    If need_token MAY be true, you must implement '_token_email',
    which should return the email the action wants the token sent to.
    While there are checks to prevent duplicates or different emails,
    try and only have one action in your chain provide the email.

    The Action can do anything it needs at one of the three functions
    called by the views:
    - 'pre_approve'
    - 'post_approve'
    - 'submit'

    All logic and validation should be handled within the action itself,
    and any other actions it is linked to. The way in which pre_approve,
    post_approve, and submit are called should rarely change. Actions
    should be built with those steps in mind, thinking about what they mean,
    and when they execute.

    By using 'get_cache' and 'set_cache' they can pass data along which
    may be needed by the action later. This cache is backed to the database.

    Passing data along to other actions is done via the task and
    it's cache, but this is in memory only, so it is only useful during the
    same action stage ('post_approve', etc.).

    Other than the task cache, actions should not be altering database
    models other than themselves. This is not enforced, just a guideline.
    """

    required = []

    def __init__(self, data, action_model=None, task=None,
                 order=None):
        """
        Build itself around an existing database model,
        or build itself and creates a new database model.
        Sets up required data as fields.
        """

        self.logger = getLogger('django.request')

        for field in self.required:
            field_data = data[field]
            setattr(self, field, field_data)

        if action_model:
            self.action = action_model
        else:
            # make new model and save in db
            action = Action.objects.create(
                action_name=self.__class__.__name__,
                action_data=data,
                task=task,
                order=order
            )
            action.save()
            self.action = action

    @property
    def valid(self):
        return self.action.valid

    @property
    def need_token(self):
        return self.action.need_token

    def get_email(self):
        return self._get_email()

    def _get_email(self):
        return None

    def get_cache(self, key):
        return self.action.cache.get(key, None)

    def set_cache(self, key, value):
        self.action.cache[key] = value
        self.action.save()

    @property
    def token_fields(self):
        return self.action.cache.get("token_fields", [])

    def set_token_fields(self, token_fields):
        self.action.cache["token_fields"] = token_fields
        self.action.save()

    def add_note(self, note):
        """
        Logs the note, and also adds it to the task action notes.
        """
        self.logger.info("(%s) - %s" % (timezone.now(), note))
        note = "%s - (%s)" % (note, timezone.now())
        self.action.task.add_action_note(
            unicode(self), note)

    def pre_approve(self):
        return self._pre_approve()

    def post_approve(self):
        return self._post_approve()

    def submit(self, token_data):
        return self._submit(token_data)

    def _pre_approve(self):
        raise NotImplementedError

    def _post_approve(self):
        raise NotImplementedError

    def _submit(self, token_data):
        raise NotImplementedError

    def __unicode__(self):
        return self.__class__.__name__


class UserAction(BaseAction):
    """
    Base action for dealing with users.
    Contains role utility functions.
    """

    def are_roles_managable(self, user_roles=[], requested_roles=[]):
        requested_roles = set(requested_roles)
        # blacklist checks
        blacklist_roles = set(['admin'])
        if len(blacklist_roles & requested_roles) > 0:
            return False

        # user managable role
        managable_roles = user_store.get_managable_roles(user_roles)
        intersection = set(managable_roles) & requested_roles
        # if all requested roles match, we can proceed
        return intersection == requested_roles


class UserIdAction(UserAction):

    def _get_target_user(self):
        """
        Gets the target user by id
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(self.user_id)

        return user
    pass


class UserNameAction(UserAction):
    """
    Base action for dealing with users. Removes username if
    USERNAME_IS_EMAIL and sets email to be username.
    """

    def __init__(self, *args, **kwargs):
        if settings.USERNAME_IS_EMAIL:
            try:
                self.required.remove('username')
            except ValueError:
                pass
                # nothing to remove
            super(UserAction, self).__init__(*args, **kwargs)
            self.username = self.email
        else:
            super(UserAction, self).__init__(*args, **kwargs)

    def _get_email(self):
        return self.email

    def _get_target_user(self):
        """
        Gets the target user by their username
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.find_user(self.username)

        return user


# TODO: rename to InviteUser
class NewUser(UserNameAction):
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
        'roles'
    ]

    def _validate(self):
        id_manager = user_store.IdentityManager()

        # Default state is invalid
        self.action.valid = False

        keystone_user = self.action.task.keystone_user

        if keystone_user['project_id'] != self.project_id:
            self.add_note('Project id does not match keystone user project.')
            return

        # Role permissions check
        if not self.are_roles_managable(user_roles=keystone_user['roles'],
                                        requested_roles=self.roles):
            self.add_note('User does not have permission to edit role(s).')
            return

        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project does not exist.')
            return

        # Get target user
        user = self._get_target_user()
        if not user:
            self.action.need_token = True
            self.set_token_fields(["password"])
            self.add_note(
                'No user present with username. Need to create new user.')
            self.action.valid = True
            return

        if user.email != self.email:
            self.add_note(
                'Found matching username, but email did not match.' +
                'Reporting as invalid.')
            return

        roles = id_manager.get_roles(user, project)
        roles = {role.name for role in roles}
        missing = set(self.roles) - roles
        if not missing:
            self.action.valid = True
            self.action.need_token = False
            self.action.state = "complete"
            self.add_note(
                'Existing user already has roles.'
            )
        else:
            self.roles = list(missing)
            self.action.valid = True
            self.action.need_token = True
            self.set_token_fields(["confirm"])
            self.action.state = "existing"
            self.add_note(
                'Existing user with matching email missing roles.')

    def _pre_approve(self):
        self._validate()
        self.action.save()

    def _post_approve(self):
        self._validate()
        self.action.save()

    def _submit(self, token_data):
        self._validate()
        self.action.save()

        if not self.valid:
            return

        id_manager = user_store.IdentityManager()

        if self.action.state == "default":
            # default action: Create a new user in the tenant and add roles
            try:
                roles = []
                for role in self.roles:
                    ks_role = id_manager.find_role(role)
                    if ks_role:
                        roles.append(ks_role)
                    else:
                        raise TypeError("Keystone missing role: %s" % role)

                user = id_manager.create_user(
                    name=self.username, password=token_data['password'],
                    email=self.email, project_id=self.project_id)

                for role in roles:
                    id_manager.add_user_role(user, role, self.project_id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating user: %s with roles: %s" %
                    (e, self.username, self.roles))
                raise

            self.add_note(
                'User %s has been created, with roles %s in project %s.'
                % (self.username, self.roles, self.project_id))
        elif self.action.state == "existing":
            # Existing action: only add roles.
            try:
                user = id_manager.find_user(self.username)

                roles = []
                for role in self.roles:
                    roles.append(id_manager.find_role(role))

                for role in roles:
                    id_manager.add_user_role(user, role, self.project_id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while attaching user: %s with roles: %s" %
                    (e, self.username, self.roles))
                raise

            self.add_note(
                'Existing user %s has been given roles %s in project %s.'
                % (self.username, self.roles, self.project_id))
        elif self.action.state == "complete":
            # complete action: nothing to do.
            self.add_note(
                'Existing user %s already had roles %s in project %s.'
                % (self.username, self.roles, self.project_id))


class NewProject(UserNameAction):
    """
    Similar functionality as the NewUser action,
    but will create the project if valid. Will setup
    the user (existing or new) with the 'default_role'.
    """

    required = [
        'project_name',
        'username',
        'email'
    ]

    # NOTE(adriant): move these to a config somewhere?
    default_roles = {
        "project_admin", "project_mod", "_member_", "heat_stack_owner"
    }

    def _validate(self):
        project_valid = self._validate_project()
        user_valid = self._validate_user()

        self.action.valid = project_valid and user_valid
        self.action.save()

    def _validate_project(self):
        id_manager = user_store.IdentityManager()

        project = id_manager.find_project(self.project_name)
        if project:
            self.add_note("Existing project with name '%s'." %
                          self.project_name)
            return False

        self.add_note("No existing project with name '%s'." %
                      self.project_name)
        return True

    def _validate_user(self):
        id_manager = user_store.IdentityManager()
        user = id_manager.find_user(self.username)

        if user:
            if user.email == self.email:
                valid = True
                self.action.state = "existing"
                self.action.need_token = False
                self.add_note("Existing user '%s' with matching email." %
                              self.email)
            else:
                valid = False
                self.add_note("Existing user '%s' with non-matching email." %
                              self.username)
        else:
            valid = True
            self.action.need_token = True
            self.set_token_fields(["password"])
            self.add_note("No user present with username '%s'." %
                          self.username)

        return valid

    def _pre_approve(self):
        self._validate()

    def _post_approve(self):
        """
        Approving a registration means we set up the project itself,
        and then the user registration token is valid for submission and
        creating the user themselves.
        """
        project_id = self.get_cache('project_id')
        if project_id:
            self.action.task.cache['project_id'] = project_id
            self.add_note("Project already created.")
            return

        self._validate()
        if not self.valid:
            return

        id_manager = user_store.IdentityManager()
        try:
            project = id_manager.create_project(
                self.project_name, created_on=str(timezone.now()))
        except Exception as e:
            self.add_note(
                "Error: '%s' while creating project: %s" %
                (e, self.project_name))
            raise
        # put project_id into action cache:
        self.action.task.cache['project_id'] = project.id
        self.set_cache('project_id', project.id)
        self.add_note("New project '%s' created." % self.project_name)

    def _submit(self, token_data):
        """
        The submit action is prformed when a token is submitted.
        This is done for a user account only, and so should now only
        set up the user, not the project, which was done in approve.
        """

        id_manager = user_store.IdentityManager()

        self.action.valid = self._validate_user()
        self.action.save()

        if not self.valid:
            return

        project_id = self.get_cache('project_id')
        self.action.task.cache['project_id'] = project_id

        project = id_manager.get_project(project_id)

        if self.action.state == "default":
            try:
                roles = []
                for role in self.default_roles:
                    ks_role = id_manager.find_role(role)
                    if ks_role:
                        roles.append(ks_role)
                    else:
                        raise TypeError("Keystone missing role: %s" % role)

                user = id_manager.create_user(
                    name=self.username, password=token_data['password'],
                    email=self.email, project_id=project.id)

                for role in roles:
                    id_manager.add_user_role(user, role, project.id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating user: %s with roles: %s" %
                    (e, self.username, self.default_roles))
                raise

            self.add_note(
                "New user '%s' created for project %s with roles: %s" %
                (self.username, self.project_name, self.default_roles))
        elif self.action.state == "existing":
            try:
                user = id_manager.find_user(self.username)

                roles = []
                for role in self.default_roles:
                    roles.append(id_manager.find_role(role))

                for role in roles:
                    id_manager.add_user_role(user, role, project.id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while attaching user: %s with roles: %s" %
                    (e, self.username, self.default_roles))
                raise

            self.add_note(("Existing user '%s' attached to project %s" +
                          " with roles: %s")
                          % (self.username, self.project_name,
                             self.default_roles))


class ResetUser(UserNameAction):
    """
    Simple action to reset a password for a given user.
    """

    username = models.CharField(max_length=200)
    email = models.EmailField()

    required = [
        'username',
        'email'
    ]

    blacklist = settings.ACTION_SETTINGS.get(
        'ResetUser', {}).get("blacklisted_roles", {})

    def _validate(self):
        id_manager = user_store.IdentityManager()

        user = id_manager.find_user(self.username)

        if not user:
            valid = False
            self.add_note('No user present with username')
            return valid

        roles = id_manager.get_all_roles(user)

        user_roles = []
        for project, roles in roles.iteritems():
            user_roles.extend(role.name for role in roles)

        if set(self.blacklist) & set(user_roles):
            valid = False
            self.add_note('Cannot reset users with blacklisted roles.')
        elif user.email == self.email:
            valid = True
            self.action.need_token = True
            self.set_token_fields(["password"])
            self.add_note('Existing user with matching email.')
        else:
            valid = False
            self.add_note('Existing user with non-matching email.')

        return valid

    def _pre_approve(self):
        self.action.valid = self._validate()
        self.action.save()

    def _post_approve(self):
        self.action.valid = self._validate()
        self.action.save()

    def _submit(self, token_data):
        self.action.valid = self._validate()
        self.action.save()

        if not self.valid:
            return

        id_manager = user_store.IdentityManager()

        user = id_manager.find_user(self.username)
        try:
            id_manager.update_user_password(user, token_data['password'])
        except Exception as e:
            self.add_note(
                "Error: '%s' while changing password for user: %s" %
                (e, self.username))
            raise
        self.add_note('User %s password has been changed.' % self.username)


class EditUserRoles(UserIdAction):
    """
    A class for adding or removing roles
    on a user for the given project.
    """

    required = [
        'user_id',
        'project_id',
        'roles',
        'remove'
    ]

    def _validate(self):
        id_manager = user_store.IdentityManager()

        keystone_user = self.action.task.keystone_user

        # TODO: This is potentially too limiting and could be changed into
        # an auth check. Perhaps just allowing 'admin' role users is enough.
        if not keystone_user['project_id'] == self.project_id:
            self.add_note('Project id does not match keystone user project.')
            self.action.valid = False
            return

        # Role permissions check
        if not self.are_roles_managable(user_roles=keystone_user['roles'],
                                        requested_roles=self.roles):
            self.add_note('User does not have permission to edit role(s).')
            self.action.valid = False
            return

        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project does not exist.')
            self.action.valid = False
            return

        # Get target user
        user = self._get_target_user()
        if not user:
            self.add_note('No user present with user_id')
            self.action.valid = False
            return

        current_roles = id_manager.get_roles(user, project)
        current_role_names = {role.name for role in current_roles}
        if self.remove:
            remaining = set(current_role_names) & set(self.roles)
            if not remaining:
                self.action.valid = True
                self.action.state = "complete"
                self.add_note(
                    "User doesn't have roles."
                )
            else:
                self.roles = list(remaining)
                self.action.valid = True
                self.add_note(
                    'User has roles to remove.')
        else:
            missing = set(self.roles) - set(current_role_names)
            if not missing:
                self.action.valid = True
                self.action.state = "complete"
                self.add_note(
                    'User already has roles.'
                )
            else:
                self.roles = list(missing)
                self.action.valid = True
                self.add_note(
                    'User user missing roles.')

    def _pre_approve(self):
        self._validate()
        self.action.save()

    def _post_approve(self):
        self._validate()
        self.action.save()

    def _submit(self, token_data):
        self._validate()
        self.action.save()

        if not self.valid:
            return

        id_manager = user_store.IdentityManager()

        if self.action.state == "default":
            try:
                user = self._get_target_user()

                roles = []
                for role in self.roles:
                    roles.append(id_manager.find_role(role))

                if self.remove:
                    for role in roles:
                        id_manager.remove_user_role(
                            user, role, self.project_id)
                else:
                    for role in roles:
                        id_manager.add_user_role(
                            user, role, self.project_id)
            except Exception as e:
                if self.remove:
                    self.add_note(
                        "Error: '%s' removing roles: %s from user: %s" %
                        (e, self.roles, self.user_id))
                else:
                    self.add_note(
                        "Error: '%s' adding roles: %s to user: %s" %
                        (e, self.roles, self.user_id))
                raise

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


# Update settings dict with tuples in the format:
#   (<ActionClass>, <ActionSerializer>)
def register_action_class(action_class, serializer_class):
    data = {}
    data[action_class.__name__] = (action_class, serializer_class)
    settings.ACTION_CLASSES.update(data)

# Register each action model
register_action_class(NewUser, serializers.NewUserSerializer)
register_action_class(NewProject, serializers.NewProjectSerializer)
register_action_class(ResetUser, serializers.ResetUserSerializer)
register_action_class(EditUserRoles, serializers.EditUserSerializer)
