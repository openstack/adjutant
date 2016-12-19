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

from jsonfield import JSONField

from django.conf import settings
from django.db import models
from django.utils import timezone


class Action(models.Model):
    """
    Database model representation of an action.
    """
    action_name = models.CharField(max_length=200)
    action_data = JSONField(default={})
    cache = JSONField(default={})
    state = models.CharField(max_length=200, default="default")
    valid = models.BooleanField(default=False)
    need_token = models.BooleanField(default=False)
    task = models.ForeignKey('api.Task')

    order = models.IntegerField()

    created = models.DateTimeField(default=timezone.now)

    def get_action(self):
        """Returns self as the appropriate action wrapper type."""
        data = self.action_data
        return settings.ACTION_CLASSES[self.action_name][0](
            data=data, action_model=self)
