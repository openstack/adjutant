# StackTask

A basic workflow framework built to help automate basic Admin tasks within an OpenStack cluster.

Primarily built as user registration service that fits into the OpenStack ecosystem alongside Keystone, its purpose to fill functionality missing from Keystone. Ultimately it is just a framework with actions that are tied to an endpoint and can require certain data fields and perform actions via the OpenStack clients.

Useful for automating generic admin tasks that users might request but otherwise can't do without the admin role. Also allows automating the signup and creation of new users, but also allows such requests to require approval first if wanted. Due to issuing of uri+tokens for final steps of some actions, allows for a password submit/reset system as well.

### Functionality:

The main workflow consists of three possible steps which can be executed at different points in time, depending on how the ActionView is defined.

The base use case is three stages:

* Recieve Request
  * Validate request data against action serializers.
  * If valid, setup Registration to represent the request, and the Actions specified for that ActionView.
  * The service runs the pre_approve function on all actions which should do any self validation to mark the actions themselves as valid or invalid, and populating the nodes in the Registration based on that.
* Admin Approval
  * An admin looks at the Registration and its notes.
  * If they decide it is safe to approve, they do so.
    * If there are any invalid actions approval will do nothing until the action data is updated and initial validation is rerun.
  * The service runs the post_approve function on all actions.
  * If any of the actions require a Token to be issued and emailed for additional data such as a user password, then that will occur.
    * If no Token is required, the Registration will run submit actions, and be marked as complete.
* Token Submit
  * User submits the Token data.
  * The service runs the submit function on all actions, passing along the Token data, normally a password.
    * The action will then complete with the given final data.
  * Registration is marked as complete.

There are cases and ActionViews that auto-approve, and thus automatically do the middle step right after the first. There are also others which do not need a Token and thus run the submit step as part of the second, or even all three at once. The exact number of 'steps' and the time between them depends on the definition of the ActionView.

Actions themselves can also effectively do anything within the scope of those three stages, and there is even the ability to chain multiple actions together, and pass data along to other actions.

The points that are modular, or will be made more modular in future, are the ActionViews and the actions tied to them. Adding new actions is easy, and attaching them to existing ActionViews is as well. Adding new ActionViews is also fairly easy, but will be made more modular in future (see Future Plans).

Creation and management of Registrations, Tokens, and Notifications is not modular and is the framework around the defined Actions and ActionViews that handles how they are executed. This helps keep the way Actions are executed consistent and simpler to maintain, but does also allow Actions to run almost any logic within those consistent steps.

#### Default Action Endpoints:

* ../project - GET
  * return a json describing the actions and required fields for the endpoint.
* ../project - POST
  * unauthenticated endpoint
  * for signup of new users/projects.
  * registration requires manual approval, sends a uri+token for password setup after the project is created and setup.
    * create project
    * add admin user to project
    * setup basic networking if needed
    * create user on password submit
* ../user - GET
  * return a json describing the actions and required fields for the endpoint.
* ../user - POST
  * authenticated endpoint limited by role
  * auto-approved
  * add/invite a user to your project
  * adds an existing user with the selected role, or if non-existent user sends a uri+token to them for setup user before adding the role.
  * allows adding of users to own project without needing an admin role
* ../reset - GET
  * return a json describing the actions and required fields for the endpoint.
* ../reset - POST
  * unauthenticated endpoint
  * auto-approved
  * issue a uri+token to user email to reset password

#### Admin Endpoints:

* ../registration - GET
  * A json containing all registrations.
    * This will be updated to take parameters to refine the list.
* ../registration/<uuid> - GET
  * Get details for a specific registration.
* ../registration/<uuid> - PUT
  * Update a registration and retrigger pre_approve.
* ../registration/<uuid> - POST
  * approve a registration
* ../token - GET
  * A json containing all tokens.
    * This will be updated to take parameters to refine the list.
* ../token - POST
  * Reissue tokens for a given registration.
* ../token - DELETE
  * Delete all expired tokens.
* ../token/<uuid> - GET
  * return a json describing the actions and required fields for the token.
* ../token/<uuid> - POST
  * submit the token.
* ../notification - GET
  * Get a list of all unacknowledged notifications.
* ../notification - POST
  * Acknowledge a list of notifications.
* ../notification/<id> - GET
  * Details on a specific notification.
* ../notification/<id> - POST
  * Acknowledge a specific notification.

### Implementation Details:

#### Requirements:

The requirements for the service started as a system capable of taking requests for user sign up, waiting for approval, then on approval doing various setup and creation actions, followed by sending a uri+token to the user to set their password.

Creating a user directly in Keystone before approval also was to be avoided, and storing the password before approval was to be avoided.

Due to the steps involved, and the time between them, data had to be stored somewhere, and some representation of the request had to be stored as well. The ability to tie other actions and pieces of automation to the process also seemed useful and time saving considering the steps setting up a user might involve.

If that was the case, the system should ideally also have been modular enough to allow swapping of actions if circumstances changed, or new pieces of automation needed to be added or removed. Pushing as much logic to the concept of an 'action' seemed the ideal situation.

#### What is an Action?

Actions are a generic database model which knows what 'type' of action it is. On pulling the actions related to a Registration from the database we wrap it into the appropriate class type which handlings all the logic associated with that action type.

An Action is both a simple database representation of itself, and a more complex in memory class that handles all the logic around it.

Each action class has the functions "pre_approve", "post_approve", and "submit". These relate to stages of the approval process, and any python code can be executed in those functions, some of which should ideally be validation that the data passed makes sense.

Multiple actions can be chained together under one Registration and will execute in the defined order. Actions can pass information along via an in memory cache/field on the registration object, but that is only safe for the same stage of execution. Actions can also store data back to the database if their logic requires some info passed along to a later step of execution.

See 'base.models' for a good idea of Actions.

#### What is a Registration?

A registration is a top level model representation of the request. It wraps the request metadata, and based on the ActionView, will have actions associated with it.

See 'api_v1.models'.

#### What is a Token?

A token is a unique identifier linking to a registration, so that anyone submitting the token will submit to the actions related to the registration.

See 'api_v1.models'.

#### What is an ActionView

ActionViews are classes which extend the base ActionView class and use it's imbuilt functions to process actions. They also have actions associated with them and the inbuilt functions from the base class are there to process and validate those against data coming in.

The ActionView will process incoming data and build it into a Registration, and the related Action classes.

They are very simple to define as the inbuilt functions handle all the real logic, but defining which functions of those are called changes the view to create a registration that either requires approval or auto-approves.

The base ActionView class has three functions:

* get
  * just a basic view function that by default returns list of actions, and their required fields for the action view.
* process_actions
  * needs to be called in the ActionView definition
  * A function to run the processing and validation of request data for actions.
  * Builds and returns the registration object, or the validation errors.
* approve
  * Takes a registration and approves it, running post_approve actions and issuing a token if needed.
  * Used only if no admin approval is needed for Registrations create by this ActionView.

See 'api_v1.views' and look at the ActionView class to get a better idea.

## Development:

### Dev Environment:

Dev is mainly done within a virtualenv setup alongside a devstack deployment.

$ cd openstack-registration
$ virtualenv venv
$ source ./venv/bin/activate
$ pip install -r requirements.txt
$ python setup.py develop
$ stacktask runserver

### Adding Actions:

Adding new actions is done by creating a new django app and defining the action models and their serializers. Action must extend the BaseAction class as defined in the base.models module. They also must add themselves to the global store of actions (see the bottom of existing models modules).

For examples of actions look in: base.models and tenant_setup.models

### Adding ActionViews:

Ideally this will be made pluggable in future, but for now requires updating and adding a url entry in api_v1.urls and adding an additional ActionView linked to that url.

For examples see the classes CreateProject, AttachUser, and ResetPassword in the api_v1.views module.

## Setup/Deployment:

This section is a work in progress, although eventually there should be a puppet module for deploying this service.

## Current Work:

* Clean up python packaging and develop a puppet module for deloyment
* Finish and clean up the client/shell tools
* Nicer handling of token emails and email templates
* Tests for username isn't email vs username is email
* Basic admin panel in horizon, and example public forms for registration and token submission.

## Future Plans:

Most future plans are around adding additional Actions to the service, but there will be some features that will require some refactoring.

Features that might require a slight refactor:

* Break out the ActionViews into a set of explorable endpoints so adding and removing ActionViews is easier.
* Add optional serializers for token data.

Additional Actions we wish to add in the near future:

* Update Quota
  * Admin is required to do this
  * Allows users to request a quota increase and by requiring an admin to simply check, and confirm the request, will make the process faster.
  * Makes it effectively a quick 2 step process.
* Stand-alone Setup Network Action + ActionView
  * For users who missed or forgot the step at Project creation, and want a quick network setup.

Additional Actions for our own deployment (may be useful to others):

* openERP client create
  * An Action that will create a client in openERP and link them to the Project
  * or if the Client already exists, just link them to the project.

Interesting but presently unlikely/far-future additions:

* Action + ActionView for removing roles from users on your Project
  * Requires Admin, and requires knowing which users have roles on your project.
  * Will require some endpoint to query what users with roles less than mine are present on my Project (Admin > project_own > project_mod > Member)
    * This might require more than making an action + actionview, and alter the api too much. Needs careful thought.
  * Allows users to self manage almost entirely even before hierarchical multi-tenancy

Even less likely, and further far-future additions:

* Remove concept of predefined action steps entirely, setup Actions to have any possible number of 'steps'.
  * Will require moving actions to an iterator style pattern with a "next_action" style function as the driving force.
  * Will alter how chaining actions together works, thus may require a lot of work to define a sensible pattern for chaining them together.
