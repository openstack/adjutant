Configuring Adjutant
====================================

.. highlight:: yaml

Adjutant is designed to be highly configurable for various needs. The goal
of Adjutant is to provide a variety of common tasks and actions that can
be easily extended or changed based upon the needs of your OpenStack.

The default Adjutant configuration is found in conf/conf.yaml, and but will
be overriden if a file is placed at ``/etc/adjutant/conf.yaml``.

The first part of the configuration file contains standard Django settings.

.. code-block:: yaml

  SECRET_KEY:

  ALLOWED_HOSTS:
      - "*"

  ADDITIONAL_APPS:
      - adjutant.api.v1
      - adjutant.actions.v1

  DATABASES:
      default:
          ENGINE: django.db.backends.sqlite3
          NAME: db.sqlite3

  LOGGING:

  EMAIL_SETTINGS:
      EMAIL_BACKEND: django.core.mail.backends.console.EmailBackend


If you have any plugins, ensure that they are also added to
**ADDITIONAL_APPS**.

The next part of the confirguration file contains a number of settings for all
taskviews.

.. code-block:: yaml

  USERNAME_IS_EMAIL: True

  KEYSTONE:
      username:
      password:
      project_name:
      auth_url: http://localhost:5000/v3
      domain_id: default

  TOKEN_SUBMISSION_URL: http://192.168.122.160:8080/token/

  # time for the token to expire in hours
  TOKEN_EXPIRE_TIME: 24

  ROLES_MAPPING:
      admin:
          - project_admin
          - project_mod
          - _member_
      project_admin:
          - project_admin
          - project_mod
          - _member_
      project_mod:
          - project_mod
          - heat_stack_owner
          - _member_

**USERNAME_IS_EMAIL** impacts account creation, and email modification actions.
In the case that it is true, any task passing a username and email pair, the
username will be ignored. This also impacts where emails are sent to.

The keystone settings must be for a user with administrative privileges,
and must use the Keystone V3 API endpoint.

If you have Horizon configured with adjutant-api **TOKEN_SUBMISSION_URL**
should point to that.

**ROLES_MAPPING** defines which roles can modify other roles. In the default
configuration a user who has the role project_mod will not be able to
modify any of the roles for a user with the project_admin role.


Standard Task Settings
----------------------

.. code-block:: yaml

    ACTIVE_TASKVIEWS:
        - UserRoles
        - UserDetail
        - UserResetPassword
        - UserSetPassword
        - UserList
        - RoleList
        - SignUp
        - UserUpdateEmail

All in use taskviews, including those that are from plugins must be included
in this list. If a task is removed from this list its endpoint will not be
accessable however users who have started tasks will still be able submit them.

.. code-block:: yaml

    DEFAULT_TASK_SETTINGS:
        duplicate_policy: null
        emails:
            initial:
                subject: Initial Confirmation
                reply: no-reply@example.com
                from: bounce+%(task_uuid)s@example.com
                template: initial.txt
                # html_template: initial.txt
            token:

            completed:
        notifications:
            EmailNotification:
                standard:
                    emails:
                        - example@example.com
                    reply: no-reply@example.com
                    from: bounce+%(task_uuid)s@example.com
                    template: notification.txt
                    # html_template: completed.txt
                error:

The default settings can be overridden for individual tasks in the
TASK_SETTINGS configuration, these are cascading overrides. Two additional
options are available, overriding the default actions or adding in additional
actions. These will run in the order specified.

.. code-block:: yaml

    signup:
        default_actions:
             - NewProjectAction
    invite_user:
        additional_actions:
            - SendAdditionalEmailAction


By default duplicate tasks will be marked as invalid, however the duplicate
policy can be set to 'cancel' to cancel duplicates and start a new class.

Email Settings
~~~~~~~~~~~~~~
The ``initial`` email will be sent after the user makes the request, the
``token`` email will be sent after approval steps are run, and the
``completed`` email will be sent after the token is submitted.

The emails will be sent to the current user, however this can be changed at
the action level with the ``get_email()`` function.

Notification Settings
~~~~~~~~~~~~~~~~~~~~~
The type of notifications can be defined here for both standard notifications
and error notifications::

  notifications:
      EmailNotification:
          standard:
              emails:
                  - example@example.com
              reply: no-reply@example.com
              template: notification.txt
          error:
              emails:
                  - errors@example.com
              reply: no-reply@example.com
              template: notification.txt
      <other notification engine>:

Currently EmailNotification is the only available notification engine however
new engines can be added through plugins and may have different settings.


Action Settings
---------------

Default action settings.
Actions will each have their own specific settings, dependent on what they
are for. The standard settings for a number of default actions are below:

An action can have it's settings overridden in the settings for it's task.
This will only effect when the action is called through that specific task
Overriding action settings for a specific task.

Email Templates
---------------

Additional templates can be placed in ``/etc/adjutant/templates/`` and will be
loaded in automatically. A plain text template and an HTML template can be
specified separately. The context for this will include the task object and
a dictionary containing the action objects.

Additional Emails
------------------

The SendAdditionalEmailAction is designed to be added in at configuration
for relevant tasks. It's templates are also passed a context dictionary with
the task and actions available. By default the template is null and the email
will not send.

The settings for this action should be defined within the action_settings
for it's related task view.

.. code-block:: yaml

    additional_actions:
      - SendAdditionalEmailAction
    action_settings:
        SendAdditionalEmailAction:
            initial:
                subject: OpenStack Email Update Requested
                template: email_update_started.txt
                email_current_user: True

The additional email action can also send to a subset of people.

The user who made the request can be emailed with ::

    email_current_user: true

Or the email can be sent to everyone who has a certain role on the project.
(Multiple roles can also be specified)

.. code-block:: yaml

   email_roles:
     - project_admin

Or an email can be sent to a specified address in the task cache
(key: ``additional_emails``) ::

    email_in_task_cache: true

Or sent to an arbitrary administrative email address(es)::

    email_additional_addresses:
       - admin@example.org

This can be useful in the case of large project affecting actions.
