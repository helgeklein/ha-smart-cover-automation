---
layout: default
title: Installation
nav_order: 2
description: "Complete installation guide for HA Smart Cover Automation via HACS or manual installation."
permalink: /installation/
---

# Installation Guide

## Method 1: HACS Installation (Recommended)

[HACS](https://hacs.xyz/) is the recommended way to install this integration.

### Prerequisites
- HACS must be installed and configured in your Home Assistant instance
- Home Assistant 2023.1.0 or newer

### Steps

1. **Add Custom Repository**
   - Open HACS in your Home Assistant instance
   - Navigate to "Integrations"
   - Click the three dots (⋮) in the top right corner
   - Select "Custom repositories"
   - Add the repository URL: `https://github.com/helgeklein/ha-smart-cover-automation`
   - Select "Integration" as the category
   - Click "ADD"

2. **Install the Integration**
   - Search for "Smart Cover Automation" in HACS
   - Click "INSTALL"
   - Restart Home Assistant when prompted

3. **Add Integration**
   - Go to Settings → Devices & Services
   - Click "+ ADD INTEGRATION"
   - Search for "Smart Cover Automation"
   - Follow the configuration wizard

## Method 2: Manual Installation

### Download and Extract

1. Download the latest release from [GitHub Releases](https://github.com/helgeklein/ha-smart-cover-automation/releases)
2. Extract the archive
3. Copy the `smart_cover_automation` folder to your Home Assistant `custom_components` directory

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

1. Navigate to **Settings** → **Devices & Services**
2. Click the **"+ ADD INTEGRATION"** button
3. Search for **"Smart Cover Automation"**
4. Click on it to start the setup process

### 2. Initial Configuration

The configuration wizard will guide you through:

- **Cover Selection**: Choose which covers to automate
- **Weather Integration**: Select your weather provider
- **Basic Settings**: Set up initial automation preferences

### 3. Verify Installation

After setup, you should see:

- New entities in the **Developer Tools** → **States** page
- The integration listed in **Settings** → **Devices & Services**
- New sensors and switches for your automated covers

## Troubleshooting Installation

### Common Issues

**Integration not found after installation**
- Ensure you restarted Home Assistant completely
- Check that files are in the correct directory
- Verify the `manifest.json` file is present

**HACS installation fails**
- Ensure HACS is properly installed and up to date
- Check your internet connection
- Verify the repository URL is correct

**Configuration wizard doesn't start**
- Check Home Assistant logs for error messages
- Ensure all dependencies are met
- Try clearing browser cache

### Getting Help

If you encounter issues:

1. Check the [Troubleshooting Guide](troubleshooting)
2. Review [Home Assistant logs](https://www.home-assistant.io/integrations/logger/)
3. [Open an issue](https://github.com/helgeklein/ha-smart-cover-automation/issues) on GitHub

## Next Steps

Once installed, proceed to the [Configuration Guide](configuration) to set up your automation rules and preferences.