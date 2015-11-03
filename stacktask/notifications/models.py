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


class NotificationEngine(object):
    """"""

    def __init__(self, conf):
        self.conf = conf

    def notify(self, task, notes, error):
        return self._notify(task, notes, error)

    def _notify(self, task, notes, error):
        raise NotImplementedError


class EmailNotification(NotificationEngine):
    """
    Basic email notification engine. Will
    send an email in the given templates.

    Example conf:
        <TaskView>:
            notifications:
                EmailNotification:
                    emails:
                        - example@example.com
                    reply: no-reply@example.com
                    template: notification.txt
                    html_template: completed.txt
                <other notification>:
                    ...
    """

    def notify(self, task, notes, error):
        return self._notify(task, notes, error)

    def _notify(self, task, notes, error):
        template = loader.get_template(self.conf['template'])
        html_template = loader.get_template(self.conf['html_template'])

        context = {'task': task, 'notes': notes}

        # NOTE(adriant): Error handling?
        message = template.render(context)
        html_message = html_template.render(context)
        if error:
            subject = "Error - %s notification" % task.task_type
        else:
            subject = "%s notification" % task.task_type
        send_mail(
            subject, message, self.conf['reply'],
            self.conf['emails'], fail_silently=False,
            html_message=html_message)


notification_engines = {
    'EmailNotification': EmailNotification,
}

settings.NOTIFICATION_ENGINES.update(notification_engines)
