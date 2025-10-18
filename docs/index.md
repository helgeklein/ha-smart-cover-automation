---
layout: default
title: Home
nav_order: 1
description: "A Home Assistant integration to automate the control of your smart home's window covers with a focus is on quality, reliability, and flexibility."
permalink: /
---

# Smart Cover Automation for Home Assistant

[![Test status](https://github.com/helgeklein/ha-smart-cover-automation/actions/workflows/test.yml/badge.svg)](https://github.com/helgeklein/ha-smart-cover-automation/actions/workflows/test.yml)
[![Test coverage](https://raw.githubusercontent.com/helgeklein/ha-smart-cover-automation/main/.github/badges/coverage.svg)](https://github.com/helgeklein/ha-smart-cover-automation/actions/workflows/test.yml)

**Current development status:** *beta, use with caution*

A Home Assistant integration to automate the control of your smart home's window covers with a focus is on quality, reliability, and flexibility.

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
- **Rich language support:** UI translations available for Chinese, Dutch, English, French, German, Italian, Polish, Portuguese, Spanish, Swedish.

## Configuration Options

Need of sunlight and desire for shade are individually very different. The integration allows you to tailor the way your covers move according to your needs. Extensive configuration options should make it possible to implement most scenarios easily.

### Try Before You Buy

Enable **simulation mode**, which shows exactly what the integration would do without actually moving the covers.

## Monitoring the Integration's Operation

The integration helps you understand what's going on in the following ways:

- Cover movements are logged in Home Assistant's **activity logbook**.
- Multiple **sensors** make key aspects of the integration's status available in the UI.
- The Home Assistant **log file** shows the integration's workings in detail.

---

<div class="center">
  <a href="installation-download" class="btn">Get Started →</a>
</div>