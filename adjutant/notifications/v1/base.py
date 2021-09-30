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

from logging import getLogger

from adjutant.config import CONF


class BaseNotificationHandler(object):
    """"""

    config_group = None

    def __init__(self):
        self.logger = getLogger("adjutant")

    def config(self, task, notification):
        """build config based on conf and defaults

        Will use the Handler defaults, and the overlay them with more
        specific overrides from the task defaults, and the per task
        type config.
        """
        try:
            notif_config = CONF.notifications.handler_defaults.get(
                self.__class__.__name__
            )
        except KeyError:
            # Handler has no config
            return {}

        task_defaults = task.config.notifications

        try:
            if notification.error:
                task_defaults = task_defaults.error_handler_config[
                    self.__class__.__name__
                ]
            else:
                task_defaults = task_defaults.standard_handler_config[
                    self.__class__.__name__
                ]
        except KeyError:
            task_defaults = {}

        return notif_config.overlay(task_defaults)

    def notify(self, task, notification):
        return self._notify(task, notification)

    def _notify(self, task, notification):
        raise NotImplementedError
