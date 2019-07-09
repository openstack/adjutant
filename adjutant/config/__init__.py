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

import os
import sys
import yaml

from confspirator import load
from confspirator import groups

from adjutant.config import api
from adjutant.config import django
from adjutant.config import identity
from adjutant.config import notification
from adjutant.config import quota
from adjutant.config import workflow

_root_config = groups.ConfigGroup("adjutant")
_root_config.register_child_config(django.config_group)
_root_config.register_child_config(identity.config_group)
_root_config.register_child_config(api.config_group)
_root_config.register_child_config(notification.config_group)
_root_config.register_child_config(workflow.config_group)
_root_config.register_child_config(quota.config_group)

_config_file = "/etc/adjutant/adjutant.yaml"
_old_config_file = "/etc/adjutant/conf.yaml"


_test_mode_commands = [
    # Adjutant commands:
    'exampleconfig',
    # Django commands:
    'check',
    'makemigrations',
    'squashmigrations',
    'test',
    'testserver',
]


def _load_config():
    if "adjutant-api" in sys.argv[0] and sys.argv[1] in _test_mode_commands:
        test_mode = True
    else:
        test_mode = False

    config_file_locations = [_config_file, _old_config_file]

    conf_file = os.environ.get("ADJUTANT_CONFIG_FILE", None)

    if conf_file:
        config_file_locations.insert(0, conf_file)

    conf_dict = None
    used_config_loc = None
    for conf_file_loc in config_file_locations:
        try:
            with open(conf_file_loc) as f:
                # NOTE(adriant): we print because we don't yet know
                # where to log to
                print("Loading config from '%s'" % conf_file_loc)
                conf_dict = yaml.load(f, Loader=yaml.FullLoader)
                used_config_loc = conf_file_loc
                break
        except IOError:
            if not test_mode:
                print(
                    "Conf file not found at '%s', trying next possible location."
                    % conf_file_loc
                )

    if used_config_loc != conf_file and used_config_loc == _old_config_file and not test_mode:
        print(
            "DEPRECATED: Using the old default config location '%s' is deprecated "
            "in favor of '%s', or setting a config location via the environment "
            "variable 'ADJUTANT_CONFIG_FILE'." % (_old_config_file, _config_file)
        )

    if conf_dict is None:
        if not test_mode:
            print(
                "No valid conf file not found, will rely on defaults and "
                "environment variables.\n"
                "Config should be placed at '%s' or a location defined via the "
                "environment variable 'ADJUTANT_CONFIG_FILE'." % _config_file
            )
        conf_dict = {}

    conf_dict = {"adjutant": conf_dict}
    return load(_root_config, conf_dict, test_mode=test_mode)


CONF = _load_config()
