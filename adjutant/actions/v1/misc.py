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

from django.conf import settings

from adjutant.actions.v1.base import BaseAction
from adjutant.actions import user_store
from adjutant.actions.utils import send_email


class SendAdditionalEmailAction(BaseAction):

    def set_email(self, conf):
        self.emails = set()
        if conf.get('email_current_user'):
            self.add_note("Adding the current user's email address")
            if settings.USERNAME_IS_EMAIL:
                self.emails.add(self.action.task.keystone_user['username'])
            else:
                try:
                    self.emails.add(self.action.task.keystone_user['email'])
                except KeyError:
                    self.add_note("Could not add current user email address")

        if conf.get('email_roles'):
            roles = set(conf.get('email_roles'))
            project_id = self.action.task.keystone_user['project_id']
            self.add_note('Adding email addresses for roles %s in project %s'
                          % (roles, project_id))

            id_manager = user_store.IdentityManager()
            users = id_manager.list_users(project_id)
            for user in users:
                user_roles = [role.name for role in user.roles]
                if roles.intersection(user_roles):
                    if settings.USERNAME_IS_EMAIL:
                        self.emails.add(user.name)
                    else:
                        self.emails.add(user.email)

        if conf.get('email_task_cache'):
            task_emails = self.task.cache.get('additional_emails', [])
            if isinstance(task_emails, six.string_types):
                task_emails = [task_emails]
            for email in task_emails:
                self.emails.add(email)

        for email in conf.get('email_additional_addresses', []):
            self.emails.add(email)

    def _validate(self):
        self.action.valid = True
        self.action.save()

    def _pre_approve(self):
        self.perform_action('initial')

    def _post_approve(self):
        self.perform_action('token')

    def _submit(self, data):
        self.perform_action('completed')

    def perform_action(self, stage):
        self._validate()

        task = self.action.task
        for action in task.actions:
            if not action.valid:
                return

        email_conf = self.settings.get(stage, {})

        # If either of these are false we won't be sending anything.
        if not email_conf or not email_conf.get('template'):
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

        context = {
            'task': task,
            'actions': actions
        }

        result = send_email(self.emails, context, email_conf, task)

        if not result:
            self.add_note("Unable to send additional email. Stage: %s" % stage)
        else:
            self.add_note("Additional email sent. Stage: %s" % stage)
