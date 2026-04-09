from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go

COLOGNE_TIMEZONE = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class EstimateParameters:
    peak_power_w: float = 7600.0
    min_elevation_deg: float = 1.0
    exponent: float = 0.8
    # Shape points are (solar azimuth in degrees, multiplier) pairs.
    # The curve implicitly starts at azimuth 0.0 with multiplier 1.0 and
    # ends at azimuth 360.0 with multiplier 1.0.
    shape_points: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "shape_points", normalize_shape_points(self.shape_points))


@dataclass(frozen=True)
class HaEntityNames:
    measured_power_sensor: str | None = None
    azimuth_sensor: str | None = None
    elevation_sensor: str | None = None


def normalize_shape_points(
    shape_points: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    normalized_points = tuple(sorted((float(azimuth_deg), float(multiplier)) for azimuth_deg, multiplier in shape_points))
    for index, (azimuth_deg, _) in enumerate(normalized_points):
        if not 0.0 <= azimuth_deg <= 360.0:
            raise ValueError("Shape point azimuths must be within 0 to 360 degrees.")
        if index > 0 and azimuth_deg == normalized_points[index - 1][0]:
            raise ValueError("Shape point azimuths must be unique.")
    return normalized_points


def interpolate_shape_factor(
    azimuth_deg: float,
    shape_points: tuple[tuple[float, float], ...],
) -> float:
    if not shape_points:
        return 1.0

    profile_points = list(shape_points)
    if profile_points[0][0] > 0.0:
        profile_points.insert(0, (0.0, 1.0))
    if profile_points[-1][0] < 360.0:
        profile_points.append((360.0, 1.0))

    if azimuth_deg <= profile_points[0][0]:
        return profile_points[0][1]
    if azimuth_deg >= profile_points[-1][0]:
        return profile_points[-1][1]

    for (start_azimuth_deg, start_multiplier), (end_azimuth_deg, end_multiplier) in zip(
        profile_points,
        profile_points[1:],
    ):
        if azimuth_deg <= end_azimuth_deg:
            interval_width = end_azimuth_deg - start_azimuth_deg
            if interval_width <= 0:
                return end_multiplier
            interval_progress = (azimuth_deg - start_azimuth_deg) / interval_width
            return start_multiplier + ((end_multiplier - start_multiplier) * interval_progress)

    return profile_points[-1][1]


def estimate_power_w(
    elevation_deg: float,
    azimuth_deg: float,
    params: EstimateParameters,
) -> float:
    if elevation_deg <= params.min_elevation_deg:
        return 0.0

    baseline_ratio = max(0.0, math.sin(math.radians(elevation_deg)))
    baseline_power_w = params.peak_power_w * (baseline_ratio**params.exponent)
    shape_factor = interpolate_shape_factor(azimuth_deg, params.shape_points)
    return max(0.0, baseline_power_w * shape_factor)


def finalize_input_data(data: pd.DataFrame) -> pd.DataFrame:
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["measured_power_w"] = pd.to_numeric(data["measured_power_w"], errors="coerce")
    data["azimuth_deg"] = pd.to_numeric(data["azimuth_deg"], errors="coerce")
    data["elevation_deg"] = pd.to_numeric(data["elevation_deg"], errors="coerce")
    data = data.dropna(subset=["measured_power_w", "azimuth_deg", "elevation_deg"])
    return data


def load_home_assistant_history_csv(
    data: pd.DataFrame,
    entity_names: HaEntityNames,
) -> pd.DataFrame:
    entity_map = {
        entity_names.measured_power_sensor: "measured_power_w",
        entity_names.azimuth_sensor: "azimuth_deg",
        entity_names.elevation_sensor: "elevation_deg",
    }
    if not all(entity_map):
        raise ValueError("Provide --measured-power-sensor, --azimuth-sensor, and --elevation-sensor.")

    rename_map = {
        "sensor_name": "entity_id",
        "sensor_value": "state",
        "last_changed": "timestamp",
    }
    data = data.rename(columns=rename_map)
    required_columns = {"entity_id", "state", "timestamp"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        raise ValueError(
            "Unsupported Home Assistant CSV format. Expected entity_id/state/last_changed "
            f"or sensor name/sensor value/timestamp. Missing columns: {missing_list}"
        )

    filtered = data[data["entity_id"].isin(entity_map)].copy()
    if filtered.empty:
        available_entities = ", ".join(sorted(data["entity_id"].dropna().astype(str).unique()))
        raise ValueError(f"None of the requested entities were found in the CSV. Available entities: {available_entities}")

    filtered["series_name"] = filtered["entity_id"].map(entity_map)
    filtered["state"] = pd.to_numeric(filtered["state"], errors="coerce")
    filtered["timestamp"] = pd.to_datetime(filtered["timestamp"], utc=True)
    filtered = filtered.dropna(subset=["timestamp", "state"])

    reshaped = (
        filtered.pivot_table(
            index="timestamp",
            columns="series_name",
            values="state",
            aggfunc="last",
        )
        .sort_index()
        .ffill()
        .reset_index()
        .rename_axis(columns=None)
    )

    missing_columns = {"timestamp", "measured_power_w", "azimuth_deg", "elevation_deg"} - set(reshaped.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"The Home Assistant history export could not be reshaped into the required columns. Missing after pivot: {missing_list}"
        )

    reshaped = reshaped[reshaped["measured_power_w"].notna()].copy()
    return finalize_input_data(reshaped)


def load_input_csv(
    csv_path: Path,
    entity_names: HaEntityNames,
) -> pd.DataFrame:
    data = pd.read_csv(csv_path)
    data.columns = [str(column).strip().lower().replace(" ", "_") for column in data.columns]
    return load_home_assistant_history_csv(data, entity_names)


def add_estimate_column(
    data: pd.DataFrame,
    params: EstimateParameters,
) -> pd.DataFrame:
    result = data.copy()
    result["estimated_power_w"] = result.apply(
        lambda row: estimate_power_w(
            elevation_deg=float(row["elevation_deg"]),
            azimuth_deg=float(row["azimuth_deg"]),
            params=params,
        ),
        axis=1,
    )
    return result


def build_estimated_curve_data(
    data: pd.DataFrame,
    params: EstimateParameters,
    sample_interval: str = "10s",
) -> pd.DataFrame:
    curve_data = data[["timestamp", "azimuth_deg", "elevation_deg"]].copy()
    curve_data = curve_data.dropna(subset=["timestamp", "azimuth_deg", "elevation_deg"])
    curve_data = curve_data.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    solar_position_changed = curve_data["azimuth_deg"].ne(curve_data["azimuth_deg"].shift()) | curve_data["elevation_deg"].ne(
        curve_data["elevation_deg"].shift()
    )
    keep_mask = solar_position_changed.copy()
    if not curve_data.empty:
        keep_mask.iloc[-1] = True
    curve_data = curve_data[keep_mask]
    curve_data = curve_data.set_index("timestamp")

    dense_curve_data = curve_data.resample(sample_interval).interpolate(method="time")
    dense_curve_data = dense_curve_data.dropna(subset=["azimuth_deg", "elevation_deg"])
    dense_curve_data = dense_curve_data.reset_index()
    dense_curve_data["estimated_power_w"] = dense_curve_data.apply(
        lambda row: estimate_power_w(
            elevation_deg=float(row["elevation_deg"]),
            azimuth_deg=float(row["azimuth_deg"]),
            params=params,
        ),
        axis=1,
    )
    return dense_curve_data


def build_shape_curve_data(
    data: pd.DataFrame,
    params: EstimateParameters,
    sample_interval: str = "10s",
) -> pd.DataFrame:
    shape_curve_data = build_estimated_curve_data(
        data,
        params,
        sample_interval=sample_interval,
    )[["timestamp", "azimuth_deg"]].copy()
    shape_curve_data["shape_multiplier"] = shape_curve_data["azimuth_deg"].apply(
        lambda azimuth_deg: interpolate_shape_factor(float(azimuth_deg), params.shape_points)
    )
    return shape_curve_data


def build_shape_point_time_data(
    shape_curve_data: pd.DataFrame,
    params: EstimateParameters,
) -> pd.DataFrame:
    if not params.shape_points or shape_curve_data.empty:
        return pd.DataFrame(columns=["timestamp", "shape_multiplier", "azimuth_deg"])

    point_rows: list[dict[str, object]] = []
    azimuth_values = shape_curve_data["azimuth_deg"].tolist()
    timestamp_values = shape_curve_data["timestamp"].tolist()

    for azimuth_deg, multiplier in params.shape_points:
        for index in range(1, len(azimuth_values)):
            start_azimuth = float(azimuth_values[index - 1])
            end_azimuth = float(azimuth_values[index])
            if start_azimuth <= azimuth_deg <= end_azimuth:
                azimuth_span = end_azimuth - start_azimuth
                if azimuth_span <= 0:
                    timestamp = timestamp_values[index]
                else:
                    progress = (azimuth_deg - start_azimuth) / azimuth_span
                    timestamp_span = timestamp_values[index] - timestamp_values[index - 1]
                    timestamp = timestamp_values[index - 1] + (timestamp_span * progress)
                point_rows.append(
                    {
                        "timestamp": timestamp,
                        "shape_multiplier": multiplier,
                        "azimuth_deg": azimuth_deg,
                    }
                )
                break

    return pd.DataFrame(point_rows)


def build_figure(data: pd.DataFrame, title: str, params: EstimateParameters) -> go.Figure:
    local_timestamps = data["timestamp"].dt.tz_convert(COLOGNE_TIMEZONE)
    estimated_curve_data = build_estimated_curve_data(data, params)
    estimated_curve_timestamps = estimated_curve_data["timestamp"].dt.tz_convert(COLOGNE_TIMEZONE)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=local_timestamps,
            y=data["measured_power_w"],
            mode="lines",
            name="Measured",
            line={"width": 1},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=estimated_curve_timestamps,
            y=estimated_curve_data["estimated_power_w"],
            mode="lines",
            name="Estimated",
            line={"width": 1},
        )
    )
    figure.update_layout(
        title=title,
        xaxis_title="Time (Europe/Berlin)",
        yaxis_title="Power (W)",
        template="plotly_white",
        hovermode="x unified",
    )
    return figure


def build_shape_figure(
    data: pd.DataFrame,
    params: EstimateParameters,
    sample_interval: str = "10s",
) -> go.Figure:
    shape_curve_data = build_shape_curve_data(
        data,
        params,
        sample_interval=sample_interval,
    )
    local_timestamps = shape_curve_data["timestamp"].dt.tz_convert(COLOGNE_TIMEZONE)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=shape_curve_data["azimuth_deg"],
            y=shape_curve_data["shape_multiplier"],
            mode="lines",
            name="Shape multiplier",
            line={"width": 2},
            customdata=local_timestamps,
            hovertemplate=("Azimuth: %{x:.1f} deg<br>Multiplier: %{y:.3f}<br>Time: %{customdata|%H:%M:%S}<extra></extra>"),
        )
    )
    shape_point_time_data = build_shape_point_time_data(shape_curve_data, params)
    if not shape_point_time_data.empty:
        figure.add_trace(
            go.Scatter(
                x=shape_point_time_data["azimuth_deg"],
                y=shape_point_time_data["shape_multiplier"],
                mode="markers",
                name="Shape points",
                marker={"size": 7},
                customdata=shape_point_time_data["timestamp"].dt.tz_convert(COLOGNE_TIMEZONE),
                hovertemplate=("Azimuth: %{x:.1f} deg<br>Multiplier: %{y:.3f}<br>Time: %{customdata|%H:%M:%S}<extra></extra>"),
            )
        )
    figure.update_layout(
        title="Shape multiplier by solar azimuth",
        xaxis_title="Solar azimuth (deg)",
        yaxis_title="Multiplier",
        template="plotly_white",
        hovermode="x unified",
    )
    return figure


def run_analysis(
    csv_path: Path,
    output_path: Path,
    params: EstimateParameters,
    entity_names: HaEntityNames,
) -> pd.DataFrame:
    data = load_input_csv(csv_path, entity_names=entity_names)
    data = add_estimate_column(data, params)
    local_timestamps = data["timestamp"].dt.tz_convert(COLOGNE_TIMEZONE)
    title = f"Measured vs estimated PV power: {local_timestamps.dt.date.iloc[0]}"
    figure = build_figure(data, title, params)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(output_path, include_plotlyjs="cdn")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overlay measured and estimated PV power curves using a shaped baseline model.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="data/history.csv",
        help="Home Assistant history export CSV",
    )
    parser.add_argument(
        "--output",
        default="output/pv_curve_shape_overlay.html",
        help="Output HTML chart path",
    )
    parser.add_argument("--peak-power", type=float, default=7600.0)
    parser.add_argument("--min-elevation", type=float, default=1.0)
    parser.add_argument("--exponent", type=float, default=0.8)
    parser.add_argument(
        "--shape-point",
        action="append",
        nargs=2,
        metavar=("AZIMUTH_DEG", "MULTIPLIER"),
        type=float,
        default=[],
        help="Repeatable azimuth/multiplier control point.",
    )
    parser.add_argument("--measured-power-sensor")
    parser.add_argument("--azimuth-sensor")
    parser.add_argument("--elevation-sensor")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = EstimateParameters(
        peak_power_w=args.peak_power,
        min_elevation_deg=args.min_elevation,
        exponent=args.exponent,
        shape_points=tuple((azimuth_deg, multiplier) for azimuth_deg, multiplier in args.shape_point),
    )
    entity_names = HaEntityNames(
        measured_power_sensor=args.measured_power_sensor,
        azimuth_sensor=args.azimuth_sensor,
        elevation_sensor=args.elevation_sensor,
    )
    csv_path = Path(args.csv_path)
    output_path = Path(args.output)
    analyzed = run_analysis(csv_path, output_path, params, entity_names=entity_names)
    print(f"Wrote chart to {output_path}")
    print(analyzed[["timestamp", "measured_power_w", "estimated_power_w"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
