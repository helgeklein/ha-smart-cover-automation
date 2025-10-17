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
- **Rich language support:** UI translations available for English, German, French, Spanish, Dutch, Italian, Portuguese, Chinese, Swedish, Polish.

## Configuration Options

- **Enabled:** Turn the automation on or off via a switch.
- **Cover selection:** Choose which covers you want the integration to control.
- **Window direction:** Set each window's horizontal angle from north (azimuth).
- **Temperature threshold:** The automation only operates on hot days, i.e., if the forecasted daily high temperature is above a threshold.
- **Sun:**
	- Minimal sun elevation above the horizon.
	- Maximum angle at which the sun is considered to be shining on the window.
- **Covers:**
	- Maximum closure (never close more than this).
	- Minimum closure (never open more than this).

## Monitoring the Integration's Operation

The integration helps you understand what's going on in the following ways:

- **Simulation mode** showing exactly what the integration would do without actually moving the covers.
- **Log file** showing the integration's workings in detail.
- Binary **availability sensor** showing if the integration is working correctly or if there's a problem.
- Automation **status sensor** summarizing the recent activity.

---

<div class="center">
  <a href="installation-download" class="btn">Get Started →</a>
</div>