from stacktask.api.models import Token, Notification
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4
from django.core.mail import send_mail
from smtplib import SMTPException
from django.conf import settings
from django.template import loader
import hashlib


def create_token(task):
    # expire needs to be made configurable.
    expire = timezone.now() + timedelta(hours=settings.TOKEN_EXPIRE_TIME)

    # is this a good way to create tokens?
    uuid = uuid4().hex
    token = Token.objects.create(
        task=task,
        token=uuid,
        expires=expire
    )
    token.save()
    return token


def send_email(registration, email_conf, token=None):
    if not email_conf:
        return

    template = loader.get_template(email_conf['template'])
    html_template = loader.get_template(email_conf['html_template'])

    emails = set()
    actions = []
    for action in registration.actions:
        act = action.get_action()
        email = act.get_email()
        if email:
            emails.add(email)
            actions.append(unicode(act))

    if len(emails) > 1:
        notes = {
            'notes':
            (("Error: Unable to send token, More than one email for" +
              " registration: %s") % registration.uuid)
        }
        create_notification(registration, notes)
        return
        # TODO(adriant): raise some error?
        # and surround calls to this function with try/except

    if token:
        context = {
            'registration': registration,
            'actions': actions,
            'tokenurl': settings.TOKEN_SUBMISSION_URL,
            'token': token.token,
        }
    else:
        context = {'registration': registration, 'actions': actions}

    try:
        message = template.render(context)
        html_message = html_template.render(context)
        send_mail(
            email_conf['subject'], message, email_conf['reply'],
            [emails.pop()], fail_silently=False, html_message=html_message)
    except SMTPException as e:
        notes = {
            'notes':
                ("Error: '%s' while emailing token for registration: %s" %
                 (e, registration.uuid))
        }
        create_notification(registration, notes, error=True)
        # TODO(adriant): raise some error?
        # and surround calls to this function with try/except


def create_notification(task, notes, error=False):
    notification = Notification.objects.create(
        task=task,
        notes=notes,
        error=error
    )
    notification.save()

    class_conf = settings.TASK_SETTINGS[task.task_type]

    # NOTE(adriant): some form of error handling is probably needed:
    for note_engine, conf in class_conf.get('notifications', {}).iteritems():
        engine = settings.NOTIFICATION_ENGINES[note_engine](conf)
        engine.notify(task, notes, error)


def create_task_hash(task_type, action_list):
    hashable_list = [task_type, ]

    for action in action_list:
        hashable_list.append(action['name'])
        # iterate like this to maintain consistent order for hash
        for field in action['action'].required:
            try:
                hashable_list.append(
                    action['serializer'].validated_data[field])
            except KeyError:
                if field is "username" and settings.USERNAME_IS_EMAIL:
                    continue
                else:
                    raise

    return hashlib.sha256(str(hashable_list)).hexdigest()
