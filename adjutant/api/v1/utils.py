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

import hashlib
import json
from datetime import timedelta
from smtplib import SMTPException
from uuid import uuid4

from decorator import decorator

from django.conf import settings
from django.core.exceptions import FieldError
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils import timezone

from rest_framework.response import Response

from adjutant.api.models import Notification, Token


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
            (("Error: Unable to send token, More than one email for" +
              " task: %s") % task.uuid)
        }
        create_notification(task, notes, error=True)
        return

    context = {
        'task': task,
        'actions': actions
    }
    if token:
        context.update({
            'tokenurl': settings.TOKEN_SUBMISSION_URL,
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
                ("Error: '%s' while emailing token for task: %s" %
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


def create_notification(task, notes, error=False, engines=True):
    notification = Notification.objects.create(
        task=task,
        notes=notes,
        error=error
    )
    notification.save()

    if not engines:
        return notification

    class_conf = settings.TASK_SETTINGS.get(
        task.task_type, settings.DEFAULT_TASK_SETTINGS)

    for note_engine, conf in class_conf.get('notifications', {}).iteritems():
        if error:
            conf = conf.get('error', {})
        else:
            conf = conf.get('standard', {})
        if not conf:
            continue
        engine = settings.NOTIFICATION_ENGINES[note_engine](conf)
        engine.notify(task, notification)

    return notification


def create_task_hash(task_type, action_list):
    hashable_list = [task_type, ]

    for action in action_list:
        hashable_list.append(action['name'])
        if not action['serializer']:
            continue
        # iterate like this to maintain consistent order for hash
        fields = sorted(action['serializer'].validated_data.keys())
        for field in fields:
            try:
                hashable_list.append(
                    action['serializer'].validated_data[field])
            except KeyError:
                if field is "username" and settings.USERNAME_IS_EMAIL:
                    continue
                else:
                    raise

    return hashlib.sha256(str(hashable_list)).hexdigest()


# "{'filters': {'fieldname': { 'operation': 'value'}}
@decorator
def parse_filters(func, *args, **kwargs):
    """
    Parses incoming filters paramters and converts them to
    Django usable operations if valid.

    BE AWARE! WILL NOT WORK UNLESS POSITIONAL ARGUMENT 3 IS FILTERS!
    """
    request = args[1]
    filters = request.query_params.get('filters', None)

    if not filters:
        return func(*args, **kwargs)
    cleaned_filters = {}
    try:
        filters = json.loads(filters)
        for field, operations in filters.iteritems():
            for operation, value in operations.iteritems():
                cleaned_filters['%s__%s' % (field, operation)] = value
    except (ValueError, AttributeError):
        return Response(
            {'errors': [
                ("Filters incorrectly formatted. Required format: " +
                 "{'filters': {'fieldname': { 'operation': 'value'}}")
            ]},
            status=400
        )

    try:
        # NOTE(adriant): This feels dirty and unclear, but it works.
        # Positional argument 3 is filters, so we just replace it.
        args = list(args)
        args[2] = cleaned_filters
        return func(*args, **kwargs)
    except FieldError as e:
            return Response({'errors': [str(e)]}, status=400)


def add_task_id_for_roles(request, processed, response_dict, req_roles):
    if request.keystone_user.get('authenticated', False):

        req_roles = set(req_roles)
        roles = set(request.keystone_user.get('roles', []))

        if roles & req_roles:
            response_dict['task'] = processed['task'].uuid
