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
from django.core.mail import send_mail
from django.template import loader
from smtplib import SMTPException
from stacktask.api.models import Notification


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
                standard:
                    EmailNotification:
                        emails:
                            - example@example.com
                        reply: no-reply@example.com
                        template: notification.txt
                        html_template: completed.txt
                error:
                    EmailNotification:
                        emails:
                            - errors@example.com
                        reply: no-reply@example.com
                        template: notification.txt
                        html_template: completed.txt
                <other notification>:
                    ...
    """

    def _notify(self, task, notification):
        template = loader.get_template(self.conf['template'])
        html_template = loader.get_template(self.conf['html_template'])

        context = {
            'task': task, 'notification': notification}

        # NOTE(adriant): Error handling?
        message = template.render(context)
        html_message = html_template.render(context)
        if notification.error:
            subject = "Error - %s notification" % task.task_type
        else:
            subject = "%s notification" % task.task_type
        try:
            send_mail(
                subject, message, self.conf['reply'],
                self.conf['emails'], fail_silently=False,
                html_message=html_message)
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
