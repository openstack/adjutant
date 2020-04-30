####################################
Welcome to Adjutant's documentation!
####################################

.. toctree::
   :maxdepth: 1

   contributing
   development
   release-notes
   devstack-guide
   configuration
   feature-sets
   quota
   guide-lines
   features
   history

A basic workflow framework built using Django and Django-Rest-Framework to
help automate Admin tasks within an OpenStack cluster.

The goal of Adjutant is to provide a place and standard actions to fill in
functionality missing from Keystone, and allow for the easy addition of
business logic into more complex tasks, and connections with outside systems.

Tasks are built around three states of initial submission, admin approval and
token submission. All of the states are not always used in every task, but this
format allows the easy implementation of systems requiring approval and checks
final user data entry.

While this is a Django application, it does not follow the standard Django
folder structure because of certain packaging requirements. As such the project
does not have a manage.py file and must be installed via setup.py or pip.

Once installed, all the normal manage.py functions can be called directly on
the 'adjutant-api' commandline function.

The command ``tox -e venv {your commands}`` can be used and will setup a
virtual environment with all the required dependencies for you.

For example, running the server on port 5050 can be done with::

  tox -e venv adjutant-api runserver 0.0.0.0:5050


***********************
Client and UI Libraries
***********************

Both a commandline/python and a horizon plugin exist for adjutant:

* `python-adjutantclient <https://opendev.org/openstack/python-adjutantclient>`_
* `adjutant-ui <https://opendev.org/openstack/adjutant-ui>`_


***********************
Tests and Documentation
***********************

Tests and documentation are managed by tox, they can be run simply with the
command ``tox``.

To run just action unit tests::

    tox adjutant.actions

To run a single api test::

    tox adjutant.api.v1.tests.test_delegate_api.DelegateAPITests.test_duplicate_tasks_new_user

Tox will run the tests in Python 2.7, Python 3.5 and produce a coverage report.

Api reference can be generated with the command ``tox -e api-ref`` . This will
be placed in the ``api-ref/build`` directory, these docs can be generated with
the command ``tox -e docs``, these will be placed inside the ``doc/build``
directory.


************
Contributing
************

Bugs and blueprints for Adjutant, its ui and client are managed `here on
launchpad. <https://launchpad.net/adjutant>`_

Changes should be submitted through the OpenStack gerrit, the guide for
contributing to OpenStack projects is
`here <https://docs.openstack.org/contributor/>`_ .
