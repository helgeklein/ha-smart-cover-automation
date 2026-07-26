# v6.1

## Morning Opening

- Previously, morning opening only worked on the next day after evening closure. Now it also opens on the same day (useful for testing).
- If a cover's minimum position is set to 0 (closed), morning opening might close a cover from its evening closure position. Now, morning opening only moves a cover if its minimum position is more open than the current position.

## Notable Changes

- Migration from `get_astral_location` to `get_astral_observer` (mandated by Home Assistant, required as of 2027.7)
- Logging: include global and per-cover min/max positions

# v6.0

## What's New

### Heat Protection Mode

- This is a new setting that allows you to quickly control the heat protection functionality from the UI. Available settings:
    - Off
    - Auto
    - Forced (sunny windows)
    - Forced (all windows)

### Additional Evening Closure & Morning Opening Modes

- Evening closure now has the additional mode "before sunset".
- Morning opening now has the additional mode "before sunrise".

## Notable Changes

- New tilt drift tolerance setting.
- Manual tilt changes now trigger manual override mode, too.
- In passive reopening mode, a cover might stay closed after position drift.
- Allow partial reopening to heat protection position from evening closure fully closed position.

## Notes

### Refactor to Properly Track Automation-Managed State

- After an upgrade from an earlier version while covers are closed, it may be necessary to manually move covers to the open position once.

# v5.0

This release brings many quality-of-life features and flexibility improvements.

## What's New

### Per-Cover Sun Azimuth Tolerance & Min/Max Elevation

- These new settings allow you to configure the exact angles at which sunlight hits a cover from the left, right, top, or bottom.
- These settings are available per cover, making it possible to replicate your building's geometry precisely while taking nearby trees or neighboring buildings that cast shade into account.
- Result: The integration's heat protection can close covers accurately when they are exposed to the sun and open them otherwise.

### Night Silence (Pre-Closure)

- In the evening before a hot, sunny day, pre-close covers that the sun will shine on the next morning.
- This avoids cover movements early in the morning while you're still sleeping.

### Quality-of-Life

- **Active/passive reopening modes:** Configure whether the integration should always reopen covers that were closed manually after the override duration has elapsed, or only reopen covers that were previously closed by the integration.
- **Heat protection:** Never open a cover that is already more closed than its target position.

### Flexibility

- **Blocked time range:** New external control mode to configure the start and end times from your automation.

### Miscellaneous

- **Delay between covers:** Delay the start of each cover movement relative to the next within the same automation cycle.
- **Weather forecast:** Store the day's minimum and maximum temperatures instead of using the next day's forecast after the afternoon cutoff time.
- **Cover opening:** When fully opening a cover, use `open_cover` instead of `set_cover_position` to fix position issues with some types of blinds.
- **Options flow:** Show friendly names instead of entity IDs in the configuration wizard.

# v4.0

## What's New

### Tilt Angle Improvements

- The **horizontal and vertical tilt positions** can now be configured. This helps with covers that don't follow HA's conventions where 100 means horizontal and 0 means vertical.

- A **tilt open to cover open delay** allows you to configure a wait time between changing the tilt angle and moving the cover up or down.

### Offline Use

- The integration caches the weather forecast response for situations when internet connectivity is unavailable. When offline, the integration continues to work as well as is possible under the circumstances.

### External Mode for Evening Closure Time

- This mirrors the existing functionality for the morning opening time. It allows you to control the evening closure time from your own **automation**. This new mode is in addition to the existing modes absolute time and relative to sunset.

**Full Changelog**: https://github.com/helgeklein/ha-smart-cover-automation/compare/v3.0...v4.0

# v3.0

## What's New

### Morning opening time

- Specifies at which time in the morning covers closed via the integration's evening closure functionality should be reopened again.
- Several modes available:
  - Absolute time
  - Relative to sunrise
  - Externally controlled

### Heat protection: minimum + maximum temperatures

- Previously, the heat protection mode would only rely on the maximum daily temperature.
- This has been complemented by the minimum daily temperature.
- This prevents heat protection from closing covers when the nights are cool enough to drain off excessive heat.

### Evening closure improvements

- You can now set the cover positions for the night independently of the daily min/max positions.
- A new setting allows the integration to re-close covers that are manually opened during the night (after manual override duration has elapsed).

### Automatic reopening during the day

- A new configuration options lets you choose how covers are reopened when closing conditions no longer apply:
  - Active: Always reopens covers.
  - Passive: Only reopens covers that were previously closed by automation. In this mode, covers that were closed manually are not reopened.
  - Off: Disables automatic reopening.
- With the default setting (passive), home occupants retain control. When someone closes a cover, e.g. for privacy reasons, it stays closed until manually re-opened.

## Requirements

- The integration now requires **Home Assistant 2026.4.1**.


**Full Changelog**: https://github.com/helgeklein/ha-smart-cover-automation/compare/v2.0.0...v3.0

# v2.0.0

## What's New

This release adds additional external control options to further increase the integration's flexibility.

### Weather hot? (external control)

- If you enable this binary switch, the integration stops using the weather forecast to determine if it’s hot. In its stead, it uses the state of this switch.
- Available as global and per-cover entities to allow for individual control per room.

### Tilt angle (external control)

- Allows you to set the tilt angle of covers with adjustable slats from your own automation.
- The integration creates additional (fully-managed) entities that receive the tilt angle.
- Available as global and per-cover entities.

**Full Changelog**: https://github.com/helgeklein/ha-smart-cover-automation/compare/v1.3.1...v2.0.0

# v1.3.1

## What's Changed

* **Evening closure:**
  * Optionally ignore manual override
  * Apply tilt after evening closure
* **Cover position drift resilience:** don't interpret position inaccuracies as manual overrides

**Full Changelog**: https://github.com/helgeklein/ha-smart-cover-automation/compare/v1.3.0...v1.3.1

# v1.3.0

## What's New

### Tilt angle control

- Control the tilt angle of covers with horizontal slats
- Multiple modes for great flexibility
- Auto mode: block direct sunlight but allow seeing through as much as possible
- Different modes for day and night
- The mode can be specified globally and overridden per cover

### External control for sunny weather

- Additional binary switch (disabled by default).
- If you enable it, the integration stops using the weather forecast to determine if it’s sunny.
- In its stead, it uses the state of this switch.
- To go back to the weather forecast, simply disable it again.

### Evening closure: absolute time

- Previously, the evening closure time was specified relative to the sunset.
- Now, you can alternatively specify a fixed time at which to close covers for the night.

**Full Changelog**: https://github.com/helgeklein/ha-smart-cover-automation/compare/v1.2.0...v1.3.0

# v1.2.0

## What's New

### Grouping

- Maintain configurations for windows with different heat or sun protection requirements by setting up **multiple instances** of the extension.

### Misc. Improvements

- **Evening closure:** improved reliability
- Weather entity: **Fahrenheit** support
- Removed temperature thresholds to facilitate testing in colder seasons
- Fixed options flow error when the user doesn't expand sections in step 3

**Full Changelog:** https://github.com/helgeklein/ha-smart-cover-automation/compare/v1.1.0...v1.2.0

# v1.1.0

## What's Changed

- **Lock mode** for wind or hail protection, and other scenarios (#20)
    - Move the covers to opened or closed state and keep them there.
    - Alternatively, lock the covers in their current position.
    - Can be triggered as an action, e.g., when a warning is received from a weather service.
- Moved several **settings from the config flow to UI entities** (#23)
  - By moving dynamic settings to UI entities, we not only improve UX but also make it possible to change them from automations.
- Code refactoring for improved state management
- Test refactoring

# v1.0.0

First production release!

## What's Changed From Beta 3

* Evening closure functionality
* Fine-tuning of thresholds and translations
* Bugfixes

# v0.9.0-beta.3

Various improvements and bugfixes from beta 2, most notably:

- **Lockout protection**
- Two **new sensors**:
  - Nighttime open block
  - Automation disabled time
- Extensive refactoring of the coordinator code
- Tests:
  - Options flow scenarios
  - HA integration test, with actual loading of the integration by Home Assistant
# v0.8.0-beta.2

Various improvements and bugfixes from beta 1, most notably:

- Cover movements are logged to Home Assistant's **activity logbook**
- Weather forecasts for hot day calculation now uses the next day's forcast after a cutoff time (in the afternoon)
- Added **time-based exceptions**:
  - Disable automatic cover opening during nighttime
  - The automation can be disabled in any given time range

# v0.7.0-beta.1

First release, primarily for testing. Use with caution.