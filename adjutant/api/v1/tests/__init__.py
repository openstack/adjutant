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
import six
import copy

from django.conf import settings
from django.test.utils import override_settings
from django.test import TestCase
from rest_framework.test import APITestCase

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

        for user_id, user_roles in roles.iteritems():
            user = self.get_user(user_id)
            user.roles = []

            for role in user_roles:
                r = mock.Mock()
                r.name = role
                user.roles.append(r)

            users.append(user)
        return users

    def create_user(self, name, password, email, created_on,
                    domain='default', default_project=None):
        domain = self._domain_from_id(domain)
        default_project = self._project_from_id(default_project)
        global temp_cache
        user = mock.Mock()
        user.id = "user_id_%s" % int(temp_cache['i'])
        user.name = name
        user.password = password
        user.email = email
        user.domain = domain.id
        user.default_project = default_project
        temp_cache['users'][user.id] = user

        temp_cache['i'] += 0.5
        return user

    def update_user_password(self, user, password):
        user = self._user_from_id(user)
        user.password = password

    def update_user_name(self, user, username):
        user = self._user_from_id(user)
        user.name = username

    def update_user_email(self, user, email):
        user = self._user_from_id(user)
        user.email = email

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

    def update_project(self, project, **kwargs):
        project = self._project_from_id(project)
        for key, arg in six.iteritems(kwargs):
            if arg is not None:
                setattr(project, key, arg)
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

    def get_region(self, region_id):
        global temp_cache
        return temp_cache['regions'].get(region_id, None)


class modify_dict_settings(override_settings):
    """
    A decorator like djangos modify_settings and override_settings, but makes
    it possible to do those same operations on dict based settings.

    The decorator will act after both override_settings and modify_settings.

    Can be applied to test functions or AdjutantTestCase,
    AdjutantAPITestCase classes. In those two classes settings can also
    be modified using:

    with self.modify_dict_settings(...):
        # code

    Example Usage:
    @modify_dict_settings(ROLES_MAPPING=[
                            {'key_list': ['project_mod'],
                            'operation': 'remove',
                            'value': 'heat_stack_owner'},
                            {'key_list': ['project_admin'],
                            'operation': 'append',
                            'value': 'heat_stack_owner'},
                            ])
    or
    @modify_dict_settings(PROJECT_QUOTA_SIZES={
                            'key_list': ['small', 'nova', 'instances'],
                            'operations': 'override',
                            'value': 11
                            })

    Available operations:
    Standard operations:
    - 'update': A dict on dict operation to update final dict with value.
    - 'override': Either overrides or adds the value to the dictionary.
    - 'delete': Removes the value from the dictionary.

    List operations:
    List operations expect that the accessed value in the dictionary is a list.
    - 'append': Add the specified values to the end of the list
    - 'prepend': Add the specifed values to the start of the list
    - 'remove': Remove the specified values from the list
    """

    def __init__(self, *args, **kwargs):
        if args:
            # Hack used when instantiating from SimpleTestCase.setUpClass.
            assert not kwargs
            self.operations = args[0]
        else:
            assert not args
            self.operations = list(kwargs.items())
        super(override_settings, self).__init__()

    def save_options(self, test_func):
        if getattr(test_func, "_modified_dict_settings", None) is None:
            test_func._modified_dict_settings = self.operations
        else:
            # Duplicate list to prevent subclasses from altering their parent.
            test_func._modified_dict_settings = list(
                test_func._modified_dict_settings) + self.operations

    def disable(self):
        self.wrapped = self._wrapped
        super(modify_dict_settings, self).disable()

    def enable(self):
        self.options = {}

        self._wrapped = copy.deepcopy(settings._wrapped)

        for name, operation_list in self.operations:
            try:
                value = self.options[name]
            except KeyError:
                value = getattr(settings, name, [])

            if not isinstance(value, dict):
                raise ValueError("Initial setting not dictionary.")

            if not isinstance(operation_list, list):
                operation_list = [operation_list]

            for operation in operation_list:
                op_type = operation['operation']

                holding_dict = value

                # Recursively find the dict we want
                key_len = len(operation['key_list'])
                final_key = operation['key_list'][0]

                for i in range(key_len):
                    current_key = operation['key_list'][i]
                    if i == (key_len - 1):
                        final_key = current_key
                    else:
                        try:
                            holding_dict = holding_dict[current_key]
                        except KeyError:
                            holding_dict[current_key] = {}
                            holding_dict = holding_dict[current_key]

                if op_type == "override":
                    holding_dict[final_key] = operation['value']
                elif op_type == "delete":
                    del holding_dict[final_key]
                elif op_type == "update":
                    holding_dict[final_key].update(operation['value'])
                else:
                    val = holding_dict.get(final_key, [])
                    items = operation['value']

                    if not isinstance(items, list):
                        items = [items]

                    if op_type == 'append':
                        holding_dict[final_key] = val + [
                            item for item in items if item not in val]
                    elif op_type == 'prepend':
                        holding_dict[final_key] = ([item for item in items if
                                                    item not in val] + val)
                    elif op_type == 'remove':
                        holding_dict[final_key] = [
                            item for item in val if item not in items]
                    else:
                        raise ValueError("Unsupported action: %s" % op_type)
            self.options[name] = value
        super(modify_dict_settings, self).enable()


class TestCaseMixin(object):
    """ Mixin to add modify_dict_settings functions to test classes """

    @classmethod
    def _apply_settings_changes(cls):
        if getattr(cls, '_modified_dict_settings', None):
            operations = {}
            for key, value in cls._modified_dict_settings:
                operations[key] = value
            cls._cls_modified_dict_context = modify_dict_settings(
                **operations)
            cls._cls_modified_dict_context.enable()

    @classmethod
    def _remove_settings_changes(cls):
        if hasattr(cls, '_cls_modified_dict_context'):
            cls._cls_modified_dict_context.disable()
            delattr(cls, '_cls_modified_dict_context')

    def modify_dict_settings(self, **kwargs):
        return modify_dict_settings(**kwargs)


class AdjutantTestCase(TestCase, TestCaseMixin):
    """
    TestCase override that has support for @modify_dict_settings as a
    class decorator and internal function
    """
    @classmethod
    def setUpClass(cls):
        super(AdjutantTestCase, cls).setUpClass()
        cls._apply_settings_changes()

    @classmethod
    def tearDownClass(cls):
        cls._remove_settings_changes()
        super(AdjutantTestCase, cls).tearDownClass()


class AdjutantAPITestCase(APITestCase, TestCaseMixin):
    """
    APITestCase override that has support for @modify_dict_settings as a
    class decorator, and internal function
    """
    @classmethod
    def setUpClass(cls):
        super(AdjutantAPITestCase, cls).setUpClass()
        cls._apply_settings_changes()

    @classmethod
    def tearDownClass(cls):
        cls._remove_settings_changes()
        super(AdjutantAPITestCase, cls).tearDownClass()
