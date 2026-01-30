---
layout: default
title: UI Configuration Entities
nav_order: 5
description: "Configuration guide part 2 for Smart Cover Automation for Home Assistant."
permalink: /ui-configuration-entities/
---

# UI Configuration Entities

In addition to the rather static configuration settings managed through the wizard, the integration's behavior can be controlled via switches and other UI configuration entities on the device page of the integration instance.

## Integration Settings

The entities in this section control how the integration works.

### Enabled

**Enables** or disables the automation. This should be viewed as a on/off switch, a quick way to stop the integration altogether, one step short of deactivating it by Home Assistant's means.

### Simulation Mode

If **simulation mode** is enabled, the automation runs through all calculations without actually moving the covers.

### Verbose Logging

**Verbose logging** enables or disables detailed logging.

## Cover Settings

The entities in this section control the cover movements.

### Lock Mode

Lock mode moves the covers to either opened or closed state, or keeps them in their current position. It then locks the covers, keeping them in that position until lock mode is disabled.

Lock mode can be manually set, but is primarily designed to be triggered as an action, e.g., when a wind or hail warning is received from a weather service. Note that such automations are not part of this integration and need to be set up by the user.

**Lock mode** has the following options:

- `Unlocked (automation active)` [default]
- `Hold current position`
- `Force open and lock`
- `Force close and lock`

### Manual Override

**Manual override duration** specifies how long a cover is skipped after it has been moved manually (0 = no skipping).

### Minimum & Maximum Position

These settings control the minimum and maximum positions to which the automation moves the covers (0 = fully closed, 100 = fully open). These options can be used to always let some light in and/or always provide a minimum of shade.

- **Maximum cover position:** Never close more than this.
- **Minimum cover position:** Never open more than this.

**Note:** The minimum and maximum positions can also be configured per cover in the configuration wizard.

## Sun & Temperature Settings

The entities in this section control at which temperatures and sun positions the integration automates cover movements.

### Sun Azimuth

**Sun azimuth tolerance:** The maximum horizontal angle at which the sun is considered to be shining on the window (degrees).

### Sun Elevation

**Minimal sun elevation:** The automation starts operating when the sun's elevation is above this threshold (degrees above the horizon).

### Temperature: Heat Threshold

**Temperature: heat threshold:** The temperature at which the automation starts closing covers to protect from heat (degrees Celsius).

## Next Steps

After configuration, see the [Troubleshooting Guide]({{ '/troubleshooting/' | relative_url }}) for common issues and solutions.