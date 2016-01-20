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
    admin_user.id = 0
    admin_user.username = 'admin'
    admin_user.password = 'password'
    admin_user.email = 'admin@example.com'

    users.update({admin_user.username: admin_user})

    global temp_cache

    temp_cache = {
        'i': 1,
        'users': users,
        'projects': projects,
        'roles': {
            'Member': 'Member',
            '_member_': '_member_',
            'admin': 'admin',
            'project_owner': 'project_owner',
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
            if user.username in usernames:
                users.append(user)
        return users


class FakeManager(object):

    def find_user(self, name):
        global temp_cache
        return temp_cache['users'].get(name, None)

    def get_user(self, user_id):
        global temp_cache
        return temp_cache['users'].get(user_id, None)

    def create_user(self, name, password, email, project_id):
        global temp_cache
        user = mock.Mock()
        temp_cache['i'] += 1
        user.id = temp_cache['i']
        user.username = name
        user.password = password
        user.email = email
        user.default_project = project_id
        temp_cache['users'][name] = user
        return user

    def update_user_password(self, user, password):
        global temp_cache
        user = temp_cache['users'][user.username]
        user.password = password

    def find_role(self, name):
        global temp_cache
        return temp_cache['roles'].get(name, None)

    def get_roles(self, user, project):
        global temp_cache
        try:
            roles = []
            for role in project.roles[user.username]:
                r = mock.Mock()
                r.name = role
                roles.append(r)
            return roles
        except KeyError:
            return []

    def add_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        try:
            project.roles[user.username].append(role)
        except KeyError:
            project.roles[user.username] = [role]

    def remove_user_role(self, user, role, project_id):
        project = self.get_project(project_id)
        try:
            project.roles[user.username].remove(role)
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
            temp_cache['i'] += 1
            project.id = temp_cache['i']
        project.name = project_name
        project.roles = {}
        temp_cache['projects'][project_name] = project
        return project
