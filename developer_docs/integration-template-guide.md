# Using This Integration as a Template

This guide documents the architecture, patterns, and conventions of the **Smart Cover Automation** integration so it can be used as a foundation for building new Home Assistant custom integrations.

---

## 1. Project Structure

```
my_integration/
├── .devcontainer.json              # Dev container (Python 3.13)
├── .gitignore
├── .python-version
├── pyproject.toml                  # pytest, coverage, ruff, mypy config
├── pyrightconfig.json              # Pylance/Pyright settings
├── hacs.json                       # HACS metadata
├── requirements.txt                # Core deps (pins HA version indirectly)
├── requirements-ha.txt             # Home Assistant + compatibility pins
├── requirements-test.txt           # pytest, pytest-homeassistant-custom-component
├── requirements-ruff.txt           # Linter version pin
├── config/
│   └── configuration.yaml          # Local HA dev instance config
├── scripts/
│   ├── setup                       # Install all deps
│   ├── lint                        # ruff format + ruff check --fix
│   ├── test                        # mypy + pytest with coverage
│   └── type-check                  # mypy standalone
├── custom_components/
│   └── <domain>/                   # The integration itself
│       ├── manifest.json
│       ├── __init__.py             # Setup/teardown/reload entry points
│       ├── const.py                # All constants, enums, domain string
│       ├── config.py               # Settings registry, defaults, resolution
│       ├── config_flow.py          # Config flow + options flow wizards
│       ├── coordinator.py          # DataUpdateCoordinator subclass
│       ├── data.py                 # Runtime data types (dataclasses)
│       ├── entity.py               # Base entity class
│       ├── log.py                  # Per-instance logger wrapper
│       ├── ha_interface.py         # HA API abstraction layer
│       ├── binary_sensor.py        # Platform: binary sensors
│       ├── sensor.py               # Platform: sensors
│       ├── switch.py               # Platform: switches
│       ├── number.py               # Platform: number entities
│       ├── select.py               # Platform: select entities
│       ├── services.yaml           # Service definitions
│       ├── util.py                 # Small shared helpers
│       ├── <business_logic>.py     # Domain-specific logic (decoupled from HA)
│       └── translations/
│           ├── en.json             # English (required)
│           └── *.json              # Additional languages
└── tests/
    ├── conftest.py                 # Shared fixtures, mocks, helpers
    ├── unit/                       # Pure unit tests (no HA deps)
    ├── components/                 # Per-platform entity tests
    ├── coordinator/                # Coordinator/automation logic tests
    ├── config_flow/                # Config/options flow tests (100% coverage)
    ├── ha_interface/               # HA API layer tests
    ├── initialization/             # Setup/teardown/reload lifecycle tests
    ├── integration/                # End-to-end scenario tests
    ├── edge_cases/                 # Robustness/boundary tests
    └── localization/               # Translation completeness tests
```

---

## 2. Key Files and Their Roles

### 2.1 `manifest.json`

Declares the integration to Home Assistant:

```json
{
    "domain": "my_domain",
    "name": "My Integration",
    "codeowners": ["@github_username"],
    "config_flow": true,
    "dependencies": [],
    "documentation": "https://...",
    "iot_class": "calculated",
    "issue_tracker": "https://...",
    "version": "1.0.0"
}
```

- `domain` — Unique identifier; must match the folder name under `custom_components/`.
- `config_flow: true` — Enables the UI-based configuration wizard.
- `iot_class` — One of: `calculated`, `local_polling`, `cloud_polling`, etc.
- `dependencies` — Other HA integrations this one depends on (e.g., `sun`, `weather`).

### 2.2 `const.py` — Constants Module

The single source of truth for all string literals, keys, and enums:

- **`DOMAIN`** / **`INTEGRATION_NAME`** — The integration's identifier and display name.
- **Entity keys** — Constants for each entity's `key` (e.g., `BINARY_SENSOR_KEY_STATUS = "status"`).
- **Enums** — `LockMode(StrEnum)`, `LogSeverity(Enum)` for type-safe values.
- **HA string literals** — Constants wrapping HA-specific strings (entity IDs, attribute names, weather conditions).
- **Module-level `LOGGER`** — A `Log` instance initialized at import time via `_init_logger()`.

**Pattern**: No magic strings anywhere. Every string that appears more than once is a constant.

### 2.3 `config.py` — Settings Registry

Centralizes all configuration with a typed, self-documenting registry:

```python
class ConfKeys(StrEnum):
    """Every configuration key as an enum member."""
    ENABLED = "enabled"
    TEMP_THRESHOLD = "temp_threshold"
    ...

@dataclass(frozen=True, slots=True)
class _ConfSpec(Generic[T]):
    """Metadata per setting: default value, type converter, runtime-configurable flag."""
    default: T
    converter: Callable[[Any], T]
    runtime_configurable: bool = False

CONF_SPECS: dict[ConfKeys, _ConfSpec[Any]] = {
    ConfKeys.ENABLED: _ConfSpec(default=True, converter=to_bool, runtime_configurable=True),
    ...
}
```

- **`ConfKeys`** — Typo-safe enum of all setting names.
- **`CONF_SPECS`** — Registry mapping each key to its default, type converter, and whether it can change at runtime without a full reload.
- **`ResolvedConfig`** — Frozen dataclass with typed fields for every setting. Built by `resolve(options)` from raw config dict.
- **`runtime_configurable`** — Settings with corresponding control entities (switches, numbers) that need only a coordinator refresh, not a full integration reload.

### 2.4 `data.py` — Runtime Data Types

```python
type IntegrationConfigEntry = ConfigEntry[RuntimeData]

@dataclass
class CoordinatorData:
    """What the coordinator returns each cycle; becomes entity attributes."""
    covers: dict[str, CoverState]
    sun_azimuth: float | None = None
    ...

@dataclass
class RuntimeData:
    """Stored on config_entry.runtime_data during setup."""
    coordinator: DataUpdateCoordinator
    integration: Integration
    config: dict[str, Any]
```

- **`IntegrationConfigEntry`** — Type alias providing type-safe `entry.runtime_data`.
- **`CoordinatorData`** — Structured output of each coordinator update cycle.
- **`RuntimeData`** — Persisted on the config entry for cross-component access.

### 2.5 `__init__.py` — Integration Lifecycle

Implements the three HA-required entry points plus a smart reload listener:

| Function | When Called | What It Does |
|---|---|---|
| `async_setup_entry()` | Initial setup, reload, HA restart | Creates coordinator, stores `RuntimeData`, forwards platform setup, triggers first refresh, registers services and update listener |
| `async_unload_entry()` | Integration removal/reload | Unloads platforms, cleans up coordinator references and services |
| `async_reload_entry()` | Config options changed | Compares old vs new config; if only `runtime_configurable` keys changed → coordinator refresh; else → full reload |

**Setup sequence** (in `async_setup_entry`):
1. Configure logging level early.
2. Run unique ID migration if needed.
3. Create `DataUpdateCoordinator`.
4. Merge config, store `RuntimeData` on entry.
5. Track coordinator in `hass.data[DOMAIN]`.
6. Register services (idempotent — checks `has_service` first).
7. Forward platform setups (`async_forward_entry_setups`).
8. Trigger `async_config_entry_first_refresh()`.
9. Register update listener via `entry.async_on_unload`.

**Smart reload pattern**: The update listener (`async_reload_entry`) compares changed keys against `runtime_configurable_keys`. Runtime-only changes (switch toggles, number edits) skip costly full reloads.

### 2.6 `coordinator.py` — DataUpdateCoordinator

Subclasses HA's `DataUpdateCoordinator[CoordinatorData]`:

```python
class DataUpdateCoordinator(BaseCoordinator[CoordinatorData]):
    config_entry: IntegrationConfigEntry

    def __init__(self, hass, config_entry):
        # Instance-specific logger
        # Create HA interface layer
        # Initialize business logic engine
        ...

    async def _async_update_data(self) -> CoordinatorData:
        # Resolve settings, gather states, run business logic
        ...
```

- **`_async_update_data()`** — Called periodically at `UPDATE_INTERVAL` (60s). Resolves config, gathers entity states, delegates to business logic, returns `CoordinatorData`.
- **Error handling** — Critical errors (`UpdateFailed`) make entities unavailable. Unexpected errors return empty results to keep entities available.
- **Per-instance logging** — Uses `Log(entry_id=...)` for prefixed log messages.

### 2.7 `entity.py` — Base Entity Class

```python
class IntegrationEntity(CoordinatorEntity[DataUpdateCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            model=INTEGRATION_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )
```

- All entities inherit from this, ensuring they appear under one device.
- `_attr_has_entity_name = True` enables the HA entity naming convention.
- `device_info` uses `entry_id` as the device identifier, supporting multiple instances.

### 2.8 `log.py` — Per-Instance Logger

```python
class Log:
    def __init__(self, entry_id: str | None = None):
        if entry_id:
            short_id = entry_id[-5:]
            self._logger = logging.getLogger(f"{_BASE_LOGGER_NAME}.{short_id}")
        else:
            self._logger = logging.getLogger(_BASE_LOGGER_NAME)
```

- Creates child loggers using the last 5 chars of `entry_id`.
- Enables per-instance log level control (verbose mode for one instance doesn't affect others).
- Implements the `logging.Logger` interface (`debug`, `info`, `warning`, `error`, `exception`, `setLevel`).

### 2.9 `ha_interface.py` — HA API Abstraction

Encapsulates all direct HA API calls behind a clean interface:

- `set_cover_position()` — Handles position-capable vs binary covers, simulation mode.
- `get_weather_condition()` — Reads weather entity state.
- `get_sun_data()` — Reads sun sensor attributes.
- `get_daily_forecast()` — Calls weather forecast service.
- `add_logbook_entry()` — Creates translated logbook entries.

**Why**: Keeps business logic testable in isolation. Tests mock `HomeAssistantInterface` instead of mocking raw HA internals.

---

## 3. Platform Entity Patterns

Each platform follows an identical structure. Here's the pattern using switches as an example:

### 3.1 Platform File Structure (`switch.py`)

```python
# 1. async_setup_entry — creates and registers entities
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data.coordinator
    entities = [EnabledSwitch(coordinator), SimulationModeSwitch(coordinator), ...]
    async_add_entities(entities)

# 2. Base class — inherits IntegrationEntity + HA platform entity
class IntegrationSwitch(IntegrationEntity, SwitchEntity):
    def __init__(self, coordinator, entity_description, config_key):
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._config_key = config_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    @property
    def is_on(self):
        resolved = resolve_entry(self.coordinator.config_entry)
        return bool(getattr(resolved, self._config_key))

    async def _async_persist_option(self, key, value):
        """Update config entry options → triggers smart reload listener."""
        entry = self.coordinator.config_entry
        options = dict(entry.options or {})
        options[key] = value
        self.coordinator.hass.config_entries.async_update_entry(entry, options=options)

# 3. Concrete entity
class EnabledSwitch(IntegrationSwitch):
    def __init__(self, coordinator):
        super().__init__(coordinator, SwitchEntityDescription(
            key=ConfKeys.ENABLED.value,
            translation_key=ConfKeys.ENABLED.value,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:toggle-switch-outline",
        ), ConfKeys.ENABLED.value)
```

### 3.2 Entity Unique IDs

All entities use `f"{entry_id}_{key}"` as their unique ID, enabling multi-instance support.

### 3.3 Platforms Registered

Platforms are declared in `__init__.py`:

```python
PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
```

Each has its own `.py` file with `async_setup_entry`.

---

## 4. Config Flow & Options Flow

### 4.1 Config Flow (`config_flow.py`)

The initial setup flow is minimal — it creates the entry with defaults:

```python
class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        # Show welcome message, create entry with empty options
        ...
```

### 4.2 Options Flow (Multi-Step Wizard)

All real configuration happens in the options flow, split across 5 steps:

| Step | Purpose |
|---|---|
| `init` (Step 1) | Select weather entity and covers |
| Step 2 | Per-cover azimuth configuration |
| Step 3 | Per-cover min/max positions (with collapsible sections) |
| Step 4 | Per-cover window sensors (collapsible sections) |
| Step 5 | Time settings: nighttime blocking, disabled time range, evening closure |

**Key patterns**:
- **`FlowHelper`** — Static validation and schema builder methods, separated from flow state.
- **Validation** — Entity existence checks, feature checks (e.g., weather must support daily forecast).
- **Dynamic schemas** — Built per step based on current config (e.g., one azimuth field per configured cover).
- **Sections** — HA's `section()` helper for collapsible groups in the UI.
- **Data flow** — Each step merges its `user_input` into accumulated `_options`, which are saved at the end.

### 4.3 Settings Persistence

All settings are stored in `config_entry.options` (not `config_entry.data`). The `resolve()` function in `config.py` resolves effective values: `options → defaults`.

---

## 5. Services

### 5.1 Definition

Services are defined in `services.yaml` and registered programmatically in `__init__.py`:

```python
# Idempotent registration
if not hass.services.has_service(DOMAIN, SERVICE_NAME):
    hass.services.async_register(DOMAIN, SERVICE_NAME, handler, schema=schema)
```

### 5.2 Service Cleanup

Services are removed in `async_unload_entry` when the last instance is unloaded.

### 5.3 Multi-Instance Routing

Service handlers route to the correct coordinator by matching:
1. Explicit `config_entry_id` parameter.
2. Entity ID matching against coordinator's managed entities.
3. Fallback to first available coordinator.

---

## 6. Translations

### 6.1 Structure (`translations/en.json`)

```json
{
    "config": { "step": { ... } },
    "options": { "error": { ... }, "step": { ... } },
    "entity": {
        "binary_sensor": { "<key>": { "name": "...", "state": { "on": "...", "off": "..." } } },
        "sensor": { ... },
        "number": { ... },
        "switch": { ... },
        "select": { "<key>": { "name": "...", "state": { "<value>": "..." } } }
    },
    "services": { ... },
    "selector": { ... }
}
```

- Entity names come from `translation_key` on the entity description.
- Config/options flow labels come from the step/data keys.
- 10 languages supported; tests verify all translations are complete.

---

## 7. Multi-Instance Support

The integration fully supports multiple instances (e.g., automating different groups of covers):

- **Unique IDs** use `entry_id` prefix: `f"{entry_id}_{key}"`.
- **Device info** uses `entry_id` in identifiers.
- **Coordinators** are tracked in `hass.data[DOMAIN][DATA_COORDINATORS]` dict keyed by `entry_id`.
- **Services** are registered once globally and route to the correct coordinator.
- **Logging** uses child loggers with `entry_id` suffix for instance isolation.
- **Unique ID migration** handles upgrading from single-instance to multi-instance format.

---

## 8. Testing Approach

### 8.1 Test Dependencies

```
pytest>=8.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
pytest-homeassistant-custom-component==0.13.271
mypy>=1.0.0
```

The `pytest-homeassistant-custom-component` plugin provides HA test infrastructure. Most tests use manual mocks for speed.

### 8.2 Test Organization

| Directory | Scope | Description |
|---|---|---|
| `unit/` | Pure Python | Tests for `config`, `const`, `entity`, `log`, `util` with no HA dependencies |
| `components/` | Per-platform | Tests for each entity platform (setup, properties, state) |
| `coordinator/` | Core logic | 15 test files covering the coordinator exhaustively |
| `config_flow/` | UI flows | Config and options flow (100% coverage required) |
| `ha_interface/` | HA API layer | Tests for the HA abstraction layer |
| `initialization/` | Lifecycle | Setup, teardown, reload, migration, services |
| `integration/` | End-to-end | Full automation scenario tests |
| `edge_cases/` | Robustness | Invalid data, boundary conditions |
| `localization/` | Translations | Verifies all languages have complete translations |

### 8.3 Key Testing Patterns

**Shared fixtures** (`conftest.py`):
- `mock_hass` — Fully mocked HA instance with states, services, config_entries.
- `coordinator` / `sun_coordinator` — Pre-configured coordinator instances.
- `create_temperature_config()` / `create_sun_config()` — Config builder functions.
- `assert_service_called()` — Helper to verify HA service calls.
- `_quiet_logs` (autouse) — Suppresses logs to ERROR; tests opt-in to lower levels.
- Centralized test constants: `MOCK_COVER_ENTITY_ID`, `TEST_HOT_TEMP`, etc.

**Parameterized tests** — Entity tests use data-driven configs:
```python
SWITCH_CONFIGS = [
    {"key": "enabled", "config_key": ConfKeys.ENABLED, ...},
    {"key": "simulation_mode", ...},
]

@pytest.mark.parametrize("config", SWITCH_CONFIGS)
async def test_switch_properties(config): ...
```

**Class-based** — Tests are organized in classes with optional inheritance:
```python
class TestErrorHandling(TestDataUpdateCoordinatorBase):
    async def test_weather_entity_missing(self): ...
```

### 8.4 Running Tests

```bash
scripts/test          # Full suite: mypy + pytest with coverage
scripts/lint          # ruff format + check
scripts/type-check    # mypy only

# Individual test file:
python3 -m pytest tests/unit/test_config.py -v
```

---

## 9. Development Environment

### 9.1 Dev Container (`.devcontainer.json`)

```json
{
    "image": "mcr.microsoft.com/devcontainers/python:3.13",
    "postCreateCommand": "scripts/setup",
    "forwardPorts": [8123, 4000],
    "customizations": {
        "vscode": {
            "extensions": ["charliermarsh.ruff", "ms-python.python", "ms-python.vscode-pylance"],
            "settings": { "python.testing.pytestEnabled": true, ... }
        }
    }
}
```

### 9.2 Tool Configuration (`pyproject.toml`)

- **pytest**: `asyncio_mode = "auto"`, strict markers/config, coverage for `custom_components.<domain>`.
- **coverage**: Source = `custom_components/<domain>`, excludes tests and `TYPE_CHECKING` blocks.
- **ruff**: Target Python 3.13, line length 140, essential rules only (E4/E7/E9/F/I). Relaxed rules for test files.
- **mypy**: Strict-ish (no `strict = true`, but `disallow_untyped_defs`, `warn_return_any`, etc.). Ignores HA module imports.

### 9.3 Local HA Instance

`config/configuration.yaml` configures a local HA dev instance with debug logging enabled for the integration. Run with `scripts/run-ha`.

---

## 10. Adapting for a New Integration

### Step 1 — Rename and Clean

1. Copy the project.
2. Replace `smart_cover_automation` with your `<domain>` everywhere (folder name, `DOMAIN`, imports).
3. Replace `Smart Cover Automation` with your display name.
4. Update `manifest.json` (domain, name, dependencies, version).
5. Update `hacs.json` if publishing to HACS.

### Step 2 — Define Your Constants (`const.py`)

1. Set `DOMAIN` and `INTEGRATION_NAME`.
2. Define entity key constants for your platforms.
3. Define any enums for typed values.
4. Remove domain-specific constants (cover positions, weather conditions, etc.).

### Step 3 — Define Your Settings (`config.py`)

1. Update `ConfKeys` enum with your settings.
2. Update `CONF_SPECS` registry with defaults, converters, and runtime_configurable flags.
3. Update `ResolvedConfig` dataclass to match.

### Step 4 — Define Your Data Types (`data.py`)

1. Update `CoordinatorData` with the fields your coordinator will produce each cycle.
2. Keep `RuntimeData` structure as-is (coordinator + integration + config).

### Step 5 — Implement Your Coordinator (`coordinator.py`)

1. Implement `_async_update_data()` with your domain logic.
2. Set `UPDATE_INTERVAL` appropriately.
3. Keep the error handling pattern (critical vs non-critical errors).

### Step 6 — Implement HA Interface (`ha_interface.py`)

1. Replace cover/weather API calls with your domain's HA API interactions.
2. Define custom exception classes for your error cases.
3. Keep the abstraction — this is what makes business logic testable.

### Step 7 — Implement Business Logic

1. Replace `automation_engine.py` and `cover_automation.py` with your domain logic.
2. Keep business logic decoupled from HA — accept data in, return decisions out.
3. The coordinator orchestrates between HA interface and business logic.

### Step 8 — Implement Entities

For each platform:
1. Keep the base class pattern (e.g., `IntegrationSensor` inheriting `IntegrationEntity` + `SensorEntity`).
2. Define concrete entities with `EntityDescription` objects.
3. Wire properties to coordinator data or resolved settings.
4. For writable entities (switch, number, select), use `_async_persist_option()` to save to config.

### Step 9 — Implement Config/Options Flow

1. Keep `FlowHandler` simple (create entry with defaults).
2. Adapt `OptionsFlowHandler` steps to your settings.
3. Use `FlowHelper` for validation and schema building.
4. Update `translations/en.json` for all flow steps and entity names.

### Step 10 — Implement Services (if needed)

1. Define in `services.yaml`.
2. Register in `async_setup_entry()` with idempotent check.
3. Clean up in `async_unload_entry()`.
4. Add translations in `en.json` under `"services"`.

### Step 11 — Write Tests

1. Start with `conftest.py` — define your mock entities, config builders, and fixtures.
2. Mirror the test directory structure.
3. Test config flow at 100% coverage.
4. Test coordinator logic exhaustively.
5. Add translation completeness tests.

---

## 11. Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                  Home Assistant                      │
│                                                      │
│  ┌──────────────┐    ┌─────────────────────────┐     │
│  │ Config Flow   │───▶│ config_entry.options     │    │
│  │ Options Flow  │    │ (all settings stored     │    │
│  └──────────────┘    │  in options, not data)   │    │
│                       └─────────┬───────────────┘    │
│                                 │                    │
│  ┌──────────────────────────────▼──────────────┐     │
│  │           __init__.py                        │    │
│  │  async_setup_entry() / async_unload_entry()  │    │
│  │  async_reload_entry() (smart reload)         │    │
│  └──────────────────┬──────────────────────────┘    │
│                      │                               │
│  ┌───────────────────▼─────────────────────────┐    │
│  │         DataUpdateCoordinator                │    │
│  │  - Periodic refresh (UPDATE_INTERVAL)        │    │
│  │  - Resolves config via config.py             │    │
│  │  - Delegates to business logic               │    │
│  │  - Returns CoordinatorData                   │    │
│  └───┬───────────────────────────────┬─────────┘    │
│      │                               │               │
│  ┌───▼───────────┐     ┌────────────▼───────────┐   │
│  │ HA Interface   │     │   Business Logic       │   │
│  │ (ha_interface) │◀────│   (automation_engine,  │   │
│  │ - API calls    │     │    cover_automation)   │   │
│  │ - Translations │     │   - Pure logic         │   │
│  └───────────────┘     │   - No HA dependency   │   │
│                         └────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐    │
│  │            Entity Layer                      │    │
│  │  IntegrationEntity (base)                    │    │
│  │    ├── IntegrationBinarySensor               │    │
│  │    ├── IntegrationSensor                     │    │
│  │    ├── IntegrationSwitch (writes to config)  │    │
│  │    ├── IntegrationNumber (writes to config)  │    │
│  │    └── IntegrationSelect (writes to config)  │    │
│  │                                              │    │
│  │  Read-only entities pull from CoordinatorData│    │
│  │  Writable entities persist to config options │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 12. Design Principles

1. **No magic strings** — All keys, entity IDs, and HA constants are centrally defined in `const.py`.
2. **Typed configuration** — `ConfKeys` enum + `ResolvedConfig` dataclass prevent typos and provide IDE support.
3. **Separation of concerns** — Business logic is decoupled from HA APIs via `ha_interface.py`.
4. **Smart reload** — Runtime-configurable settings skip costly full reloads.
5. **Multi-instance ready** — All IDs, logging, and state are scoped to `entry_id`.
6. **Robust error handling** — Critical errors make entities unavailable; non-critical errors preserve system stability.
7. **Comprehensive testing** — Test structure mirrors code structure; fixtures eliminate duplication.
8. **Per-instance logging** — Child loggers enable per-instance verbose mode control.
