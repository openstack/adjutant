Project History
===============

Adjutant was started by CatalystCloud to fill our needs around missing
features in OpenStack. CatalystCloud is public cloud provider based in New
Zealand with a strong focus on opensource, with a team of operators and
developers who are all contributors to OpenStack itself.

Early prototyping for Adjutant began at the end of 2015 to fill some of the
missing pieces we needed as a public cloud provider. It was initially something
we had started designing as far back as early 2014, with the scope and design
changing many times until initial prototyping and implementation was started in
late 2015.

Originally it was designed to act as a service to manage customers, their
users, projects, quotas, and to be able to process signups and initial resource
creation for new customers. It would act as a layer above OpenStack and most
non-authentication based identity management from a user perspective would
happen through it, with the service itself making the appropriate changes to
the underlying OpenStack services and resources. The reason why it didn't end
up quite so complex and so big is because OpenStack itself, and many of the
services (and the future roadmap) had planned solutions to many of the things
we wanted, and our business requirements changed to storing our customer
information in an external ERP system (Odoo/OpenERP at the time) rather than a
standalone service.

So instead of something so grand, we tried smaller, a service that handles our
unique public cloud requirements for signup. It should take in signup data from
some source such as a public API that our website posts to, then validate it,
give us those validation notes, and lets us decide if we wanted that customer,
or even have the system itself based on certain criteria approve that customer
itself. It would then create the user in Keystone, create a project, give them
access, create a default network, and then also link and store the customer
data in our ERP and billing systems. This was the initial
'openstack-registration' project, and the naming of which is present in our git
history, and where the initial service-type name comes from.

As we prototyped this we realised that it was just a workflow system for
business logic, so we decided to make it flexible, and found other things we
could use it for:

- Allowing non-admin users to invite other users to their project.
- Let users reset their password by sending an email token to them.
- Manage and create child-projects in a single domain environment.
- Request quota increases for their projects.

All with the optional step of actually requiring an admin to approve the user
request if needed. And with a good audit trail as to where the actions came
from, and who approved them.

Eventually it also got a rename, because calling it OpenStack Registration got
dull and wasn't accurate anymore. The name it got at the time was StackTask,
and there are still elements of that naming in our systems, and plenty in the
git history. Eventually we would rename it again because the name still being
feel right, and was too close to StackTach.

Around that time we also added plugin support to try and keep any company
specific code out of the core codebase, and in the process realised just how
much further flexibility we'd now added.

The service gave us an easy way to build APIs around workflow we wanted our
customers to be able to trigger around larger normally unsafe admin APIs in
OpenStack itself. With the ability to have those workflows do changes to our
ERP system, and other external systems. It gave us the missing glue we needed
to make our public cloud business requirements and logic actually work.

But we were always clear, that if something made better sense as a feature in
another service, we should implemented in that other service. This was meant to
be a glue layer, or potentially for mini API features that don't entirely have
a good place for them, or just a wrapper around an existing OpenStack feature
that needs organisation specific logic added to it.

Throughout all this, the goal was always to keep this project fully opensource,
to invite external contribution, to do our planning, bug tracking, and
development where the OpenStack community could see and be transparent about
our own internal usage of the service and our plans for it. The code had been
on our company github for a while, but it was time to move it somewhere better.

So we renamed again, and then finally moved all the core repos to OpenStack
infrastructure, as well as the code review, bug, and spec tracking.

Adjutant, in it's current form is the culmination of that process, and while
the core driving force behind Adjutant was our own needs, it always was the
intention to provide Adjutant for anyone to build and use themselves so that
their effort isn't wasted threading the same ground.
