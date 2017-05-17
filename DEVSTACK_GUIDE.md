# Deploying Adjutant in Devstack

This is a guide to setting up Adjutant in a running Devstack environment similar to how we have been running it for development purposes.

This guide assumes you are running this in a clean ubuntu 14.04 virtual machine with sudo access.

## Deploy Devstack

Grab the Devstack repo. For this we are going to focus on mitaka.

```
git clone https://github.com/openstack-dev/devstack.git -b stable/mitaka
```

And then define a basic localrc file with the password set and place that in the devstack folder:
```
ADMIN_PASSWORD=openstack
MYSQL_PASSWORD=openstack
DATABASE_PASSWORD=openstack
RABBIT_PASSWORD=openstack
SERVICE_PASSWORD=openstack
```

Run the devstack build:
```
./devstack/stack.sh
```

Provided your VM has enough ram to handle a devstack install this should take a while, but go smoothly. Ideally give your VM 5gb or more of ram, any less can cause the devstack build to fail.


## Deploy Adjutant

Grab the Adjutant repo.

```
git clone https://github.com/catalyst/adjutant.git
```

Then you'll want to setup a virtual environment.
```
cd adjutant
virtualenv venv
source venv/bin/activate
```

Once that is done you can install Adjutant into your virtual environment, which will also install all the required python libraries:
```
python setup.py develop
```

If you prefer you can install it fully, but using develop instead allows you update the Adjutant code and have the service reflect that without rerunning the install.


## Running Adjutant

Still in the Adjutant repo directory, you will now need to run the migrations to build a basic database. By default this will use sqlite3, and for testing and development this is ideal and easier.
```
adjutant-api migrate
```

Now the that the migrations have been setup and the database built run the service from the same directory, and it will revert to using the config file at 'conf/conf.yaml':
```
adjutant-api runserver 0.0.0.0:5050
```
Note: The port doesn't matter, but 5050 is a safe bet as it isn't used by any other DevStack services and we can then safely assume you will be using the same url for the rest of the guide.

Now you have Adjutant running, keep this window open as you'll want to keep an eye on the console output.


## Add Adjutant to Keystone Catalogue

In a new SSH termimal connected to your ubuntu VM setup your credentials as environment variables:
```
export OS_USERNAME=admin
export OS_PASSWORD=openstack
export OS_TENANT_NAME=demo
export OS_AUTH_URL=http://localhost:5000/v2.0
export OS_REGION_NAME=RegionOne
```

If you used the localrc file as given above, these should work.

Now setup a new service in Keystone for Adjutant and add an endpoint for it:
```
openstack service create registration --name adjutant
openstack endpoint create adjutant --publicurl http://0.0.0.0:5050/v1 --region RegionOne
```


## Adjutant specific roles

To allow certain actions, Adjutant requires two special roles to exist. You can create them as such:
```
openstack role create project_admin
openstack role create project_mod
```


## Testing Adjutant via the CLI

Now that the service is running, and the endpoint setup, you will want to install the client and try talking to the service:
```
sudo pip install python-adjutantclient
```
In this case the client is safe to install globally as none of its requirements will conflict with OpenStack.

Now lets check the status of the service:
```
adjutant status
```

What you should get is:
```
{
    "error_notifications": [],
    "last_completed_task": null,
    "last_created_task": null
}
```
Seeing as we've done nothing to the service yet this is the expected output.

To list the users on your current project (admin users are hidden):
```
adjutant user-list
```

Now lets try inviting a new user:
```
adjutant user-invite --email bob@example.com --roles project_admin
```
You then then get a note saying your invitation has been sent followed by a print out of the users on your current project (same as doing 'adjutant user-list').


Now if you look at the log in the Adjutant terminal you should still have open, you will see a print out of the email that would have been sent to bob@example.com. In the email is a line that looks like this:
```
http://192.168.122.160:8080/token/e86cbfb187d34222ace90845f900893c
```
Normally that would direct the user to a Horizon dashboard page where they can submit their password.

Since we don't have that running, your only option is to submit it via the CLI. This is cumbersome, but doable. From that url in your Adjutant output, grab the values after '.../token/'. That is bob's token. You can submit that via the CLI:
```
adjutant token-submit <bobs_token> --data '{"password": "123456"}'
```

Now if you get the user list, you will see bob is now active:
```
adjutant user-list
```

And also shows up as a user if you do:
```
openstack user list
```


## Setting Up Adjutant on Horizon

This is a little annoying, since we can't simple install the changes as a plugin, but for the purposes of our demo we will be using a fork of Horizon with our internal Horizon changes rebased on top.

First grab the Adjutant fork of horizon:
```
git clone https://github.com/catalyst/horizon.git -b stable/mitaka_adjutant
```

Now we will copy the code from that repo to replace the code devstack is using:
```
cp -r horizon/* /opt/stack/horizon/
```

We will also need to add the Adjutant url to the local_settings file for the non-authed views:
```
echo 'OPENSTACK_REGISTRATION_URL="http://0.0.0.0:5050/v1"' >> /opt/stack/horizon/openstack_dashboard/local/local_settings.py
```

Now we need to restart apache:
```
sudo service apache2 restart
```

Now if you go to your devstack Horizon dashboard you will be able to access the new panel and new un-authed views.


To help testing token submission, you probably will want to update this line in the Adjutant conf from:
```
TOKEN_SUBMISSION_URL: http://192.168.122.160:8080/dashboard/token/
```
To point to the ip or url of your devstack VM:
```
TOKEN_SUBMISSION_URL: <ip_or_url_to_devstack>/dashboard/token/
```
Setting that url will mean the token links send in the emails will be usable via your Horizon.


## Sending email via a mail server

By default the conf is set to output emails to console, but if you have a mail server you can use update the conf to reflect that and the service will send emails through that.

Simply replace this part of the conf:
```yaml
EMAIL_SETTINGS:
    EMAIL_BACKEND: django.core.mail.backends.console.EmailBackend
```

With this, adding in your server and port:
```yaml
EMAIL_SETTINGS:
    EMAIL_BACKEND: django.core.mail.backends.smtp.EmailBackend
    EMAIL_HOST: <server_url>
    EMAIL_PORT: <server_port>
```

Or this if your server needs a username and password:
```yaml
EMAIL_SETTINGS:
    EMAIL_BACKEND: django.core.mail.backends.smtp.EmailBackend
    EMAIL_HOST: <server_url>
    EMAIL_PORT: <server_port>
    EMAIL_HOST_USER: <username>
    EMAIL_HOST_PASSWORD: <password>
```

Once the service has reset, it should now send emails via that server rather than print them to console.

## Updating adjutant

Adjutant doesn't have a typical manage.py file, instead this functionality is installed into the virtual enviroment when adjutant is installed.
All of the expected Django functionality can be used using the 'adjutant-api' cli.
