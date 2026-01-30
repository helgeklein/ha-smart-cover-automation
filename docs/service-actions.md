---
layout: default
title: Service Actions
nav_order: 8
description: "Service actions provided by Smart Cover Automation for Home Assistant."
permalink: /service-actions/
---

# Service Actions

This guide describes the service actions provided by the integration.

## Set Cover Lock

- **Name:** Set Cover Lock
- **Description:** Lock all covers in a specific state to prevent automation from moving them. Useful for weather emergencies (hail, storms) or manual override scenarios.
- **More information:** See the [lock mode]({{ 'ui-configuration-entities/#lock-mode' | relative_url }}) documentation.

## Create Logbook Entry

This service is for internal use and should not be used. Its implementation may be changed at any time without prior notice.