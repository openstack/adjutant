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


config_group = groups.ConfigGroup("django")

config_group.register_child_config(
    fields.StrConfig(
        "secret_key",
        help_text="The Django secret key.",
        required=True,
        default="Do not ever use this awful secret in prod!!!!",
        secret=True,
        unsafe_default=True,
    )
)
config_group.register_child_config(
    fields.BoolConfig(
        "debug",
        help_text="Django debug mode is turned on.",
        default=False,
        unsafe_default=True,
    )
)
config_group.register_child_config(
    fields.ListConfig(
        "allowed_hosts",
        help_text="The Django allowed hosts",
        required=True,
        default=["*"],
        unsafe_default=True,
    )
)
config_group.register_child_config(
    fields.StrConfig(
        "secure_proxy_ssl_header",
        help_text="The header representing a HTTP header/value combination "
        "that signifies a request is secure.",
        default="HTTP_X_FORWARDED_PROTO",
    )
)
config_group.register_child_config(
    fields.StrConfig(
        "secure_proxy_ssl_header_value",
        help_text="The value representing a HTTP header/value combination "
        "that signifies a request is secure.",
        default="https",
    )
)
config_group.register_child_config(
    fields.DictConfig(
        "databases",
        help_text="Django databases config.",
        default={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"}
        },
        is_json=True,
        unsafe_default=True,
    )
)
config_group.register_child_config(
    fields.DictConfig(
        "logging",
        help_text="A full override of the Django logging config for more customised logging.",
        is_json=True,
    )
)
config_group.register_child_config(
    fields.StrConfig(
        "log_file",
        help_text="The name and location of the Adjutant log file, "
        "superceded by 'adjutant.django.logging'.",
        default="adjutant.log",
    )
)

_email_group = groups.ConfigGroup("email")
_email_group.register_child_config(
    fields.StrConfig(
        "email_backend",
        help_text="Django email backend to use.",
        default="django.core.mail.backends.console.EmailBackend",
        required=True,
    )
)
_email_group.register_child_config(
    fields.IntConfig("timeout", help_text="Email backend timeout.")
)
_email_group.register_child_config(
    fields.HostNameConfig("host", help_text="Email backend server location.")
)
_email_group.register_child_config(
    fields.PortConfig("port", help_text="Email backend server port.")
)
_email_group.register_child_config(
    fields.StrConfig("host_user", help_text="Email backend user.")
)
_email_group.register_child_config(
    fields.StrConfig("host_password", help_text="Email backend user password.")
)
_email_group.register_child_config(
    fields.BoolConfig(
        "use_tls",
        help_text="Whether to use TLS for email. Mutually exclusive with 'use_ssl'.",
        default=False,
    )
)
_email_group.register_child_config(
    fields.BoolConfig(
        "use_ssl",
        help_text="Whether to use SSL for email. Mutually exclusive with 'use_tls'.",
        default=False,
    )
)

config_group.register_child_config(_email_group)
