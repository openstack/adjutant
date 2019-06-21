###################################
Admin Logic Version 1 API reference
###################################

This is the reference for Adjutant when it is using the default configuration.
Different deployments may exclude certain DelegateAPIs or include their own
additional ones.

The core functionality of Adjutant is built around the concept of tasks and
actions.

Actions are both concepts in the database and code that can execute whatever
logic is necessary at each stage.

Tasks can bundle a number of actions and have 3 main steps.

1. A user submits a request to the specified endpoint.
2. An admin approves the request, or it is automatically approved. At this
   point the admin can also update invalid data inside the task.
3. If necessary a user will be emailed a token and will submit additional data
   (ie passwords or a confirmation) to finish the task.

Depending on the task and the data provided some steps may be skipped.


**************
Authentication
**************

The 'X-Auth-Token' header value should be provided for authentication
with a valid Keystone token.

******************
HTTP Status Codes
******************

.. rest_status_code:: success http-status.yaml

    - 200
    - 200: task-view
    - 202


.. rest_status_code:: error http-status.yaml

    - 400
    - 401
    - 403
    - 404
    - 405
    - 409
    - 500
    - 503


******************
Service Discovery
******************

Version Discovery Endpoint
==========================

.. rest_method::  GET /

Unauthenticated.

JSON containing details of the currently available versions (just v1 for now)

Normal response code: 200

Version One Details Endpoint
=============================
.. rest_method::  GET /v1

Unauthenticated.

Details V1 version details.

Normal response code: 200

.. include:: admin-api.inc

.. include:: delegate-apis.inc


****************************
Additional API Documentation
****************************

While in debug mode the service will supply online browsable documentation via
Django REST Swagger.

This is viewable at: ../docs
