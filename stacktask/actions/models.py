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
from uuid import uuid4

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

        self.logger = getLogger('stacktask')

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


class ResourceMixin(object):
    """Base Mixin class for dealing with Openstack resources."""

    def _validate_keystone_user(self):
        keystone_user = self.action.task.keystone_user

        if keystone_user['project_domain_id'] != self.domain_id:
            self.add_note('Domain id does not match keystone user domain.')
            return False

        if keystone_user['project_id'] != self.project_id:
            self.add_note('Project id does not match keystone user project.')
            return False
        return True

    def _validate_domain_id(self):
        id_manager = user_store.IdentityManager()
        domain = id_manager.get_domain(self.domain_id)
        if not domain:
            self.add_note('Domain does not exist.')
            return False

        return True

    def _validate_project_id(self):
        # Handle an edge_case where some actions set their
        # own project_id value.
        if not self.project_id:
            self.add_note('No project_id given.')
            return False

        # Now actually check the project exists.
        id_manager = user_store.IdentityManager()
        project = id_manager.get_project(self.project_id)
        if not project:
            self.add_note('Project with id %s does not exist.' %
                          self.project_id)
            return False
        self.add_note('Project with id %s exists.' % self.project_id)
        return True

    def _validate_domain_name(self):
        id_manager = user_store.IdentityManager()

        self.domain = id_manager.find_domain(self.domain_name)
        if not self.domain:
            self.add_note('Domain does not exist.')
            return False
        return True


class UserMixin(ResourceMixin):
    """Mixin with functions for users."""

    def _validate_username_exists(self):
        id_manager = user_store.IdentityManager()

        self.user = id_manager.find_user(self.username, self.domain.id)
        if not self.user:
            self.add_note('No user present with username')
            return False
        return True

    def _grant_roles(self, user, roles, project_id):
        id_manager = user_store.IdentityManager()
        ks_roles = []
        for role in roles:
            ks_role = id_manager.find_role(role)
            if ks_role:
                ks_roles.append(ks_role)
            else:
                raise TypeError("Keystone missing role: %s" % role)

        for role in ks_roles:
            id_manager.add_user_role(user, role, project_id)

    def _validate_role_permissions(self):
        keystone_user = self.action.task.keystone_user
        # Role permissions check
        if not self.are_roles_managable(user_roles=keystone_user['roles'],
                                        requested_roles=self.roles):
            self.add_note('User does not have permission to edit role(s).')
            return False
        return True

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


class ProjectMixin(ResourceMixin):
    """Mixin with functions for projects."""

    def _validate_parent_project(self):
        id_manager = user_store.IdentityManager()
        # NOTE(adriant): If parent id is None, Keystone defaults to the domain.
        # So we only care to validate if parent_id is not None.
        if self.parent_id:
            parent = id_manager.get_project(self.parent_id)
            if not parent:
                self.add_note("Parent id: '%s' does not exist." %
                              self.project_name)
                return False
        return True

    def _validate_project_absent(self):
        id_manager = user_store.IdentityManager()
        project = id_manager.find_project(
            self.project_name, self.domain_id)
        if project:
            self.add_note("Existing project with name '%s'." %
                          self.project_name)
            return False

        self.add_note("No existing project with name '%s'." %
                      self.project_name)
        return True

    def _create_project(self):
        id_manager = user_store.IdentityManager()
        try:
            project = id_manager.create_project(
                self.project_name, created_on=str(timezone.now()),
                parent=self.parent_id, domain=self.domain_id)
        except Exception as e:
            self.add_note(
                "Error: '%s' while creating project: %s" %
                (e, self.project_name))
            raise
        # put project_id into action cache:
        self.action.task.cache['project_id'] = project.id
        self.set_cache('project_id', project.id)
        self.add_note("New project '%s' created." % project.name)


class UserIdAction(BaseAction):

    def _get_target_user(self):
        """
        Gets the target user by id
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(self.user_id)

        return user


class UserNameAction(BaseAction):
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
            super(UserNameAction, self).__init__(*args, **kwargs)
            self.username = self.email
        else:
            super(UserNameAction, self).__init__(*args, **kwargs)

    def _get_email(self):
        return self.email

    def _get_target_user(self):
        """
        Gets the target user by their username
        """
        id_manager = user_store.IdentityManager()
        user = id_manager.find_user(self.username, self.domain_id)

        return user


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

    def _validate_targer_user(self):
        id_manager = user_store.IdentityManager()

        # check if user exists and is valid
        # this may mean we need a token.
        user = self._get_target_user()
        if not user:
            self.action.need_token = True
            self.set_token_fields(["password"])
            self.add_note(
                'No user present with username. Need to create new user.')
            return True
        if user.email != self.email:
            self.add_note(
                'Found matching username, but email did not match.' +
                'Reporting as invalid.')
            return False

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
            self.add_note(
                'Existing user with matching email missing roles.')

        return True

    def _validate(self):
        self.action.valid = (
            self._validate_role_permissions() and
            self._validate_keystone_user() and
            self._validate_domain_id() and
            self._validate_project_id() and
            self._validate_targer_user()
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

        id_manager = user_store.IdentityManager()

        if self.action.state == "default":
            # default action: Create a new user in the tenant and add roles
            try:
                user = id_manager.create_user(
                    name=self.username, password=token_data['password'],
                    email=self.email, domain=self.domain_id,
                    created_on=str(timezone.now()))

                self._grant_roles(user, self.roles, self.project_id)
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
                user = id_manager.find_user(self.username, self.domain_id)

                self._grant_roles(user, self.roles, self.project_id)
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


# TODO(adriant): Write tests for this action.
class NewProjectAction(BaseAction, ProjectMixin, UserMixin):
    """
    Creates a new project for the current keystone_user.

    This action can only be used for an autheticated taskview.
    """

    required = [
        'domain_id',
        'parent_id',
        'project_name',
    ]

    def __init__(self, *args, **kwargs):
        super(NewProjectAction, self).__init__(*args, **kwargs)

    def _validate(self):
        self.action.valid = (
            self._validate_domain_id() and
            self._validate_parent_project() and
            self._validate_project_absent())
        self.action.save()

    def _validate_domain_id(self):
        keystone_user = self.action.task.keystone_user

        if keystone_user['project_domain_id'] != self.domain_id:
            self.add_note('Domain id does not match keystone user domain.')
            return False

        return super(NewProjectAction, self)._validate_domain_id()

    def _validate_parent_project(self):
        if self.parent_id:
            keystone_user = self.action.task.keystone_user

            if self.parent_id != keystone_user['project_id']:
                self.add_note(
                    'Parent id does not match keystone user project.')
                return False
            return super(NewProjectAction, self)._validate_parent_project()
        return True

    def _pre_approve(self):
        self._validate()

    def _post_approve(self):
        project_id = self.get_cache('project_id')
        if project_id:
            self.action.task.cache['project_id'] = project_id
            self.add_note("Project already created.")
        else:
            self._validate()

            if not self.valid:
                return

            self._create_project()

        user_id = self.get_cache('user_id')
        if user_id:
            self.action.task.cache['user_id'] = user_id
            self.add_note("User already given roles.")
        else:
            default_roles = settings.ACTION_SETTINGS.get(
                'NewProjectAction', {}).get("default_roles", {})

            project_id = self.get_cache('project_id')
            keystone_user = self.action.task.keystone_user

            try:
                id_manager = user_store.IdentityManager()
                user = id_manager.get_user(keystone_user['user_id'])

                self._grant_roles(user, default_roles, project_id)
            except Exception as e:
                self.add_note(
                    ("Error: '%s' while adding roles %s "
                     "to user '%s' on project '%s'") %
                    (e, self.username, default_roles, project_id))
                raise

            # put user_id into action cache:
            self.action.task.cache['user_id'] = user.id
            self.set_cache('user_id', user.id)
            self.add_note(("Existing user '%s' attached to project %s" +
                          " with roles: %s")
                          % (self.username, project_id,
                             default_roles))

    def _submit(self, token_data):
        """
        Nothing to do here. Everything is done at post_approve.
        """
        pass


class NewProjectWithUserAction(UserNameAction, ProjectMixin, UserMixin):
    """
    Makes a new project for the given username. Will create the user if it
    doesn't exists.
    """

    required = [
        'domain_id',
        'parent_id',
        'project_name',
        'username',
        'email'
    ]

    def __init__(self, *args, **kwargs):
        super(NewProjectWithUserAction, self).__init__(*args, **kwargs)

    def _validate(self):
        self.action.valid = (
            self._validate_domain_id() and
            self._validate_parent_project() and
            self._validate_project_absent() and
            self._validate_user())
        self.action.save()

    def _validate_user(self):
        id_manager = user_store.IdentityManager()
        user = id_manager.find_user(self.username, self.domain_id)

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

    def _validate_user_submit(self):
        user_id = self.get_cache('user_id')
        project_id = self.get_cache('project_id')

        id_manager = user_store.IdentityManager()

        user = id_manager.get_user(user_id)
        project = id_manager.get_project(project_id)

        if user and project:
            self.action.valid = True
        else:
            self.action.valid = False

        self.action.save()

    def _pre_approve(self):
        self._validate()

    def _post_approve(self):
        """
        Approving a new project means we set up the project itself,
        and if the user doesn't exist, create it right away. An existing
        user automatically gets added to the new project.
        """
        project_id = self.get_cache('project_id')
        if project_id:
            self.action.task.cache['project_id'] = project_id
            self.add_note("Project already created.")
        else:
            self.action.valid = (
                self._validate_domain_id() and
                self._validate_parent_project() and
                self._validate_project_absent())
            self.action.save()

            if not self.valid:
                return

            self._create_project()

        # User validation and checks
        user_id = self.get_cache('user_id')
        if user_id:
            self.action.task.cache['user_id'] = user_id
            self.add_note("User already created.")
        else:
            self.action.valid = self._validate_user()
            self.action.save()

            if not self.valid:
                return

            self._create_user_for_project()

    def _create_user_for_project(self):
        id_manager = user_store.IdentityManager()
        default_roles = settings.ACTION_SETTINGS.get(
            'NewProjectAction', {}).get("default_roles", {})

        project_id = self.get_cache('project_id')

        if self.action.state == "default":
            try:
                # Generate a temporary password:
                password = uuid4().hex + uuid4().hex

                user = id_manager.create_user(
                    name=self.username, password=password,
                    email=self.email, domain=self.domain_id,
                    created_on=str(timezone.now()))

                self._grant_roles(user, default_roles, project_id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating user: %s with roles: %s" %
                    (e, self.username, default_roles))
                raise

            # put user_id into action cache:
            self.action.task.cache['user_id'] = user.id
            self.set_cache('user_id', user.id)
            self.add_note(
                "New user '%s' created for project %s with roles: %s" %
                (self.username, project_id, default_roles))
        elif self.action.state == "existing":
            try:
                user = id_manager.find_user(
                    self.username, self.domain_id)

                self._grant_roles(user, default_roles, project_id)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while attaching user: %s with roles: %s" %
                    (e, self.username, default_roles))
                raise

            # put user_id into action cache:
            self.action.task.cache['user_id'] = user.id
            self.set_cache('user_id', user.id)
            self.add_note(("Existing user '%s' attached to project %s" +
                          " with roles: %s")
                          % (self.username, project_id,
                             default_roles))

    def _submit(self, token_data):
        """
        The submit action is performed when a token is submitted.
        This is done to set a user password only, and so should now only
        change the user password. The project and user themselves are created
        on post_approve.
        """

        self._validate_user_submit()

        if not self.valid:
            return

        project_id = self.get_cache('project_id')
        self.action.task.cache['project_id'] = project_id
        user_id = self.get_cache('user_id')
        self.action.task.cache['user_id'] = user_id
        id_manager = user_store.IdentityManager()

        if self.action.state == "default":
            user = id_manager.get_user(user_id)
            try:
                id_manager.update_user_password(
                    user, token_data['password'])
            except Exception as e:
                self.add_note(
                    "Error: '%s' while changing password for user: %s" %
                    (e, self.username))
                raise
            self.add_note('User %s password has been changed.' % self.username)

        elif self.action.state == "existing":
            # do nothing, everything is already done.
            self.add_note(
                "Existing user '%s' already attached to project %s" % (
                    user_id, project_id))


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

    blacklist = settings.ACTION_SETTINGS.get(
        'ResetUserPasswordAction', {}).get("blacklisted_roles", {})

    def _validate_user_roles(self):
        id_manager = user_store.IdentityManager()

        self.user = id_manager.find_user(self.username, self.domain.id)
        roles = id_manager.get_all_roles(self.user)

        user_roles = []
        for project, roles in roles.iteritems():
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

        id_manager = user_store.IdentityManager()
        try:
            id_manager.update_user_password(self.user, token_data['password'])
        except Exception as e:
            self.add_note(
                "Error: '%s' while changing password for user: %s" %
                (e, self.username))
            raise
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

    def _post_approve(self):
        self._validate()

    def _submit(self, token_data):
        self._validate()

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
register_action_class(NewUserAction, serializers.NewUserSerializer)
register_action_class(
    NewProjectWithUserAction, serializers.NewProjectWithUserSerializer)
register_action_class(ResetUserPasswordAction, serializers.ResetUserSerializer)
register_action_class(EditUserRolesAction, serializers.EditUserRolesSerializer)
