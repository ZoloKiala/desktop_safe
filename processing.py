import csv
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_PRIMARY_EXTS = (
    ".csv",
    ".xlsx",
    ".xls",
    ".shp",
    ".geojson",
    ".json",
    ".gpkg",
)

LAT_CANDIDATES = ("latitude", "lat", "y")
LON_CANDIDATES = ("longitude", "lon", "long", "lng", "x")
DATE_CANDIDATES = ("date", "sampling_date", "sample_date", "observation_date")
ID_CANDIDATES = ("id", "_id", "plotid", "plot_id", "sensor_id", "station_id")
DESCRIPTION_CANDIDATES = ("description", "desc", "notes", "comment", "remarks")


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = out.columns.astype(str).str.strip()
    return out


def list_primary_input_files_from_folder(folder: str | Path = ".") -> list[str]:
    folder = Path(folder)
    files_found = []
    for ext in SUPPORTED_PRIMARY_EXTS:
        files_found.extend(str(p.resolve()) for p in folder.glob(f"*{ext}"))
    return sorted(set(files_found))


def guess_default_input_file(file_list: list[str]) -> str | None:
    if not file_list:
        return None
    shp_files = [f for f in file_list if f.lower().endswith(".shp")]
    if len(shp_files) == 1:
        return shp_files[0]
    return file_list[0]


def find_candidate(columns, candidates):
    lookup = {str(col).casefold(): col for col in columns}
    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return None


def parse_dates(series: pd.Series, input_format: str | None, output_format: str) -> pd.Series:
    if input_format:
        parsed = pd.to_datetime(series, format=input_format, errors="coerce")
    else:
        parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")

    missing_mask = parsed.isna() & series.notna()
    if missing_mask.any():
        fallback = pd.to_datetime(series, errors="coerce", dayfirst=True)
        parsed = parsed.fillna(fallback)

    return parsed.dt.strftime(output_format)


def normalize_ascii(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.strip()
    )


def read_input_file(file_path: str):
    suffix = Path(file_path).suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
        return normalize_column_names(df), False

    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, engine="openpyxl")
        return normalize_column_names(df), False

    if suffix in (".shp", ".geojson", ".json", ".gpkg"):
        gdf = gpd.read_file(file_path)
        return normalize_column_names(gdf), True

    raise ValueError(f"Unsupported file type: {suffix}")


def build_geodataframe(
    data,
    is_geo: bool,
    lat_col: str | None,
    lon_col: str | None,
    date_col: str | None,
    id_col: str | None,
    date_input_format: str | None,
    date_output_format: str,
    auto_reproject_to_wgs84: bool,
    require_point_geometry: bool,
) -> gpd.GeoDataFrame:
    if is_geo:
        gdf = data.copy()

        if "geometry" not in gdf.columns:
            raise ValueError("The selected geospatial file has no geometry column.")

        gdf = gdf[gdf.geometry.notna()].copy()

        if gdf.empty:
            raise ValueError("The selected geospatial file contains no valid geometries.")

        if auto_reproject_to_wgs84 and gdf.crs is not None:
            gdf = gdf.to_crs("EPSG:4326")

        if require_point_geometry:
            non_points = ~gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
            if non_points.any():
                sample_types = gdf.geometry.geom_type[non_points].head(5).tolist()
                raise ValueError(
                    f"Point geometry is required, but non-point types were found: {sample_types}"
                )

        if date_col and date_col in gdf.columns:
            gdf[date_col] = parse_dates(gdf[date_col], date_input_format, date_output_format)

        if id_col and id_col in gdf.columns:
            gdf["_generic_id"] = gdf[id_col]
        else:
            gdf["_generic_id"] = pd.RangeIndex(start=1, stop=len(gdf) + 1)

        return gdf

    df = data.copy()

    if not lat_col or not lon_col:
        raise ValueError("Latitude and longitude columns are required for CSV/Excel input.")

    df = df.rename(columns={lat_col: "latitude", lon_col: "longitude"})

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    bad_coords = df[df["latitude"].isna() | df["longitude"].isna()]
    if not bad_coords.empty:
        raise ValueError(
            "Some rows have invalid coordinates. Example rows:\n"
            + bad_coords.head(5).to_string(index=False)
        )

    if date_col and date_col in df.columns:
        df[date_col] = parse_dates(df[date_col], date_input_format, date_output_format)

    if id_col and id_col in df.columns:
        df["_generic_id"] = df[id_col]
    else:
        df["_generic_id"] = pd.RangeIndex(start=1, stop=len(df) + 1)

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return gdf


def choose_series(df: pd.DataFrame, source_col: str, typed_value: str, fallback: pd.Series) -> pd.Series:
    if source_col and source_col != "(none)":
        return df[source_col]

    if str(typed_value).strip():
        return pd.Series([typed_value] * len(df), index=df.index)

    return fallback


def zip_outputs(paths: list[Path], zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            zf.write(path, arcname=path.name)
    return zip_path


def process_file(
    *,
    input_file: str,
    data,
    is_geo: bool,
    lat_col: str | None,
    lon_col: str | None,
    date_col: str | None,
    id_col: str | None,
    auto_desc_col: str | None,
    level1_source: str,
    level2_source: str,
    level3_source: str,
    description_source: str,
    level1_text: str,
    level2_text: str,
    level3_text: str,
    description_text: str,
    date_input_format: str | None,
    date_output_format: str,
    auto_reproject_to_wgs84: bool,
    require_point_geometry: bool,
):
    gdf = build_geodataframe(
        data=data,
        is_geo=is_geo,
        lat_col=lat_col,
        lon_col=lon_col,
        date_col=date_col,
        id_col=id_col,
        date_input_format=date_input_format,
        date_output_format=date_output_format,
        auto_reproject_to_wgs84=auto_reproject_to_wgs84,
        require_point_geometry=require_point_geometry,
    )

    stem = Path(input_file).stem

    with_wkt = gdf.assign(WKT=gdf.geometry.to_wkt())
    with_wkt_path = OUTPUT_DIR / f"{stem}_with_WKT.csv"
    with_wkt.to_csv(with_wkt_path, index=False)

    out = gdf.copy()
    out["Coords"] = out.geometry.apply(
        lambda geom: json.dumps(mapping(geom), separators=(",", ":"))
    )

    out["Level1"] = choose_series(
        out,
        level1_source,
        level1_text,
        pd.Series([""] * len(out), index=out.index),
    )

    out["Level2"] = choose_series(
        out,
        level2_source,
        level2_text,
        pd.Series([""] * len(out), index=out.index),
    )

    if description_source == "(auto detected description column)" and auto_desc_col:
        description_choice = auto_desc_col
    elif description_source == "(auto detected description column)" and not auto_desc_col:
        description_choice = "(none)"
    else:
        description_choice = description_source

    out["Description"] = choose_series(
        out,
        description_choice,
        description_text,
        pd.Series([""] * len(out), index=out.index),
    )

    if level3_source != "(none)":
        out["Level3"] = out[level3_source]
    elif str(level3_text).strip():
        out["Level3"] = level3_text
    elif "_generic_id" in out.columns:
        out["Level3"] = out["_generic_id"]
    else:
        out["Level3"] = pd.RangeIndex(start=1, stop=len(out) + 1)

    for col in ("Level1", "Level2", "Level3", "Description"):
        out[col] = normalize_ascii(out[col])

    import_table = out[["Level1", "Level2", "Level3", "Description", "Coords"]].copy()

    duplicate_mask = import_table.duplicated(
        subset=["Level1", "Level2", "Level3"],
        keep=False,
    )

    import_path = OUTPUT_DIR / f"import_{stem}.txt"
    sample_path = OUTPUT_DIR / f"import_{stem}_sample.txt"

    import_table.to_csv(
        import_path,
        sep="\t",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
        index=False,
        header=False,
    )

    import_table.tail(1).to_csv(
        sample_path,
        sep="\t",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
        index=False,
        header=False,
    )

    zip_path = OUTPUT_DIR / f"{stem}_outputs.zip"
    zip_outputs([with_wkt_path, import_path, sample_path], zip_path)

    return {
        "gdf": gdf,
        "import_table": import_table,
        "duplicate_mask": duplicate_mask,
        "with_wkt_path": with_wkt_path,
        "import_path": import_path,
        "sample_path": sample_path,
        "zip_path": zip_path,
    }