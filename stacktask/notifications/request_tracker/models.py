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
from stacktask.notifications.models import NotificationEngine
import rt


class RTNotification(NotificationEngine):
    """
    Request Tracker notification engine. Will
    create a new ticket in RT for the notification.

    Example conf:
        <TaskView>:
            notifications:
                RTNotification:
                    url: http://localhost/rt/REST/1.0/
                    queue: helpdesk
                    username: example@example.com
                    password: password
                    template: notification.txt
                <other notification>:
                    ...
    """

    def __init__(self, conf):
        super(RTNotification, self).__init__(conf)
        # in memory dict to be used for passing data between actions:
        tracker = rt.Rt(
            self.conf['url'], self.conf['username'], self.conf['password'])
        tracker.login()
        self.tracker = tracker

    def notify(self, task, notes, error):
        return self._notify(task, notes, error)

    def _notify(self, task, notes, error):
        template = loader.get_template(self.conf['template'])

        context = {'task': task, 'notes': notes}

        # NOTE(adriant): Error handling?
        message = template.render(context)

        if error:
            subject = "Error - %s notification" % task.task_type
        else:
            subject = "%s notification" % task.task_type

        self.tracker.create_ticket(
            Queue=self.conf['queue'], Subject=subject,
            # newline + space tells the RT api to actually treat it like a
            # newline.
            Text=message.replace('\n', '\n '))


notification_engines = {
    'RTNotification': RTNotification,
}

settings.NOTIFICATION_ENGINES.update(notification_engines)
