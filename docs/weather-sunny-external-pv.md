---
layout: default
title: "Weather: Sunny? via PV Output"
nav_order: 10
description: "How to determine if the sun is shining from your photovoltaic power output."
permalink: /weather-sunny-external-pv/
---

# How to Determine if the Sun is Shining from Photovoltaic Power Output

## Description

If you have a photovoltaic installation, you can use its current power output as an indicator for sunshine.

Using a fixed watt threshold is too simplistic because clear-sky PV output depends strongly on the sun's elevation above the horizon. A practical approximation is to estimate the current clear-sky power generation (i.e., the potential maximum) from the sun elevation and then compare the actual PV power against that estimate.

This guide shows how to implement that logic in Home Assistant and then feed the resulting sunny/not-sunny signal into Smart Cover Automation via its **Weather: sunny? (external control)** switch.

Many PV systems don't generate a perfect output curve that is mathematically easy to describe. East- or west-facing arrays, mixed roof orientations, and local shading can make the PV curve depart from a simple symmetric clear-sky shape. In that case, it is useful to start with one elevation-based baseline curve and then apply an azimuth-dependent correction profile.

## Requirements

- A PV system that receives directly sunlight during the entire day.
- A Home Assistant sensor that reports your current PV power generation in watts.
- The Home Assistant `sun` integration enabled so that `sun.sun` provides the current elevation and azimuth.
- Smart Cover Automation installed.
- The Smart Cover Automation entity **Weather: sunny? (external control)** enabled.

## Implementation

### Quick Start

If you want the shortest path to a working setup, use this order:

1. Export one mostly cloudless day from Home Assistant history with measured PV power, solar azimuth, and solar elevation.
2. Open the Jupyter notebook in the repository's [examples directory](https://github.com/helgeklein/ha-smart-cover-automation/tree/main/examples/weather-sunny-external-pv/) and tune `peak_power_w`, `exponent`, and, if needed, a small number of `shape_points`.
3. Copy the calibrated values into the template sensor definitions below and create the three HA entities: **PV Clear-Sky Power Estimate**, **PV Utilization**, and **PV Sunny**.
4. Add the automation further below so that `binary_sensor.pv_sunny` drives Smart Cover Automation's **Weather: sunny? (external control)** switch.

### Formula

Estimate the *current* clear-sky maximum PV power in two steps.

First, calculate a baseline from sun elevation:

`P_base(alpha) = P_peak * max(0, sin(alpha))^k`

where:

- `alpha` is the sun elevation above the horizon
- `P_peak` is the absolute clear-sky maximum power of your PV system
- `k` is a global exponent that controls how broad or narrow the elevation-based baseline curve is

Lower `k` makes the curve broader: the estimate rises earlier in the morning, stays higher in the shoulders, and falls later in the evening. Higher `k` makes the curve narrower: the estimate stays lower in the shoulders and drops faster away from the daily peak.

Then optionally correct that baseline with an azimuth-dependent shape multiplier:

`P_max(alpha, azimuth) = P_base(alpha) * shape(azimuth)`

The `shape(azimuth)` function is defined by control points. Each control point is an azimuth/multiplier pair, and the multiplier is linearly interpolated between neighboring points. If no control points are defined, the multiplier is `1.0` everywhere and the model falls back to the pure elevation-based baseline.

This makes the model easy to tune:

- `P_peak` sets the overall height of the curve.
- `k` sets the overall broadness of the curve.
- `shape(azimuth)` handles local effects such as array orientation, shading, or a sharper drop on one side of the day.

Then calculate the current normalized PV percentage as:

`PV% = 100 * P_current / max(P_max(alpha), P_floor)`

The minimum reference power `P_floor` avoids unrealistic percentages close to sunrise and sunset, where the theoretical output is near zero but your inverter may still report a small non-zero value.

Recommended starting values:

- `P_peak`: highest power your PV system generates on sunny days in watts
- `k`: `0.8` to `1.0`
- Shape points: none at first, unless you already know your system has a consistent azimuth-specific distortion
- Minimum sun elevation for the clear-sky estimate: `0°` to `3°`
- Minimum sun elevation for the sunny decision: `8°`
- `P_floor`: `300 W`
- Sunny threshold: `75%`

If your system is fairly symmetric, you may never need any shape points at all.

You should calibrate `P_peak`, `k`, any shape points, and the sunny threshold from a few clear days of your own data (see tips below).

### Template Sensors

Paste the following into `configuration.yaml`.

Adjust the measured-power entity IDs, `peak_power_w`, `min_elevation_deg`, `exponent`, any `shape_points`, and the thresholds to match your installation.

{% raw %}
```yaml
template:
    - sensor:
        - name: "PV Clear-Sky Power Estimate"
        unique_id: pv_clear_sky_power_estimate
        unit_of_measurement: "W"
        device_class: power
        state_class: measurement
        state: >
            {% macro interpolate_shape_factor(azimuth_deg, shape_points) -%}
            {% set ns = namespace(
                previous_azimuth_deg=0.0,
                previous_multiplier=1.0,
                result=1.0,
                matched=false
            ) %}
            {% for point in shape_points %}
                {% set point_azimuth_deg = point['azimuth_deg'] %}
                {% set point_multiplier = point['multiplier'] %}
                {% if not ns.matched and azimuth_deg <= point_azimuth_deg %}
                {% set interval_width = point_azimuth_deg - ns.previous_azimuth_deg %}
                {% if interval_width <= 0 %}
                    {% set ns.result = point_multiplier %}
                {% else %}
                    {% set interval_progress = (azimuth_deg - ns.previous_azimuth_deg) / interval_width %}
                    {% set ns.result = ns.previous_multiplier + ((point_multiplier - ns.previous_multiplier) * interval_progress) %}
                {% endif %}
                {% set ns.matched = true %}
                {% endif %}
                {% if not ns.matched %}
                {% set ns.previous_azimuth_deg = point_azimuth_deg %}
                {% set ns.previous_multiplier = point_multiplier %}
                {% endif %}
            {% endfor %}
            {% if not ns.matched %}
                {% set interval_width = 360.0 - ns.previous_azimuth_deg %}
                {% if interval_width <= 0 %}
                {% set ns.result = 1.0 %}
                {% else %}
                {% set interval_progress = (azimuth_deg - ns.previous_azimuth_deg) / interval_width %}
                {% set ns.result = ns.previous_multiplier + ((1.0 - ns.previous_multiplier) * interval_progress) %}
                {% endif %}
            {% endif %}
            {{ ns.result }}
            {%- endmacro %}

            {# Live sun data #}
            {% set elevation_deg = state_attr('sun.sun', 'elevation') | float(0) %}
            {% set azimuth_deg = state_attr('sun.sun', 'azimuth') | float(0) %}

            {# Parameters transposed from pv_curve_analysis.ipynb #}
            {% set peak_power_w = 6800.0 %}
            {% set min_elevation_deg = 0.0 %}
            {% set exponent = 0.8 %}
            {% set shape_points = [
                # Example azimuth/multiplier points:
                # {'azimuth_deg': 170.0, 'multiplier': 0.9},
                # {'azimuth_deg': 210.0, 'multiplier': 0.75},
            ] %}

            {# Base elevation formula #}
            {% set deg_to_rad = 0.017453292519943295 %}
            {% set current_elevation_rad = elevation_deg * deg_to_rad %}

            {% if elevation_deg <= min_elevation_deg %}
            0
            {% else %}
            {% set baseline_ratio = [0.0, sin(current_elevation_rad)] | max %}
            {% set baseline_power_w = peak_power_w * (baseline_ratio ** exponent) %}
            {% set shape_multiplier = interpolate_shape_factor(azimuth_deg, shape_points) | float(1.0) %}
            {{ (baseline_power_w * shape_multiplier) | round(0) }}
            {% endif %}

        - name: "PV Utilization"
        unique_id: pv_utilization
        unit_of_measurement: "%"
        state_class: measurement
        state: >
            {% set current_power_w = states('sensor.fems_productiondcactualpower') | float(0) %}
            {% set estimated_max_w = states('sensor.pv_clear_sky_power_estimate') | float(0) %}
            {% set minimum_reference_power_w = 300 %}
            {% if estimated_max_w <= 0 %}
            0
            {% else %}
            {% set reference_power_w = [estimated_max_w, minimum_reference_power_w] | max %}
            {{ ([100, (100 * current_power_w / reference_power_w)] | min) | round(0) }}
            {% endif %}

    - binary_sensor:
        - name: "PV Sunny"
        unique_id: pv_sunny
        device_class: light
        delay_on:
            minutes: 5
        delay_off:
            minutes: 10
        state: >
            {% set elevation_deg = state_attr('sun.sun', 'elevation') | float(0) %}
            {% set sunny_threshold_percent = 75 %}
            {% set min_decision_elevation_deg = 3 %}
            {% set pv_utilization_percent = states('sensor.pv_utilization') | float(0) %}
            {{ elevation_deg >= min_decision_elevation_deg and pv_utilization_percent >= sunny_threshold_percent }}
```
{% endraw %}

The `shape_points` list is empty in the code above. That means the shape multiplier is `1.0` everywhere and only the elevation-based baseline is active. If you need azimuth-specific corrections, add dictionaries with `azimuth_deg` and `multiplier` values to that list.

This creates three entities:

- **PV Clear-Sky Power Estimate:** estimated maximum current PV power for the present sun elevation, with an optional azimuth-dependent correction profile.
- **PV Utilization:** current PV generation as a percentage of the estimated potential maximum for the present sun elevation.
- **PV Sunny:** debounced binary sensor that reports whether it is sunny enough according to your threshold. The `delay_on` and `delay_off` settings stabilize the sensor and avoid flapping when a cloud passes over, for example.

### Connect the Result to Smart Cover Automation

Smart Cover Automation does not read the template binary sensor directly. Instead, enable its entity **Weather: sunny? (external control)** and drive that switch from the template binary sensor.

Create an automation in Home Assistant and paste the following YAML. Replace `switch.smart_cover_automation_weather_sunny_external_control` with the actual entity ID of your Smart Cover Automation switch.

```yaml
alias: SCA weather sunny external control from PV
description: "Set the Smart Cover Automation sunny state according to photovoltaic output."
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.pv_sunny
conditions: []
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: binary_sensor.pv_sunny
            state: "on"
        sequence:
          - action: switch.turn_on
            metadata: {}
            target:
              entity_id: switch.smart_cover_automation_weather_sunny_external_control
    default:
      - action: switch.turn_off
        metadata: {}
        target:
          entity_id: switch.smart_cover_automation_weather_sunny_external_control
mode: single
```

After adding the automation, run it manually to set the current state of the **Weather: sunny? (external control)** entity as the automation is only triggered on state changes.

### Calibration

To improve accuracy, calibrate the constants from your own data. The easiest way is to use the companion notebook and script in the repository's [examples directory](https://github.com/helgeklein/ha-smart-cover-automation/tree/main/examples/weather-sunny-external-pv/), because they let you compare measured and estimated power directly and tune the parameters before copying them into Home Assistant.

Recommended workflow:

- Export one mostly cloudless day from Home Assistant history. The notebook expects measured PV power, solar azimuth, and solar elevation.
- Open `examples/weather-sunny-external-pv/pv_curve_analysis.ipynb` and set the CSV path, entity IDs, and initial parameters in the first code cell.
- Start with no shape points.
- Run the notebook and inspect the overlay chart of measured versus estimated PV power.
- Tune `peak_power_w` first until the overall peak height is plausible.
- Tune `exponent` next until the baseline is broadly correct across the day. This parameter should fix large-scale shoulder behavior, not local bumps or dips.
- Only after the baseline is reasonably close, add shape points to correct systematic local deviations at specific azimuths.

How to interpret the parameters:

- If the estimate is too low across most of the day, increase `peak_power_w`. If it is too high across most of the day, decrease it.
- If the estimate rises and falls too quickly away from solar noon, decrease `exponent` slightly.
- If the estimate stays too high in the shoulders and too broad through the day, increase `exponent` slightly.
- If the estimate is only wrong in a limited azimuth range, leave `exponent` alone and use shape points instead.
- Use multipliers below `1.0` where the baseline overestimates production in a specific azimuth window.
- Use multipliers above `1.0` where the baseline underestimates production in a specific azimuth window.

Guidance for shape points:

- Keep the list as small as possible. Add points only where there is a repeatable pattern.
- Treat shape points as local corrections, not as a replacement for the baseline fit.
- Because the multiplier is linearly interpolated, neighboring points influence the whole interval between them.
- Use a few broad corrections before adding narrow notches for local shading effects.
- Recheck the result on more than one clear day if possible, because a very detailed point set can overfit one day's data.

After the estimate is good, tune the sunny decision:

- Copy the calibrated `peak_power_w`, `min_elevation_deg`, `exponent`, and `shape_points` into the Home Assistant template.
- Watch `PV Utilization` on clear, mixed, and cloudy periods.
- Adjust `sunny_threshold_percent` until **PV Sunny** matches your local observation.
- If the state flips too easily at low sun angles, raise `minimum_reference_power_w` and/or `min_decision_elevation_deg`.

Typical useful ranges:

- `peak_power_w`: your system-specific value
- `exponent`: `0.5` to `1.5`
- `shape_point.multiplier`: often `0.3` to `1.1`, depending on how strong the local deviation is
- `shape_point.azimuth_deg`: any solar azimuth where a repeatable deviation begins, ends, or changes slope
- `sunny_threshold_percent`: `60` to `85`
- `min_elevation_deg`: `0` to `3`
- `minimum_reference_power_w`: `200` to `500`

## Test

To test the setup:

1. Verify that **PV Clear-Sky Power Estimate** rises and falls smoothly through the day.
2. Check that **PV Utilization** is high on clear days and low during cloudy periods.
3. Confirm that **PV Sunny** does not flap rapidly when passing clouds move through.
4. Enable Smart Cover Automation's **Weather: sunny? (external control)** entity and verify that the switch follows `binary_sensor.pv_sunny`.

If the sunny state flips too often around sunrise or sunset, raise either `min_decision_elevation_deg` or `minimum_reference_power_w`.
