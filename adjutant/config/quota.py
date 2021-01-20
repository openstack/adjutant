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

from confspirator import groups
from confspirator import fields
from confspirator import types


DEFAULT_QUOTA_SIZES = {
    "small": {
        "nova": {
            "instances": 10,
            "cores": 20,
            "ram": 65536,
            "floating_ips": 10,
            "fixed_ips": 0,
            "metadata_items": 128,
            "injected_files": 5,
            "injected_file_content_bytes": 10240,
            "key_pairs": 50,
            "security_groups": 20,
            "security_group_rules": 100,
        },
        "cinder": {
            "gigabytes": 5000,
            "snapshots": 50,
            "volumes": 20,
        },
        "neutron": {
            "floatingip": 10,
            "network": 3,
            "port": 50,
            "router": 3,
            "security_group": 20,
            "security_group_rule": 100,
            "subnet": 3,
        },
        "octavia": {
            "health_monitor": 5,
            "listener": 1,
            "load_balancer": 1,
            "member": 2,
            "pool": 1,
        },
        "trove": {
            "instances": 3,
            "volumes": 3,
            "backups": 15,
        },
    },
    "medium": {
        "cinder": {"gigabytes": 10000, "volumes": 100, "snapshots": 300},
        "nova": {
            "metadata_items": 128,
            "injected_file_content_bytes": 10240,
            "ram": 327680,
            "floating_ips": 25,
            "key_pairs": 50,
            "instances": 50,
            "security_group_rules": 400,
            "injected_files": 5,
            "cores": 100,
            "fixed_ips": 0,
            "security_groups": 50,
        },
        "neutron": {
            "security_group_rule": 400,
            "subnet": 5,
            "network": 5,
            "floatingip": 25,
            "security_group": 50,
            "router": 5,
            "port": 250,
        },
        "octavia": {
            "health_monitor": 50,
            "listener": 5,
            "load_balancer": 5,
            "member": 5,
            "pool": 5,
        },
        "trove": {
            "instances": 10,
            "volumes": 10,
            "backups": 50,
        },
    },
    "large": {
        "cinder": {"gigabytes": 50000, "volumes": 200, "snapshots": 600},
        "nova": {
            "metadata_items": 128,
            "injected_file_content_bytes": 10240,
            "ram": 655360,
            "floating_ips": 50,
            "key_pairs": 50,
            "instances": 100,
            "security_group_rules": 800,
            "injected_files": 5,
            "cores": 200,
            "fixed_ips": 0,
            "security_groups": 100,
        },
        "neutron": {
            "security_group_rule": 800,
            "subnet": 10,
            "network": 10,
            "floatingip": 50,
            "security_group": 100,
            "router": 10,
            "port": 500,
        },
        "octavia": {
            "health_monitor": 100,
            "listener": 10,
            "load_balancer": 10,
            "member": 10,
            "pool": 10,
        },
        "trove": {
            "instances": 20,
            "volumes": 20,
            "backups": 100,
        },
    },
}


config_group = groups.ConfigGroup("quota")

config_group.register_child_config(
    fields.DictConfig(
        "sizes",
        help_text="A definition of the quota size groups that Adjutant should use.",
        value_type=types.Dict(value_type=types.Dict()),
        check_value_type=True,
        is_json=True,
        default=DEFAULT_QUOTA_SIZES,
    )
)
config_group.register_child_config(
    fields.ListConfig(
        "sizes_ascending",
        help_text="An ascending list of all the quota size names, "
        "so that Adjutant knows their relative sizes/order.",
        default=["small", "medium", "large"],
    )
)
config_group.register_child_config(
    fields.DictConfig(
        "services",
        help_text="A per region definition of what services Adjutant should manage "
        "quotas for. '*' means all or default region.",
        value_type=types.List(),
        default={"*": ["cinder", "neutron", "nova"]},
    )
)
