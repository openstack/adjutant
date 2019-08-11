========================
Team and repository tags
========================

.. image:: https://governance.openstack.org/tc/badges/adjutant.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

.. Change things from this point on

Adjutant
========

A basic workflow framework built using Django and
Django-Rest-Framework to help automate basic Admin tasks within an
OpenStack cluster.

Primarily built as user registration service that fits into the
OpenStack ecosystem alongside Keystone, its purpose to fill
functionality missing from Keystone. Ultimately it is just a framework
with actions that are tied to an endpoint and can require certain data
fields and perform actions via the OpenStack clients as well as talk
to external systems as needed.

Useful for automating generic admin tasks that users might request but
otherwise can't do without the admin role. Also allows automating the
signup and creation of new users, but also allows such requests to
require approval first if wanted. Due to issuing of uri+tokens for
final steps of some actions, allows for a password submit/reset system
as well.

Documentation
=============

Documentation can be found at: https://docs.openstack.org/adjutant/latest

Documentation is stored in doc/, a sphinx build of the documentation
can be generated with the command `tox -e docs`.

An API Reference is stored in api-ref. This is also a sphinx build and
can be generated with `tox -e api-ref`.
