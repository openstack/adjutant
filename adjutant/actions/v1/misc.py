# Copyright (C) 2016 Catalyst IT Ltd
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

import six

from confspirator import groups
from confspirator import fields
from confspirator import types

from adjutant.actions.v1.base import BaseAction
from adjutant.actions.v1 import serializers
from adjutant.actions.utils import send_email
from adjutant.common import user_store
from adjutant.common import constants
from adjutant.config import CONF


def _build_default_email_group(group_name):
    email_group = groups.ConfigGroup(group_name)
    email_group.register_child_config(
        fields.StrConfig(
            "subject",
            help_text="Email subject for this stage.",
            default="Openstack Email Notification",
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "from",
            help_text="From email for this stage.",
            regex=constants.EMAIL_WITH_TEMPLATE_REGEX,
            default="bounce+%(task_uuid)s@example.com",
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "reply",
            help_text="Reply-to email for this stage.",
            regex=constants.EMAIL_WITH_TEMPLATE_REGEX,
            default="no-reply@example.com",
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "template",
            help_text="Email template for this stage. "
            "No template will cause the email not to send.",
            default=None,
        )
    )
    email_group.register_child_config(
        fields.StrConfig(
            "html_template",
            help_text="Email html template for this stage. "
            "No template will cause the email not to send.",
            default=None,
        )
    )
    email_group.register_child_config(
        fields.BoolConfig(
            "email_current_user",
            help_text="Email the user who started the task.",
            default=False,
        )
    )
    email_group.register_child_config(
        fields.BoolConfig(
            "email_task_cache",
            help_text="Send to an email set in the task cache.",
            default=False,
        )
    )
    email_group.register_child_config(
        fields.ListConfig(
            "email_roles",
            help_text="Send emails to the given roles on the project.",
            default=[],
        )
    )
    email_group.register_child_config(
        fields.ListConfig(
            "email_additional_addresses",
            help_text="Send emails to an arbitrary admin emails",
            item_type=types.String(regex=constants.EMAIL_WITH_TEMPLATE_REGEX),
            default=[],
        )
    )
    return email_group


class SendAdditionalEmailAction(BaseAction):

    serializer = serializers.SendAdditionalEmailSerializer

    config_group = groups.DynamicNameConfigGroup(
        children=[
            _build_default_email_group("prepare"),
            _build_default_email_group("approve"),
            _build_default_email_group("submit"),
        ],
    )

    def set_email(self, conf):
        self.emails = set()
        if conf.get("email_current_user"):
            self.add_note("Adding the current user's email address")
            if CONF.identity.username_is_email:
                self.emails.add(self.action.task.keystone_user["username"])
            else:
                try:
                    id_manager = user_store.IdentityManager()
                    email = id_manager.get_user(
                        self.action.task.keystone_user["user_id"]
                    ).email
                    self.emails.add(email)
                except AttributeError:
                    self.add_note("Could not add current user email address")

        if conf.get("email_roles"):
            roles = set(conf.get("email_roles"))
            project_id = self.action.task.keystone_user["project_id"]
            self.add_note(
                "Adding email addresses for roles %s in project %s"
                % (roles, project_id)
            )

            id_manager = user_store.IdentityManager()
            users = id_manager.list_users(project_id)
            for user in users:
                user_roles = [role.name for role in user.roles]
                if roles.intersection(user_roles):
                    if CONF.identity.username_is_email:
                        self.emails.add(user.name)
                    else:
                        self.emails.add(user.email)

        if conf.get("email_task_cache"):
            task_emails = self.action.task.cache.get("additional_emails", [])
            if isinstance(task_emails, six.string_types):
                task_emails = [task_emails]
            for email in task_emails:
                self.emails.add(email)

        for email in conf.get("email_additional_addresses"):
            self.emails.add(email)

    def _validate(self):
        self.action.valid = True
        self.action.save()

    def _prepare(self):
        self.perform_action("prepare")

    def _approve(self):
        self.perform_action("approve")

    def _submit(self, token_data, keystone_user=None):
        self.perform_action("submit")

    def perform_action(self, stage):
        self._validate()

        task = self.action.task
        for action in task.actions:
            if not action.valid:
                return

        email_conf = self.config.get(stage)

        # If either of these are false we won't be sending anything.
        if not email_conf or not email_conf.get("template"):
            return

        self.set_email(email_conf)

        if not self.emails:
            self.add_note(self.emails)
            self.add_note("Email address not set. Stage: %s" % stage)
            return

        self.add_note("Sending emails to: %s" % self.emails)

        actions = {}
        for action in task.actions:
            act = action.get_action()
            actions[str(act)] = act

        context = {"task": task, "actions": actions}

        result = send_email(self.emails, context, email_conf, task)

        if not result:
            self.add_note("Unable to send additional email. Stage: %s" % stage)
        else:
            self.add_note("Additional email sent. Stage: %s" % stage)
