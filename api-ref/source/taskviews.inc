************************************
OpenStack Style TaskView Endpoints
************************************

A response of 'task created' means that the task requires admin approval and
a response of 'created token' indicates that the task has been auto-approved
and awaits the submission of an emailed token.

List users
========================
.. rest_method:: GET /v1/openstack/users

Authentication: Project Moderator or Admin

List current and pending users in the current project.

Request Example
----------------
.. code-block:: bash

    curl -H "X-Auth-Token: $NOS_TOKEN" http://0.0.0.0:5050/v1/openstack/users

Response Example
-----------------
.. code-block:: javascript

    {
        "users": [
            {
                "cohort": "Member",
                "email": "demo@example.com",
                "id": "",
                "manageable": false,
                "name": "demo",
                "roles": [
                    "project_admin",
                    "__member__"
                ],
                "status": "Active"
            }
        ]
    }


Invite User
============
.. rest_method:: POST /v1/openstack/users

Authentication: Project Moderator or Admin

An auto-approved task that will add a user to the project. If the user already
exists it will add them directly, otherwise it will create a user when the
invitee submits a token sent to them though email

.. rest_parameters:: parameters.yaml

    - roles: roles
    - email: email
    - username: username

Request Example
-----------------
.. code-block:: bash

    curl -H "X-Auth-Token: $NOS_TOKEN" http://0.0.0.0:5050/v1/openstack/users \
     -H 'Content-Type: application/json' \
    -d '{"roles": ["_member_"], "email": "new@example.com"}'

Response Example
-----------------
.. code-block:: javascript

    {
      "notes": ["created token"]
    }

User Details
=============
.. rest_method:: GET /v1/openstack/users/<user_id>

Authentication: Project Moderator or Admin

Get details on the given user including their roles on your project

.. rest_parameters:: parameters.yaml

    - user_id: user_id

Cancel User Invite
==================
.. rest_method:: DELETE /v1/openstack/users/<user_id>

Authentication: Project Moderator or Admin

Cancel a pending user invitation. Current users can be removed from your
project by removing all of their roles.

.. rest_parameters:: parameters.yaml

    - user_id: user_id

List User Roles
==================
.. rest_method:: GET /v1/openstack/users/<user_id>/roles

Authentication: Project Moderator or Admin

List all roles the user has on the current project

.. rest_parameters:: parameters.yaml

    - user_id: user_id

Add User Roles
==================
.. rest_method:: PUT /v1/openstack/users/<user_id>/roles

Authentication: Project Moderator or Admin

Add the specified roles to the user on the current project.

There is additional authentication in the forms of what roles can be edited
by the current user. If the target user has any role not editable by the
current user the user will not be able to edit any of their roles.
Editiable roles can be found at the ``List available roles`` endpoint.


.. rest_parameters:: parameters.yaml

    - user_id: user_id
    - roles: roles

Request Example
-----------------
.. code-block:: bash

    curl -H "X-Auth-Token: $NOS_TOKEN" -H 'Content-Type: application/json' \
    -d '{"roles": ["project_mod"]}' -X PUT \
    http://0.0.0.0:5050/v1/openstack/users/5123ca764f3d40d79e3589e91f1ccb8f/roles

Response Example
-----------------
.. code-block:: javascript

    {
        "notes": [
            "Task completed successfully."
        ]
    }

Remove User Roles
==================
.. rest_method:: DELETE /v1/openstack/users/<user_id>/roles

Authentication: Project Moderator or Admin

Remove the specified roles from the user on the current project.

A project moderator will not be able to change the roles of a project admin.

.. rest_parameters:: parameters.yaml

    - user_id: user_id
    - roles: roles

Request Example
-----------------
.. code-block:: bash

    curl -H "X-Auth-Token: $NOS_TOKEN" -H 'Content-Type: application/json' \
    -d '{"roles": ["project_mod"]}' -X DELETE \
    http://0.0.0.0:5050/v1/openstack/users/5123ca764f3d40d79e3589e91f1ccb8f/roles

Response Example
-----------------
.. code-block:: javascript

    {
        "notes": [
            "Task completed successfully."
        ]
    }


List Available Roles
=====================
.. rest_method:: GET /v1/openstack/roles

Authentication: Project Moderator or Admin

List the roles available for the current user to modify.

Request Example
----------------
.. code-block:: bash

    curl -H "X-Auth-Token: $NOS_TOKEN" http://0.0.0.0:5050/v1/openstack/roles/

Response Example
-----------------
.. code-block:: javascript

    {
        "roles": [
            {
                "domain_id": null,
                "id": "b81efc1e23a043d0976dc39b3e2727c3",
                "links": {
                    "self": "http://identity/v3/roles/b81efc1e23a043d0976dc39b3e2727c3"
                },
                "name": "project_mod"
            },
            {
                "domain_id": null,
                "id": "9fe2ff9ee4384b1894a90878d3e92bab",
                "links": {
                    "self": "http://identity/v3/roles/9fe2ff9ee4384b1894a90878d3e92bab"
                },
                "name": "_member_"
            },
        ]
    }

Password Reset
===================
.. rest_method:: POST /v1/openstack/users/password-reset

Authentication: Unauthenticated

Unauthenticated for forgotten password requests. If the email has an associated
user a token will be sent to them to use to reset their password with.

.. rest_parameters:: parameters.yaml

    - email: email_password
    - username: username_password

Request Example
----------------
.. code-block:: bash

    curl -d '{"email": "demo@example.org"}' http://0.0.0.0:5050/v1/openstack/users/password-reset

Response Example
-----------------
.. code-block:: javascript

    {
      "notes": ["If user with email exists, reset token will be issued."]
    }

Update Email Address
=====================
.. rest_method:: POST /v1/openstack/email-update

Authentication: Authenticated

Submit a new email address for the current user. A submission token will be
sent to the new address, and a notification to the old email address. The
account address will not change until the token submission.

.. rest_parameters:: parameters.yaml

    - email: email

Sign Up
========
.. rest_method:: POST /v1/openstack/sign-up

Authentication: Unauthenticated

Account creation endpoint.


.. rest_parameters:: parameters.yaml

    - email: email
    - username: username
    - project_name: project_name
    - setup_network: setup_network
    - region: region

Request Example
----------------
.. code-block:: bash

  curl -H 'X-Auth-Token: $OS_TOKEN' -H 'Content-Type: application/json' -d '{
      "email": "example@example.com", "project_name": "example_project"}'
      -X POST  http://0.0.0.0:5050/v1/openstack/sign-up

Response Example
-----------------
.. code-block:: javascript

    {
      "notes": ["task created"]
    }
