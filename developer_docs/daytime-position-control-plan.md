# Daytime Control Plan

## Goal

Make normal daytime cover behavior configurable when no higher-priority automation rule applies. Heat protection and evening closure retain priority; this proposal controls normal daytime behavior outside those modes.

## Settings

The following runtime-configurable selects belong together under **Cover Settings**.

### Daytime Control Mode

Rename the user-facing **Automatic Reopening** setting to **Daytime Control Mode**. It decides whether the integration may control a cover during normal daytime operation.

- **Active:** Control every eligible cover when normal daytime control applies.
- **Passive:** Control only covers that were previously moved by the integration and are at their last integration-set position. A manually moved cover stays where it is.
- **Off:** Do not automatically control covers during normal daytime operation.

UI description: "Choose which covers normal daytime control may move. Active can move every eligible cover. Passive can move only covers that were previously moved by the integration and are at their last integration-set position. Off does not move covers."

Keep the stored key and entity unique ID `automatic_reopening_mode` for backward compatibility. Rename only the user-facing select class, labels, descriptions, and documentation.

### Daytime Strategy

Add a runtime-configurable select that defines the cover position normal daytime control tries to reach after the cover is eligible for automation. Configure it in a new required **Step 3: Daytime Strategy** of the configuration wizard. The initial strategies are:

UI description: "Choose how the integration should position covers during the day when heat protection is not active."

Option descriptions:

- **Let light in:** "Move the cover toward its minimum cover position to let daylight into the room."
- **Privacy:** "Move the cover toward its maximum cover position to reduce visibility into the room."
- **External control:** "Use the position set in the daytime cover position: external control entity."

The strategy sets a target position only. **Daytime Movement Directions** still decides whether the integration may open, close, or move in either direction to reach that target.

For **Let light in**, the existing **Minimum cover position** is used. For **Privacy**, the existing **Maximum cover position** is used. For both strategies, the corresponding per-cover position overrides the global position.

#### External Control Position Entities

Follow the existing external-tilt pattern: external control is a number entity on the integration device, whose value is stored in the integration options and triggers an immediate coordinator refresh. It receives a target position from Home Assistant automations; it does not reference or poll another entity.

- **Daytime cover position: external control:** Created when the global Daytime Strategy is **External control**. Its value applies to every cover that uses the global strategy.
- **{Cover name}: Daytime cover position: external control:** Created when that cover overrides Daytime Strategy to **External control**. Its value applies only to that cover.

The numbers accept whole percentages from 0 to 100. `0` is fully closed and `100` is fully open. An external target must be explicitly set: when it is unavailable, the integration holds the affected cover and logs that the external daytime position is not set. It must not silently fall back to Minimum or Maximum cover position.

Step 3 configures the global Daytime Strategy and optional per-cover strategy overrides. A per-cover strategy overrides the global strategy. A cover using a per-cover **External control** strategy uses its per-cover external position number; otherwise an **External control** global strategy uses the global external position number.

Insert the new step before the current position settings. Renumber the existing wizard steps as follows:

| Current step | New step |
| --- | --- |
| Step 3: Max/Min Positions | Step 4: Max/Min Positions |
| Step 4: Tilt Angle Control | Step 5: Tilt Angle Control |
| Step 5: Additional Settings and Window Sensors | Step 6: Additional Settings and Window Sensors |
| Step 6: Time Settings | Step 7: Time Settings |

### Daytime Movement Directions

Add a runtime-configurable select that limits which movements the selected daytime strategy may make after daytime control is allowed.

- **Open only** (default): Move only to open the cover. This preserves current behavior.
- **Close only:** Move only to close the cover.
- **Open and close:** Move in either direction.

Proposed UI description: "When normal daytime control is allowed, choose whether it may open covers, close covers, or both."

For **Let light in** with a Minimum cover position of 70%, and **Privacy** with a Maximum cover position of 30%:

| Current position | Open only | Close only | Open and close |
| --- | --- | --- | --- |
| 30%, Let light in | Open to 70% | Hold | Open to 70% |
| 100%, Let light in | Hold | Close to 70% | Close to 70% |
| 70%, Privacy | Hold | Close to 30% | Close to 30% |
| 0%, Privacy | Open to 30% | Hold | Open to 30% |

## Decision Model

Manual override is evaluated before the daytime settings. When an external position or tilt change is detected, the integration skips that cover for the configured manual override duration. This applies to every Daytime Control Mode and every Daytime Movement Directions option. The existing evening-closure setting may bypass manual override during its initial closing trigger.

After the manual override duration ends, when applicable, and when heat protection, evening closure, and other higher-priority rules do not apply, evaluate the daytime settings in this order:

1. **Daytime Control Mode** decides whether this cover may be controlled. Active allows control. Passive requires that the cover was previously moved by the integration and is at its last integration-set position. Off prevents control.
2. **Daytime Strategy** determines the desired daytime position: Minimum cover position for Let light in, Maximum cover position for Privacy, or the relevant external-control number for External control.
3. **Daytime Movement Directions** decides whether the required opening or closing move is allowed.

For all strategies, a missing target results in no movement. The normal daytime rules do not use a fallback target from a different strategy.

The integration holds its current position when heat-protection inputs are indeterminate, during pre-closing, while morning reopening is blocked, when an external morning opening time is invalid, or when the applicable below-horizon guard prevents daytime movement. Lock mode and an active manual-override pause continue to take precedence.

## Implementation Scope

- Rename the existing `AutomaticReopeningModeSelect` user-facing class and translation text to Daytime Control Mode without changing the `automatic_reopening_mode` persisted identifier.
- Generalize the passive ownership check from a prior automation closure to any prior integration movement. This intentionally extends the current reopening-only behavior so that Passive mode also works after a daytime opening or closing movement.
- Add `DaytimeStrategy` with `LET_LIGHT_IN`, `PRIVACY`, and `EXTERNAL_CONTROL`, plus `DaytimeMovementDirection` with `OPEN_ONLY`, `CLOSE_ONLY`, and `OPEN_AND_CLOSE`.
- Add runtime-configurable config options, coordinator properties and setters, select entities, and translations for Daytime Strategy and Daytime Movement Directions. Support a global Daytime Strategy and optional per-cover strategy overrides.
- Insert a required `Step 3: Daytime Strategy` in the configuration wizard for the global strategy and per-cover overrides. Renumber the current position, tilt, additional-settings, and time-settings steps from 3-6 to 4-7 in the flow, constants, translations, and wizard documentation.
- Add global and per-cover external daytime-position number entities modelled on the existing external tilt number entities. Create each entity only when its matching global or per-cover strategy is External control. Persist their values as runtime-configurable options and refresh the coordinator when they change.
- In the normal daytime branch, resolve the strategy's desired position, compare it with the current position, and hold when the required direction is not enabled.
- When the external-control position is unset, hold the affected cover and emit a cover-specific debug log. Do not substitute a Minimum or Maximum cover position.
- Preserve the current default behavior with `Daytime Control Mode: Passive`, `Daytime Strategy: Let light in`, and `Daytime Movement Directions: Open only`.
- Keep all three settings in Cover Settings rather than the evening-closure configuration group.

## Translations

- Update every integration locale: `de`, `en`, `es`, `fr`, `it`, `nl`, `pl`, `pt`, `sv`, and `zh-CN`.
- Rename the existing `automatic_reopening_mode` config-flow and select-entity labels to **Daytime Control Mode** while preserving the persisted key. Replace reopening-focused help text with the approved control-mode description and translate the Active, Passive, and Off semantics.
- Add config-flow labels, help text, and option labels for **Daytime Strategy**: Let light in, Privacy, and External control. Use the approved shared option descriptions in the configuration flow and documentation.
- Add the **Daytime Movement Directions** select-entity label, help text, and option labels: Open only, Close only, and Open and close.
- Add global and per-cover number-entity names for **Daytime cover position: external control**, following the existing global/per-cover external tilt translation pattern.
- Add wizard section titles, field labels, option labels, and field descriptions for the new Step 3. Renumber translation keys and their references for the existing Steps 3-6 to Steps 4-7.
- Preserve translation-key and entity unique-ID compatibility where a change is only user-facing. New settings receive stable, descriptive keys from the start.

## Documentation

- Update `docs/configuration-wizard.md` with a new **Step 3: Daytime Strategy** section. Explain all three strategies, the global setting, optional per-cover overrides, external-control number entities, unset external-target behavior, and the relationship with Daytime Movement Directions.
- Renumber every affected wizard heading, cross-reference, and explanatory sentence: Max/Min Positions to Step 4, Tilt Angle Control to Step 5, Additional Settings and Window Sensors to Step 6, and Time Settings to Step 7.
- Update `docs/configuration-entities.md` under Cover Settings: rename **Automatic Reopening** to **Daytime Control Mode**, add the three mode descriptions and manual-override interaction, and add **Daytime Strategy** and **Daytime Movement Directions** using the approved user-facing descriptions.
- Document the global and per-cover **Daytime cover position: external control** number entities beside the existing external tilt controls. State their `0`-`100` range, creation conditions, precedence, automation use, and hold-on-unset behavior.
- Update existing references to automatic reopening so they use Daytime Control Mode terminology and accurately describe control after a prior integration movement. Do not edit generated `docs/_site` or `.jekyll-cache` files; regenerate them only through the normal documentation build.

## Tests

- Preserve existing normal daytime behavior with the default settings.
- Verify manual override pauses daytime control in every control mode, strategy, and direction combination until the configured duration ends.
- Verify after expiry that Daytime Control Mode Active controls every eligible cover. Verify Passive controls only a cover that was previously moved by the integration and is at its integration-set position; it must not control a manually repositioned cover or one without a prior integration movement. Verify Off holds position.
- Verify Let light in resolves the global or per-cover Minimum cover position; verify Privacy resolves the global or per-cover Maximum cover position.
- Verify Let light in and Privacy each move only in the directions enabled by Daytime Movement Directions.
- Verify External control uses the global number for the global strategy and a per-cover number for a per-cover External control strategy.
- Verify per-cover strategy overrides take precedence over the global strategy.
- Verify an unset External control number holds only the affected cover and does not fall back to Minimum or Maximum cover position.
- Verify the configuration flow exposes the new Step 3 and that the existing steps follow it in their new order.
- Verify the global and per-cover external-position number entities are created only for External control strategies and persist a changed value through a coordinator refresh.
- Validate translation files and build the documentation site so renamed labels, new entities, and renumbered wizard steps render correctly.
- Verify the existing manual-override, ownership, below-horizon, pre-closing, missing external-time, blocked-morning, indeterminate-weather, heat-protection, evening-closure, and lock-mode safeguards retain their precedence.