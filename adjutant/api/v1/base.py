# Copyright (C) 2019 Catalyst IT Ltd
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

from adjutant.api.v1.views import APIViewWithLogger

from adjutant.config import CONF


class BaseDelegateAPI(APIViewWithLogger):
    """Base Class for Adjutant's deployer configurable APIs."""

    url = None

    config_group = None

    def __init__(self, *args, **kwargs):
        super(BaseDelegateAPI, self).__init__(*args, **kwargs)
        # NOTE(adriant): This is only used at registration,
        #                so lets not expose it:
        self.config_group = None

    @property
    def config(self):
        return CONF.api.delegate_apis.get(self.__class__.__name__)
