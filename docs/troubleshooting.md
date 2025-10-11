---
layout: default
title: Troubleshooting
nav_order: 4
description: "Common issues and solutions for Smart Cover Automation for Home Assistant."
permalink: /troubleshooting/
---

# Troubleshooting Guide

This guide helps resolve common issues with the Smart Cover Automation integration.

## Installation Problems

### Integration Not Found After Installation

**Symptoms:**

- Integration doesn't appear in the add integration list
- Error: "Integration not found"

**Solutions:**

1. **Restart Home Assistant** completely (not just reload)
2. **Verify file location:**
   ```
   config/
      custom_components/
         smart_cover_automation/
         ├── __init__.py
         ├── manifest.json
         └── ... (other files)
   ```
3. **Check file permissions** (should be readable by Home Assistant user)

### HACS Installation Fails

**Symptoms:**

- "Repository not found" error
- Download fails

**Solutions:**

1. **Check repository URL:** `https://github.com/helgeklein/ha-smart-cover-automation`
2. **Update HACS** to the latest version
3. **Check internet connectivity** from Home Assistant instance

## Debugging

### Enable Verbose Logging

Make sure to enable verbose (debug) logging when analyzing a problem. This can be done via the UI (see the [Configuration Guide]({{ '/configuration/' | relative_url }}))

### Log File Location

In the file system, you can find the **Home Assistant Core** log at `config/home-assistant.log`. It includes the log messages from this integration (filter for `smart_cover_automation`).

In the UI, you can find the same log at **Settings** → **Systems** → **Logs**.

## Getting Help

### Before Seeking Help

1. **Enable verbose logging** and reproduce the issue
2. **Check Home Assistant logs**
3. **Document your configuration** and the exact problem

### Where to Get Help

1. **GitHub Issues:** [Report a bug](https://github.com/helgeklein/ha-smart-cover-automation/issues)
2. **Home Assistant Community:** [Forum discussion](https://community.home-assistant.io/)
3. **Documentation:** Review all sections of this documentation
