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

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from smtplib import SMTPException
from adjutant.api.models import Notification


class NotificationEngine(object):
    """"""

    def __init__(self, conf):
        self.conf = conf

    def notify(self, task, notification):
        return self._notify(task, notification)

    def _notify(self, task, notification):
        raise NotImplementedError


class EmailNotification(NotificationEngine):
    """
    Basic email notification engine. Will
    send an email with the given templates.

    Example conf:
        <TaskView>:
            notifications:
                EmailNotification:
                    standard:
                        emails:
                            - example@example.com
                        reply: no-reply@example.com
                        template: notification.txt
                        html_template: completed.txt
                    error:
                        emails:
                            - errors@example.com
                        reply: no-reply@example.com
                        template: notification.txt
                        html_template: completed.txt
                <other notification engine>:
                    ...
    """

    def _notify(self, task, notification):
        template = loader.get_template(
            self.conf['template'],
            using='include_etc_templates')
        html_template = self.conf.get('html_template', None)
        if html_template:
            html_template = loader.get_template(
                html_template,
                using='include_etc_templates')

        context = {
            'task': task, 'notification': notification}

        if notification.error:
            subject = "Error - %s notification" % task.task_type
        else:
            subject = "%s notification" % task.task_type
        try:
            message = template.render(context)

            # from_email is the return-path and is distinct from the
            # message headers
            from_email = self.conf.get('from')
            if not from_email:
                from_email = self.conf['reply']
            elif "%(task_uuid)s" in from_email:
                from_email = from_email % {'task_uuid': task.uuid}

            # these are the message headers which will be visible to
            # the email client.
            headers = {
                'X-Adjutant-Task-UUID': task.uuid,
                # From needs to be set to be disctinct from return-path
                'From': self.conf['reply'],
                'Reply-To': self.conf['reply'],
            }

            email = EmailMultiAlternatives(
                subject,
                message,
                from_email,
                self.conf['emails'],
                headers=headers,
            )

            if html_template:
                email.attach_alternative(
                    html_template.render(context), "text/html")

            email.send(fail_silently=False)
            if not notification.error:
                notification.acknowledge = True
                notification.save()
        except SMTPException as e:
            notes = {
                'errors':
                    [("Error: '%s' while sending email notification") % e]
            }
            error_notification = Notification.objects.create(
                task=notification.task,
                notes=notes,
                error=True
            )
            error_notification.save()


notification_engines = {
    'EmailNotification': EmailNotification,
}

settings.NOTIFICATION_ENGINES.update(notification_engines)
