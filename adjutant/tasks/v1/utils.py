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

from logging import getLogger

from datetime import timedelta
from smtplib import SMTPException
from uuid import uuid4

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils import timezone

from adjutant import exceptions
from adjutant.api.models import Token
from adjutant.api.v1.utils import create_notification


LOG = getLogger('adjutant')


def handle_task_error(e, task, error_text="while running task"):
    import traceback
    trace = traceback.format_exc()
    LOG.critical((
        "(%s) - Exception escaped! %s\nTrace: \n%s") % (
            timezone.now(), e, trace))

    notes = ["Error: %s(%s) %s. See task itself for details."
             % (type(e).__name__, e, error_text)]

    raise exceptions.TaskActionsFailed(task, internal_message=notes)


def create_token(task):
    expire = timezone.now() + timedelta(hours=settings.TOKEN_EXPIRE_TIME)

    uuid = uuid4().hex
    token = Token.objects.create(
        task=task,
        token=uuid,
        expires=expire
    )
    token.save()
    return token


def send_stage_email(task, email_conf, token=None):
    if not email_conf:
        return

    text_template = loader.get_template(
        email_conf['template'],
        using='include_etc_templates')
    html_template = email_conf.get('html_template', None)
    if html_template:
        html_template = loader.get_template(
            html_template,
            using='include_etc_templates')

    emails = set()
    actions = {}
    # find our set of emails and actions that require email
    for action in task.actions:
        act = action.get_action()
        email = act.get_email()
        if email:
            emails.add(email)
            actions[str(act)] = act

    if not emails:
        return

    if len(emails) > 1:
        notes = {
            'errors':
            ("Error: Unable to send update, more than one email for task: %s"
             % task.uuid)
        }
        create_notification(task, notes, error=True)
        return

    context = {
        'task': task,
        'actions': actions
    }
    if token:
        if settings.HORIZON_URL:
            tokenurl = settings.HORIZON_URL
            if not tokenurl.endswith('/'):
                tokenurl += '/'
            tokenurl += 'token/'
        else:
            tokenurl = settings.TOKEN_SUBMISSION_URL
            if not tokenurl.endswith('/'):
                tokenurl += '/'
        context.update({
            'tokenurl': tokenurl,
            'token': token.token
        })

    try:
        message = text_template.render(context)

        # from_email is the return-path and is distinct from the
        # message headers
        from_email = email_conf.get('from')
        if not from_email:
            from_email = email_conf['reply']
        elif "%(task_uuid)s" in from_email:
            from_email = from_email % {'task_uuid': task.uuid}

        # these are the message headers which will be visible to
        # the email client.
        headers = {
            'X-Adjutant-Task-UUID': task.uuid,
            # From needs to be set to be disctinct from return-path
            'From': email_conf['reply'],
            'Reply-To': email_conf['reply'],
        }

        email = EmailMultiAlternatives(
            email_conf['subject'],
            message,
            from_email,
            [emails.pop()],
            headers=headers,
        )

        if html_template:
            email.attach_alternative(
                html_template.render(context), "text/html")

        email.send(fail_silently=False)

    except SMTPException as e:
        notes = {
            'errors':
                ("Error: '%s' while emailing update for task: %s" %
                    (e, task.uuid))
        }

        errors_conf = settings.TASK_SETTINGS.get(
            task.task_type, settings.DEFAULT_TASK_SETTINGS).get(
                'errors', {}).get("SMTPException", {})

        if errors_conf:
            notification = create_notification(
                task, notes, error=True,
                engines=errors_conf.get('engines', True))

            if errors_conf.get('notification') == "acknowledge":
                notification.acknowledged = True
                notification.save()
        else:
            create_notification(task, notes, error=True)
