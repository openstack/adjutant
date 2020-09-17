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

from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils import timezone

from confspirator import groups
from confspirator import fields
from confspirator import types

from adjutant.config import CONF
from adjutant.common import constants
from adjutant.api.models import Notification
from adjutant.notifications.v1 import base


class EmailNotification(base.BaseNotificationHandler):
    """
    Basic email notification handler. Will
    send an email with the given templates.
    """

    config_group = groups.DynamicNameConfigGroup(
        children=[
            fields.ListConfig(
                "emails",
                help_text="List of email addresses to send this notification to.",
                item_type=types.String(regex=constants.EMAIL_REGEX),
                default=[],
            ),
            fields.StrConfig(
                "from",
                help_text="From email for this notification.",
                regex=constants.EMAIL_WITH_TEMPLATE_REGEX,
                sample_default="bounce+%(task_uuid)s@example.com",
            ),
            fields.StrConfig(
                "reply",
                help_text="Reply-to email for this notification.",
                regex=constants.EMAIL_REGEX,
                sample_default="no-reply@example.com",
            ),
            fields.StrConfig(
                "template",
                help_text="Email template for this notification. "
                "No template will cause the email not to send.",
                default="notification.txt",
            ),
            fields.StrConfig(
                "html_template",
                help_text="Email html template for this notification.",
            ),
        ]
    )

    def _notify(self, task, notification):
        conf = self.config(task, notification)
        if not conf or not conf["emails"]:
            # Log that we did this!!
            note = (
                "Skipped sending notification for task: %s (%s) "
                "as notification handler conf is None, or no emails "
                "were configured." % (task.task_type, task.uuid)
            )
            self.logger.info("(%s) - %s" % (timezone.now(), note))
            return

        template = loader.get_template(conf["template"], using="include_etc_templates")
        html_template = conf["html_template"]
        if html_template:
            html_template = loader.get_template(
                html_template, using="include_etc_templates"
            )

        context = {"task": task, "notification": notification}

        if CONF.workflow.horizon_url:
            task_url = CONF.workflow.horizon_url
            notification_url = CONF.workflow.horizon_url
            if not task_url.endswith("/"):
                task_url += "/"
            if not notification_url.endswith("/"):
                notification_url += "/"
            task_url += "management/tasks/%s" % task.uuid
            notification_url += "management/notifications/%s" % notification.uuid
            context["task_url"] = task_url
            context["notification_url"] = notification_url

        if notification.error:
            subject = "Error - %s notification" % task.task_type
        else:
            subject = "%s notification" % task.task_type
        try:
            message = template.render(context)

            # from_email is the return-path and is distinct from the
            # message headers
            from_email = conf["from"]
            if not from_email:
                from_email = conf["reply"]
            elif "%(task_uuid)s" in from_email:
                from_email = from_email % {"task_uuid": task.uuid}

            # these are the message headers which will be visible to
            # the email client.
            headers = {
                "X-Adjutant-Task-UUID": task.uuid,
                # From needs to be set to be disctinct from return-path
                "From": conf["reply"],
                "Reply-To": conf["reply"],
            }

            email = EmailMultiAlternatives(
                subject, message, from_email, conf["emails"], headers=headers
            )

            if html_template:
                email.attach_alternative(html_template.render(context), "text/html")

            email.send(fail_silently=False)
            notification.acknowledged = True
            notification.save()
        except SMTPException as e:
            notes = {"errors": [("Error: '%s' while sending email notification") % e]}
            error_notification = Notification.objects.create(
                task=notification.task, notes=notes, error=True
            )
            error_notification.save()
