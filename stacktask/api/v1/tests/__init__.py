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
    admin_user = mock.Mock()
    admin_user.id = 'user_id_0'
    admin_user.name = 'admin'
    admin_user.password = 'password'
    admin_user.email = 'admin@example.com'

    users.update({admin_user.id: admin_user})

    global temp_cache

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
        }
    }


class FakeProject():

    def __init__(self, project):
        self.id = project.id
        self.name = project.name
        self.roles = project.roles

    def list_users(self):
        global temp_cache
        usernames = []
        for username, roles in self.roles.iteritems():
            if roles:
                usernames.append(username)
        users = []
        for user in temp_cache['users'].values():
            if user.name in usernames:
                users.append(user)
        return users


class FakeManager(object):

    def find_user(self, name):
        global temp_cache
        for user in temp_cache['users'].values():
            if user.name == name:
                return user
        return None

    def get_user(self, user_id):
        global temp_cache
        return temp_cache['users'].get(user_id, None)

    def list_users(self, project):
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

    def create_user(self, name, password, email, project_id):
        global temp_cache
        user = mock.Mock()
        user.id = "user_id_%s" % int(temp_cache['i'])
        user.name = name
        user.password = password
        user.email = email
        user.default_project = project_id
        temp_cache['users'][user.id] = user

        temp_cache['i'] += 0.5
        return user

    def update_user_password(self, user, password):
        global temp_cache
        user = temp_cache['users'][user.id]
        user.password = password

    def find_role(self, name):
        global temp_cache
        if temp_cache['roles'].get(name, None):
            role = mock.Mock()
            role.name = name
            return role
        return None

    def get_roles(self, user, project):
        global temp_cache
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
        global temp_cache
        projects = {}
        for project in temp_cache['projects'].values():
            projects[project.id] = []
            for role in project.roles[user.id]:
                r = mock.Mock()
                r.name = role
                projects[project.id].append(r)

        return projects

    def add_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        try:
            project.roles[user.id].append(role.name)
        except KeyError:
            project.roles[user.id] = [role.name]

    def remove_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        try:
            project.roles[user.id].remove(role.name)
        except KeyError:
            pass

    def find_project(self, project_name):
        global temp_cache
        return temp_cache['projects'].get(project_name, None)

    def get_project(self, project_id):
        global temp_cache
        for project in temp_cache['projects'].values():
            if project.id == project_id:
                return FakeProject(project)

    def create_project(self, project_name, created_on, p_id=None):
        global temp_cache
        project = mock.Mock()
        if p_id:
            project.id = p_id
        else:
            temp_cache['i'] += 0.5
            project.id = "project_id_%s" % int(temp_cache['i'])
        project.name = project_name
        project.roles = {}
        temp_cache['projects'][project_name] = project
        return project
