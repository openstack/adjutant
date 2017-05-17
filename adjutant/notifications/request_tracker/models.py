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
from django.template import loader
from adjutant.notifications.models import NotificationEngine
from adjutant.api.models import Notification
from rtkit.resource import RTResource
from rtkit.authenticators import CookieAuthenticator
from rtkit.errors import RTResourceError


class RTNotification(NotificationEngine):
    """
    Request Tracker notification engine. Will
    create a new ticket in RT for the notification.

    Example conf:
        <TaskView>:
            notifications:
                standard:
                    RTNotification:
                        url: http://localhost/rt/REST/1.0/
                        queue: helpdesk
                        username: example@example.com
                        password: password
                        template: notification.txt
                error:
                    RTNotification:
                        url: http://localhost/rt/REST/1.0/
                        queue: errors
                        username: example@example.com
                        password: password
                        template: notification.txt
                <other notification>:
                    ...
    """

    def __init__(self, conf):
        super(RTNotification, self).__init__(conf)
        tracker = RTResource(
            self.conf['url'], self.conf['username'], self.conf['password'],
            CookieAuthenticator)
        self.tracker = tracker

    def _notify(self, task, notification):
        template = loader.get_template(self.conf['template'])

        context = {'task': task, 'notification': notification}

        message = template.render(context)

        if notification.error:
            subject = "Error - %s notification" % task.task_type
        else:
            subject = "%s notification" % task.task_type

        content = {
            'content': {
                'Queue': self.conf['queue'],
                'Subject': subject,
                'Text': message,
            }
        }

        try:
            self.tracker.post(path='ticket/new', payload=content)
            if not notification.error:
                notification.acknowledged = True
                notification.save()
        except RTResourceError as e:
            notes = {
                'errors':
                    [("Error: '%s' while sending notification to " +
                      "RT.") % e]
            }
            error_notification = Notification.objects.create(
                task=notification.task,
                notes=notes,
                error=True
            )
            error_notification.save()


notification_engines = {
    'RTNotification': RTNotification,
}

settings.NOTIFICATION_ENGINES.update(notification_engines)
