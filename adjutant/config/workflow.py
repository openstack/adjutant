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


config_group = groups.ConfigGroup("workflow")

config_group.register_child_config(
    fields.URIConfig(
        "horizon_url",
        help_text="The base Horizon url for Adjutant to use when producing links to Horizon.",
        schemes=["https", "http"],
        required=True,
        sample_default="http://localhost/",
        test_default="http://localhost/",
    )
)
config_group.register_child_config(
    fields.IntConfig(
        "default_token_expiry",
        help_text="The default token expiry time for Task tokens.",
        default=24 * 60 * 60,  # 24hrs in seconds
    )
)


def _build_default_email_group(
    group_name,
    email_subject,
    email_from,
    email_reply,
    email_template,
    email_html_template,
):
    email_group = groups.ConfigGroup(group_name)
    email_group.register_child_config(
        fields.StrConfig(
            "subject",
            help_text="Default email subject for this stage",
            default=email_subject,
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "from", help_text="Default from email for this stage", default=email_from
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "reply",
            help_text="Default reply-to email for this stage",
            default=email_reply,
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "template",
            help_text="Default email template for this stage",
            default=email_template,
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "html_template",
            help_text="Default email html template for this stage",
            default=email_html_template,
        )
    )
    return email_group


_task_defaults_group = groups.ConfigGroup("task_defaults")
config_group.register_child_config(_task_defaults_group)

_email_defaults_group = groups.ConfigGroup("emails")
_task_defaults_group.register_child_config(_email_defaults_group)
_email_defaults_group.register_child_config(
    _build_default_email_group(
        group_name="initial",
        email_subject="Task Confirmation",
        email_reply="no-reply@example.com",
        email_from="bounce+%(task_uuid)s@example.com",
        email_template="initial.txt",
        email_html_template=None,
    )
)
_email_defaults_group.register_child_config(
    _build_default_email_group(
        group_name="token",
        email_subject="Task Token",
        email_reply="no-reply@example.com",
        email_from="bounce+%(task_uuid)s@example.com",
        email_template="token.txt",
        email_html_template=None,
    )
)
_email_defaults_group.register_child_config(
    _build_default_email_group(
        group_name="completed",
        email_subject="Task Completed",
        email_reply="no-reply@example.com",
        email_from="bounce+%(task_uuid)s@example.com",
        email_template="completed.txt",
        email_html_template=None,
    )
)

_notifications_defaults_group = groups.ConfigGroup("notifications")
_task_defaults_group.register_child_config(_notifications_defaults_group)

_notifications_defaults_group.register_child_config(
    fields.ListConfig(
        "standard_handlers",
        help_text="Handlers to use for standard notifications.",
        required=True,
        default=[
            "EmailNotification",
        ],
    )
)
_notifications_defaults_group.register_child_config(
    fields.ListConfig(
        "error_handlers",
        help_text="Handlers to use for error notifications.",
        required=True,
        default=[
            "EmailNotification",
        ],
    )
)
_notifications_defaults_group.register_child_config(
    fields.DictConfig(
        "standard_handler_config",
        help_text="Settings for standard notification handlers.",
        default={},
        is_json=True,
    )
)
_notifications_defaults_group.register_child_config(
    fields.DictConfig(
        "error_handler_config",
        help_text="Settings for error notification handlers.",
        default={},
        is_json=True,
    )
)
_notifications_defaults_group.register_child_config(
    fields.ListConfig(
        "safe_errors",
        help_text="Error types which are safe to acknowledge automatically.",
        required=True,
        default=["SMTPException"],
    )
)

action_defaults_group = groups.ConfigGroup("action_defaults", lazy_load=True)
tasks_group = groups.ConfigGroup("tasks", lazy_load=True)

config_group.register_child_config(action_defaults_group)
config_group.register_child_config(tasks_group)
