# Copyright (C) 2014 Catalyst IT Ltd
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
import json
from django.utils import timezone
from openstack_clients import get_keystoneclient
from keystoneclient.openstack.common.apiclient import exceptions
from serializers import (NewUserSerializer, NewProjectSerializer,
                         ResetUserSerializer)
from django.conf import settings


class Action(models.Model):
    """Database model representation of the related action."""
    action_name = models.CharField(max_length=200)
    action_data = models.TextField()
    state = models.CharField(max_length=200, default="default")
    valid = models.BooleanField(default=False)
    need_token = models.BooleanField(default=True)
    registration = models.ForeignKey('api_v1.Registration')

    order = models.IntegerField()

    created = models.DateTimeField(default=timezone.now)

    def get_action(self):
        """"""
        data = json.loads(self.action_data)
        return settings.ACTION_CLASSES[self.action_name][0](
            data=data, action_model=self)


class BaseAction(object):
    """Base class for the object wrapping around the database model.
       Setup to allow multiple action types and different internal logic
       per type but built from a single database type.
       - 'required' defines what fields to setup from the data.
       - 'token_fields' defined which fields are needed by this action
         at the token stage."""

    required = []

    token_fields = []

    def __init__(self, data, action_model=None, registration=None,
                 order=None):
        """Build itself around an existing database model,
           or build itself and creates a new database model.
           Sets up required data as fields."""

        for field in self.required:
            field_data = data[field]
            setattr(self, field, field_data)

        if action_model:
            self.action = action_model
        else:
            # make new model and save in db
            action = Action.objects.create(
                action_name=self.__class__.__name__,
                action_data=json.dumps(data),
                registration=registration,
                order=order
            )
            action.save()
            self.action = action

    @property
    def valid(self):
        return self.action.valid

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


class NewUser(BaseAction):
    """Setup a new user with a role on the given project.
       Creates the user if they don't exist, otherwise
       if the username and email for the request match the
       existing one, will simply add the project role."""

    required = [
        'username',
        'email',
        'project_id',
        'role'
    ]

    token_fields = ['password']

    def _validate(self):
        # TODO(Adriant): Figure out how to set this up as a generic
        # user store object/module that can handle most of this and
        # be made pluggable down the line.
        keystone = get_keystoneclient()
        try:
            user = keystone.users.find(name=self.username)
        except exceptions.NotFound:
            user = None

        keystone_user = json.loads(self.action.registration.keystone_user)

        if not ("admin" in keystone_user['roles'] or
                keystone_user['project_id'] == self.project_id):
            return ['Project id does not match keystone user project.']

        try:
            project = keystone.tenants.find(name=self.project_name)
        except exceptions.NotFound:
            project = None

        if not project:
            return ['Project does exist.']

        if user:
            if user.email == self.email:
                self.action.valid = True
                self.action.need_token = False
                self.action.state = "existing"
                self.action.save()
                return ['Existing user with matching email.']
            else:
                return ['Existing user with non-matching email.']
        else:
            self.action.valid = True
            self.action.save()
            return ['No user present with username']

    def _pre_approve(self):
        return self._validate()

    def _post_approve(self):
        return self._validate()

    def _submit(self, token_data):
        self._validate()

        if self.valid:
            keystone = get_keystoneclient()

            if self.action.state == "default":
                user = keystone.users.create(
                    name=self.username, password=token_data['password'],
                    email=self.email, tenant_id=self.project_id)
                role = keystone.roles.find(name=self.role)
                keystone.roles.add_user_role(user, role, self.project_id)

                return [
                    ('User %s has been created, with role %s in project %s.'
                     % (self.username, self.role, self.project_id)), ]
            elif self.action.state == "existing":
                user = keystone.users.find(name=self.username)
                role = keystone.roles.find(name=self.role)
                keystone.roles.add_user_role(user, role, self.project_id)
                return [
                    ('Existing user %s has been given role %s in project %s.'
                     % (self.username, self.role, self.project_id)), ]


class NewProject(BaseAction):
    """Similar functionality as the NewUser action,
       but will create the project if valid. Will setup
       the user (existing or new) with the 'default_role'."""

    required = [
        'project_name',
        'username',
        'email'
    ]

    default_role = "project_owner"

    token_fields = ['password']

    def _validate(self):
        keystone = get_keystoneclient()

        try:
            user = keystone.users.find(name=self.username)
        except exceptions.NotFound:
            user = None

        try:
            project = keystone.tenants.find(name=self.project_name)
        except exceptions.NotFound:
            project = None

        notes = []

        if user:
            if user.email == self.email:
                self.action.valid = True
                self.action.state = "existing"
                self.action.need_token = False
                self.action.save()
                notes.append("Existing user '%s' with matching email." %
                             self.email)
            else:
                notes.append("Existing user '%s' with non-matching email." %
                             self.username)
        else:
            self.action.valid = True
            self.action.save()
            notes.append("No user present with username '%s'." %
                         self.username)

        if project:
            self.action.valid = False
            self.action.save()
            notes.append("Existing project with name '%s'." %
                         self.project_name)
        else:
            notes.append("No existing project with name '%s'." %
                         self.project_name)

        return notes

    def _pre_approve(self):
        return self._validate()

    def _post_approve(self):
        return self._validate()

    def _submit(self, token_data):
        print "make project"
        self._validate()

        if self.valid:
            keystone = get_keystoneclient()

            if self.action.state == "default":
                project = keystone.tenants.create(self.project_name)
                # put project_id into action cache:
                self.action.registration.cache['project_id'] = project.id
                user = keystone.users.create(
                    name=self.username, password=token_data['password'],
                    email=self.email, tenant_id=project.id)
                role = keystone.roles.find(name=self.default_role)
                keystone.roles.add_user_role(user, role, project.id)

                return [
                    ("New project '%s' created with user '%s'."
                     % (self.project_name, self.username)), ]
            elif self.action.state == "existing":
                project = keystone.tenants.create(self.project_name)
                # put project_id into action cache:
                self.action.registration.cache['project_id'] = project.id
                user = keystone.users.find(name=self.username)
                role = keystone.roles.find(name=self.default_role)
                keystone.roles.add_user_role(user, role, project.id)
                return [
                    ("New project '%s' created for existing user '%s'."
                     % (self.project_name, self.username)), ]


class ResetUser(BaseAction):
    """Simple action to reset a password for a given user."""

    username = models.CharField(max_length=200)
    email = models.EmailField()

    required = [
        'username',
        'email'
    ]

    token_fields = ['password']

    def _validate(self):
        keystone = get_keystoneclient()

        try:
            user = keystone.users.find(name=self.username)
        except exceptions.NotFound:
            user = None

        if user:
            if user.email == self.email:
                self.action.valid = True
                self.action.save()
                return ['Existing user with matching email.']
            else:
                return ['Existing user with non-matching email.']
        else:
            return ['No user present with username']

    def _pre_approve(self):
        return self._validate()

    def _post_approve(self):
        return self._validate()

    def _submit(self, token_data):
        self._validate()

        if self.valid:
            keystone = get_keystoneclient()

            user = keystone.users.find(name=self.username)
            keystone.users.update_password(user, token_data['password'])
            return [('User %s password has been changed.' % self.username), ]


# A dict of tuples in the format: (<ActionClass>, <ActionSerializer>)
action_classes = {
    'NewUser': (NewUser, NewUserSerializer),
    'NewProject': (NewProject, NewProjectSerializer),
    'ResetUser': (ResetUser, ResetUserSerializer)
}

# setup action classes and serializers for global access
settings.ACTION_CLASSES.update(action_classes)
