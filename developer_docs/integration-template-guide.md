# Smart Cover Automation as an Integration Template

This repository is a strong template for Home Assistant custom integrations that need UI-first configuration, a coordinator-centered runtime model, thin entity layers, and strong tests.

It is not a minimal example. It is a production-style layout with clear separation between Home Assistant glue code and domain logic.

## What This Integration Demonstrates

- one config entry managing many related entities under one device
- all user settings stored in `config_entry.options`
- a `DataUpdateCoordinator` as the runtime center
- business logic kept out of entity classes
- entity changes persisted back to options so HA can refresh or reload correctly

## Core Structure

```text
custom_components/smart_cover_automation/
├── manifest.json                # HA metadata
├── __init__.py                  # setup, unload, reload, services, migrations
│
├── const.py                     # constants, enums, entity keys
├── config.py                    # typed config registry and resolution
├── data.py                      # RuntimeData and CoordinatorData
├── log.py                       # per-entry logger wrapper
│
├── config_flow.py               # minimal config flow + multi-step options flow
├── coordinator.py               # update loop, refresh logic, error handling
├── entity.py                    # common base entity and device grouping
├── ha_interface.py              # Home Assistant API boundary
│
├── automation_engine.py         # orchestration of automation decisions
├── cover_automation.py          # per-cover logic and state
├── cover_position_history.py    # recent-position tracking
│
├── binary_sensor.py             # condition and status entities
├── sensor.py                    # telemetry and state-summary entities
├── switch.py                    # boolean runtime controls
├── number.py                    # numeric runtime controls
├── select.py                    # enum-backed controls
├── time.py                      # external time input entities
│
├── services.yaml                # service schemas
└── translations/                # UI, entity, selector, and service strings

tests/
├── unit/                        # pure Python modules
├── components/                  # entity platforms
├── config_flow/                 # config and options flows
├── coordinator/                 # refresh and runtime behavior
├── ha_interface/                # HA boundary layer
├── initialization/              # setup, unload, reload, migrations
├── integration/                 # higher-level end-to-end behavior
└── localization/                # translation completeness
```

## Architecture

### Lifecycle in `__init__.py`

`__init__.py` owns startup and teardown:

- declares platforms
- migrates legacy option keys and entity unique IDs
- creates the coordinator and stores `RuntimeData` on the config entry
- forwards platform setup
- registers services
- listens for option changes and chooses refresh vs full reload

The key pattern is the reload split: settings marked runtime-configurable in `config.py` trigger a coordinator refresh; structural changes trigger a full reload.

### Typed config in `config.py`

Configuration is centralized in three layers:

- `ConfKeys`: enum of persisted option keys
- `CONF_SPECS`: default, converter, and runtime-configurable flag for each key
- `ResolvedConfig`: typed resolved settings built from raw options

This keeps parsing and defaults out of entities and out of the coordinator loop.

### Coordinator-centered runtime

`coordinator.py` is the runtime hub. On each refresh it:

- reads current options
- resolves typed settings
- applies per-entry verbose logging
- gathers HA state
- delegates decision-making to `AutomationEngine`
- returns `CoordinatorData` for entities

Critical configuration or sensor problems raise `UpdateFailed`. Less severe failures return empty but valid data so entities can stay available.

### Business logic outside HA wrappers

The clean separation is:

- HA-facing code: `__init__.py`, platform files, `config_flow.py`, `ha_interface.py`
- domain logic: `automation_engine.py`, `cover_automation.py`, `cover_position_history.py`

That split makes the integration easier to test and evolve.

## Entity Pattern

All entities inherit from `IntegrationEntity` in `entity.py`, which provides:

- `CoordinatorEntity` behavior
- `_attr_has_entity_name = True`
- one device per config entry via `device_info`
- unique IDs based on `entry_id`

Platform files remain thin:

- `binary_sensor.py`: status and condition flags
- `sensor.py`: telemetry and state summaries
- `switch.py`: boolean runtime controls
- `number.py`: numeric settings and dynamic external-control numbers
- `select.py`: enum-backed controls such as lock mode
- `time.py`: external morning opening time when needed

The recurring entity write pattern is simple: update `config_entry.options`, then let the listener in `__init__.py` decide whether HA should refresh or reload.

## Config Flow Pattern

The config flow is intentionally minimal:

- `async_step_user` shows a welcome screen
- submitting it creates the entry
- all real settings are handled in the options flow

The options flow is dynamic and split into 6 steps:

1. weather entity and covers
2. per-cover azimuth
3. global and per-cover min/max closure
4. tilt behavior and per-cover tilt overrides
5. per-cover window sensors
6. time range, evening closure, and morning opening settings

Important patterns in `config_flow.py`:

- `FlowHelper` builds schemas and validation helpers
- sections are used for collapsible groups
- per-cover settings are stored as flat keys with suffixes from `const.py`
- cleanup logic removes orphaned values when covers or modes change

If you copy this pattern, keep the cleanup logic. Dynamic flows become brittle without it.

## Services, Logging, and Translations

Two services are defined in `services.yaml` and registered in `__init__.py`:

- `set_lock`: sets integration-wide lock mode
- `logbook_entry`: creates translated logbook entries for cover movement

The `logbook_entry` service also supports HA translation requirements for localized logbook messages.

Logging is instance-aware:

- `log.py` creates per-entry child loggers
- verbose logging can be enabled per config entry
- multiple integration instances remain distinguishable in logs

Translations are first-class: entity names, options flow labels, service fields, and selector labels all come from `translations/*.json`, and localization is tested.

## Conventions Worth Reusing

- put repeated strings and suffixes in `const.py`
- keep persisted settings in one registry, not spread across platforms
- use typed `entry.runtime_data` from `data.py`
- derive unique IDs from `entry_id`, not just the domain
- keep entities thin and push behavior into coordinator or domain modules
- add migrations early for renamed options and legacy unique IDs

## Development Workflow

Useful repo commands:

- `scripts/lint`: version sync check, `ruff format`, `ruff check --fix`
- `scripts/test`: installs locked deps, runs mypy, then all tests
- `python3 -m pytest tests/...`: use for targeted test files

Testing in this repo is intentionally split by concern: config flow, coordinator, entity components, HA interface, initialization, localization, and pure unit logic. Config flow coverage is especially important.

## When This Template Fits

Use this structure if your integration has:

- several related entities backed by one controller
- meaningful runtime configuration in the UI
- enough complexity to benefit from typed config and isolated business logic
- a need for multi-instance support without entity-ID collisions

Use a smaller template if your integration only exposes a single passive entity or has no real options flow.

## Adapting This Template

If you use this integration as a starter, the safest sequence is:

1. Rename the package and identity.
	Update the integration folder, `DOMAIN`, display name, manifest metadata, imports, translation keys, and HACS metadata if needed.
2. Replace the domain model.
	Keep the coordinator/entity/config split, but replace `automation_engine.py`, `cover_automation.py`, and related domain-specific helpers with your own logic.
3. Redefine configuration in one place.
	Update `ConfKeys`, `CONF_SPECS`, and `ResolvedConfig` in `config.py` before changing entities or flows.
4. Adapt the options flow.
	Keep the minimal config flow, then rewrite the multi-step options flow to match your settings, validation rules, and any per-entity dynamic sections.
5. Rebuild the platforms you actually need.
	Keep `IntegrationEntity` and the pattern of thin platform files, but remove unused platforms and replace entity descriptions, state mapping, and write-back logic.
6. Keep the HA boundary explicit.
	Use `ha_interface.py` for Home Assistant API calls so business logic remains testable without deep HA mocks.
7. Review migrations and cleanup paths.
	Remove migrations you do not need, but keep the pattern for renamed options, unique IDs, and stale dynamic settings.
8. Rewrite translations and services together.
	If a flow, entity, selector, or service exists in code, add or update its translations at the same time.
9. Reshape the tests with the same architecture.
	Mirror the code structure in `tests/`, keep config flow coverage high, and add fixtures around your new coordinator inputs and HA interface behavior.

What is worth keeping almost unchanged:

- the typed config registry in `config.py`
- `RuntimeData` and coordinator-owned runtime state
- entry-ID-based unique IDs for multi-instance support
- thin entities that persist changes via `config_entry.options`
- service registration and reload handling in `__init__.py`

## Bottom Line

The main idea to copy is the combination of typed config resolution, coordinator-owned runtime state, thin entities, explicit HA abstraction boundaries, and aggressive tests. That combination scales well once an integration moves beyond a proof of concept.
