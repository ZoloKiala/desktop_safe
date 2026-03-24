from __future__ import annotations

from pathlib import Path

import pandas as pd
import psycopg2

from .processing_constants import OUTPUT_DIR, PARAMETERS_SQL, SERIES_SQL
from .processing_utils import normalize_column_names, safe_text


def create_parameters_csv_from_db(
    output_csv_path: str | Path,
    *,
    db_host: str,
    db_port: int | str,
    db_name: str,
    db_user: str,
    db_password: str,
) -> Path:
    output_csv_path = Path(output_csv_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=int(str(db_port)),
            dbname=db_name,
            user=db_user,
            password=db_password,
        )
        df = pd.read_sql_query(PARAMETERS_SQL, conn)
        df = normalize_column_names(df)
        df.to_csv(output_csv_path, index=False)
        return output_csv_path
    finally:
        if conn is not None:
            conn.close()


def create_series_csv_from_db(
    output_csv_path: str | Path,
    *,
    db_host: str,
    db_port: int | str,
    db_name: str,
    db_user: str,
    db_password: str,
) -> Path:
    output_csv_path = Path(output_csv_path)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=int(str(db_port)),
            dbname=db_name,
            user=db_user,
            password=db_password,
        )
        df = pd.read_sql_query(SERIES_SQL, conn)
        df = normalize_column_names(df)
        df.to_csv(output_csv_path, index=False)
        return output_csv_path
    finally:
        if conn is not None:
            conn.close()


def get_default_parameters_csv_path() -> Path:
    return OUTPUT_DIR / "parameters.csv"


def get_default_series_csv_path() -> Path:
    return OUTPUT_DIR / "Series.csv"


def ensure_parameters_csv(
    *,
    preferred_file: str | Path | None = None,
    db_host: str = "",
    db_port: int | str = "",
    db_name: str = "",
    db_user: str = "",
    db_password: str = "",
    always_create: bool = False,
) -> Path:
    if preferred_file:
        preferred_path = Path(preferred_file)
        if preferred_path.exists():
            return preferred_path

    csv_path = get_default_parameters_csv_path()

    if csv_path.exists() and not always_create:
        return csv_path

    has_db_config = all(
        [
            safe_text(db_host),
            safe_text(db_name),
            safe_text(db_user),
            safe_text(db_password),
            safe_text(db_port),
        ]
    )

    if has_db_config:
        return create_parameters_csv_from_db(
            csv_path,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
        )

    if csv_path.exists():
        return csv_path

    raise ValueError(
        "No parameters.csv available for time series mode.\n"
        "Generate parameters.csv first. If database access fails, upload parameter_catalog.csv."
    )


def ensure_series_csv(
    *,
    preferred_file: str | Path | None = None,
    db_host: str = "",
    db_port: int | str = "",
    db_name: str = "",
    db_user: str = "",
    db_password: str = "",
    always_create: bool = False,
) -> Path:
    if preferred_file:
        preferred_path = Path(preferred_file)
        if preferred_path.exists():
            return preferred_path

    csv_path = get_default_series_csv_path()

    if csv_path.exists() and not always_create:
        return csv_path

    has_db_config = all(
        [
            safe_text(db_host),
            safe_text(db_name),
            safe_text(db_user),
            safe_text(db_password),
            safe_text(db_port),
        ]
    )

    if has_db_config:
        return create_series_csv_from_db(
            csv_path,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
        )

    if csv_path.exists():
        return csv_path

    raise ValueError(
        "No Series.csv available for time series mode.\n"
        "Generate Series.csv first from the database."
    )


def load_parameters_table(parameters_file: str | Path) -> pd.DataFrame:
    path = Path(parameters_file)
    if not path.exists():
        raise ValueError(f"Parameters file not found: {path}")

    df = pd.read_csv(path)
    df = normalize_column_names(df)

    rename_map = {}
    for col in df.columns:
        key = str(col).strip().casefold()
        if key == "parameter":
            rename_map[col] = "ParameterName"
        elif key == "parametername":
            rename_map[col] = "ParameterName"
        elif key == "parameterid":
            rename_map[col] = "ParameterId"
        elif key == "unit":
            rename_map[col] = "Unit"
        elif key == "unitid":
            rename_map[col] = "UnitId"

    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"ParameterName", "Unit", "UnitId"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "parameters.csv is missing required columns for time-series series matching: "
            + ", ".join(sorted(missing))
        )

    df["ParameterName"] = df["ParameterName"].fillna("").astype(str).str.strip()
    df["Unit"] = df["Unit"].fillna("").astype(str).str.strip()
    df["UnitId"] = pd.to_numeric(df["UnitId"], errors="coerce")

    if df["UnitId"].isna().any():
        raise ValueError("parameters.csv contains invalid UnitId values.")

    if "ParameterId" in df.columns:
        df["ParameterId"] = pd.to_numeric(df["ParameterId"], errors="coerce")

    return df


def load_series_table(series_file: str | Path) -> pd.DataFrame:
    path = Path(series_file)
    if not path.exists():
        raise ValueError(f"Series file not found: {path}")

    df = pd.read_csv(path)
    df = normalize_column_names(df)

    required = {"SeriesId", "UnitsId", "Name", "TopologyId", "Key", "DatasetId", "DatasetName"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "Series.csv is missing required columns: "
            + ", ".join(sorted(missing))
        )

    for col in ["SeriesId", "UnitsId", "TopologyId"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["Name", "Key", "DatasetId", "DatasetName"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df