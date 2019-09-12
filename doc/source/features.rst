Project Features
################

To be clear, Adjutant doesn't really have features. It's a framework for
deployer defined workflow, and a service to expose those workflows on
configurable APIs, and supplementary micro APIs. This provides useful ways to
extend some functionality in OpenStack and wrap sensible business logic around
it, all while providing a clear audit trail for all tasks that Adjutant
handles.

Adjutant does have default implementations of workflows and the APIs for
them. These are in part meant to be workflow that is applicable to any cloud,
but also example implementations, as well as actions that could potentially be
reused in deployer specific workflow in their own feature sets. If anything
could be considered a feature, it potentially could be these. The plan is to
add many of these, which any cloud can use out of the box, or augment as
needed.

To enable these they must be added to `ACTIVE_DELEGATE_APIS` in the conf file.

For most of these there are matching panels in Horizon.

Built in Tasks and APIs
=======================

UserList
++++++++

List the users on your project if you have the `project_admin` or `project_mod`
role, and allow the invitiation of additional members (via email) to your
project.

.. note:: Adjutant-UI exposes this with the Project Users panel for Horizon.

UserRoles
+++++++++

Allows the editing of roles for users in the same project provided you have
the `project_admin` or `project_mod` role.

.. note:: Adjutant-UI exposes this with the Project Users panel for Horizon.

RoleList
++++++++

Mirco API to list roles that can be managed by your current user for users on
your project.

.. note:: Adjutant-UI exposes this with the Project Users panel for Horizon.

UserDetail
++++++++++

Just a micro API to show details of users on your project, and cancel invite
user tasks.

.. note:: Adjutant-UI exposes this with the Project Users panel for Horizon.

UserResetPassword
+++++++++++++++++

An unauthenticated API that allows password reset request submissions. Will
check if user exists, and email user with password reset token to reset
password. This token is usable in Horizon, or via the API directly.

.. note:: Adjutant-UI exposes this with the Forgot Password panel for Horizon.

SignUp
++++++

An unauthenticated API that allows prospective users to submit requests to have
a project and account created. This will then notify an admin as configured
and an admin can approve or cancel the request.

This is mostly built as a basic example of a signup workflow. Most companies
would use this only as a template and expand on the actions to talk to external
systems and facilitate much more complex validation.

A more complex example of a signup process built on top of the defaults is
Catalyst Cloud's own one: https://github.com/catalyst-cloud/adjutant-odoo

.. note:: Adjutant-UI exposes this with the Sign Up panel for Horizon.

UserUpdateEmail
+++++++++++++++

A simple task that allows a user to update their own email address (or username
if username==email). An email is sent to the old email informing them of the
change, and a token to the new email so that the user must confirm they have
correctly given their email.

.. note:: Adjutant-UI exposes this with the Update Email Address panel for
          Horizon.


UpdateProjectQuotas
+++++++++++++++++++

A way for users to request quota changes between given sizes. These requests
are either automatically approved if configured as such, or require an admin
to approve the quota change.

.. note:: Adjutant-UI exposes this with the Quota Management panel for Horizon.
