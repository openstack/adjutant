Adjutant is a service that sits along Keystone and allows the
automation and approval of tasks normally requiring a user with an
admin role. Adjutant allows defining of such tasks as part of a
workflow which can either be entirely automatic, or require admin
approval. The goal is to automate business logic, and augment the
functionality of Keystone and other OpenStack services without getting
in the way of future OpenStack features or duplicating development
effort.

Quick Dev Deployment
====================

To quickly deploy the service for testing you can install via pip,
setup a default config file, and then run the test Django server.

::

    pip install adjutant

Then running the service will look for a config in either
**/etc/adjutant/conf.yaml** or it will default to **conf/conf.yaml**
from the directory you run the command in.

::

    adjutant migrate
    adjutant runserver <port>

For now you will have to source the default conf from the github repo
or the library install location itself, but we hope to add an
additional commandline function which will copy and setup a basic
default config in **/etc/adjutant/conf.yaml**.
