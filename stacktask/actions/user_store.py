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

from collections import defaultdict

from django.conf import settings

from keystoneclient.openstack.common.apiclient import (
    exceptions as ks_exceptions
)

from openstack_clients import get_keystoneclient


def get_managable_roles(user_roles):
    """
    Given a list of user role names, returns a list of names
    that the user is allowed to manage.
    """
    manage_mapping = settings.ROLES_MAPPING
    # merge mapping lists to form a flat permitted roles list
    managable_role_names = [mrole for role_name in user_roles
                            if role_name in manage_mapping
                            for mrole in manage_mapping[role_name]]
    # a set has unique items
    managable_role_names = set(managable_role_names)
    return managable_role_names


class IdentityManager(object):
    """
    A wrapper object for the Keystone Client. Mainly setup as
    such for easier testing, but also so it can be replaced
    later with an LDAP + Keystone Client variant.
    """

    def __init__(self):
        self.ks_client = get_keystoneclient()

    def find_user(self, name):
        try:
            user = self.ks_client.users.find(name=name)
        except ks_exceptions.NotFound:
            user = None
        return user

    def get_user(self, user_id):
        try:
            user = self.ks_client.users.get(user_id)
        except ks_exceptions.NotFound:
            user = None
        return user

    def list_users(self, project):
        """
        Build a list of users for a given project using
        the v3 api. Less straightforward than the v2 api,
        but because we have the role data already, we add it
        to the user model so later roles fetching is not needed.
        """
        try:
            roles = self.ks_client.roles.list()
            role_dict = {role.id: role for role in roles}

            users = {}
            user_assignments = self.ks_client.role_assignments.list(
                project=project)
            for assignment in user_assignments:
                try:
                    user = users.get(assignment.user['id'], None)
                    if user:
                        user.roles.append(role_dict[assignment.role['id']])
                    else:
                        user = self.ks_client.users.get(assignment.user['id'])
                        user.roles = [role_dict[assignment.role['id']], ]
                        users[user.id] = user
                except AttributeError:
                    # Just means the assignment is a group, so ignore it.
                    pass
        except ks_exceptions.NotFound:
            users = []
        return users.values()

    def create_user(self, name, password, email, project_id):
        user = self.ks_client.users.create(
            name=name, password=password,
            email=email, project_id=project_id)
        return user

    def update_user_password(self, user, password):
        self.ks_client.users.update(user, password=password)

    def find_role(self, name):
        try:
            role = self.ks_client.roles.find(name=name)
        except ks_exceptions.NotFound:
            role = None
        return role

    def get_roles(self, user, project):
        return self.ks_client.roles.list(user=user, project=project)

    def get_all_roles(self, user):
        """
        Returns roles for a given user across all projects.

        Uses the new v3 assignments api method to quickly do this.
        """
        roles = self.ks_client.roles.list()
        role_dict = {role.id: role for role in roles}

        user_assignments = self.ks_client.role_assignments.list(user=user)
        projects = defaultdict(list)
        for assignment in user_assignments:
            project = assignment.scope['project']['id']
            projects[project].append(role_dict[assignment.role['id']])

        return projects

    def add_user_role(self, user, role, project_id):
        try:
            self.ks_client.roles.grant(role, user=user, project=project_id)
        except ks_exceptions.Conflict:
            # Conflict is ok, it means the user already has this role.
            pass

    def remove_user_role(self, user, role, project_id):
        self.ks_client.roles.revoke(role, user=user, project=project_id)

    def find_project(self, project_name):
        try:
            project = self.ks_client.projects.find(name=project_name)
        except ks_exceptions.NotFound:
            project = None
        return project

    def get_project(self, project_id):
        try:
            project = self.ks_client.projects.get(project_id)
        except ks_exceptions.NotFound:
            project = None
        return project

    def create_project(self, project_name, created_on):
        project = self.ks_client.projects.create(project_name,
                                                 created_on=created_on)
        return project
