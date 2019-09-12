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

from django.apps import AppConfig

from adjutant.startup import checks
from adjutant.startup import loading


class StartUpConfig(AppConfig):
    name = "adjutant.startup"

    def ready(self):
        """A pre-startup function for the api

        Code run here will occur before the API is up and active but after
        all models have been loaded.

        Loads feature_sets.

        Useful for any start up checks.
        """
        # load all the feature sets
        loading.load_feature_sets()

        # First check that all expect DelegateAPIs are present
        checks.check_expected_delegate_apis()
        # Now check if all the actions those views expecte are present.
        checks.check_configured_actions()
