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

import mock


temp_cache = {}


def setup_temp_cache(projects, users):
    default_domain = mock.Mock()
    default_domain.id = 'default'
    default_domain.name = 'Default'

    admin_user = mock.Mock()
    admin_user.id = 'user_id_0'
    admin_user.name = 'admin'
    admin_user.password = 'password'
    admin_user.email = 'admin@example.com'
    admin_user.domain = default_domain.id

    users.update({admin_user.id: admin_user})

    region_one = mock.Mock()
    region_one.id = 'region_id_0'
    region_one.name = 'RegionOne'

    global temp_cache

    # TODO(adriant): region and project keys are name, should be ID.
    temp_cache = {
        'i': 1,
        'users': users,
        'projects': projects,
        'roles': {
            '_member_': '_member_',
            'admin': 'admin',
            'project_admin': 'project_admin',
            'project_mod': 'project_mod',
            'heat_stack_owner': 'heat_stack_owner'
        },
        'regions': {
            'RegionOne': region_one,
        },
        'domains': {
            default_domain.id: default_domain,
        },
    }


class FakeManager(object):

    def _project_from_id(self, project):
        if isinstance(project, mock.Mock):
            return project
        else:
            return self.get_project(project)

    def _role_from_id(self, role):
        if isinstance(role, mock.Mock):
            return role
        else:
            return self.get_role(role)

    def _user_from_id(self, user):
        if isinstance(user, mock.Mock):
            return user
        else:
            return self.get_user(user)

    def _domain_from_id(self, domain):
        if isinstance(domain, mock.Mock):
            return domain
        else:
            return self.get_domain(domain)

    def find_user(self, name, domain):
        domain = self._domain_from_id(domain)
        global temp_cache
        for user in temp_cache['users'].values():
            if user.name == name and user.domain == domain.id:
                return user
        return None

    def get_user(self, user_id):
        global temp_cache
        return temp_cache['users'].get(user_id, None)

    def list_users(self, project):
        project = self._project_from_id(project)
        global temp_cache
        roles = temp_cache['projects'][project.name].roles
        users = []

        for user_id, roles in roles.iteritems():
            user = self.get_user(user_id)
            user.roles = []

            for role in roles:
                r = mock.Mock()
                r.name = role
                user.roles.append(r)
        return users

    def create_user(self, name, password, email, created_on,
                    domain='default', default_project=None):
        domain = self._project_from_id(domain)
        default_project = self._project_from_id(default_project)
        global temp_cache
        user = mock.Mock()
        user.id = "user_id_%s" % int(temp_cache['i'])
        user.name = name
        user.password = password
        user.email = email
        user.domain = domain
        user.default_project = default_project
        temp_cache['users'][user.id] = user

        temp_cache['i'] += 0.5
        return user

    def update_user_password(self, user, password):
        user = self._user_from_id(user)
        user.password = password

    def enable_user(self, user):
        user = self._user_from_id(user)
        user.enabled = True

    def disable_user(self, user):
        user = self._user_from_id(user)
        user.enabled = False

    def find_role(self, name):
        global temp_cache
        if temp_cache['roles'].get(name, None):
            role = mock.Mock()
            role.name = name
            return role
        return None

    def get_roles(self, user, project):
        user = self._user_from_id(user)
        project = self._project_from_id(project)
        try:
            roles = []
            for role in project.roles[user.id]:
                r = mock.Mock()
                r.name = role
                roles.append(r)
            return roles
        except KeyError:
            return []

    def get_all_roles(self, user):
        user = self._user_from_id(user)
        global temp_cache
        projects = {}
        for project in temp_cache['projects'].values():
            projects[project.id] = []
            for role in project.roles[user.id]:
                r = mock.Mock()
                r.name = role
                projects[project.id].append(r)

        return projects

    def add_user_role(self, user, role, project):
        user = self._user_from_id(user)
        role = self._role_from_id(role)
        project = self._project_from_id(project)
        try:
            project.roles[user.id].append(role.name)
        except KeyError:
            project.roles[user.id] = [role.name]

    def remove_user_role(self, user, role, project):
        user = self._user_from_id(user)
        role = self._role_from_id(role)
        project = self._project_from_id(project)
        try:
            project.roles[user.id].remove(role.name)
        except KeyError:
            pass

    def find_project(self, project_name, domain):
        domain = self._domain_from_id(domain)
        global temp_cache
        for project in temp_cache['projects'].values():
            if project.name == project_name and project.domain == domain.id:
                return project
        return None

    def get_project(self, project_id):
        global temp_cache
        for project in temp_cache['projects'].values():
            if project.id == project_id:
                return project

    def create_project(self, project_name, created_on, parent=None,
                       domain='default', p_id=None):
        parent = self._project_from_id(parent)
        global temp_cache
        project = mock.Mock()
        if p_id:
            project.id = p_id
        else:
            temp_cache['i'] += 0.5
            project.id = "project_id_%s" % int(temp_cache['i'])
        project.name = project_name
        if parent:
            project.parent = parent
        else:
            project.parent = domain
        project.domain = domain
        project.roles = {}
        temp_cache['projects'][project_name] = project
        return project

    def find_domain(self, domain_name):
        global temp_cache
        for domain in temp_cache['domains'].values():
            if domain.name == domain_name:
                return domain
        return None

    def get_domain(self, domain_id):
        global temp_cache
        return temp_cache['domains'].get(domain_id, None)

    def find_region(self, region_name):
        global temp_cache
        return temp_cache['regions'].get(region_name, None)

    def get_region(self, region_id):
        global temp_cache
        for region in temp_cache['regions'].values():
            if region.id == region_id:
                return region
