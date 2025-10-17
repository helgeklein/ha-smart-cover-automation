---
layout: default
title: "Installation 1/2"
nav_order: 2
description: "Installation guide part 1 for Smart Cover Automation for Home Assistant, via HACS or manually."
permalink: /installation-download/
---

# Installation Guide 1/2: Download Integration

## Method 1: Via HACS (Recommended)

### Prerequisites

- [HACS](https://hacs.xyz/) must be installed and configured in your Home Assistant instance.

### Steps

1. **Add the Integration's Repository**

   Click the button below to add this integration's repository to HACS:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=helgeklein&repository=ha-smart-cover-automation&category=Integration)

   Alternatively, if the button above doesn't work for you, add the integration's repository manually to HACS:

   - Open HACS in your Home Assistant instance.
   - Click the three dots (⋮) in the top right corner.
   - Select **Custom repositories**.
   - Add the repository URL for this integration: `https://github.com/helgeklein/ha-smart-cover-automation`.
   - Select **Integration** as the category.
   - Click **Add**.

2. **Download the Integration**

   - Search for **Smart Cover Automation** in HACS.
   - Click **Download** in the bottom right corner.
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

## Next Steps

Once downloaded, proceed to [part 2 of the installation guide]({{ '/installation-add/' | relative_url }}) to add the integration.