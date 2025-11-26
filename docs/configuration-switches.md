---
layout: default
title: UI Configuration Entities
nav_order: 5
description: "Configuration guide part 2 for Smart Cover Automation for Home Assistant."
permalink: /ui-configuration-entities/
---

# Configuration Guide: UI Config Entities

In addition to the rather static configuration settings managed through the wizard, the integration's behavior can be controlled via switches and other UI configuration entities on the integration card.

## Switch Entities

Switches allow a setting to be toggled between on/off, locked/unlocked, etc. The following switches are available:

- **Enabled:** Enables or disables the automation.
- **Simulation mode:** If enabled, the automation runs through all calculations without actually moving the covers.
- **Verbose logging:** Enables or disables detailed logging.

## Select Entities

Selects allow a setting to be changed between multiple predefined values. The following select entities are available:

### Lock Mode

Lock mode moves the covers to either opened or closed state, or keeps them in their current position. It then locks the covers, keeping them in that position until lock mode is disabled.

Lock mode can be manually set, but is primarily designed to be triggered as an action, e.g., when a wind or hail warning is received from a weather service. Note that such automations are not part of this integration and need to be set up by the user.

**Lock mode** has the following options:

- `Unlocked (automation active)` [default]
- `Hold current position`
- `Force open and lock`
- `Force close and lock`

## Next Steps

After configuration, see the [Troubleshooting Guide]({{ '/troubleshooting/' | relative_url }}) for common issues and solutions.