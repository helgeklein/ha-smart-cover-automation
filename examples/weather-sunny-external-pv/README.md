# PV Curve Analysis

This folder contains two ways to compare measured PV output with the Home Assistant estimate formula:

- `analyze_pv_curve.py`: repeatable script that reads CSV and writes one overlay chart as HTML.
- `pv_curve_analysis.ipynb`: notebook for interactive tuning in VS Code.

## Input data

The script and notebook expect a Home Assistant history export CSV.

Supported column sets:

- `entity_id`, `state`, `last_changed`
- `sensor name`, `sensor value`, `timestamp`

The file must contain history for all three entities:

- measured PV power
- solar azimuth
- solar elevation

The loader aligns the entity histories by timestamp and forward-fills the latest solar values to each measured-power sample.

## Python setup

This example uses its own Python environment and dependencies. They are intentionally separate from the main repository's development environment.

If you work on this repository in a devcontainer, create and use the virtual environment inside the container:

```bash
cd examples/weather-sunny-external-pv
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The requirements include `ipykernel`, which is needed for the virtual environment to appear as a notebook kernel in VS Code.

The workspace is configured to search for this example environment via `.vscode/settings.json`.

Then select `examples/weather-sunny-external-pv/.venv/bin/python` as the interpreter in VS Code and use the same interpreter as the kernel for `pv_curve_analysis.ipynb`. If the environment does not appear immediately, run `Developer: Reload Window` once and reopen the notebook.

After a devcontainer rebuild, this should continue to work as long as `examples/weather-sunny-external-pv/.venv` still exists. If the virtual environment is gone, recreate it with the commands above and then reload the window.

For the notebook workflow in VS Code, install these Microsoft extensions if they are not already present:

- `ms-python.python`
- `ms-toolsai.jupyter`

The local virtual environment is ignored by Git via `.gitignore`.

## Run the script

```bash
python analyze_pv_curve.py data/history.csv --output output/pv_curve_overlay.html --measured-power-sensor sensor.fems_productiondcactualpower --azimuth-sensor sensor.smart_cover_automation_sonnenazimut --elevation-sensor sensor.smart_cover_automation_sonnenhohe
```

Useful parameters:

- `--peak-power 7600`
- `--min-elevation 1`
- `--exponent 0.8`
- `--shape-point 170 0.9`
- `--shape-point 210 0.75`
- `--measured-power-sensor sensor.fems_productiondcactualpower`
- `--azimuth-sensor sensor.smart_cover_automation_sonnenazimut`
- `--elevation-sensor sensor.smart_cover_automation_sonnenhohe`

The script writes an interactive Plotly HTML chart to `output/`, which is ignored by Git.

## Use the notebook

Open `pv_curve_analysis.ipynb`, select the example virtual environment as the kernel, update the CSV path, entity names, and parameters in the first code cell, then run the next two code cells. The last code cell renders the chart.

## Git ignore behavior

The local `.gitignore` in this folder excludes:

- `.venv/` for the example-specific virtual environment
- `.ipynb_checkpoints/` and Python cache files
- `output/` for generated charts
- `data/history.csv` for local exports that should not be committed

That scope is appropriate for this example because it keeps the ignore rules close to the example-specific artifacts without affecting the rest of the repository.
