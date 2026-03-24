from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import mapping

from .processing_parameters import load_parameters_table, load_series_table
from .processing_utils import (
    blank_series,
    choose_series,
    get_passthrough_columns,
    normalize_ascii,
    resolve_description_choice,
    resolve_export_date_series,
    resolve_level3_series,
)


def build_base_output_df(
    *,
    gdf,
    date_col: str | None,
    auto_desc_col: str | None,
    level1_source: str,
    level2_source: str,
    level3_source: str,
    date_source: str | None,
    description_source: str,
    level1_text: str,
    level2_text: str,
    level3_text: str,
    date_text: str,
    description_text: str,
    date_input_format: str | None,
    date_output_format: str,
) -> pd.DataFrame:
    out = gdf.copy()

    out["Coords"] = out.geometry.apply(
        lambda geom: json.dumps(mapping(geom), separators=(",", ":"))
    )

    out["Level1"] = choose_series(out, level1_source, level1_text, blank_series(out))
    out["Level2"] = choose_series(out, level2_source, level2_text, blank_series(out))
    out["Level3"] = resolve_level3_series(out, level3_source, level3_text)

    description_choice = resolve_description_choice(description_source, auto_desc_col)
    out["Description"] = choose_series(
        out,
        description_choice,
        description_text,
        blank_series(out),
    )

    out["Date"] = resolve_export_date_series(
        df=out,
        detected_date_col=date_col,
        date_source=date_source,
        date_text=date_text,
        date_input_format=date_input_format,
        date_output_format=date_output_format,
    )

    for col in ("Level1", "Level2", "Level3", "Date", "Description"):
        out[col] = normalize_ascii(out[col])

    return out


def build_location_import_table(
    out: pd.DataFrame,
    original_input_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    import_table = out[["Level1", "Level2", "Level3", "Date", "Description", "Coords"]].copy()

    duplicate_mask = import_table.duplicated(
        subset=["Level1", "Level2", "Level3", "Date"],
        keep=False,
    )

    source_df = original_input_data.loc[out.index].copy()
    for col in source_df.columns:
        if str(col) == "geometry":
            continue

        out_col = str(col).strip()
        if out_col in import_table.columns:
            out_col = f"{out_col}_src"

        import_table[out_col] = source_df[col].values

    return import_table, duplicate_mask


def build_timeseries_outputs(
    *,
    out: pd.DataFrame,
    timeseries_mappings: list[dict],
    parameters_file: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    if not timeseries_mappings:
        raise ValueError("Time series mode requires at least one parameter mapping.")

    if "Date" not in out.columns or out["Date"].astype(str).str.strip().eq("").all():
        raise ValueError("Time series output requires a valid Date field.")

    parameters_and_units = load_parameters_table(parameters_file)

    passthrough_exclude = {
        "geometry",
        "Level1",
        "Level2",
        "Level3",
        "Date",
        "Parameter",
        "Unit",
        "DatasetName",
        "DatasetID",
        "ParameterId",
        "ParameterName",
        "UnitId",
        "UnitName",
        "Group",
        "MonitoringLocation",
        "MonitoringStation",
        "Value",
        "SourceColumn",
        "SeriesId",
    }
    passthrough_cols = get_passthrough_columns(out, passthrough_exclude)

    caf_timeseries = pd.DataFrame()

    for mapping in timeseries_mappings:
        parameter = str(mapping["parameter"]).strip()
        source_column = str(mapping["source_column"]).strip()
        unit = str(mapping["unit"]).strip()
        dataset_name = str(mapping["dataset_name"]).strip()
        dataset_id = str(mapping["dataset_id"]).strip()

        if source_column not in out.columns:
            raise ValueError(f"Time series source column not found: {source_column}")

        keep_cols = ["Level1", "Level2", "Level3", "Date"] + passthrough_cols
        ts = out[keep_cols].copy()

        ts["SourceColumn"] = source_column
        ts["Value"] = out[source_column]
        ts["Parameter"] = parameter
        ts["Unit"] = unit
        ts["DatasetName"] = dataset_name
        ts["DatasetID"] = dataset_id

        caf_timeseries = pd.concat([caf_timeseries, ts], axis=0, ignore_index=True)

    caf_timeseries["Value"] = pd.to_numeric(caf_timeseries["Value"], errors="coerce")
    bad_values = caf_timeseries[caf_timeseries["Value"].isna()]
    if not bad_values.empty:
        raise ValueError(
            "Some time series values are invalid. Example rows:\n"
            + bad_values.head(5).to_string(index=False)
        )

    caf_timeseries = pd.merge(
        caf_timeseries,
        parameters_and_units,
        left_on=["Parameter", "Unit"],
        right_on=["ParameterName", "Unit"],
        how="inner",
    )

    if caf_timeseries.empty:
        raise ValueError(
            "No match found in parameters.csv for the selected Parameter and Unit mappings."
        )

    caf_timeseries["Group"] = caf_timeseries["Level1"]
    caf_timeseries["MonitoringLocation"] = caf_timeseries["Level2"]
    caf_timeseries["MonitoringStation"] = caf_timeseries["Level3"].astype(str)

    for col in (
        "Group",
        "MonitoringLocation",
        "MonitoringStation",
        "Parameter",
        "Unit",
        "Date",
        "DatasetName",
        "DatasetID",
        "SourceColumn",
    ):
        caf_timeseries[col] = normalize_ascii(caf_timeseries[col])

    series_key_cols = [
        "TsType",
        "DatasetID",
        "DatasetName",
        "Server",
        "IDProdutivo",
        "User",
        "PWD",
        "Group",
        "MonitoringLocation",
        "MonitoringStation",
        "Parameter",
        "Unit",
    ]

    import_timeseries_df = caf_timeseries[
        [
            "MonitoringStation",
            "Group",
            "MonitoringLocation",
            "Parameter",
            "Unit",
            "DatasetName",
            "DatasetID",
        ]
    ].copy()

    import_timeseries_df["TsType"] = 3
    import_timeseries_df["Server"] = "-"
    import_timeseries_df["IDProdutivo"] = "-"
    import_timeseries_df["User"] = np.nan
    import_timeseries_df["PWD"] = np.nan

    import_timeseries_df = import_timeseries_df[
        [
            "TsType",
            "DatasetID",
            "DatasetName",
            "Server",
            "IDProdutivo",
            "User",
            "PWD",
            "Group",
            "MonitoringLocation",
            "MonitoringStation",
            "Parameter",
            "Unit",
        ]
    ].copy()

    import_extra_cols = [
        col
        for col in passthrough_cols
        if col not in import_timeseries_df.columns and col in caf_timeseries.columns
    ]

    if import_extra_cols:
        import_timeseries_df = pd.concat(
            [
                import_timeseries_df,
                caf_timeseries[import_extra_cols].reset_index(drop=True),
            ],
            axis=1,
        )

    import_timeseries_df = import_timeseries_df.drop_duplicates(
        subset=series_key_cols,
        keep="first",
    ).copy()

    values_leading_cols = [
        "MonitoringStation",
        "Group",
        "MonitoringLocation",
        "Parameter",
        "Unit",
        "UnitId",
        "Date",
        "Value",
        "SourceColumn",
        "DatasetName",
        "DatasetID",
    ]

    missing_value_cols = [c for c in values_leading_cols if c not in caf_timeseries.columns]
    if missing_value_cols:
        raise ValueError(
            "Time-series output is missing required columns after parameter merge: "
            + ", ".join(missing_value_cols)
            + ". Regenerate parameters.csv so it includes UnitId."
        )

    values_extra_cols = [
        col
        for col in passthrough_cols
        if col not in values_leading_cols and col in caf_timeseries.columns
    ]

    values_table = caf_timeseries[values_leading_cols + values_extra_cols].copy()

    duplicate_mask = values_table.duplicated(
        subset=["MonitoringStation", "Parameter", "Date"],
        keep=False,
    )

    return import_timeseries_df, values_table, duplicate_mask


def _parse_topology_key(value: str) -> tuple[str, str, str]:
    text = str(value or "").strip()

    group = ""
    location = ""
    station = ""

    if "lvl1:" in text and "_lvl2:" in text:
        group = text.split("lvl1:", 1)[1].split("_lvl2:", 1)[0]

    if "_lvl2:" in text and "_lvl3:" in text:
        location = text.split("_lvl2:", 1)[1].split("_lvl3:", 1)[0]

    if "_lvl3:" in text:
        station = text.split("_lvl3:", 1)[1]

    return group.strip(), location.strip(), station.strip()


def build_series_population_outputs(
    *,
    values_table: pd.DataFrame,
    series_file: str | Path,
    populate_output_dir: str | Path,
) -> tuple[pd.DataFrame, list[Path]]:
    series_df = load_series_table(series_file).copy()

    parsed = series_df["Key"].apply(_parse_topology_key)
    series_df["group"] = parsed.map(lambda x: x[0])
    series_df["location"] = parsed.map(lambda x: x[1])
    series_df["station"] = parsed.map(lambda x: x[2]).astype(str)

    values = values_table.copy()
    values["MonitoringStation"] = values["MonitoringStation"].astype(str)

    merged = values.merge(
        series_df,
        left_on=["Group", "MonitoringLocation", "MonitoringStation", "Parameter", "UnitId"],
        right_on=["group", "location", "station", "Name", "UnitsId"],
        how="inner",
    )

    merged["date"] = pd.to_datetime(merged["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = merged.dropna(subset=["date", "Value", "SeriesId"]).copy()

    populate_output_dir = Path(populate_output_dir)
    populate_output_dir.mkdir(parents=True, exist_ok=True)

    all_path = populate_output_dir / "populate_timeseries_all.csv"
    merged[["date", "Value", "SeriesId"]].rename(columns={"Value": "value"}).to_csv(all_path, index=False)

    per_parameter_paths: list[Path] = [all_path]

    for parameter, gdf in merged.groupby("Parameter", dropna=False):
        safe_parameter = str(parameter).replace("/", "_").replace("\\", "_").replace(" ", "_")
        out_path = populate_output_dir / f"insert_mongo_{safe_parameter}.csv"
        gdf[["date", "Value", "SeriesId"]].rename(columns={"Value": "value"}).to_csv(out_path, index=False)
        per_parameter_paths.append(out_path)

    return merged, per_parameter_paths