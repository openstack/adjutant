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

from adjutant import notifications
from adjutant.api.models import Notification


def create_notification(task, notes, error=False, handlers=True):
    notification = Notification.objects.create(task=task, notes=notes, error=error)
    notification.save()

    if not handlers:
        return notification

    notif_conf = task.config.notifications

    if error:
        notif_handlers = notif_conf.error_handlers
    else:
        notif_handlers = notif_conf.standard_handlers

    if notif_handlers:
        for notif_handler in notif_handlers:
            handler = notifications.NOTIFICATION_HANDLERS[notif_handler]()
            handler.notify(task, notification)

    return notification
