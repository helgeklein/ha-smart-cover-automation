# Smart Cover Automation for Home Assistant

[![Test status](https://github.com/helgeklein/ha-smart-cover-automation/actions/workflows/test.yml/badge.svg)](https://github.com/helgeklein/ha-smart-cover-automation/actions/workflows/test.yml)
[![Test coverage](https://raw.githubusercontent.com/helgeklein/ha-smart-cover-automation/main/.github/badges/coverage.svg)](https://github.com/helgeklein/ha-smart-cover-automation/actions/workflows/test.yml)

A Home Assistant integration to automate the control of your smart home's window covers with a focus is on quality, reliability, and flexibility.

**Current development status:** *beta, use with caution*

## Functionality

- **Easy to use**:
	- Simple to configure, transparent and reliable operation.
    - All settings are available from the UI, no need to edit YAML.
- **Sun heat protection:**
	- Close covers while the sun shines on a window to prevent the house from heating up.
	- Open covers when there's no direct sunlight to minimize dark cave feeling.
	- The automation takes into account:
        - Is the sun shining or is it cloudy?
        - Is it a hot day?
        - Is the sun in a position to shine on a given window?
- **Lockout protection:** (TODO)
	- Pause automations for a cover if the door/window is open.
- **Manual override detection:**
	- Detect manual adjustments and pause automation to avoid conflicts.
- **Night silence**: (TODO)
	- Don't move the covers when people are sleeping.
- **Prepositioning before silent phases:** (TODO)
	- Move the covers to the position they need to be in ahead of time so that there's silence at night but the covers are closed when the sun starts shining in the morning.
- **Plant light:**
	- Define min/max positions for the covers so that plants on the windowsill receive enough light.
- **Comfort:**
	- Micro-adjustments are avoided.
- **Supported covers:** Works with any cover entity that supports open/close or position control.
- **Rich language support:** UI translations available for English, German, French, Spanish, Dutch, Italian, Portuguese, Chinese, Swedish, Polish.


## Installation & Usage

For installation instructions, configuration guides, and troubleshooting info please **visit the [documentation website](https://helgeklein.github.io/ha-smart-cover-automation/).**

## Developer Information

This repository contains the source code for the integration. For user documentation and guides, please visit the [documentation website](https://helgeklein.github.io/ha-smart-cover-automation/).

### Setting Up a Development Environment

Please see [this blog post](https://helgeklein.com/blog/developing-custom-integrations-for-home-assistant-getting-started/) for details on how to set up your own development environment for this integration (or even for Home Assistant integrations in general).
