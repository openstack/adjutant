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
from uuid import uuid4

from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils import timezone

from adjutant.api.models import Token
from adjutant.common import user_store
from adjutant.notifications.utils import create_notification
from adjutant.config import CONF
from adjutant import exceptions


LOG = getLogger("adjutant")


def handle_task_error(e, task, error_text="while running task"):
    import traceback

    trace = traceback.format_exc()
    LOG.critical(
        ("(%s) - Exception escaped! %s\nTrace: \n%s") % (timezone.now(), e, trace)
    )

    notes = [
        "Error: %s(%s) %s. See task itself for details."
        % (type(e).__name__, e, error_text)
    ]

    raise exceptions.TaskActionsFailed(task, internal_message=notes)


def create_token(task, expiry_time=None):
    if not expiry_time:
        expiry_time = CONF.workflow.default_token_expiry
    expire = timezone.now() + timedelta(seconds=expiry_time)

    uuid = uuid4().hex
    token = Token.objects.create(task=task, token=uuid, expires=expire)
    token.save()
    return token


def send_stage_email(task, email_conf, token=None):
    """Send one or more stage emails for a task using the given configuration.

    This also accepts ``None`` for ``email_conf``, in which case
    no emails are sent.

    :param task: Task to send the stage email for
    :type task: Task
    :param email_conf: Stage email configuration (if configured)
    :type email_conf: confspirator.groups.GroupNamespace | None
    :param token: Token to add to the email template, defaults to None
    :type token: str | None, optional
    """

    if not email_conf:
        return

    # Send one or more emails according to per-email configurations
    # if provided. If not, send a single email using the stage-global
    # email configuration values.
    emails = email_conf["emails"] or [{}]

    # For each per-email configuration, send a stage email using
    # that configuration.
    # We want to use the per-email configuration values if provided,
    # but fall back to the stage-global email configuration value
    # for any that are not.
    for conf in emails:
        _send_stage_email(
            task=task,
            token=token,
            subject=conf.get("subject", email_conf["subject"]),
            template=conf.get("template", email_conf["template"]),
            html_template=conf.get(
                "html_template",
                email_conf["html_template"],
            ),
            email_from=conf.get("from", email_conf["from"]),
            email_to=conf.get("to", email_conf["to"]),
            email_reply=conf.get("reply", email_conf["reply"]),
            email_current_user=conf.get(
                "email_current_user",
                email_conf["email_current_user"],
            ),
        )


def _send_stage_email(
    task,
    token,
    subject,
    template,
    html_template,
    email_from,
    email_to,
    email_reply,
    email_current_user,
):
    text_template = loader.get_template(template, using="include_etc_templates")
    if html_template:
        html_template = loader.get_template(
            html_template, using="include_etc_templates"
        )

    # find our set of emails and actions that require email
    emails = set()
    actions = {}

    # Fetch all possible email addresses that can be configured.
    # Even if these are not actually used as the target email,
    # they are made available in the email templates to be referenced.
    if CONF.identity.username_is_email and "username" in task.keystone_user:
        email_current_user_address = task.keystone_user["username"]
    elif "user_id" in task.keystone_user:
        id_manager = user_store.IdentityManager()
        user = id_manager.get_user(task.keystone_user["user_id"])
        email_current_user_address = user.email if user else None
    else:
        email_current_user_address = None
    email_action_addresses = {}
    for action in task.actions:
        act = action.get_action()
        email = act.get_email()
        if email:
            action_name = str(act)
            email_action_addresses[action_name] = email
            actions[action_name] = act

    if email_to:
        emails.add(email_to)
    elif email_current_user:
        if not email_current_user_address:
            notes = {
                "errors": (
                    "Error: Unable to send update, "
                    "task email is configured to send to current user "
                    f"but no username or user ID found in task: {task.uuid}"
                ),
            }
            create_notification(task, notes, error=True)
            return
        emails.add(email_current_user_address)
    else:
        emails |= set(email_action_addresses.values())

    if not emails:
        return

    if len(emails) > 1:
        notes = {
            "errors": (
                "Error: Unable to send update, more than one email for task: %s"
                % task.uuid
            )
        }
        create_notification(task, notes, error=True)
        return

    # from_email is the return-path and is distinct from the
    # message headers
    from_email = email_from % {"task_uuid": task.uuid} if email_from else email_reply
    email_address = emails.pop()

    context = {
        "task": task,
        "actions": actions,
        "from_address": from_email,
        "reply_address": email_reply,
        "email_address": email_address,
        "email_current_user_address": email_current_user_address,
        "email_action_addresses": email_action_addresses,
    }
    if token:
        tokenurl = CONF.workflow.horizon_url
        if not tokenurl.endswith("/"):
            tokenurl += "/"
        tokenurl += "token/"
        context.update({"tokenurl": tokenurl, "token": token.token})

    try:
        message = text_template.render(context)

        # these are the message headers which will be visible to
        # the email client.
        headers = {
            "X-Adjutant-Task-UUID": task.uuid,
            # From needs to be set to be disctinct from return-path
            "From": email_reply,
            "Reply-To": email_reply,
        }

        email = EmailMultiAlternatives(
            subject,
            message,
            from_email,
            [email_address],
            headers=headers,
        )

        if html_template:
            email.attach_alternative(html_template.render(context), "text/html")

        email.send(fail_silently=False)

    except Exception as e:
        notes = {
            "errors": (
                "Error: '%s' while emailing update for task: %s" % (e, task.uuid)
            )
        }

        notif_conf = task.config.notifications

        if e.__class__.__name__ in notif_conf.safe_errors:
            notification = create_notification(task, notes, error=True, handlers=False)
            notification.acknowledged = True
            notification.save()
        else:
            create_notification(task, notes, error=True)
