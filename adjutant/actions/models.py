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

from django.db import models
from django.utils import timezone

from adjutant import actions


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
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE)
    # NOTE(amelia): Auto approve is technically a ternary operator
    #               If all in a task are None it will not auto approve
    #               However if at least one action has it set to True it
    #               will auto approve. If any are set to False this will
    #               override all of them.
    #               Can be thought of in terms of priority, None has the
    #               lowest priority, then True with False having the
    #               highest priority
    auto_approve = models.NullBooleanField(default=None)
    order = models.IntegerField()
    created = models.DateTimeField(default=timezone.now)

    def get_action(self):
        """Returns self as the appropriate action wrapper type."""
        data = self.action_data
        return actions.ACTION_CLASSES[self.action_name](data=data, action_model=self)
