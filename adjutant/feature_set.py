# Copyright (C) 2019 Catalyst Cloud Ltd
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

from rest_framework import serializers as drf_serializers

from confspirator import exceptions as conf_exceptions
from confspirator import groups

from adjutant import exceptions

from adjutant import actions
from adjutant.actions.v1.base import BaseAction
from adjutant.config.workflow import action_defaults_group

from adjutant import tasks
from adjutant.tasks.v1 import base as tasks_base
from adjutant.config.workflow import tasks_group

from adjutant import api
from adjutant.api.v1.base import BaseDelegateAPI
from adjutant.config.api import delegate_apis_group as api_config

from adjutant import notifications
from adjutant.notifications.v1.base import BaseNotificationHandler
from adjutant.config.notification import handler_defaults_group

from adjutant.config.feature_sets import config_group as feature_set_config


def register_action_class(action_class):
    if not issubclass(action_class, BaseAction):
        raise exceptions.InvalidActionClass(
            "'%s' is not a built off the BaseAction class." % action_class.__name__
        )
    if action_class.serializer and not issubclass(
        action_class.serializer, drf_serializers.Serializer
    ):
        raise exceptions.InvalidActionSerializer(
            "serializer for '%s' is not a valid DRF serializer." % action_class.__name__
        )
    data = {}
    data[action_class.__name__] = action_class
    actions.ACTION_CLASSES.update(data)
    if action_class.config_group:
        # NOTE(adriant): We copy the config_group before naming it
        # to avoid cases where a subclass inherits but doesn't extend it
        setting_group = action_class.config_group.copy()
        setting_group.set_name(action_class.__name__, reformat_name=False)
        action_defaults_group.register_child_config(setting_group)


def register_task_class(task_class):
    if not issubclass(task_class, tasks_base.BaseTask):
        raise exceptions.InvalidTaskClass(
            "'%s' is not a built off the BaseTask class." % task_class.__name__
        )
    data = {}
    data[task_class.task_type] = task_class
    if task_class.deprecated_task_types:
        for old_type in task_class.deprecated_task_types:
            data[old_type] = task_class
    tasks.TASK_CLASSES.update(data)

    config_group = tasks_base.make_task_config(task_class)
    config_group.set_name(task_class.task_type, reformat_name=False)
    tasks_group.register_child_config(config_group)


def register_delegate_api_class(api_class):
    if not issubclass(api_class, BaseDelegateAPI):
        raise exceptions.InvalidAPIClass(
            "'%s' is not a built off the BaseDelegateAPI class." % api_class.__name__
        )
    data = {}
    data[api_class.__name__] = api_class
    api.DELEGATE_API_CLASSES.update(data)
    if api_class.config_group:
        # NOTE(adriant): We copy the config_group before naming it
        # to avoid cases where a subclass inherits but doesn't extend it
        setting_group = api_class.config_group.copy()
        setting_group.set_name(api_class.__name__, reformat_name=False)
        api_config.register_child_config(setting_group)


def register_notification_handler(notification_handler):
    if not issubclass(notification_handler, BaseNotificationHandler):
        raise exceptions.InvalidActionClass(
            "'%s' is not a built off the BaseNotificationHandler class."
            % notification_handler.__name__
        )
    notifications.NOTIFICATION_HANDLERS[
        notification_handler.__name__
    ] = notification_handler
    if notification_handler.config_group:
        # NOTE(adriant): We copy the config_group before naming it
        # to avoid cases where a subclass inherits but doesn't extend it
        setting_group = notification_handler.config_group.copy()
        setting_group.set_name(notification_handler.__name__, reformat_name=False)
        handler_defaults_group.register_child_config(setting_group)


def register_feature_set_config(feature_set_group):
    if not isinstance(feature_set_group, groups.ConfigGroup):
        raise conf_exceptions.InvalidConfigClass(
            "'%s' is not a valid config group class" % feature_set_group
        )
    feature_set_config.register_child_config(feature_set_group)


class BaseFeatureSet(object):
    """A grouping of Adjutant pluggable features.

    Contains within it definitions for:
    - actions
    - tasks
    - delegate_apis
    - notification_handlers

    And additional feature set specific config:
    - config

    These are just lists of the appropriate class types, and will
    imported into Adjutant when the featureset is included.
    """

    actions = None
    tasks = None
    delegate_apis = None
    notification_handlers = None

    config = None

    def __init__(self):
        self.logger = getLogger("adjutant")

    def load(self):
        self.logger.info("Loading feature set: '%s'" % self.__class__.__name__)

        if self.actions:
            for action in self.actions:
                register_action_class(action)

        if self.tasks:
            for task in self.tasks:
                register_task_class(task)

        if self.delegate_apis:
            for delegate_api in self.delegate_apis:
                register_delegate_api_class(delegate_api)

        if self.notification_handlers:
            for notification_handler in self.notification_handlers:
                register_notification_handler(notification_handler)

        if self.config:
            if isinstance(self.config, groups.DynamicNameConfigGroup):
                self.config.set_name(self.__class__.__name__)
            register_feature_set_config(self.config)
