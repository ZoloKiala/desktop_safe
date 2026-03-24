from __future__ import annotations

import geopandas as gpd
import pandas as pd

from .processing_utils import parse_dates


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