####################################
Quota Management
####################################

The quota API will allow users to change their quota values in any region to
a number of preset quota definitions. If a user has updated their quota in
the past 30 days or are attempting to jump across quota values, administrator
approval is required. The exact number of days can be modified in the
configuration file.

Adjutant will assume that you have quotas setup for nova, cinder and neutron.
Adjutant offers deployers a chance to define what services they offer in which
region that require quota updates. At present Adjutant does not check the
catalog for what services are available, but will in future, with the below
setting acting as an override.

The setting ``QUOTA_SERVICES`` can be modified to include or remove a service
from quota listing and updating, and it is a mapping of region name to services
with ``*`` acting as a wildcard for all regions:

.. code-block:: yaml

  QUOTA_SERVICES:
      "*":
          - cinder
          - neutron
          - nova
          - octavia
      RegionThree:
          - nova
          - cinder
          - neutron

A new service can be added by creating a new helper object, like
``adjutant.common.quota.QuotaManager.ServiceQuotaCinderHelper`` and adding
it into the ``_quota_updaters`` class value dictionary. The key being the
name that is specified in ``QUOTA_SERVICES`` and on the quota definition.
