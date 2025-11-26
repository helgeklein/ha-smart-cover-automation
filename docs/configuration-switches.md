---
layout: default
title: Configuration Switches
nav_order: 5
description: "Configuration guide part 2 for Smart Cover Automation for Home Assistant."
permalink: /configuration-switches/
---

# Configuration Guide: Switches & Selects

In addition to the rather static configuration settings managed through the wizard, the integration's behavior can be controlled via switches and selects on the integration card.

## Switches

- **Enabled:** Enables or disables the automation.
- **Simulation mode:** If enabled, the automation runs through all calculations without actually moving the covers.
- **Verbose logging:** Enables or disables detailed logging.

## Selects

- **Lock mode:** Which of the following lock modes is active:
    - `Unlocked (automation active)` [default]
    - `Hold current position`
    - `Force open and lock`
    - `Force close and lock`

## Next Steps

After configuration, see the [Troubleshooting Guide]({{ '/troubleshooting/' | relative_url }}) for common issues and solutions.