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

from django.db import models
from django.utils import timezone
from stacktask.base.user_store import IdentityManager
from stacktask.base.serializers import (NewUserSerializer,
                                        NewProjectSerializer,
                                        ResetUserSerializer)
from django.conf import settings
from jsonfield import JSONField
from logging import getLogger


class Action(models.Model):
    """
    Database model representation of an action.
    """
    action_name = models.CharField(max_length=200)
    action_data = JSONField(default={})
    cache = JSONField(default={})
    state = models.CharField(max_length=200, default="default")
    valid = models.BooleanField(default=False)
    need_token = models.BooleanField()
    registration = models.ForeignKey('api_v1.Registration')

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
    - 'token_fields' defined which fields are needed by this action
      at the token stage. If there aren't any, the need_token value
      defaults to False.

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

    Passing data along to other actions is done via the registration and
    it's cache, but this is in memory only, so it is only useful during the
    same action stage ('post_approve', etc.).

    Other than the registration cache, actions should not be altering database
    models other than themselves. This is not enforced, just a guideline.
    """

    required = []

    token_fields = []

    def __init__(self, data, action_model=None, registration=None,
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
            if self.token_fields:
                need_token = True
            else:
                need_token = False
            # make new model and save in db
            action = Action.objects.create(
                action_name=self.__class__.__name__,
                action_data=data,
                need_token=need_token,
                registration=registration,
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

    def token_email(self):
        return self._token_email()

    def _token_email(self):
        raise NotImplementedError

    def get_cache(self, key):
        return self.action.cache.get(key, None)

    def set_cache(self, key, value):
        self.action.cache[key] = value
        self.action.save()

    def add_note(self, note):
        """
        Logs the note, and also adds it to the registration action notes.
        """
        self.logger.info("(%s) - %s" % (timezone.now(), note))
        note = "%s - (%s)" % (note, timezone.now())
        self.action.registration.add_action_note(
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

    def _token_email(self):
        return self.email


class NewUser(UserAction):
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
        'role'
    ]

    token_fields = ['password']

    default_roles = {"Member"}

    def _validate(self):
        id_manager = IdentityManager()

        user = id_manager.find_user(self.username)

        keystone_user = self.action.registration.keystone_user

        if not ("admin" in keystone_user['roles'] or
                keystone_user['project_id'] == self.project_id):
            self.add_note('Project id does not match keystone user project.')
            return False

        if ('project_owner' not in keystone_user['roles'] and
                self.role == "project_mod"):
            self.add_note('User does not have permission to add role.')
            return False

        project = id_manager.get_project(self.project_id)

        if not project:
            self.add_note('Project does not exist.')
            valid = False
        else:
            if user:
                if user.email == self.email:
                    roles = id_manager.get_roles(user, project)
                    if self.role in roles:
                        valid = True
                        self.action.need_token = False
                        self.action.state = "complete"
                        self.add_note(
                            'Existing user already has role, no action needed.'
                        )
                    else:
                        valid = True
                        self.action.need_token = False
                        self.action.state = "existing"
                        self.add_note(
                            'Existing user with matching email and no role.')
                else:
                    valid = False
                    self.add_note('Existing user with non-matching email.')
            else:
                valid = True
                self.add_note('No user present with username')

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

        if self.valid:
            id_manager = IdentityManager()

            if self.action.state == "default":
                try:
                    self.default_roles.add(self.role)

                    roles = []
                    for role in self.default_roles:
                        roles.append(id_manager.find_role(role))

                    user = id_manager.create_user(
                        name=self.username, password=token_data['password'],
                        email=self.email, project_id=self.project_id)

                    for role in roles:
                        id_manager.add_user_role(user, role, self.project_id)
                except Exception as e:
                    self.add_note(
                        "Error: '%s' while creating user: %s with role: %s" %
                        (e, self.username, self.role))
                    raise

                self.add_note(
                    'User %s has been created, with role %s in project %s.'
                    % (self.username, self.role, self.project_id))
            elif self.action.state == "existing":
                try:
                    user = id_manager.find_user(self.username)

                    roles = []
                    for role in self.default_roles:
                        roles.append(id_manager.find_role(role))

                    for role in roles:
                        id_manager.add_user_role(user, role, self.project_id)
                except Exception as e:
                    self.add_note(
                        "Error: '%s' while attaching user: %s with role: %s" %
                        (e, self.username, self.role))
                    raise

                self.add_note(
                    'Existing user %s has been given role %s in project %s.'
                    % (self.username, self.role, self.project_id))
            elif self.action.state == "complete":
                self.add_note(
                    'Existing user %s already had role %s in project %s.'
                    % (self.username, self.role, self.project_id))


class NewProject(UserAction):
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

    token_fields = ['password']

    default_roles = {"Member", "project_owner", "project_mod"}

    def _validate_project(self):
        id_manager = IdentityManager()

        project = id_manager.find_project(self.project_name)

        valid = self._validate_user(id_manager)

        if project:
            valid = False
            self.add_note("Existing project with name '%s'." %
                          self.project_name)
        else:
            self.add_note("No existing project with name '%s'." %
                          self.project_name)

        return valid

    def _validate_user(self, id_manager):
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
            self.add_note("No user present with username '%s'." %
                          self.username)

        return valid

    def _pre_approve(self):
        self.action.valid = self._validate_project()
        self.action.save()

    def _post_approve(self):
        project_id = self.get_cache('project_id')
        if project_id:
            self.action.registration.cache['project_id'] = project_id
            self.add_note("Project already created.")
            return

        self.action.valid = self._validate_project()
        self.action.save()

        if self.valid:
            id_manager = IdentityManager()
            try:
                project = id_manager.create_project(self.project_name)
            except Exception as e:
                self.add_note(
                    "Error: '%s' while creating project: %s" %
                    (e, self.project_name))
                raise
            # put project_id into action cache:
            self.action.registration.cache['project_id'] = project.id
            self.set_cache('project_id', project.id)
            self.add_note("New project '%s' created." % self.project_name)

    def _submit(self, token_data):
        id_manager = IdentityManager()

        self.action.valid = self._validate_user(id_manager)
        self.action.save()

        if self.valid:

            project_id = self.get_cache('project_id')
            self.action.registration.cache['project_id'] = project_id

            project = id_manager.get_project(project_id)

            if self.action.state == "default":
                try:
                    roles = []
                    for role in self.default_roles:
                        roles.append(id_manager.find_role(role))

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


class ResetUser(UserAction):
    """
    Simple action to reset a password for a given user.
    """

    username = models.CharField(max_length=200)
    email = models.EmailField()

    required = [
        'username',
        'email'
    ]

    token_fields = ['password']

    def _validate(self):
        id_manager = IdentityManager()

        user = id_manager.find_user(self.username)

        if user:
            if user.email == self.email:
                valid = True
                self.add_note('Existing user with matching email.')
            else:
                valid = False
                self.add_note('Existing user with non-matching email.')
        else:
            valid = False
            self.add_note('No user present with username')

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

        if self.valid:
            id_manager = IdentityManager()

            user = id_manager.find_user(self.username)
            try:
                id_manager.update_user_password(user, token_data['password'])
            except Exception as e:
                self.add_note(
                    "Error: '%s' while changing password for user: %s" %
                    (e, self.username))
                raise
            self.add_note('User %s password has been changed.' % self.username)


# A dict of tuples in the format: (<ActionClass>, <ActionSerializer>)
action_classes = {
    'NewUser': (NewUser, NewUserSerializer),
    'NewProject': (NewProject, NewProjectSerializer),
    'ResetUser': (ResetUser, ResetUserSerializer)
}

# setup action classes and serializers for global access
settings.ACTION_CLASSES.update(action_classes)
