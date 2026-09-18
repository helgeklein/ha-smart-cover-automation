# Daytime Control Plan

## Scope

Make normal daytime cover behavior configurable. Daytime control applies only when no higher-priority rule applies: lock mode, evening closure, active heat protection, or missing required weather data while the sun is hitting the cover. This proposal does not change heat-protection or evening-closure criteria.

The default behavior must remain unchanged: **Daytime Control Mode: Passive**, **Daytime Strategy: Let light in**, and **Daytime Movement Directions: Open only**.

## Configuration

**Daytime Control Mode** remains an existing runtime configuration select on the integration device. **Daytime Strategy** and **Daytime Movement Directions** are new configuration-wizard settings only; they do not create runtime select entities.

### Daytime Control Mode

Rename the existing user-facing **Automatic Reopening** setting. It remains in its current configuration location and defines which covers normal daytime control may move.

| Option | Behavior |
| --- | --- |
| **Active** | Control every eligible cover. |
| **Passive** | Control only covers that were previously moved by the integration and are at their last integration-set position. A manually moved cover stays where it is. |
| **Off** | Do not automatically control covers during normal daytime operation. |

UI description: "Choose which covers normal daytime control may move. Active can move every eligible cover. Passive can move only covers that were previously moved by the integration and are at their last integration-set position. Off does not move covers."

### Daytime Strategy

This new wizard setting defines the position daytime control tries to reach. Configure the global strategy and optional per-cover overrides in the new required **Step 3: Daytime Strategy** of the configuration wizard.

Wizard description: "Choose how the integration should position covers during the day when heat protection is not active."

| Option | Target position | Shared description |
| --- | --- | --- |
| **Let light in** | Minimum cover position | "Move the cover toward its minimum cover position to let daylight into the room." |
| **Privacy** | Maximum cover position | "Move the cover toward its maximum cover position to reduce visibility into the room." |
| **External control** | External daytime-position number | "Use the position set in the daytime cover position: external control entity." |

For Let light in and Privacy, the relevant per-cover Minimum or Maximum cover position overrides the global setting. A per-cover Daytime Strategy overrides the global strategy.

### Daytime Movement Directions

This new wizard setting limits which movements the selected Daytime Strategy may make. It affects direction only, not the strategy's target position.

| Option | Behavior |
| --- | --- |
| **Open only** | Move only to open the cover. This preserves current behavior. |
| **Close only** | Move only to close the cover. |
| **Open and close** | Move in either direction. |

Wizard description: "When normal daytime control is allowed, choose whether it may open covers, close covers, or both."

For example, Let light in with a Minimum cover position of 70% opens a cover at 30% in Open only or Open and close mode. Privacy with a Maximum cover position of 30% closes a cover at 70% in Close only or Open and close mode.

## External Daytime Position

External control follows the existing external-tilt pattern: it is a number entity on the integration device, not a reference to another entity. Home Assistant automations write the target position to it; the value is stored in integration options and triggers an immediate coordinator refresh.

| Entity | Created when | Scope |
| --- | --- | --- |
| **Daytime cover position: external control** | The global Daytime Strategy is External control. | Every cover using the global strategy. |
| **{Cover name}: Daytime cover position: external control** | The cover overrides Daytime Strategy with External control. | That cover only. |

The number accepts whole percentages from 0 to 100: `0` is fully closed and `100` is fully open. An unset external target holds the affected cover and emits a cover-specific debug log. It never falls back to Minimum or Maximum cover position.

## Decision Flow

1. Apply existing higher-priority rules and guards. Lock mode, evening closure, active heat protection, and missing required weather data while the sun is hitting the cover prevent normal daytime control.
2. Apply manual override. An external position or tilt change skips that cover for the configured duration, regardless of the daytime settings. The existing evening-closure trigger may bypass manual override when configured.
3. Check normal daytime guards. Hold position during pre-closing, a blocked morning reopening period, a missing external morning opening time, or when the applicable below-horizon guard prevents movement.
4. Apply Daytime Control Mode. Active allows every eligible cover; Passive requires prior integration movement and the current position to match the integration-owned position; Off holds position.
5. Resolve the strategy target: Minimum cover position for Let light in, Maximum cover position for Privacy, or the relevant external number for External control. A missing target holds position.
6. Compare the current and target positions. Move only if the required opening or closing direction is enabled; existing minimum-position-delta rules still determine whether a command is sent.

## Configuration And Entities

- Keep the persisted `automatic_reopening_mode` key and entity unique ID for backward compatibility; rename only its user-facing select class, labels, descriptions, and documentation to Daytime Control Mode.
- Add stable, non-runtime config keys for `DaytimeStrategy` (`LET_LIGHT_IN`, `PRIVACY`, `EXTERNAL_CONTROL`) and `DaytimeMovementDirection` (`OPEN_ONLY`, `CLOSE_ONLY`, `OPEN_AND_CLOSE`). They are changed only through the configuration wizard and take effect when the updated configuration reloads the integration.
- Add global Daytime Strategy plus optional per-cover strategy overrides in the wizard. A per-cover External control strategy uses its per-cover external-position number; otherwise External control uses the global number.
- Keep Daytime Control Mode as the existing runtime select and configuration field; do not move it into the new l 3. Add only global/per-cover external daytime-position number entities as new runtime entities. Create each number only for the relevant External control strategy, following external tilt lifecycle behavior.
- Insert **Step 3: Daytime Strategy** before position settings. Renumber the existing steps in the flow, constants, translations, and wizard documentation. The current Time Settings step, including the existing Daytime Control Mode field, moves from Step 6 to Step 7.

| Current step | New step |
| --- | --- |
| Step 3: Max/Min Positions | Step 4: Max/Min Positions |
| Step 4: Tilt Angle Control | Step 5: Tilt Angle Control |
| Step 5: Additional Settings and Window Sensors | Step 6: Additional Settings and Window Sensors |
| Step 6: Time Settings | Step 7: Time Settings |

- Generalize the passive ownership check from an automation closure to any integration movement so Passive works after daytime openings and closings.
- Resolve the selected strategy and allowed direction in the normal daytime branch without changing the precedence of existing guards.

## Translations And Documentation

- Update all integration locales: `de`, `en`, `es`, `fr`, `it`, `nl`, `pl`, `pt`, `sv`, and `zh-CN`. Include the new Step 3 titles, fields, option labels, and wizard descriptions; the renamed Daytime Control Mode select and its existing configuration field; and global/per-cover external number names.
- Preserve translation-key and entity-ID compatibility for renamed user-facing settings. Give all new settings stable descriptive keys.
- Update `docs/configuration-wizard.md` with Step 3, all strategy choices, per-cover overrides, external-position entities, unset-target behavior, movement directions, and Steps 4-7 renumbering.
- Update `docs/configuration-entities.md` with the renamed Daytime Control Mode, its manual-override behavior, and the global/per-cover external-position numbers including range, creation conditions, precedence, and automation use. Keep Daytime Strategy and Daytime Movement Directions in the configuration-wizard guide because they are wizard-only settings.
- Replace existing automatic-reopening references with Daytime Control Mode terminology and ownership behavior. Modify only documentation sources; regenerate `docs/_site` and `.jekyll-cache` through the normal documentation build.

## Verification

- Preserve the default normal daytime behavior.
- Test the control-mode matrix: Active moves every eligible cover, Passive requires a prior integration movement and its owned position, and Off holds position.
- Test manual-override pause and expiry for every daytime control mode. Confirm the existing evening-closure bypass remains limited to its initial trigger.
- Test all strategies with all permitted movement directions, including per-cover Minimum/Maximum position overrides.
- Test global and per-cover External control target resolution, strategy precedence, entity creation/removal, immediate refresh after a value change, and hold-on-unset behavior.
- Test the new wizard Step 3 and the renumbered Steps 4-7. Verify Daytime Strategy and Daytime Movement Directions are configured only through the wizard and have no select entities.
- Validate all translation files and build the documentation site so labels, entities, and wizard steps render correctly.
- Retain coverage for lock mode, heat protection, evening closure, indeterminate weather, pre-closing, morning guards, below-horizon checks, ownership, and movement delta behavior.