---
layout: default
title: Multiple Instances
nav_order: 7
description: "Configuring multiple instances of Smart Cover Automation for Home Assistant."
permalink: /multiple-instances/
---

# UI Multiple Instances

The integration supports multiple instances. This can be useful if you have varying heat or sun protection requirements for different groups of covers.

## Creating Instances

After the initial installation, additional integration instances can be created on the integration page by clicking **Add entry** > **Submit**. In the **Device created** dialog, specify a name that helps you distinguish the instances (see below for examples), then click **Finish**.

## Entity ID Names

The names of an instance's entity IDs are constructed by Home Assistant from the following components:

- Entity type (e.g., binary sensor)
- Device name (e.g., SCA North Windows)
- Entity name (e.g., Status)

The example above would result in the entity ID: `binary_sensor.sca_north_windows_status`.

## Use Case Examples

### North and South Covers

#### Requirements

Let's assume you have covers on the south and the north side of the building. You want to configure these as follows:

- **South covers:** enable heat protection already at moderate temperatures, e.g., a daily maximum of 24° C.
- **North covers:** enable heat protection only at high temperatures, e.g., a daily maximum of 30° C.

#### Configuration

On the integration page, rename the default integration entry (the one you get after installing the integration) from `Smart Cover Automation` to `South Covers`.

Also on the integration page, click **Add entry** to create a second instance of the integration.

