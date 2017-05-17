import six
from smtplib import SMTPException

from adjutant.api.v1.utils import create_notification

from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.conf import settings


def send_email(to_addresses, context, conf, task):
    """
    Function for sending emails from actions
    """

    if not conf.get('template'):
        return

    if not to_addresses:
        return
    if isinstance(to_addresses, six.string_types):
        to_addresses = [to_addresses]
    elif isinstance(to_addresses, set):
        to_addresses = list(to_addresses)

    text_template = loader.get_template(
        conf['template'],
        using='include_etc_templates')

    html_template = conf.get('html_template', None)
    if html_template:
        html_template = loader.get_template(
            html_template,
            using='include_etc_templates')

    try:
        message = text_template.render(context)
        # from_email is the return-path and is distinct from the
        # message headers
        from_email = conf.get('from')
        if not from_email:
            from_email = conf['reply']
        elif "%(task_uuid)s" in from_email:
            from_email = from_email % {'task_uuid': task.uuid}

        reply_email = conf['reply']
        # these are the message headers which will be visible to
        # the email client.
        headers = {
            'X-Adjutant-Task-UUID': task.uuid,
            # From needs to be set to be distinct from return-path
            'From': reply_email,
            'Reply-To': reply_email,
        }

        email = EmailMultiAlternatives(
            conf['subject'],
            message,
            from_email,
            to_addresses,
            headers=headers,
        )

        if html_template:
            email.attach_alternative(
                html_template.render(context), "text/html")

        email.send(fail_silently=False)
        return True

    except SMTPException as e:
        notes = {
            'errors':
                ("Error: '%s' while sending additional email for task: %s"
                    % (e, task.uuid))
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

        return False
