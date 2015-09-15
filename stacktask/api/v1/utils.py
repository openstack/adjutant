from stacktask.api.models import Token, Notification
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from django.core.mail import send_mail
from smtplib import SMTPException

from django.template import loader, Context


def create_token(task):
    # expire needs to be made configurable.
    expire = timezone.now() + timedelta(hours=24)

    # is this a good way to create tokens?
    uuid = uuid4().hex
    token = Token.objects.create(
        task=task,
        token=uuid,
        expires=expire
    )
    token.save()
    return token


def send_email(task, email_conf, token=None):
    if email_conf:
        template = loader.get_template(email_conf['template'])
        html_template = loader.get_template(email_conf['html_template'])

        emails = set()
        actions = []
        for action in task.actions:
            act = action.get_action()
            email = act.get_email()
            if email:
                emails.add(email)
                actions.append(unicode(act))

        if len(emails) > 1:
            notes = {
                'notes':
                    (("Error: Unable to send token, More than one email for" +
                     " task: %s") % task.uuid)
            }
            create_notification(task, notes)
            return
            # TODO(adriant): raise some error?
            # and surround calls to this function with try/except

        if token:
            context = {'task': task, 'actions': actions,
                       'token': token.token}
        else:
            context = {'task': task, 'actions': actions}

        try:
            message = template.render(Context(context))
            html_message = html_template.render(Context(context))
            send_mail(
                email_conf['subject'], message, email_conf['reply'],
                [emails.pop()], fail_silently=False, html_message=html_message)
        except SMTPException as e:
            notes = {
                'notes':
                    ("Error: '%s' while emailing token for task: %s" %
                     (e, task.uuid))
            }
            create_notification(task, notes)
            # TODO(adriant): raise some error?
            # and surround calls to this function with try/except


def create_notification(task, notes):
    notification = Notification.objects.create(
        task=task,
        notes=notes
    )
    notification.save()
