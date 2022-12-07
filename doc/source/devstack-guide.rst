###############################
Deploying Adjutant in Devstack
###############################

This is a guide to setting up Adjutant in a running Devstack
environment close to how we have been running it for development purposes.

This guide assumes you are running this in a clean Ubuntu 20.04
virtual machine as user `ubuntu`.

***************
Deploy Devstack
***************

Grab the Devstack repo::

    git clone https://opendev.org/openstack/devstack
    cd devstack

And then define a basic `local.conf` file with the password set and place that
in the devstack folder::

    [[local|localrc]]
    ADMIN_PASSWORD=openstack
    DATABASE_PASSWORD=openstack
    RABBIT_PASSWORD=openstack
    SERVICE_PASSWORD=openstack
    HOST_IP=<Floating IP of VM, if needed>

Run the devstack build::

    ./stack.sh

Provided your VM has enough RAM (5GiB suggested) to handle a devstack install
this should take a while, but go smoothly.

***************
Deploy Adjutant
***************

Grab the Adjutant repo::

    git clone https://opendev.org/openstack/adjutant

Then you'll want to setup a virtual environment::

    cd adjutant
    virtualenv venv
    source venv/bin/activate

Once that is done you can install Adjutant and its requirements::

    pip install -r requirements.txt
    python setup.py develop

If you prefer you can install it fully, but using develop instead allows you
update the Adjutant code and have the service reflect that without rerunning
the install.

******************
Configure Adjutant
******************

Most of the default conf values should work fine against devstack, but you will
need to set a few, as detailed in the headings below.

Identity user
==================

Adjutant needs to know which service account user to operate as.

By default these are unset, and need to be configured:

* `identity.auth.username`
* `identity.auth.password`
* `identity.auth.project_name`
* `identity.auth.auth_url`

Find the values for these from devstack `local.conf` or from the environment::

    cd devstack
    source openrc admin
    env | grep OS_

Network UUIDs
=================

To be able to use the actions `NewDefaultNetworkAction` and
`NewProjectDefaultNetworkAction` you will need to set the the network uuids in:

* `workflow.action_defaults.NewDefaultNetworkAction.public_network`
* `workflow.action_defaults.NewProjectDefaultNetworkAction.public_network`

If you don't set the `public_network` values to match your OpenStack
environment, then signups or tasks using those actions will not be able to
correctly create a default network as they cannot find the correct external
public network.

On a fresh devstack there is only one public network so to find the public
network uuid you can to run::

    source openrc admin
    openstack network show public

And then grab the id value and put that into the Adjutant conf.

Username is email
=================

The example conf for Adjutant is setup with `identity.username_is_email = true`
which works on the assumption that usernames are emails. This is easy to change
in the conf, but a fairly useful way of avoiding username clashes. If you set
this to `false` then usernames will be required as well as emails for most
tasks that deal with user creation.

Migrating between the two states hasn't yet been handled entirely, so once you
pick a value for `identity.username_is_email` stick with it, or clear the
database in between.

****************
Running Adjutant
****************

If you wish you use a different Adjutant config file path than /etc/adjutant,
you need to set the environment variable::

    export ADJUTANT_CONFIG_FILE=etc/adjutant.yaml

Still in the Adjutant repo directory, you will now need to run the migrations
to build a basic database. By default this will use sqlite3.::

    adjutant-api migrate

Now the that the migrations have been setup and the database built, run the
API service from the same directory::

    adjutant-api runserver 0.0.0.0:5050

.. note::

    The port doesn't matter, but 5050 is a safe bet as it isn't used by any
    other DevStack services and we can then safely assume you will be using
    the same url for the rest of the guide.

Now you have Adjutant running, keep this window open as you'll want to keep
an eye on the console output.

API request logs are written to `adjutant.log` by default.

**********************************
Add Adjutant to Keystone Catalogue
**********************************

In a new SSH termimal, connected to your Ubuntu VM, set up your credentials as
environment variables::

    export OS_USERNAME=admin
    export OS_PASSWORD=openstack
    export OS_PROJECT_NAME=demo
    export OS_USER_DOMAIN_NAME=default
    export OS_PROJECT_DOMAIN_NAME=default
    export OS_AUTH_URL=http://localhost/identity
    export OS_IDENTITY_API_VERSION=3
    export OS_REGION_NAME=RegionOne

If you used the `local.conf` file as given above, these should work.

Alternatively, use the `openrc` file provided in the devstack directory::

    source openrc admin

Now we can set up a new service in Keystone for Adjutant, and add an endpoint
to the catalog::

    openstack service create registration --name adjutant
    openstack endpoint create adjutant public http://127.0.0.1:5050/v1 --region RegionOne

**********************************
Adjutant specific roles
**********************************

To allow certain actions, Adjutant requires two special roles to exist.
You can create them as such::

    openstack role create project_admin
    openstack role create project_mod

Also because Adjutant by default also adds the role, you will want to create
'heat_stack_owner' which isn't by default present in devstack unless you
install Heat::

    openstack role create heat_stack_owner


**********************************
Testing Adjutant via the CLI
**********************************

Now that the service is running, and the endpoint set up, you will want
to install the client and try talking to the service::

    pip install python-adjutantclient

Now lets check the status of the service::

    openstack adjutant status


What you should get is::

    {
        "error_notifications": [],
        "last_completed_task": null,
        "last_created_task": null
    }

Seeing as we've done nothing to the service yet this is the expected output.

To list the users on your current project (admin users are hidden by default)::

    openstack project user list

The above action is only possibly for users with the following roles:
'admin', 'project_admin', 'project_mod'

Now lets try inviting a new user::

    openstack project user invite bob@example.com project_admin

You will then get a note saying your invitation has been sent. You can list
your project users again with 'openstack project user list' to see your invite.


Now if you look at the log in the Adjutant terminal you should still
have open, you will see a print out of the email that would have been sent
to bob@example.com. In the email is a line that looks like this::

  http://192.168.122.160:8080/token/e86cbfb187d34222ace90845f900893c

Normally that would direct the user to a Horizon dashboard page where they can
submit their password.

Since we don't have that running, your only option is to submit it via the CLI.
This is cumbersome, but doable.

Using the url in Adjutant's output, grab the values after '.../token/'.
That is bob's token. You can submit that via the CLI::

    openstack admin task token submit <token> <json_data>
    openstack admin task token submit e86cbfb187d34222ace90845f900893c '{"password": "123456"}'


Now if you get the user list, you will see bob is now active::

    openstack project user list

And also shows up as a user if you do::

    openstack user list


And since you are an admin, you can even take a look at the tasks themselves::

    openstack admin task list

The topmost one should be your invite, and if you then do a show using that
id you can see some details about it::

    openstack admin task show <UUID>


**********************************
Setting Up Adjutant on Horizon
**********************************
Adjutant has a Horizon UI plugin, the code and setup instructions for it can
be found `here <https://opendev.org/openstack/adjutant-ui>`_.

If you do set this up, you will want to edit the default Adjutant conf to so
that the value for `workflow.horizon_url` is correctly set to point at your
Horizon URL.
