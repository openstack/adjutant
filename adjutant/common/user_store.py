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

from keystoneclient import exceptions as ks_exceptions

from adjutant.config import CONF
from adjutant.common.openstack_clients import get_keystoneclient


def subtree_ids_list(subtree, id_list=None):
    if id_list is None:
        id_list = []
    if not subtree:
        return id_list
    for key in subtree.keys():
        id_list.append(key)
        if subtree[key]:
            subtree_ids_list(subtree[key], id_list)
    return id_list


# NOTE(adriant): I'm adding no cover here since this class can never be covered
# by unit and non-tempest functional tests. This class only works when talking
# to a real Keystone, so tests can never cover it.
class IdentityManager(object):  # pragma: no cover
    """
    A wrapper object for the Keystone Client. Mainly setup as
    such for easier testing, but also so it can be replaced
    later with an LDAP + Keystone Client variant.
    """

    def __init__(self):
        self.ks_client = get_keystoneclient()

        # TODO(adriant): decide if we want to have some function calls
        # throw errors if this is false.
        self.can_edit_users = CONF.identity.can_edit_users

    def find_user(self, name, domain):
        try:
            users = self.ks_client.users.list(name=name, domain=domain)
            if users:
                # NOTE(adriant) usernames are unique in a domain
                return users[0]
            else:
                return None
        except ks_exceptions.NotFound:
            return None

    def get_user(self, user_id):
        try:
            user = self.ks_client.users.get(user_id)
        except ks_exceptions.NotFound:
            user = None
        return user

    def list_users(self, project):
        """
        Build a list of users for a given project using
        the v3 api.

        Rather than simply list users, we use the assignments
        endpoint so we can also fetch all the roles for those users
        in the given project. Saves further api calls later on.
        """
        try:
            roles = self.ks_client.roles.list()
            role_dict = {role.id: role for role in roles}

            users = {}

            user_assignments = self.ks_client.role_assignments.list(project=project)
            for assignment in user_assignments:
                try:
                    user = users.get(assignment.user["id"], None)
                    if not user:
                        user = self.ks_client.users.get(assignment.user["id"])
                        user.roles = []
                        user.inherited_roles = []
                        users[user.id] = user

                    if assignment.scope.get("OS-INHERIT:inherited_to"):
                        user.inherited_roles.append(role_dict[assignment.role["id"]])
                    else:
                        user.roles.append(role_dict[assignment.role["id"]])
                except AttributeError:
                    # Just means the assignment is a group, so ignore it.
                    pass
        except ks_exceptions.NotFound:
            return []
        return users.values()

    def list_inherited_users(self, project):
        """
        Find all the users whose roles are inherited down to the given project.
        """
        try:
            roles = self.ks_client.roles.list()
            role_dict = {role.id: role for role in roles}

            users = {}

            project = self.ks_client.projects.get(project)
            while project.parent_id:
                project = self.ks_client.projects.get(project.parent_id)
                user_assignments = self.ks_client.role_assignments.list(project=project)
                for assignment in user_assignments:
                    if not assignment.scope.get("OS-INHERIT:inherited_to"):
                        continue
                    try:
                        user = users.get(assignment.user["id"], None)
                        if user:
                            user.roles.append(role_dict[assignment.role["id"]])
                        else:
                            user = self.ks_client.users.get(assignment.user["id"])
                            user.roles = [
                                role_dict[assignment.role["id"]],
                            ]
                            user.inherited_roles = []
                            users[user.id] = user
                    except AttributeError:
                        # Just means the assignment is a group.
                        pass
            for user in users.values():
                user.roles = list(set(user.roles))
        except ks_exceptions.NotFound:
            return []
        return users.values()

    def create_user(
        self, name, password, email, created_on, domain=None, default_project=None
    ):

        user = self.ks_client.users.create(
            name=name,
            password=password,
            domain=domain,
            email=email,
            default_project=default_project,
            created_on=created_on,
        )
        return user

    def enable_user(self, user):
        self.ks_client.users.update(user, enabled=True)

    def disable_user(self, user):
        self.ks_client.users.update(user, enabled=False)

    def update_user_password(self, user, password):
        self.ks_client.users.update(user, password=password)

    def update_user_email(self, user, email):
        self.ks_client.users.update(user, email=email)

    def update_user_name(self, user, name):
        self.ks_client.users.update(user, name=name)

    def find_role(self, name):
        try:
            role = self.ks_client.roles.find(name=name)
        except ks_exceptions.NotFound:
            role = None
        return role

    def get_roles(self, user, project, inherited=False):
        roles = self.ks_client.roles.list()
        role_dict = {role.id: role for role in roles}

        user_roles = []
        user_assignments = self.ks_client.role_assignments.list(
            user=user, project=project
        )
        for assignment in user_assignments:
            if (assignment.scope.get("OS-INHERIT:inherited_to") and not inherited) or (
                inherited and not assignment.scope.get("OS-INHERIT:inherited_to")
            ):
                continue
            user_roles.append(role_dict[assignment.role["id"]])
        return user_roles

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
            project = assignment.scope["project"]["id"]
            projects[project].append(role_dict[assignment.role["id"]])

        return projects

    def add_user_role(self, user, role, project, inherited=False):
        try:
            if inherited:
                self.ks_client.roles.grant(
                    role,
                    user=user,
                    project=project,
                    os_inherit_extension_inherited=inherited,
                )
            else:
                self.ks_client.roles.grant(role, user=user, project=project)
        except ks_exceptions.Conflict:
            # Conflict is ok, it means the user already has this role.
            pass

    def remove_user_role(self, user, role, project, inherited=False):
        if inherited:
            self.ks_client.roles.revoke(
                role,
                user=user,
                project=project,
                os_inherit_extension_inherited=inherited,
            )
        else:
            self.ks_client.roles.revoke(role, user=user, project=project)

    def find_project(self, project_name, domain):
        try:
            # Using a filtered list as find is more efficient than
            # using the client find
            projects = self.ks_client.projects.list(name=project_name, domain=domain)
            if projects:
                # NOTE(adriant) project names are unique in a domain so
                # it is safe to assume filtering on project name and domain
                # will only ever return one.
                return projects[0]
            else:
                return None
        except ks_exceptions.NotFound:
            return None

    def get_project(self, project_id, subtree_as_ids=False, parents_as_ids=False):
        try:
            project = self.ks_client.projects.get(
                project_id, subtree_as_ids=subtree_as_ids, parents_as_ids=parents_as_ids
            )
            if parents_as_ids:
                depth = 1
                last_root = None
                root = project.parents.keys()[0]
                value = project.parents.values()[0]
                while value is not None:
                    depth += 1
                    last_root = root
                    root = value.keys()[0]
                    value = value.values()[0]
                project.root = last_root
                project.depth = depth
                project.parent_ids = subtree_ids_list(project.parents)
            if subtree_as_ids:
                project.subtree_ids = subtree_ids_list(project.subtree)
            return project
        except ks_exceptions.NotFound:
            return None

    def list_sub_projects(self, project_id):
        try:
            return self.ks_client.projects.list(parent_id=project_id)
        except ks_exceptions.NotFound:
            return []

    def update_project(
        self, project, name=None, domain=None, description=None, enabled=None, **kwargs
    ):
        try:
            return self.ks_client.projects.update(
                project=project,
                domain=domain,
                name=name,
                description=description,
                enabled=enabled,
                **kwargs,
            )
        except ks_exceptions.NotFound:
            return None

    def create_project(
        self, project_name, created_on, parent=None, domain=None, description=""
    ):
        project = self.ks_client.projects.create(
            project_name,
            domain,
            parent=parent,
            created_on=created_on,
            description=description,
        )
        return project

    def get_domain(self, domain_id):
        try:
            return self.ks_client.domains.get(domain_id)
        except ks_exceptions.NotFound:
            return None

    def find_domain(self, domain_name):
        try:
            domains = self.ks_client.domains.list(name=domain_name)
            if domains:
                # NOTE(adriant) domain names are unique
                return domains[0]
            else:
                return None
        except ks_exceptions.NotFound:
            return None

    def get_region(self, region_id):
        try:
            region = self.ks_client.regions.get(region_id)
        except ks_exceptions.NotFound:
            region = None
        return region

    def list_regions(self, **kwargs):
        return self.ks_client.regions.list(**kwargs)

    def list_credentials(self, user_id, cred_type=None):
        return self.ks_client.credentials.list(user_id=user_id, type=cred_type)

    def add_credential(self, user, cred_type, blob, project=None):
        return self.ks_client.credentials.create(
            user=user, type=cred_type, blob=blob, project=project
        )

    def delete_credential(self, credential):
        return self.ks_client.credentials.delete(credential)

    def clear_credential_type(self, user_id, cred_type):
        # list credentials of the type for the user
        credentials = self.ks_client.credentials.list(user_id=user_id, type=cred_type)
        for cred in credentials:
            if cred.user_id == user_id and cred.type == cred_type:
                self.ks_client.credentials.delete(cred)

    # TODO(adriant): Move this to a BaseIdentityManager class when
    #                it exists.
    def get_manageable_roles(self, user_roles=None):
        """Get roles which can be managed

        Given a list of user role names, returns a list of names
        that the user is allowed to manage.

        If user_roles is not given, returns all possible roles.
        """
        roles_mapping = CONF.identity.role_mapping
        if user_roles is None:
            all_roles = []
            for options in roles_mapping.values():
                all_roles += options
            return list(set(all_roles))

        # merge mapping lists to form a flat permitted roles list
        manageable_role_names = [
            mrole
            for role_name in user_roles
            if role_name in roles_mapping
            for mrole in roles_mapping[role_name]
        ]
        # a set has unique items
        manageable_role_names = set(manageable_role_names)
        return manageable_role_names
