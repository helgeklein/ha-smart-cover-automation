# Issue Title

Per-cover sun azimuth start/end in Home Assistant options flow

# Issue Body

## Purpose and use case

I want to support per-cover sun azimuth window configuration in the Home Assistant GUI, so each window/cover can have its own sun hit range instead of relying only on the global azimuth tolerance.

This is especially useful when a house does not have a simple rectangular shape. In such cases, a building corner can shade a specific window earlier than the default azimuth window assumes, so per-cover start/end values are needed for accurate behavior.

Specifically, in step 2 of the configuration wizard, each cover should allow:

- Sun azimuth start
- Sun azimuth end

These values should override global settings for that specific cover when provided.

## Architecture

- Keep global sun azimuth tolerance start/end as defaults.
- Add optional per-cover override keys for start/end.
- Resolve effective values with the following precedence:
  1. Per-cover start/end override
  2. Legacy per-cover tolerance fallback
  3. Global start/end values

## Implementation already done

1. Added per-cover config keys:

- cover_sun_azimuth_tolerance_start
- cover_sun_azimuth_tolerance_end

2. Extended options flow step 2:

- Added optional per-cover sun azimuth window section.
- Added per-cover start/end fields.
- Kept fields optional to allow no override.

3. Added validation:

- Accept integer values or empty input.
- Reject invalid non-integer text and stay on step 2 with field-level errors.

4. Updated step 2 persistence logic:

- Store per-cover start/end values to config data.
- Handle collapsed section submission correctly.
- Preserve default cover azimuth for newly added covers when azimuth section is omitted.

5. Added localization and UX messaging:

- Step 2 text clarifies that per-cover values override global settings.

6. Added and updated tests:

- Section visibility in step 2.
- Correct save of per-cover start/end.
- Validation of invalid input.
- Edge cases: collapsed sections, new covers, legacy fallback handling.

## Expected behavior

- GUI supports per-cover sun azimuth start/end configuration.
- Empty per-cover values mean global settings are used.
- Set per-cover values take precedence over global values.

## Acceptance criteria

- [ ] Step 2 displays per-cover start/end fields.
- [ ] Empty values do not cause validation errors.
- [ ] Invalid values are blocked with clear errors.
- [ ] Legacy per-cover tolerance is still respected as fallback.
- [ ] Config and options flow tests pass.
