*************************
Administrative Endpoints
*************************

Endpoints for the management of tasks, tokens, and notifications. Most of
these are limited by roles, or are for admin use only.

Status
=======
.. rest_method:: GET /v1/status

Authentication: Administrator

Normal Response Code: 200

Simple status endpoint.

Returns a list of unacknowledged error notifications,
and both the last created and last completed tasks.


List Tasks
===========
.. rest_method::  GET /v1/tasks

Authentication: Administrator

Normal Response Codes: 200

Error Response Codes: 401, 403

Lists all tasks.

.. rest_parameters:: parameters.yaml

   - filters: filters
   - page: page
   - tasks_per_page: tasks_per_page

Request Example
-----------------

.. code-block:: bash

   curl -H "X-Auth-Token: $OS_TOKEN" http://adjutant/v1/tasks

Response Example
------------------
.. code-block:: javascript

  {
      "tasks": [
          {
              "action_notes": {
                  "ResetUserPasswordAction": [
                      "Existing user with matching email.",
                  ]
              },
              "actions": [
                  {
                      "action_name": "ResetUserPasswordAction",
                      "data": {
                          "domain_name": "Default",
                          "email": "demo@example.com"
                      },
                      "valid": true
                  }
              ],
              "approved": true,
              "approved_by": {},
              "approved_on": "2017-08-30T21:29:48.484441Z",
              "cancelled": false,
              "completed": true,
              "completed_on": "2017-08-30T21:30:13.269498Z",
              "created_on": "2017-08-30T21:29:47.989851Z",
              "ip_address": "127.0.0.1",
              "keystone_user": {},
              "project_id": null,
              "task_type": "reset_user_password",
              "uuid": "d5c7901cfecd45ec9a87871035c9f662"
          },
          {
          "action_notes": {
              "NewProjectDefaultNetworkAction": [],
              "NewProjectWithUserAction": [],
              "SetProjectQuotaAction": []
          },
          "actions": [
              {
                  "action_name": "NewProjectWithUserAction",
                  "data": {
                      "domain_id": "default",
                      "email": "test@example.com",
                      "parent_id": null,
                      "project_name": "test_project"
                  },
                  "valid": true
              },
              {
                  "action_name": "NewProjectDefaultNetworkAction",
                  "data": {
                      "region": "RegionOne",
                      "setup_network": false
                  },
                  "valid": true
              },
              {
                  "action_name": "SetProjectQuotaAction",
                  "data": {},
                  "valid": true
              }
          ],
          "approved": false,
          "approved_by": {},
          "approved_on": None,
          "cancelled": false,
          "completed": false,
          "completed_on": null,
          "created_on": "2017-07-26T21:44:21.082248Z",
          "ip_address": "127.0.0.1",
          "keystone_user": {},
          "project_id": null,
          "task_type": "create_project_and_user",
          "uuid": "370d952c63ba410c8704abc12cfd97b7"
      }
  }

Task Details
=============
.. rest_method::  GET /v1/tasks/<task_id>

Authentication: Administrator

Normal Response Codes: 200

Error Response Codes: 401, 403, 404

Gives details for the specific task.

.. rest_parameters:: parameters.yaml

  - task_id: task_id

Request Example
----------------

.. code-block:: bash

    curl -H "X-Auth-Token: $OS_TOKEN" http://adjutant/v1/tasks/d5c7901cfecd45ec9a87871035c9f662

Response Example
-----------------
.. code-block:: javascript

  {
      "action_notes": {
          "ResetUserPasswordAction": [
              "Existing user with matching email.",
          ]
      },
      "actions": [
          {
              "action_name": "ResetUserPasswordAction",
              "data": {
                  "domain_name": "Default",
                  "email": "demo@example.com"
              },
              "valid": true
          }
      ],
      "approved": true,
      "approved_by": {},
      "approved_on": "2017-08-30T21:29:48.484441Z",
      "cancelled": false,
      "completed": true,
      "completed_on": null,
      "created_on": "2017-08-30T21:29:47.989851Z",
      "ip_address": "127.0.0.1",
      "keystone_user": {},
      "project_id": null,
      "task_type": "reset_user_password",
      "uuid": "d5c7901cfecd45ec9a87871035c9f662"
  }


Update Task
============
.. rest_method::  PUT /v1/tasks/<task_id>

Authentication: Project Admin or Project Moderator

Normal Response Codes: 200

Error Response Codes: 400, 401, 403, 404

Replace the data in an unapproved action and rerun the preapproval steps


.. rest_parameters:: parameters.yaml

   - task_data: task_data

Request Example
----------------

.. code-block:: bash

    curl -H "X-Auth-Token: $OS_TOKEN" \
        -H 'Content-Type: application/json' \
        -X PUT --data '{
            "project_name": "a_project",
            "email": "example.a@t.com",
            "region": "RegionOne",
            "setup_network": false
          }' http://0.0.0.0:5050/v1/tasks/19dbe418ecc14aeb94053f23eda01c78

Response Example
----------------
.. code-block:: javascript

  {
    "notes": ["Task successfully updated."]
  }

Approve Task
============
.. rest_method::  POST /v1/tasks/<task_id>

Authentication: Administrator

Normal Response Codes: 200

Error Response Codes: 400, 401, 403, 404

Approves a task and runs the actions approval steps.

.. rest_parameters:: parameters.yaml

    - task_id: task_id
    - approved: approved

Request Example
----------------

.. code-block:: bash

  curl -H "X-Auth-Token: $OS_TOKEN" -H 'Content-Type: application/json' \
        -d '{"approved": true}' http://0.0.0.0:5050/v1/tasks/19dbe418ecc14aeb94053f23eda01c78

Response Example
-----------------
.. code-block:: javascript

  {
    "notes": ["Created Token."]
  }

In most cases an email will be sent after approval to the user who requested
the task.

Cancel Task
===========
.. rest_method::  DELETE /v1/tasks/<task_id>

Authentication: Administrator, Project Admin or Project Moderator

Normal Response Codes: 200

Error Response Codes: 400, 401, 403, 404

Cancel a task. Tasks can be cancelled at any stage prior to their completion,
an issued token for a cancelled task will be invalidated.

Project Admins and Project Moderators can only cancel tasks associated with
their projects.

.. rest_parameters:: parameters.yaml

    - task_id: task_id

List tokens
============
.. rest_method::  GET /v1/tokens

Authentication: Administrator

Normal Response Codes: 200

Error Response Codes: 401, 403

List all active tokens.

.. rest_parameters:: parameters.yaml

    - filters: filters

Reissue Tokens
===============
.. rest_method::  POST /v1/tokens

Authentication: Administrator, Project Admin or Project Moderator

Normal Response Codes: 200

Error Response Codes: 400, 401, 403, 404

Reissue a token for the specified task.

.. rest_parameters:: parameters.yaml

    - task_id: task_id_body

Delete Expired Tokens
======================
.. rest_method::  DELETE /v1/token

Authentication: Administrator

Normal Response Codes: 200

Error Response Codes: 401, 403

Delete all expired tokens.

Note that if a token has expired it will be deleted when someone attempts to
access it, this will prevent the database from clogging up however will not
have an effect on functionality.


Get Token Details
======================
.. rest_method::  GET /v1/token/<token_id>

Authentication: Unauthenticated

Normal Response Codes: 200

Error Response Codes: 401, 403, 404

Details the actions, task_type and required fields of the token

.. rest_parameters:: parameters.yaml

    - token_id: token_id

Request Example
----------------
.. code-block:: bash

  curl http://0.0.0.0:5050/v1/tokens/771af33fb28e46aab45e265bd6a6d469

Response Example
-----------------
.. code-block:: javascript

  {
    "actions": [
        "NewProjectWithUserAction",
        "NewProjectDefaultNetworkAction",
        "SetProjectQuotaAction"
    ],
    "required_fields": [
        "password"
    ],
    "task_type": "create_project_and_user"
  }


Submit Token
======================
.. rest_method::  POST /v1/token/<token_id>

Authentication: Unauthenticated

Normal Response Codes: 200

Error Response Codes: 400, 404

Submit a token and it's data to the last stage of an action execution.
A 400 will be return if it does not contain all of the necessary fields.

.. rest_parameters:: parameters.yaml

    - token_id: token_id
    - token_data: token_data

Request Example
------------------
.. code-block:: bash

  curl -H 'Content-Type: application/json' \
       -d '{"password": "12345"}' http://0.0.0.0:5050/v1/tokens/771af33fb28e46aab45e265bd6a6d469

Response Example
-----------------
.. code-block:: javascript

    {"notes":["Token submitted successfully."]}

In most cases an email will be sent after token submission, detailing what
has changed.

List Notifications
======================
.. rest_method::  GET /v1/notification

Authentication: Administrator

Normal Response Codes: 200

Error Response Codes: 401, 403

List all unacknowledged notifications

.. rest_parameters:: parameters.yaml

    - filters: filters

Acknowledge a List of Notifications
===================================
.. rest_method:: POST /v1/notification

Authentication: Administrator

Mark a given list of notifications as acknowledged

.. rest_parameters:: parameters.yaml

    - notifications: notifications

Notification Details
=====================
.. rest_method:: GET /v1/notification/<notification_id>

Get details of a specific notification

.. rest_parameters:: parameters.yaml

    - notification_id: notification_id


Acknowledge Notification
========================
.. rest_method:: GET /v1/notification/<notification_id>

Acknowledge a specific notification.

.. rest_parameters:: parameters.yaml

    - notification_id: notification_id
    - acknowledged: acknowledged



Filtering Tasks, Tokens, and Notifications
==========================================
The task, token, and notification list endpoints can be filtered using a
slight variant of the Django ORM filters.

This is done but sending a json with filters via HTTP parameters:

.. code-block:: javascript

    {'filters': {'fieldname': { 'operation': 'value'}}


Example:

.. code-block:: javascript

    {'filters': {'task_id': { 'exact': '842433bb-fa08-4fc1-8c3b-aa9904ceb370'}}


This looks a bit messy in the url as that json ends up being url-safe encoded,
but doing the filters this way gives us a fairly large amount of flexibility.

Possible field lookup operations:
https://docs.djangoproject.com/en/1.11/ref/models/querysets/#id4
