---
layout: default
title: "Installation: Download"
nav_order: 2
description: "Installation guide part 1 for Smart Cover Automation for Home Assistant, via HACS or manually."
permalink: /installation-download/
---

# Installation Guide 1: Download Integration

## Method 1: Via HACS (Recommended)

### Prerequisites

- [HACS](https://hacs.xyz/) must be installed and configured in your Home Assistant instance.

### Download the Integration

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