# Daytime Control Plan

## Scope

Make normal daytime cover behavior configurable without changing the criteria for heat protection or evening closure. Daytime control continues until lock mode, evening closure, active heat protection, or missing required weather data while the sun hits the cover takes precedence. At or below the horizon, the existing opening guard holds opening targets, while closing targets may still apply.

The defaults are **Daytime Control Mode: Passive**, **Daytime Strategy: Let light in**, and **Daytime Movement Directions: Open only**. Passive intentionally treats every successful integration position command as ownership, so it supports subsequent daytime openings and closings.

## Settings

| Setting | Location | Scope | Default |
| --- | --- | --- | --- |
| **Daytime Control Mode** | Existing integration-device select | Runtime configurable | Passive |
| **Daytime Strategy** | New required wizard Step 3 | Required global setting, with optional per-cover overrides | Let light in |
| **Daytime Movement Directions** | New required wizard Step 3 | Required global setting only | Open only |

Rename the existing user-facing **Automatic Reopening** select to **Daytime Control Mode**. Keep its persisted `automatic_reopening_mode` key and entity unique ID for compatibility. Remove this setting from the Time Settings wizard schema, input handling, and config-flow translations; the integration-device select is its only user-facing control. The two new settings are changed only through the options-flow wizard, take effect after integration reload, and do not create select entities.

### Daytime Control Mode

| Option | Behavior |
| --- | --- |
| **Active** | Move every eligible cover. |
| **Passive** | Move only a cover previously moved by the integration that remains at its integration-owned position. A manual change outside the existing drift tolerance blocks Passive until the cover returns to that position or Active moves it again. |
| **Off** | Do not move covers during normal daytime operation. |

Description: "Choose which covers normal daytime control may move. Active can move every eligible cover. Passive can move only covers previously moved by the integration that are at their last integration-set position. Off does not move covers."

### Daytime Strategy

| Option | Target |
| --- | --- |
| **Let light in** | Minimum cover position |
| **Privacy** | Maximum cover position |
| **External control** | Relevant external daytime-position number |

Description: "Choose how the integration should position covers during the day when heat protection is not active."

The global selector is required. Per-cover overrides are optional in a collapsible section. Per-cover Minimum or Maximum cover position values apply to Let light in and Privacy. A per-cover Daytime Strategy overrides the global strategy. Include a UI-only **Use global setting** choice as the default in every per-cover selector; selecting it removes the `{cover_entity_id}_daytime_strategy` option instead of persisting a sentinel value. A per-cover External control strategy uses its own number; otherwise External control uses the global number.

Let light in and Privacy use the Minimum and Maximum cover positions configured in Step 4. External control creates its target number only after the wizard is saved and the integration reloads.

### Daytime Movement Directions

| Option | Behavior |
| --- | --- |
| **Open only** | Allow only opening movements. |
| **Close only** | Allow only closing movements. |
| **Open and close** | Allow movements in either direction. |

Description: "When normal daytime control is allowed, choose whether it may open covers, close covers, or both." This setting only filters the strategy target's required direction; there are no per-cover direction overrides. When a target requires a disabled direction, the cover holds its current position; no alternate target is selected.

## External Daytime Position

External control follows the external-tilt pattern: Home Assistant automations write a whole-number percentage to an integration `number` entity, which stores the value in integration options and immediately refreshes the coordinator. It is not a reference to another entity.

| Entity | Creation rule |
| --- | --- |
| **Daytime cover position: external control** | One global entity whenever the global strategy is External control, including when every cover overrides it. It serves covers that inherit the global strategy. |
| **{Cover name}: Daytime cover position: external control** | One entity for each cover whose strategy override is External control. |

When a strategy no longer uses External control, remove its integration-created number entity and stored value during integration reload, matching the existing external tilt and time cleanup lifecycle. The valid range is 0 through 100, where `0` is fully closed and `100` is fully open. An unset target holds that cover, emits a cover-specific debug log, and never falls back to Minimum or Maximum cover position.

## Runtime Behavior

1. Apply existing higher-priority guards: lock mode, evening closure, active heat protection, and missing required weather data while the sun hits the cover.
2. Apply the existing manual-override pause. An external position or tilt change skips that cover for its configured duration. The existing evening-closure trigger may still bypass manual override when configured.
3. Apply existing normal-daytime guards: pre-closing, blocked morning reopening, and a missing external morning opening time.
4. Apply Daytime Control Mode. In Passive, require the current position to match its integration-owned position within the existing drift tolerance.
5. Resolve the strategy target. A missing external target holds the cover, otherwise derive its required opening or closing direction.
6. At or below the horizon, retain the existing opening guard: hold an opening target but allow a closing target to continue. Apply Daytime Movement Directions to the remaining target.
7. For an opening target immediately after heat protection, retain the existing tilt-to-cover-open delay when automatic daytime tilt and a positive delay are configured. A hold or closing target clears a pending delayed reopen.
8. Send a position command only when the target remains allowed and the existing minimum-position-delta rule permits it. After every successful integration position command, record its position as owned under the command's control mode: normal daytime uses `DAYTIME_CONTROL`; Heat Protection, Evening Closure, and Lock retain their existing modes. All four modes satisfy Passive ownership eligibility.

## Implementation

- Add `ConfKeys.DAYTIME_STRATEGY` (`daytime_strategy`) and `ConfKeys.DAYTIME_MOVEMENT_DIRECTIONS` (`daytime_movement_directions`) with enum converters, defaults of `LET_LIGHT_IN` and `OPEN_ONLY`, and corresponding `ResolvedConfig` fields. The defaults ensure existing entries retain the new default configuration.
- Add `DaytimeStrategy`: `LET_LIGHT_IN`, `PRIVACY`, and `EXTERNAL_CONTROL`; and `DaytimeMovementDirections`: `OPEN_ONLY`, `CLOSE_ONLY`, and `OPEN_AND_CLOSE`. Add `COVER_SFX_DAYTIME_STRATEGY` (`daytime_strategy`) for optional per-cover strategy overrides.
- Add `AutomationMode.DAYTIME_CONTROL` for durable daytime position ownership. Persist and restore it through the existing `AutomationManagedState`; do not map it to a legacy "closed by automation" reason. Keep the existing Heat Protection, Evening Closure, and Lock modes for their follow-up transitions.
- Add `NUMBER_KEY_DAYTIME_EXTERNAL_POSITION` (`daytime_external_position`) and `NUMBER_KEY_COVER_DAYTIME_EXTERNAL_POSITION` (`cover_daytime_external_position`) for the global and per-cover number translation keys. Store the global value under `daytime_external_position` and each per-cover value under `{cover_entity_id}_daytime_external_position`.
- Register the global external-position key and the per-cover `_daytime_external_position` suffix with the runtime-configurable-key checks so number updates refresh the coordinator without reloading. The two wizard settings remain non-runtime and require reload.
- Extend the existing stale external-entity cleanup helpers to recognize global and per-cover daytime external-position keys. On reload, remove stale daytime number entity-registry entries and their stored option values.
- Add the required global strategy and global-only movement-direction selectors to the configuration wizard as new Step 3. Add optional per-cover strategy overrides in a collapsible section; every selector defaults to a UI-only Use global setting choice that clears the override. Shift Max/Min Positions to Step 4, Tilt Angle Control to Step 5, Additional Settings and Window Sensors to Step 6, and Time Settings to Step 7.
- Remove Daytime Control Mode from the Time Settings wizard schema and its translations. Keep it only as the renamed runtime select on the integration device. Add only the required global and per-cover external daytime-position number entities at runtime.
- Generalize integration ownership from an automation closure to every successful integration position command. Set `DAYTIME_CONTROL` only for a normal-daytime position command; do not grant position ownership for tilt-only movements. Preserve `HEAT_PROTECTION`, `EVENING_CLOSURE`, and `LOCK` when their position commands establish ownership; all four modes make a cover eligible for Passive. Resolve strategy and direction only in the normal daytime branch; preserve all existing guard precedence.

## Translations And Documentation

- Update `de`, `en`, `es`, `fr`, `it`, `nl`, `pl`, `pt`, `sv`, and `zh-CN` with the Step 3 fields and options, renamed Daytime Control Mode, and external-number names. Preserve existing translation keys and entity IDs where applicable.
- Update `docs/configuration-wizard.md` for Step 3, required global fields, optional per-cover overrides, its Step 4 position dependency, Use global setting behavior, direction no-ops, external-target availability after reload, and renumbered steps. Remove Daytime Control Mode from Time Settings. Replace every current Automatic Reopening reference there with a short reference to the device-page Daytime Control Mode and its effect on normal daytime movement, including morning reopening after evening closure.
- Update `docs/configuration-entities.md` only for the renamed Daytime Control Mode and external-position numbers, including range, lifecycle, precedence, and automation use.
- Replace human-facing Automatic Reopening wording with Daytime Control Mode. Describe all external tilt, time, and daytime-position entities consistently: when their controlling mode changes, integration reload removes the entity and stored value. Modify documentation sources only; regenerate `docs/_site` and `.jekyll-cache` through the usual build.

## Verification

- Cover the Active, Passive, and Off control-mode matrix, including Passive ownership after daytime openings and closings, manual changes, drift tolerance, restart persistence, tilt-only movements, and Active re-establishment of ownership. Verify that normal daytime moves use `DAYTIME_CONTROL` without overwriting Heat Protection, Evening Closure, or Lock ownership modes and their follow-up transitions.
- Cover each strategy with every allowed direction, per-cover Minimum/Maximum positions, all existing higher-priority and normal-daytime guards, below-horizon behavior, and the heat-protection tilt-to-cover-open delay.
- Cover global and per-cover External control precedence, number creation, stale entity and option cleanup after reload, updates, unset targets, immediate refresh, and debug logging.
- Cover the options-flow Step 3: required global fields, optional per-cover section, default and clearing behavior of Use global setting, Step 4 target dependencies, and direction no-ops. Cover removal of Daytime Control Mode from Time Settings, its continued device-page select behavior, Steps 4-7 renumbering, all translations, and documentation-site generation.