# Test Relevance Improvement Plan

## Problem Statement

The test suite has **674 tests across 42 files** with a 3.5:1 test-to-code ratio — strong
coverage by volume. However, approximately **85% are mock-heavy unit tests** that exercise mock
interactions rather than real code paths. Only **9 tests** use a real Home Assistant instance,
and those only verify lifecycle (setup/teardown), not runtime behavior.

Real-world integration bugs — wiring errors, event loop issues, state machine transitions,
schema validation — typically surface in the layers **above** unit tests. The goal of this plan
is to shift testing effort toward tests that catch these higher-level bugs without abandoning
the existing unit test base.

---

## Current Test Architecture

| Layer | Directory | Tests | Pattern | Catches |
|---|---|---|---|---|
| Unit | `unit/`, `cover_automation/`, `ha_interface/`, `automation_engine/`, `coordinator/`, `config_flow/`, `edge_cases/` | ~575 | Fully mocked `hass`, `MagicMock` dependencies | Algorithm correctness, edge cases |
| Component | `components/` | ~73 | Mock coordinator, real entity classes | Entity properties, platform setup |
| Mock integration | `integration/test_integration.py`, `test_lock_mode_integration.py` | ~25 | Real coordinator, mocked `hass` | Business logic flow |
| Real HA integration | `integration/test_integration_real_ha.py`, `test_set_lock_service_integration.py` | ~9 | Real `hass` fixture, `async_setup_component` | Lifecycle only |

### Key Observations

1. **Over-mocking**: `mock_hass` is a `MagicMock` without spec in most fixtures. Any attribute
   access returns another mock silently, masking real wiring errors.

2. **Dual MockConfigEntry**: A custom `MockConfigEntry` in `conftest.py` stores config in
   `.options` alongside the real `MockConfigEntry` from
   `pytest_homeassistant_custom_component.common`. These behave differently.

3. **No runtime behavior with real HA**: The 9 real-HA tests verify that the integration loads,
   creates entities, and unloads. None trigger a coordinator update cycle or verify that cover
   service calls are issued.

4. **Global mutable state**: `_CURRENT_WEATHER_TEMP` is a module-level global mutated by
   `set_weather_forecast_temp()`, creating inter-test coupling risk.

5. **Measured coverage is 30.4%** despite 674 tests — mocks intercept calls before reaching
   production code.

---

## Improvement Plan

### Phase 1: Real-HA Runtime Behavior Tests (Highest Impact)

**Goal**: Test the full automation chain with a real HA instance: state change → coordinator
update → automation engine → cover service call.

**What this catches that unit tests miss**:
- Wiring bugs between coordinator, automation engine, and HA interface
- `hass.services.async_call` schema/parameter issues
- Entity state propagation through the real HA state machine
- Event loop ordering and `async_block_till_done` interactions

#### Tests to Add

All tests use the real `hass` fixture from `pytest-homeassistant-custom-component` and call
`async_setup_component`. Cover/weather/sun entity states are set via `hass.states.async_set`.
Coordinator updates are triggered via `async_fire_time_changed` + `hass.async_block_till_done`.

| # | Test | Scenario | Verifies |
|---|---|---|---|
| 1.1 | `test_heat_protection_closes_cover` | Weather reports 30°C, sun hitting cover → coordinator cycle | Cover service `set_cover_position` called with closed position |
| 1.2 | `test_comfortable_temp_opens_cover` | Weather reports 20°C → coordinator cycle | Cover stays/moves to open position |
| 1.3 | `test_sun_azimuth_direct_hit` | Sun azimuth within cover's window, high elevation | Cover closes for sun protection |
| 1.4 | `test_sun_azimuth_no_hit` | Sun azimuth outside cover's window | Cover remains open |
| 1.5 | `test_evening_closure_at_sunset` | Sun elevation drops below threshold, `close_covers_after_sunset` enabled | Relevant covers close |
| 1.6 | `test_lock_mode_force_open_overrides_heat` | FORCE_OPEN lock + hot temperature | Cover stays open despite heat |
| 1.7 | `test_lock_mode_force_close_overrides_cold` | FORCE_CLOSE lock + cold temperature | Cover closes despite no heat |
| 1.8 | `test_lock_mode_hold_position_blocks_all` | HOLD_POSITION lock + any condition | No cover movement at all |
| 1.9 | `test_window_sensor_lockout` | Window sensor is "on" (open), heat protection active | Cover does NOT close (lockout) |
| 1.10 | `test_nighttime_block_opening` | Sun below horizon, `nighttime_block_opening` enabled | Cover does not open automatically |

**Infrastructure needed**:
- A shared `setup_integration` fixture that loads the integration with real HA + configurable
  options and returns the config entry and coordinator reference
- `async_fire_time_changed` helper from `homeassistant.util.dt` to trigger coordinator cycles
- Cover entities set up via `hass.states.async_set` with appropriate attributes
  (`current_position`, `supported_features`)

**Estimated effort**: 2-3 days
**File**: `tests/integration/test_runtime_real_ha.py`

---

### Phase 2: Coordinator → Entity Data Flow Tests

**Goal**: Verify that after a coordinator refresh, HA entities expose the correct state values.
Currently, `components/` tests mock the coordinator, so a data type mismatch between
`CoordinatorData` / `CoverState` and entity `native_value` / `is_on` would go undetected.

#### Tests to Add

| # | Test | Entity Type | Verifies |
|---|---|---|---|
| 2.1 | `test_binary_sensor_status_reflects_coordinator` | `binary_sensor` | Status sensor reflects `coordinator.data` after real update |
| 2.2 | `test_binary_sensor_temp_hot` | `binary_sensor` | `temp_hot` binary sensor matches `coordinator.data.temp_hot` |
| 2.3 | `test_sensor_sun_azimuth` | `sensor` | Sun azimuth sensor shows `coordinator.data.sun_azimuth` |
| 2.4 | `test_sensor_temp_current_max` | `sensor` | Temperature sensor shows `coordinator.data.temp_current_max` |
| 2.5 | `test_sensor_lock_mode` | `sensor` | Lock mode sensor shows current lock mode |
| 2.6 | `test_number_entity_updates_config` | `number` | Changing a number entity value persists to config entry options |
| 2.7 | `test_select_lock_mode_changes_coordinator` | `select` | Selecting a lock mode updates `coordinator.lock_mode` |
| 2.8 | `test_switch_enabled_toggles_automation` | `switch` | Toggling enabled switch → coordinator picks up new value |

**What this catches**:
- Data type mismatches (`float` vs `str`, `None` handling)
- Entity `unique_id` / registry wiring
- Entity availability tracking when coordinator errors occur

**Estimated effort**: 1-2 days
**File**: `tests/integration/test_entity_data_flow.py`

---

### Phase 3: Config & Options Flow with Real HA

**Goal**: Test the 5-step options flow wizard and config flow with a real HA instance, catching
voluptuous schema errors, selector misconfigurations, and step transition bugs.

#### Tests to Add

| # | Test | Verifies |
|---|---|---|
| 3.1 | `test_config_flow_creates_entry` | User flow creates a valid config entry with defaults |
| 3.2 | `test_options_flow_full_wizard` | Walking all 5 steps produces valid config in `entry.options` |
| 3.3 | `test_options_flow_entity_validation` | Invalid entity IDs are rejected at step boundaries |
| 3.4 | `test_options_flow_preserves_existing` | Opening options flow pre-fills current values |
| 3.5 | `test_options_flow_cover_add_remove` | Adding/removing covers updates config correctly |

**What this catches**:
- Voluptuous schema validation errors that `MagicMock` silently accepts
- `FlowResultType` transitions between steps
- Selector configurations matching real HA selector infrastructure
- Default value propagation

**Estimated effort**: 1-2 days
**File**: `tests/config_flow/test_config_flow_real_ha.py`

---

### Phase 4: Smart Reload End-to-End

**Goal**: Verify that the smart reload optimization works correctly — runtime-configurable key
changes trigger a coordinator refresh (not full reload), while structural changes trigger a full
entry reload.

#### Tests to Add

| # | Test | Verifies |
|---|---|---|
| 4.1 | `test_runtime_key_change_refreshes_only` | Changing `TEMP_THRESHOLD` → coordinator refresh, entry stays `LOADED` |
| 4.2 | `test_structural_key_change_reloads_entry` | Changing `COVERS` → full reload cycle |
| 4.3 | `test_multiple_runtime_keys_single_refresh` | Changing several runtime keys at once → single refresh |
| 4.4 | `test_lock_mode_change_via_options_update` | Lock mode persisted to options triggers refresh |

**What this catches**:
- `get_runtime_configurable_keys()` correctness against actual behavior
- Reload listener registration/cleanup
- Race conditions during reload

**Estimated effort**: 1 day
**File**: `tests/integration/test_smart_reload.py`

---

### Phase 5: Multi-Instance & Service Routing

**Goal**: Verify that two config entries can coexist and that services route to the correct
instance.

#### Tests to Add

| # | Test | Verifies |
|---|---|---|
| 5.1 | `test_two_instances_load` | Two config entries both reach `LOADED` state |
| 5.2 | `test_set_lock_routes_to_correct_instance` | `set_lock` service with `entry_id` targets only that instance |
| 5.3 | `test_logbook_service_routes_correctly` | Logbook entry routes to matching instance |
| 5.4 | `test_unload_one_instance_keeps_other` | Unloading one entry doesn't affect the other |
| 5.5 | `test_service_removed_on_last_unload` | Services only removed when last instance unloads |

**What this catches**:
- Service registration/removal lifecycle with multiple entries
- `DATA_COORDINATORS` dict management
- Per-instance logger isolation

**Estimated effort**: 1 day
**File**: `tests/integration/test_multi_instance.py`

---

### Phase 6: Infrastructure Improvements (Enablers)

These aren't tests themselves but improvements to the test infrastructure that make the
higher-level tests more reliable and reduce false confidence from over-mocking.

| # | Improvement | Description | Impact |
|---|---|---|---|
| 6.1 | **Add `spec=HomeAssistant` to `mock_hass`** | The primary `mock_hass` fixture uses bare `MagicMock()`. Adding `spec=HomeAssistant` causes `AttributeError` on wrong attribute access, catching typos and API drift. | Prevents silent mock pass-through |
| 6.2 | **Consolidate `MockConfigEntry`** | Remove the custom `MockConfigEntry` class from `conftest.py`. Migrate all tests to use the real `MockConfigEntry` from `pytest_homeassistant_custom_component.common`. | Eliminates behavioral discrepancy between test types |
| 6.3 | **Replace global `_CURRENT_WEATHER_TEMP`** | Replace the module-level mutable global with a fixture-scoped value (e.g., a `weather_temp` fixture or a context manager). | Eliminates inter-test coupling |
| 6.4 | **Shared `setup_integration` fixture** | Create a parameterizable fixture that loads the integration in a real HA instance, sets up dependencies (sun, weather, covers), and returns handles for coordinator + entry. Reusable across all Phase 1-5 tests. | Reduces boilerplate, ensures consistency |
| 6.5 | **Add `async_fire_time_changed` helper** | Import or create a helper to advance HA's time and trigger coordinator update intervals. | Required for runtime behavior tests |

**Estimated effort**: 1-2 days (can be done incrementally alongside phases 1-5)

---

## Prioritization & Sequencing

```
Phase 6 (Infrastructure) ──────────────────────────────────►
  │
  ├─► Phase 1 (Runtime Behavior)     ← Start here, highest ROI
  │     │
  │     └─► Phase 2 (Entity Data Flow)
  │
  ├─► Phase 3 (Config Flow)          ← Can run in parallel with Phase 1
  │
  ├─► Phase 4 (Smart Reload)
  │
  └─► Phase 5 (Multi-Instance)
```

**Recommended order**:
1. Phase 6.4 + 6.5 (shared fixture + time helper) — prerequisite for Phase 1
2. Phase 1 (runtime behavior) — highest impact, catches the most real-world bugs
3. Phase 2 (entity data flow) — builds on Phase 1 infrastructure
4. Phase 3 (config flow) — independent, can overlap with Phase 1-2
5. Phase 4 (smart reload) — moderate impact
6. Phase 5 (multi-instance) — lowest priority but important for correctness
7. Phase 6.1-6.3 (mock improvements) — can be done anytime, each is independent

---

## Expected Outcomes

| Metric | Before | After (projected) |
|---|---|---|
| Real-HA runtime tests | 0 | 10+ |
| Real-HA tests (total) | 9 | 35-40 |
| Code coverage (measured) | 30.4% | 60-70% (more real code paths exercised) |
| Bugs caught by tests | Algorithm errors only | + wiring, schema, lifecycle, routing bugs |
| Test execution time | ~15s | ~25-30s (real-HA tests are slower) |

---

## What NOT to Change

- **Existing unit tests**: Keep them. They're fast, catch algorithm bugs, and serve as
  documentation. The goal is to complement them, not replace them.
- **Production code**: This plan only adds/modifies tests and test infrastructure.
- **Test framework**: Continue using `pytest` + `pytest-homeassistant-custom-component`. No new
  dependencies needed.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Real-HA tests are slower (~0.5-2s each) | Keep count focused (35-40 total), run unit tests first for fast feedback |
| Real-HA tests break when HA core APIs change | `pytest-homeassistant-custom-component` handles compatibility; pin version |
| Large fixture setup for real-HA tests | Invest in shared `setup_integration` fixture (Phase 6.4) |
| Dual test patterns confuse contributors | Document both patterns in test README; prefer real-HA for new integration tests |

---

## Summary

The single highest-impact improvement is **Phase 1**: adding 10 real-HA runtime behavior tests
that exercise the full automation chain. This, combined with the infrastructure work in
**Phase 6**, would catch the class of bugs that currently slip through — wiring errors, event
ordering, schema mismatches, and service routing — while preserving the existing unit test base
for fast algorithm-level feedback.
