# Daytime Control Plan

## Scope

Make normal daytime cover behavior configurable without changing the criteria for heat protection or evening closure. Daytime control runs only after lock mode, evening closure, active heat protection, and missing required weather data while the sun hits the cover have held the cover in place.

The defaults are **Daytime Control Mode: Passive**, **Daytime Strategy: Let light in**, and **Daytime Movement Directions: Open only**. Passive intentionally treats every successful integration movement as ownership, so it supports subsequent daytime openings and closings.

## Settings

| Setting | Location | Scope | Default |
| --- | --- | --- | --- |
| **Daytime Control Mode** | Existing integration-device select and current Time Settings field | Runtime configurable | Passive |
| **Daytime Strategy** | New required wizard Step 3 | Global, with optional per-cover overrides | Let light in |
| **Daytime Movement Directions** | New required wizard Step 3 | Global only | Open only |

Rename the existing user-facing **Automatic Reopening** select to **Daytime Control Mode**. Keep its persisted `automatic_reopening_mode` key and entity unique ID for compatibility. The two new settings are changed only through the initial and options-flow wizards, take effect after integration reload, and do not create select entities.

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

Per-cover Minimum or Maximum cover position values apply to Let light in and Privacy. A per-cover Daytime Strategy overrides the global strategy. A per-cover External control strategy uses its own number; otherwise External control uses the global number.

### Daytime Movement Directions

| Option | Behavior |
| --- | --- |
| **Open only** | Allow only opening movements. |
| **Close only** | Allow only closing movements. |
| **Open and close** | Allow movements in either direction. |

Description: "When normal daytime control is allowed, choose whether it may open covers, close covers, or both." This setting only filters the strategy target's required direction; there are no per-cover direction overrides.

## External Daytime Position

External control follows the external-tilt pattern: Home Assistant automations write a whole-number percentage to an integration `number` entity, which stores the value in integration options and immediately refreshes the coordinator. It is not a reference to another entity.

| Entity | Creation rule |
| --- | --- |
| **Daytime cover position: external control** | One global entity whenever the global strategy is External control, including when every cover overrides it. It serves covers that inherit the global strategy. |
| **{Cover name}: Daytime cover position: external control** | One entity for each cover whose strategy override is External control. Remove it on reload when that override changes. |

The valid range is 0 through 100, where `0` is fully closed and `100` is fully open. An unset target holds that cover, emits a cover-specific debug log, and never falls back to Minimum or Maximum cover position.

## Runtime Behavior

1. Apply existing higher-priority guards: lock mode, evening closure, active heat protection, and missing required weather data while the sun hits the cover.
2. Apply the existing manual-override pause. An external position or tilt change skips that cover for its configured duration. The existing evening-closure trigger may still bypass manual override when configured.
3. Apply existing normal-daytime guards: pre-closing, blocked morning reopening, missing external morning opening time, and applicable below-horizon checks.
4. Apply Daytime Control Mode. In Passive, record or update the integration-owned position after every successful integration move and require the current position to match it within the existing drift tolerance.
5. Resolve the strategy target. A missing external target holds the cover.
6. Move only when the required direction is enabled and the existing minimum-position-delta rule permits a command.

## Implementation

- Add non-runtime `DaytimeStrategy` keys: `LET_LIGHT_IN`, `PRIVACY`, and `EXTERNAL_CONTROL`; and `DaytimeMovementDirection` keys: `OPEN_ONLY`, `CLOSE_ONLY`, and `OPEN_AND_CLOSE`.
- Add the global strategy, optional per-cover strategy overrides, and global-only movement directions to both configuration wizards as new Step 3. Shift Max/Min Positions to Step 4, Tilt Angle Control to Step 5, Additional Settings and Window Sensors to Step 6, and Time Settings to Step 7.
- Keep Daytime Control Mode in its current runtime select and Time Settings field. Add only the required global and per-cover external daytime-position number entities at runtime.
- Generalize integration ownership from an automation closure to any successful integration movement. Resolve strategy and direction only in the normal daytime branch; preserve all existing guard precedence.

## Translations And Documentation

- Update `de`, `en`, `es`, `fr`, `it`, `nl`, `pl`, `pt`, `sv`, and `zh-CN` with the Step 3 fields and options, renamed Daytime Control Mode, and external-number names. Preserve existing translation keys and entity IDs where applicable.
- Update `docs/configuration-wizard.md` for Step 3, strategy overrides, movement directions, external target behavior, and renumbered steps.
- Update `docs/configuration-entities.md` only for the renamed Daytime Control Mode and external-position numbers, including range, lifecycle, precedence, and automation use.
- Replace human-facing Automatic Reopening wording with Daytime Control Mode. Modify documentation sources only; regenerate `docs/_site` and `.jekyll-cache` through the usual build.

## Verification

- Cover the Active, Passive, and Off control-mode matrix, including Passive ownership after daytime openings and closings, manual changes, drift tolerance, and Active re-establishment of ownership.
- Cover each strategy with every allowed direction, per-cover Minimum/Maximum positions, and all existing higher-priority and normal-daytime guards.
- Cover global and per-cover External control precedence, number-entity creation and removal, updates, unset targets, immediate refresh, and debug logging.
- Cover the initial and options-flow Step 3, Steps 4-7 renumbering, absence of new select entities, all translations, and documentation-site generation.