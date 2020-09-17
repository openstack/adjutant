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

from smtplib import SMTPException
from unittest import mock

from confspirator.tests import utils as conf_utils
from django.core import mail

from adjutant.actions.v1.misc import SendAdditionalEmailAction
from adjutant.actions.utils import send_email
from adjutant.api.models import Task
from adjutant.common.tests.fake_clients import FakeManager
from adjutant.common.tests.utils import AdjutantTestCase
from adjutant.config import CONF

default_email_conf = {
    "from": "adjutant@example.com",
    "reply": "adjutant@example.com",
    "template": "initial.txt",
    "html_template": "completed.txt",
    "subject": "additional email",
}


class FailEmail(mock.MagicMock):
    def send(self, *args, **kwargs):
        raise SMTPException


@mock.patch("adjutant.common.user_store.IdentityManager", FakeManager)
class MiscActionTests(AdjutantTestCase):
    def test_send_email(self):
        # include html template
        to_address = "test@example.com"

        task = Task.objects.create(keystone_user={})

        context = {"task": task, "actions": ["action_1", "action_2"]}

        result = send_email(to_address, context, default_email_conf, task)

        # check the email itself
        self.assertNotEqual(result, None)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue("action_1" in mail.outbox[0].body)

    def test_send_email_no_addresses(self):
        to_address = []

        task = Task.objects.create(keystone_user={})

        context = {"task": task, "actions": ["action_1", "action_2"]}

        result = send_email(to_address, context, default_email_conf, task)
        self.assertEqual(result, None)
        self.assertEqual(len(mail.outbox), 0)

    @mock.patch("adjutant.actions.utils.EmailMultiAlternatives", FailEmail)
    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.action_defaults.SendAdditionalEmailAction.approve": [
                {
                    "operation": "overlay",
                    "value": {
                        "email_task_cache": True,
                        "subject": "Email Subject",
                        "template": "token.txt",
                    },
                },
            ],
        },
    )
    def test_send_additional_email_fail(self):
        """
        Tests that a failure to send an additional email doesn't cause
        it to become invalid or break.
        """

        task = Task.objects.create(
            keystone_user={},
            task_type="edit_roles",
        )

        action = SendAdditionalEmailAction({}, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        task.cache["additional_emails"] = ["thisguy@righthere.com", "nope@example.com"]

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            "Unable to send additional email. Stage: approve"
            in action.action.task.action_notes["SendAdditionalEmailAction"][1]
        )

        action.submit({})
        self.assertEqual(action.valid, True)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.action_defaults.SendAdditionalEmailAction.approve": [
                {
                    "operation": "overlay",
                    "value": {
                        "email_task_cache": True,
                        "subject": "Email Subject",
                        "template": "token.txt",
                    },
                },
            ],
        },
    )
    def test_send_additional_email_task_cache(self):
        """
        Tests sending an additional email with the address placed in the
        task cache.
        """

        task = Task.objects.create(keystone_user={})

        action = SendAdditionalEmailAction({}, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        task.cache["additional_emails"] = ["thisguy@righthere.com", "nope@example.com"]

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            set(mail.outbox[0].to), set(["thisguy@righthere.com", "nope@example.com"])
        )

        action.submit({})
        self.assertEqual(action.valid, True)
        self.assertEqual(len(mail.outbox), 1)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.action_defaults.SendAdditionalEmailAction.approve": [
                {
                    "operation": "overlay",
                    "value": {
                        "email_task_cache": True,
                        "subject": "Email Subject",
                        "template": "token.txt",
                    },
                },
            ],
        },
    )
    def test_send_additional_email_task_cache_none_set(self):
        """
        Tests sending an additional email with 'email_task_cache' set but
        no address placed in the task cache.
        """

        task = Task.objects.create(keystone_user={})

        action = SendAdditionalEmailAction({}, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(len(mail.outbox), 0)

        action.submit({})
        self.assertEqual(action.valid, True)

    @conf_utils.modify_conf(
        CONF,
        operations={
            "adjutant.workflow.action_defaults.SendAdditionalEmailAction.approve": [
                {
                    "operation": "overlay",
                    "value": {
                        "email_additional_addresses": ["anadminwhocares@example.com"],
                        "subject": "Email Subject",
                        "template": "token.txt",
                    },
                },
            ],
        },
    )
    def test_send_additional_email_email_in_config(self):
        """
        Tests sending an additional email with the address placed in the
        task cache.
        """

        task = Task.objects.create(keystone_user={})

        action = SendAdditionalEmailAction({}, task=task, order=1)

        action.prepare()
        self.assertEqual(action.valid, True)

        action.approve()
        self.assertEqual(action.valid, True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["anadminwhocares@example.com"])

        action.submit({})
        self.assertEqual(action.valid, True)
        self.assertEqual(len(mail.outbox), 1)
