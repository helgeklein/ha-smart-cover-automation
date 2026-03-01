# Tilt Angle Control — Implementation Analysis

## 1. Feature Overview

Tilt angle control is for covers composed of horizontal slats (e.g., Venetian blinds) whose tilt angle can be varied. The Home Assistant cover platform represents tilt as a **0–100 percentage** (not degrees), where:

- **0** = fully closed (slats vertical, blocking all light)
- **100** = fully open (slats horizontal, letting maximum light through)

### User-Facing Tilt Modes

The integration will offer four tilt control modes, configured globally and optionally overridden per cover:

| Mode | Behavior (Day) | Behavior (Night / Evening Closure) |
|---|---|---|
| **Open** | Set tilt to 100 (horizontal — let light in) | Set tilt to 100 |
| **Closed** | Set tilt to 0 (vertical — block light completely) | Set tilt to 0 |
| **Manual** | After moving a cover, restore the manually set tilt angle | After moving a cover, restore the manually set tilt angle |
| **Auto** | Dynamically block direct sunlight (see §5) | N/A — falls back to **Closed** at night |

---

## 2. Configuration (Options Flow)

### 2.1 New Step: Step 4 (between current steps 3 and 4)

The current flow is 5 steps. Insert a tilt configuration step after step 3 (min/max positions), making the flow **6 steps**. The current steps 4 and 5 become steps 5 and 6.

**Step renumbering:**

| Old Step | New Step | Content |
|---|---|---|
| 1 (init) | 1 (init) | Cover & weather selection |
| 2 | 2 | Azimuth per cover |
| 3 | 3 | Min/max positions |
| — | **4 (new)** | **Tilt angle control** |
| 4 | 5 | Window sensors |
| 5 | 6 | Time settings |

### 2.2 New Step UI Layout

Model on current step 3 (global settings at top, per-cover overrides in collapsible sections):

```
┌────────────────────────────────────────────────────────┐
│ Smart Cover Automation — Step 4 of 6                   │
│                                                        │
│ Configure tilt angle control for covers with           │
│ tiltable slats (optional).                             │
│                                                        │
│ Cover tilt angle control (day):     [Open ▼]           │
│ Cover tilt angle control (night):   [Closed ▼]         │
│ Minimum tilt change:                [5] %              │
│ Slat overlap ratio (d/L):           [0.9]              │
│                                                        │
│ ▶ Per-cover tilt angle control (day)    [collapsed]     │
│ ▶ Per-cover tilt angle control (night)  [collapsed]     │
└────────────────────────────────────────────────────────┘
```

**Key UI behavior:** Only covers that support tilt (`CoverEntityFeature.SET_TILT_POSITION`) are shown in the per-cover sections. Tilt support is detected by checking the cover entity's `supported_features` attribute at schema build time.

### 2.3 New Constants (`const.py`)

```python
# Per-cover configuration key suffixes (tilt)
COVER_SFX_TILT_MODE_DAY: Final[str] = "cover_tilt_mode_day"
COVER_SFX_TILT_MODE_NIGHT: Final[str] = "cover_tilt_mode_night"

# Options flow section names (step 4)
STEP_4_SECTION_TILT_DAY: Final[str] = "section_tilt_day"
STEP_4_SECTION_TILT_NIGHT: Final[str] = "section_tilt_night"
```

Update existing section constants to reflect renumbering:

```python
# Rename STEP_4_SECTION_WINDOW_SENSORS → STEP_5_SECTION_WINDOW_SENSORS
STEP_5_SECTION_WINDOW_SENSORS: Final[str] = "section_window_sensors"
# Rename STEP_5_SECTION_* → STEP_6_SECTION_*
STEP_6_SECTION_TIME_RANGE: Final[str] = "section_time_range"
STEP_6_SECTION_CLOSE_AFTER_SUNSET: Final[str] = "section_close_after_sunset"
```

> **Note on renaming:** The step-number prefix in these constants is a code readability convention only — the string values (e.g., `"section_window_sensors"`) are stored in the HA config entry and in translations. **Do NOT change the string values** or it will break existing installations. Only rename the Python constant identifiers.

### 2.4 New Tilt Mode Enum (`const.py`)

```python
class TiltMode(StrEnum):
    """Tilt angle control mode for covers with tiltable slats."""

    OPEN = "open"           # Horizontal position — let light in (tilt = 100)
    CLOSED = "closed"       # Vertical position — block light (tilt = 0)
    MANUAL = "manual"       # Restore manually set angle after cover movement
    AUTO = "auto"           # Dynamically block direct sunlight
```

### 2.5 New Config Keys (`config.py`)

Add to `ConfKeys`:

```python
TILT_MODE_DAY = "tilt_mode_day"            # Global tilt mode during daytime
TILT_MODE_NIGHT = "tilt_mode_night"        # Global tilt mode at night / evening closure
TILT_MIN_CHANGE_DELTA = "tilt_min_change_delta"  # Minimum tilt change (%) to actually send a service call
TILT_SLAT_OVERLAP_RATIO = "tilt_slat_overlap_ratio"  # Slat spacing/width ratio (d/L) for Auto tilt calculation
```

Add to `CONF_SPECS`:

```python
ConfKeys.TILT_MODE_DAY: _ConfSpec(default="open", converter=_Converters.to_str),
ConfKeys.TILT_MODE_NIGHT: _ConfSpec(default="closed", converter=_Converters.to_str),
ConfKeys.TILT_MIN_CHANGE_DELTA: _ConfSpec(default=5, converter=_Converters.to_int),
ConfKeys.TILT_SLAT_OVERLAP_RATIO: _ConfSpec(default=0.9, converter=_Converters.to_float),
```

Add corresponding fields to `ResolvedConfig`:

```python
tilt_mode_day: str              # "open", "closed", "manual", "auto"
tilt_mode_night: str            # "open", "closed", "manual", "auto"
tilt_min_change_delta: int      # Minimum tilt change (%) to send a service call (default: 5)
tilt_slat_overlap_ratio: float  # Slat spacing/width ratio d/L for Auto mode (default: 0.9)
```

### 2.6 Config Flow Changes (`config_flow.py`)

#### New: `build_schema_step_4` for tilt

```python
@staticmethod
def build_schema_step_4_tilt(
    covers: list[str],
    defaults: Mapping[str, Any],
    resolved_settings: ResolvedConfig,
    hass: Any,
) -> vol.Schema:
```

This method:
1. Adds global `tilt_mode_day` and `tilt_mode_night` selectors (using `selector.SelectSelector` with the `TiltMode` options)
2. Detects which covers support tilt by checking `hass.states.get(cover).attributes.get("supported_features") & CoverEntityFeature.SET_TILT_POSITION`
3. For tilt-capable covers only, builds per-cover `tilt_mode_day` and `tilt_mode_night` selectors inside collapsible sections

#### Step renumbering

- Current `async_step_4` → `async_step_5`
- Current `async_step_5` → `async_step_6`
- New `async_step_4` handles tilt configuration

#### `_build_section_cover_settings` update

The method needs to handle the new tilt section names and suffixes:

```python
elif suffix in (const.COVER_SFX_TILT_MODE_DAY, const.COVER_SFX_TILT_MODE_NIGHT):
    section_names = {const.STEP_4_SECTION_TILT_DAY, const.STEP_4_SECTION_TILT_NIGHT}
```

#### `_finalize_and_save` update

Add the new tilt suffixes to the orphan cleanup:

```python
suffixes = (
    f"_{const.COVER_SFX_AZIMUTH}",
    f"_{const.COVER_SFX_MAX_CLOSURE}",
    f"_{const.COVER_SFX_MIN_CLOSURE}",
    f"_{const.COVER_SFX_WINDOW_SENSORS}",
    f"_{const.COVER_SFX_TILT_MODE_DAY}",      # new
    f"_{const.COVER_SFX_TILT_MODE_NIGHT}",     # new
)
```

### 2.7 Translations (`translations/en.json`)

Update step titles from "Step X of 5" → "Step X of 6". Add new step 4 translations:

```json
"4": {
    "title": "Smart Cover Automation - Step 4 of 6",
    "description": "Configure **tilt angle control** for covers with tiltable slats (optional).\nGlobal settings apply to all tilt-capable covers unless overridden per cover.",
    "data": {
        "tilt_mode_day": "Tilt angle control (day):",
        "tilt_mode_night": "Tilt angle control (night):",
        "tilt_min_change_delta": "Minimum tilt change:",
        "tilt_slat_overlap_ratio": "Slat overlap ratio (d/L):"
    },
    "data_description": {
        "tilt_mode_day": "How to control the tilt angle of cover slats during the day.",
        "tilt_mode_night": "How to control the tilt angle of cover slats at night (applied during evening closure).",
        "tilt_min_change_delta": "Minimum tilt change (%) required before sending a command. Prevents excessive motor wear from small adjustments.",
        "tilt_slat_overlap_ratio": "Ratio of slat spacing to slat width (0.5–1.0). Lower values mean more overlap between slats. The default of 0.9 works well for most venetian blinds. Only relevant for Auto mode."
    },
    "sections": {
        "section_tilt_day": {
            "name": "Per-cover tilt angle control (day)"
        },
        "section_tilt_night": {
            "name": "Per-cover tilt angle control (night)"
        }
    }
}
```

Add `TiltMode` selector translations:

```json
"selector": {
    "tilt_mode": {
        "options": {
            "open": "Open (horizontal — let light in)",
            "closed": "Closed (vertical — block light)",
            "manual": "Manual (restore manually set angle)",
            "auto": "Auto (block direct sunlight)"
        }
    }
}
```

---

## 3. Implementation — Setting the Tilt Angle

### 3.1 HA Interface Layer (`ha_interface.py`)

Add a new method to `HomeAssistantInterface`:

```python
async def set_cover_tilt_position(self, entity_id: str, tilt_position: int, features: int) -> int:
    """Set cover tilt position.

    Args:
        entity_id: The cover entity ID
        tilt_position: Target tilt (0=closed, 100=open)
        features: Cover's supported features bitmask

    Returns:
        The actual tilt position set

    Raises:
        ServiceCallError: If the service call fails
    """
```

This mirrors `set_cover_position()` but calls `SERVICE_SET_COVER_TILT_POSITION` with `ATTR_TILT_POSITION`. If the cover doesn't support `SET_TILT_POSITION`, fall back to `SERVICE_OPEN_COVER_TILT` / `SERVICE_CLOSE_COVER_TILT`.

Required imports to add:

```python
from homeassistant.components.cover import (
    ATTR_TILT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    CoverEntityFeature,
)
from homeassistant.const import (
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_CLOSE_COVER_TILT,
)
```

### 3.2 Cover Automation Logic (`cover_automation.py`)

#### 3.2.1 Tilt Mode Resolution

Add a helper method to `CoverAutomation` that resolves the effective tilt mode for a cover:

```python
def _get_effective_tilt_mode(self, is_night: bool) -> str | None:
    """Get the effective tilt mode for this cover.

    Checks per-cover override first, falls back to global setting.
    Returns None if the cover doesn't support tilt.
    """
```

The method:
1. Checks if the cover supports `CoverEntityFeature.SET_TILT_POSITION` — if not, returns `None`
2. Checks for per-cover override key (e.g., `cover.living_room_cover_tilt_mode_day`)
3. Falls back to global `resolved.tilt_mode_day` or `resolved.tilt_mode_night`

#### 3.2.2 Manual Tilt Tracking

For the **Manual** mode, we need to track the tilt position before the cover is moved:

- **Before** a cover position change: read `ATTR_CURRENT_TILT_POSITION` from the cover state
- **After** the position change: set the tilt back to the saved value

This can be stored alongside the position history or in a separate field on `CoverState`:

```python
@dataclass
class CoverState:
    # ... existing fields ...
    tilt_current: int | None = None         # Current tilt position
    tilt_target: int | None = None          # Target tilt position set by automation
```

#### 3.2.3 Auto Tilt Calculation — Formula Research & Decision

The goal is to calculate the optimal slat tilt that blocks direct sunlight while letting in as much diffuse daylight as possible. Three approaches were evaluated:

##### Approach A: Linear Mapping (Naive)

```
tilt% = sun_elevation * 100 / 90
```

Simple and predictable, but **far too conservative** — at 20° elevation it sets tilt to 22% (nearly closed), when the physics-correct answer is ~58% (mostly open). This unnecessarily blocks daylight.

##### Approach B: Full Slat Geometry (ha-smart-venetian-blinds)

The [ha-smart-venetian-blinds](https://github.com/herpaderpaldent/ha-smart-venetian-blinds) integration uses the physically correct formula for slat cut-off geometry:

1. **Horizontal Shadow Angle (HSA):** `HSA = sun_azimuth - facade_azimuth` (normalized to ±180°)
2. **Profile Angle (ω):** `ω = atan(tan(elevation) / cos(HSA))` — the vertical angle of the sun projected onto a plane perpendicular to the facade
3. **Slat cut-off angle (θ):** Solved from `sin(θ + ω) = (d/L) · cos(ω)` where `d` = slat spacing (bottom-to-bottom), `L` = slat width
4. **Convert to HA tilt %:** `tilt% = 100 · (1 - θ/90)`

This is **physically accurate** but requires the user to measure slat width and slat spacing — two measurements that most users won't know offhand or may measure incorrectly.

##### Approach C: Simplified Physics (Chosen)

Use the same trigonometric profile-angle formula as Approach B, but assume a **standard slat overlap ratio `d/L = 0.9`** instead of requiring user measurements. This ratio is representative of common venetian blinds (typical values: 0.84–0.92).

**Why d/L = 0.9 is a good default:**
- For real blinds with d/L ≈ 0.85, a 0.9 assumption closes slats slightly more than needed → small built-in safety margin
- For blinds with d/L ≈ 0.92, the result is nearly exact
- No user measurements required — just works out of the box

**Numerical comparison at 20° sun elevation / 0° HSA:**

| Approach | Tilt % | Light blocked? |
|---|---|---|
| Linear (A) | 22% | Yes, excessively |
| Full geometry d/L=0.9 (B) | 58% | Yes, accurately |
| Simplified d/L=0.9 (C) | 58% | Yes, accurately |
| Full geometry d/L=1.0 | 44% | Yes, overly cautious |

Approach C gives identical results to Approach B for the same d/L ratio, without requiring any user input. However, the d/L ratio is also exposed as a **configurable global setting** (`tilt_slat_overlap_ratio`, default 0.9) so users who know their slat geometry can fine-tune it.

##### Implementation

```python
import math

@staticmethod
def _calculate_auto_tilt(
    sun_elevation: float,
    sun_azimuth_diff: float,
    slat_overlap_ratio: float,
) -> int:
    """Calculate optimal tilt to block direct sunlight while maximizing daylight.

    Uses the profile-angle / slat-cutoff formula with a configurable slat overlap
    ratio (d/L). The default of 0.9 works for most venetian blinds without
    requiring the user to measure their slats.

    Args:
        sun_elevation: Sun elevation in degrees (0-90).
        sun_azimuth_diff: Absolute azimuth difference between sun and cover (0-180°).
        slat_overlap_ratio: Ratio of slat spacing to slat width (d/L, typically 0.5-1.0).

    Returns:
        Tilt position 0-100 (0 = closed/vertical, 100 = open/horizontal).
    """

    if sun_elevation <= 0:
        return 0  # Sun at/below horizon → fully closed

    # Step 1: Profile angle (ω) — vertical sun angle projected onto facade-normal plane
    alt_rad = math.radians(sun_elevation)
    hsa_rad = math.radians(sun_azimuth_diff)
    cos_hsa = math.cos(hsa_rad)

    if abs(cos_hsa) < 1e-10:
        # Sun nearly parallel to facade → profile angle approaches 90°
        omega_rad = math.pi / 2
    else:
        omega_rad = math.atan(math.tan(alt_rad) / cos_hsa)

    # Step 2: Slat cut-off angle (θ) from sin(θ + ω) = (d/L) · cos(ω)
    cos_omega = math.cos(omega_rad)
    ratio = slat_overlap_ratio * cos_omega

    if ratio > 1.0:
        # Geometry impossible — fully close
        theta_deg = 90.0
    elif ratio < -1.0:
        theta_deg = 0.0
    else:
        theta_rad = math.asin(ratio) - omega_rad
        theta_deg = math.degrees(theta_rad)

    # Step 3: Clamp and convert to HA tilt percentage
    theta_deg = max(0.0, min(90.0, theta_deg))
    tilt_percent = 100.0 * (1.0 - theta_deg / 90.0)
    return max(0, min(100, round(tilt_percent)))
```

The caller passes `self.resolved.tilt_slat_overlap_ratio` into this method.

The `sun_azimuth_diff` parameter is already computed by the existing `_calculate_sun_hitting` method (`_calculate_angle_difference`). Since `cos()` is an even function, the unsigned (absolute) difference works correctly here.

#### 3.2.4 Integration into `_move_cover_if_needed`

After successfully moving a cover's position, apply tilt if applicable:

```python
async def _move_cover_if_needed(self, ...) -> tuple[bool, int | None, str]:
    # ... existing position movement logic ...

    if movement_needed:
        # After position change, handle tilt
        tilt_position = self._calculate_tilt_for_movement(sensor_data, movement_reason)
        if tilt_position is not None:
            await self._ha_interface.set_cover_tilt_position(
                self.entity_id, tilt_position, features
            )
```

#### 3.2.5 Tilt Application per Movement Reason

| Movement Reason | Day Tilt Mode Applied | Night Tilt Mode Applied |
|---|---|---|
| `CLOSING_HEAT_PROTECTION` | Yes (day mode) | No |
| `OPENING_LET_LIGHT_IN` | Yes (day mode) | No |
| `CLOSING_AFTER_SUNSET` | No | Yes (night mode) |

When a cover doesn't move (position unchanged), tilt should still be updated if the mode requires it (e.g., **Auto** mode adjusts tilt every cycle based on sun elevation).

#### 3.2.6 Process Method Changes

In `CoverAutomation.process()`, add tilt handling after position determination:

```python
async def process(self, state: State | None, sensor_data: SensorData) -> CoverState:
    # ... existing logic up to position movement ...

    # Read current tilt position (for Manual mode tracking)
    if features & CoverEntityFeature.SET_TILT_POSITION:
        cover_state.tilt_current = to_int_or_none(
            state.attributes.get(ATTR_CURRENT_TILT_POSITION)
        )

    # ... existing position movement ...

    # Apply tilt after position movement (or update tilt even without position change for Auto mode)
    await self._apply_tilt(cover_state, sensor_data, features, movement_reason)

    return cover_state
```

### 3.3 Tilt-Only Updates (No Position Change)

For **Auto** mode, the tilt should be updated even when the cover position doesn't change, as the sun elevation changes continuously. This means:

- In each automation cycle, if tilt mode is **Auto** and the sun is hitting the window, recalculate and set the tilt
- Apply the configurable `tilt_min_change_delta` threshold (default: 5%) to tilt changes to avoid excessive service calls — if `|new_tilt - current_tilt| < tilt_min_change_delta`, skip the update
- This threshold is a global options flow setting (step 4), separate from `covers_min_position_delta` which applies to cover position

### 3.4 Evening Closure Tilt

When `CLOSING_AFTER_SUNSET` triggers, apply the **night** tilt mode. For most users this will be **Closed** (tilt = 0, fully block light for privacy).

---

## 4. Data Model Changes

### 4.1 `CoverState` (`cover_automation.py`)

Add tilt fields:

```python
@dataclass
class CoverState:
    # ... existing fields ...
    tilt_current: int | None = None
    tilt_target: int | None = None
```

### 4.2 `CoordinatorData` (`data.py`)

No changes needed — `CoordinatorData.covers` already stores `CoverState` per cover, and the new tilt fields are part of `CoverState`.

### 4.3 Manual Tilt History

For **Manual** mode, we need to remember what tilt position the user had set before automation moved the cover.

**Approach: Extend `CoverPositionHistoryManager`** — add a `tilt_position` field to history entries. This is consistent with how position history already works and handles edge cases (multiple position changes, timeouts) naturally.

**Capture timing:** The manual tilt is captured on the **first automation run** — i.e., from the cover's current `ATTR_CURRENT_TILT_POSITION` when the automation first processes it. This is the simplest approach and gives the correct result: whatever tilt the cover had when the automation started is the "manual" tilt to restore.

Add to `CoverPositionHistory` entry:

```python
@dataclass
class PositionHistoryEntry:
    position: int
    tilt_position: int | None = None   # Add tilt tracking
    timestamp: datetime
    cover_moved: bool
```

---

## 5. Testing Strategy

### 5.1 Config Flow Tests

**File:** `tests/config_flow/test_options_flow.py`

New test class: `TestOptionsFlowStep4Tilt`

Tests needed:
- Step 4 shows form with default tilt modes
- Step 4 shows only tilt-capable covers in per-cover sections
- Step 4 skips per-cover section when no covers support tilt
- Step 4 proceeds to step 5 (window sensors)
- Step 4 stores global tilt settings
- Step 4 stores per-cover tilt overrides
- Step 4 stores tilt_min_change_delta setting
- Per-cover tilt settings extracted correctly from section input

**File:** `tests/config_flow/test_options_flow_scenarios.py`

Update all existing scenario tests:
- All `async_step_4()` calls become `async_step_5()` (window sensors)
- All `async_step_5()` calls become `async_step_6()` (time settings)
- Insert `async_step_4()` calls for the new tilt step in each scenario
- Add scenario: complete flow with tilt settings modified
- Add scenario: complete flow with per-cover tilt overrides

**File:** `tests/config_flow/test_helper.py`

Add tests for:
- `build_schema_step_4_tilt` schema construction
- Tilt-capable cover detection
- Per-cover tilt override schema building

### 5.2 Cover Automation Tests

**File:** `tests/cover_automation/` (new test file: `test_tilt_control.py`)

Tests needed:
- Tilt not applied when cover doesn't support tilt
- Tilt mode **Open**: sets tilt to 100 after position change
- Tilt mode **Closed**: sets tilt to 0 after position change
- Tilt mode **Manual**: captures tilt on first run, restores after move
- Tilt mode **Auto**: calculates correct tilt from sun elevation and azimuth diff
- Auto tilt at various profile angles (boundary cases: elevation 0°, 45°, 90°; HSA 0°, 45°, 89°)
- Auto tilt formula produces expected values (verify against physics: e.g., elevation 20° / HSA 0° → tilt ≈ 58%)
- Night tilt mode applied during evening closure
- Day tilt mode applied during heat protection
- Per-cover tilt override takes precedence over global
- Tilt delta threshold (`tilt_min_change_delta`) prevents excessive updates
- Tilt delta threshold of 0 always sends updates
- Auto tilt updates even without position change
- Lock mode HOLD_POSITION suppresses tilt automation
- Lock mode FORCE_OPEN also sets tilt to 100
- Lock mode FORCE_CLOSE also sets tilt to 0

### 5.3 HA Interface Tests

**File:** `tests/ha_interface/` (new test file or addition: `test_set_tilt_position.py`)

Tests needed:
- `set_cover_tilt_position` calls correct service
- Fallback to `open_cover_tilt`/`close_cover_tilt` when `SET_TILT_POSITION` not supported
- Simulation mode skips tilt service call
- Error handling for tilt service failures
- Tilt position validation (0-100 range)

### 5.4 Integration Tests

Update existing integration tests to account for:
- New step 4 in the options flow
- Tilt fields in `CoverState`
- Covers with and without tilt support in mixed scenarios

### 5.5 Test Fixtures (`conftest.py`)

Existing constants to leverage:
```python
TEST_TILT_ANGLE = 20.0              # Already defined
TEST_CLOSED_TILT_POSITION = 0       # Already defined
```

New constants to add:
```python
TEST_OPEN_TILT_POSITION = 100       # Fully open tilt
TEST_PARTIAL_TILT_POSITION = 50     # Partially tilted
```

New/updated fixtures:
```python
@pytest.fixture
def mock_cover_with_tilt():
    """Create a mock cover entity that supports tilt."""
    state = MagicMock()
    state.attributes = {
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION,
        ATTR_CURRENT_POSITION: 100,
        ATTR_CURRENT_TILT_POSITION: 50,
    }
    return state
```

---

## 6. Documentation Impact

### 6.1 Configuration Wizard (`docs/configuration-wizard.md`)

Update to reflect 6 steps (was 5). Add description of new step 4 for tilt angle control.

### 6.2 Configuration Entities (`docs/configuration-entities.md`)

No new HA entities needed for tilt (tilt mode is configured in the options flow, not via runtime entities). However, if runtime tilt mode switching is desired later, a `select` entity could be added.

### 6.3 README.md

Update feature list to mention tilt angle control support.

---

## 7. Migration Considerations

### 7.1 Schema Version

The integration's `VERSION = 1` should be bumped to `VERSION = 2` with an `async_migrate_entry` method that:
- Adds default tilt settings for existing installations
- No data loss — existing config entries just get new keys with default values

### 7.2 Backward Compatibility

- Existing installations without tilt-capable covers are unaffected
- The default tilt modes (`open` day, `closed` night) provide sensible behavior without user intervention
- Per-cover tilt overrides are optional

---

## 8. Files to Modify

| File | Changes |
|---|---|
| `const.py` | Add `TiltMode` enum, `COVER_SFX_TILT_*`, `STEP_4_SECTION_TILT_*`, rename step 4/5 section constants |
| `config.py` | Add `TILT_MODE_DAY`, `TILT_MODE_NIGHT`, `TILT_MIN_CHANGE_DELTA`, `TILT_SLAT_OVERLAP_RATIO` to `ConfKeys`, `CONF_SPECS`, `ResolvedConfig` |
| `config_flow.py` | Add `build_schema_step_4_tilt`, new `async_step_4`, renumber steps 4→5 and 5→6, update `_build_section_cover_settings`, update `_finalize_and_save` |
| `ha_interface.py` | Add `set_cover_tilt_position()` method |
| `cover_automation.py` | Add tilt fields to `CoverState`, add `_get_effective_tilt_mode`, `_calculate_auto_tilt` (profile-angle formula), `_apply_tilt`, update `process()`, `_move_cover_if_needed()`, and `_process_lock_mode()` (lock tilt too) |
| `cover_position_history.py` | Add `tilt_position` to history entries (for Manual mode) |
| `translations/en.json` | Add step 4 tilt translations, update step numbers, add tilt mode selector |
| `translations/*.json` | Same structure updates (non-English files) |
| Tests (multiple files) | See §5 above |

---

## 9. Implementation Order

Recommended implementation sequence:

1. **Constants & config** (`const.py`, `config.py`) — foundation for everything else
2. **HA interface** (`ha_interface.py`) — `set_cover_tilt_position()` method
3. **Cover automation logic** (`cover_automation.py`) — tilt calculation and application
4. **Config flow** (`config_flow.py`) — new step 4, step renumbering
5. **Translations** (`translations/*.json`) — UI strings
6. **Tests** — comprehensive testing per §5
7. **Documentation** — update docs (only when asked)

---

## 10. Design Decisions (Resolved)

1. **Auto tilt formula:** Use the **physics-based profile-angle / slat-cutoff formula** with a **configurable** `d/L` ratio (default 0.9, exposed as `tilt_slat_overlap_ratio` in step 4, see §3.2.3). This provides accurate sun protection out of the box, while allowing users who know their slat geometry to fine-tune. The formula was researched against the [ha-smart-venetian-blinds](https://github.com/herpaderpaldent/ha-smart-venetian-blinds) integration which uses the same underlying math but requires explicit slat width/spacing measurements.

2. **Tilt update threshold:** Use a **configurable `tilt_min_change_delta` setting** (default: 5%) exposed as a global option in step 4 of the options flow. Auto mode tilt is updated every coordinator cycle (60s) but the service call is only made when the change exceeds this threshold.

3. **Manual mode — capture timing:** Capture the manual tilt on the **first automation run**, reading the cover's current `ATTR_CURRENT_TILT_POSITION` from its state. This is the simplest approach and gives the correct result.

4. **Tilt during lock modes:** **Lock tilt too.** When locks are active (HOLD_POSITION, FORCE_OPEN, FORCE_CLOSE), tilt automation is also suppressed, consistent with position locking behavior. FORCE_OPEN sets tilt to 100, FORCE_CLOSE sets tilt to 0.

5. **Step number in constant names:** **Rename Python constant identifiers** for readability (e.g., `STEP_4_SECTION_WINDOW_SENSORS` → `STEP_5_SECTION_WINDOW_SENSORS`), but **do NOT change the string values** (e.g., `"section_window_sensors"`) since those are stored in config entries and translations.
