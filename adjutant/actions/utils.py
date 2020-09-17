import six

from django.core.mail import EmailMultiAlternatives
from django.template import loader

from adjutant.notifications.utils import create_notification


def validate_steps(validation_steps):
    """Helper function for validation in actions

    Takes a list of validation functions or validation function results.
    If function, will call it first, otherwise checks if valid. Will break
    and return False on first validation failure, or return True if all valid.

    It is best to pass in the functions and let this call them so that it
    doesn't keep validating after the first invalid result.
    """
    for step in validation_steps:
        if callable(step):
            if not step():
                return False
        if not step:
            return False
    return True


def send_email(to_addresses, context, conf, task):
    """
    Function for sending emails from actions
    """

    if not conf.get("template"):
        return

    if not to_addresses:
        return
    if isinstance(to_addresses, six.string_types):
        to_addresses = [to_addresses]
    elif isinstance(to_addresses, set):
        to_addresses = list(to_addresses)

    text_template = loader.get_template(conf["template"], using="include_etc_templates")

    html_template = conf.get("html_template")
    if html_template:
        html_template = loader.get_template(
            html_template, using="include_etc_templates"
        )

    try:
        message = text_template.render(context)
        # from_email is the return-path and is distinct from the
        # message headers
        from_email = conf.get("from")
        if not from_email:
            from_email = conf.get("reply")
            if not from_email:
                return
        elif "%(task_uuid)s" in from_email:
            from_email = from_email % {"task_uuid": task.uuid}

        reply_email = conf["reply"]
        # these are the message headers which will be visible to
        # the email client.
        headers = {
            "X-Adjutant-Task-UUID": task.uuid,
            # From needs to be set to be distinct from return-path
            "From": reply_email,
            "Reply-To": reply_email,
        }

        email = EmailMultiAlternatives(
            conf["subject"],
            message,
            from_email,
            to_addresses,
            headers=headers,
        )

        if html_template:
            email.attach_alternative(html_template.render(context), "text/html")

        email.send(fail_silently=False)
        return True

    except Exception as e:
        notes = {
            "errors": (
                "Error: '%s' while sending additional email for task: %s"
                % (e, task.uuid)
            )
        }

        notif_conf = task.config.notifications

        if e.__class__.__name__ in notif_conf.safe_errors:
            notification = create_notification(task, notes, error=True, handlers=False)
            notification.acknowledged = True
            notification.save()
        else:
            create_notification(task, notes, error=True)

        return False
