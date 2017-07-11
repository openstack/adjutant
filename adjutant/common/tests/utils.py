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


import copy

from django.conf import settings
from django.test.utils import override_settings
from django.test import TestCase
from rest_framework.test import APITestCase


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
        for update_dict in self.update_dicts:
            update_dict['pointer'].clear()
            update_dict['pointer'].update(update_dict['copy'])

        super(modify_dict_settings, self).disable()

    def enable(self):
        self.options = {}

        self.update_dicts = []
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
                    # Needs to be saved seperately and update re-used on
                    # disable due to pointers
                    self.update_dicts.append(
                        {'pointer': holding_dict[final_key],
                         'copy': copy.deepcopy(holding_dict[final_key])})
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
