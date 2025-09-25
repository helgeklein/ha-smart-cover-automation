---
layout: default
title: Installation
nav_order: 2
description: "Installation guide for Smart Cover Automation for Home Assistant, via HACS or manually."
permalink: /installation/
---

# Installation Guide

## Method 1: HACS Installation (Recommended)

[HACS](https://hacs.xyz/) is the recommended way to install this integration.

### Prerequisites

- HACS must be installed and configured in your Home Assistant instance.

### Steps

1. **Add Custom Repository**

   - Open HACS in your Home Assistant instance.
   - Navigate to **Integrations**.
   - Click the three dots (⋮) in the top right corner.
   - Select **Custom repositories**.
   - Add the repository URL for this integration: `https://github.com/helgeklein/ha-smart-cover-automation`.
   - Select **Integration** as the category.
   - Click **Add**.

2. **Install the Integration**

   - Search for **Smart Cover Automation** in HACS.
   - Click **Install**.
   - Restart Home Assistant when prompted.

## Method 2: Manual Installation

### Download and Extract

1. Download the latest release from [GitHub Releases](https://github.com/helgeklein/ha-smart-cover-automation/releases).
2. Extract the archive.
3. Copy the `smart_cover_automation` folder to your Home Assistant `custom_components` directory.

### Directory Structure

Your directory structure should look like this:

```
config/
├── custom_components/
│   └── smart_cover_automation/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       └── ... (other files)
└── configuration.yaml
```

### Restart Home Assistant

After copying the files, restart Home Assistant to load the new integration.

## Post-Installation Setup

### 1. Add the Integration

1. Navigate to **Settings** → **Devices & Services**.
2. Click the **Add Integration** button.
3. Search for **Smart Cover Automation**.
4. Click on it to start the setup process.

### 2. Initial Configuration

See the [Configuration Guide]({{ '/configuration/' | relative_url }}) for details on how to configure the integration.

### 3. Verify Installation

After setup, you should see:

- New entities in the **Developer Tools** → **States** page.
- The integration listed in **Settings** → **Devices & Services**.
- New sensors and switches.

## Troubleshooting Installation

See the [Troubleshooting Guide]({{ '/troubleshooting/' | relative_url }}) for details.

## Next Steps

Once installed, proceed to the [Configuration Guide]({{ '/configuration/' | relative_url }}) to set up the automation.