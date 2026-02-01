# Plan: Add Global Max/Min Closure Settings to Step 3

## Problem

Step 3 currently only contains two collapsed per-cover sections (min/max positions). If the user doesn't expand at least one section, the form submission fails in step 4 with error:

```
"extra keys not allowed @ data['section_window_sensors']"
```

## Solution

Add global `COVERS_MAX_CLOSURE` and `COVERS_MIN_CLOSURE` settings **above** the per-cover sections. This ensures:

1. The form always has visible required fields
2. Users can set a default for all covers without configuring each individually

## Files to Modify

### 1. config_flow.py

#### Modify `build_schema_step_3` (lines 131-158)

- Change method signature from:
  ```python
  def build_schema_step_3(covers: list[str], defaults: Mapping[str, Any]) -> vol.Schema:
  ```
  To:
  ```python
  def build_schema_step_3(covers: list[str], defaults: Mapping[str, Any], resolved_settings: ResolvedConfig) -> vol.Schema:
  ```

- Add two global settings **before** the per-cover sections:
  - `COVERS_MAX_CLOSURE` - NumberSelector (0-100, step 1, unit %)
  - `COVERS_MIN_CLOSURE` - NumberSelector (0-100, step 1, unit %)

#### Modify `async_step_3` (lines 777-816)

- Update call to `build_schema_step_3` to pass `resolved_settings`
- Store the global settings (`covers_max_closure`, `covers_min_closure`) in `_config_data` when processing user input

### 2. translations/en.json

#### Add to `options.step.3`

Add `data` and `data_description` sections with labels and help text:

```json
"data": {
    "covers_max_closure": "Maximum cover position (all covers):",
    "covers_min_closure": "Minimum cover position (all covers):"
},
"data_description": {
    "covers_max_closure": "The maximum closed position for all covers (0 = fully closed, 100 = fully open). Per-cover overrides can be set below.",
    "covers_min_closure": "The minimum open position for all covers (0 = fully closed, 100 = fully open). Per-cover overrides can be set below."
}
```

## Implementation Details

### Number selector configuration

Matching existing entity number settings from the codebase:

- Min: 0
- Max: 100
- Step: 1
- Unit: `%`
- Mode: `box`

### Default values

From `config.py` CONF_SPECS:

- `COVERS_MAX_CLOSURE`: 0 (fully closed maximum)
- `COVERS_MIN_CLOSURE`: 100 (fully open minimum)

## Testing

After implementation:

1. Run `scripts/lint` to check for errors
2. Run existing tests to ensure no regressions
3. Update/add tests for step 3 if needed to maintain 100% coverage on config_flow.py
