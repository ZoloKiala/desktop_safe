from __future__ import annotations

import csv
from pathlib import Path

from .processing_builders import (
    build_base_output_df,
    build_location_import_table,
    build_series_population_outputs,
    build_timeseries_outputs,
)
from .processing_constants import (
    DATE_CANDIDATES,
    DESCRIPTION_CANDIDATES,
    ID_CANDIDATES,
    LAT_CANDIDATES,
    LON_CANDIDATES,
    OUTPUT_DIR,
    SUPPORTED_PRIMARY_EXTS,
)
from .processing_geodata import build_geodataframe
from .processing_io import (
    guess_default_input_file,
    list_primary_input_files_from_folder,
    read_input_file,
    zip_outputs,
)
from .processing_parameters import (
    create_parameters_csv_from_db,
    create_series_csv_from_db,
    ensure_parameters_csv,
    ensure_series_csv,
    get_default_parameters_csv_path,
    get_default_series_csv_path,
    load_parameters_table,
    load_series_table,
)
from .processing_utils import (
    find_candidate,
    normalize_column_names,
    safe_text,
)

__all__ = [
    "OUTPUT_DIR",
    "SUPPORTED_PRIMARY_EXTS",
    "LAT_CANDIDATES",
    "LON_CANDIDATES",
    "DATE_CANDIDATES",
    "ID_CANDIDATES",
    "DESCRIPTION_CANDIDATES",
    "normalize_column_names",
    "list_primary_input_files_from_folder",
    "guess_default_input_file",
    "find_candidate",
    "read_input_file",
    "create_parameters_csv_from_db",
    "create_series_csv_from_db",
    "get_default_parameters_csv_path",
    "get_default_series_csv_path",
    "ensure_parameters_csv",
    "ensure_series_csv",
    "load_parameters_table",
    "load_series_table",
    "build_geodataframe",
    "process_file",
]


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
    date_source: str | None = None,
    description_source: str = "(none)",
    level1_text: str = "",
    level2_text: str = "",
    level3_text: str = "",
    date_text: str = "",
    description_text: str = "",
    date_input_format: str | None = None,
    date_output_format: str = "%Y-%m-%d",
    auto_reproject_to_wgs84: bool = True,
    require_point_geometry: bool = False,
    output_type: str = "location",
    timeseries_mappings: list[dict] | None = None,
    db_host: str = "",
    db_port: int | str = "",
    db_name: str = "",
    db_user: str = "",
    db_password: str = "",
    parameters_file: str | Path | None = None,
    series_file: str | Path | None = None,
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

    out = build_base_output_df(
        gdf=gdf,
        date_col=date_col,
        auto_desc_col=auto_desc_col,
        level1_source=level1_source,
        level2_source=level2_source,
        level3_source=level3_source,
        date_source=date_source,
        description_source=description_source,
        level1_text=level1_text,
        level2_text=level2_text,
        level3_text=level3_text,
        date_text=date_text,
        description_text=description_text,
        date_input_format=date_input_format,
        date_output_format=date_output_format,
    )

    output_type = safe_text(output_type).lower() or "location"

    if output_type == "time_series":
        parameters_csv_path = ensure_parameters_csv(
            preferred_file=parameters_file,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            always_create=False,
        )

        series_csv_path = ensure_series_csv(
            preferred_file=series_file,
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            always_create=False,
        )

        series_table, values_table, duplicate_mask_values = build_timeseries_outputs(
            out=out,
            timeseries_mappings=timeseries_mappings or [],
            parameters_file=parameters_csv_path,
        )

        import_path = OUTPUT_DIR / f"import_timeseries_{stem}.txt"
        sample_path = OUTPUT_DIR / f"import_timeseries_{stem}_sample.txt"
        timeseries_values_path = OUTPUT_DIR / f"timeseries_values_{stem}.csv"

        series_table.to_csv(
            import_path,
            sep="\t",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
            index=False,
            header=False,
        )

        values_table.to_csv(timeseries_values_path, index=False)

        series_table.tail(1).to_csv(
            sample_path,
            sep="\t",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
            index=False,
            header=False,
        )

        duplicate_mask_series = series_table.duplicated(
            subset=[
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
            ],
            keep=False,
        )

        populate_dir = OUTPUT_DIR / f"{stem}_populate"
        populate_joined_df, populate_paths = build_series_population_outputs(
            values_table=values_table,
            series_file=series_csv_path,
            populate_output_dir=populate_dir,
        )
        populate_path = populate_dir / "populate_timeseries_all.csv"

        zip_path = OUTPUT_DIR / f"{stem}_timeseries_outputs.zip"
        zip_outputs(
            [
                with_wkt_path,
                parameters_csv_path,
                series_csv_path,
                import_path,
                timeseries_values_path,
                sample_path,
                *populate_paths,
            ],
            zip_path,
        )

        return {
            "gdf": gdf,
            "mode": "time_series",
            "import_table": values_table,
            "duplicate_mask": duplicate_mask_values,
            "import_definition_table": series_table,
            "import_definition_duplicate_mask": duplicate_mask_series,
            "with_wkt_path": with_wkt_path,
            "parameters_csv_path": parameters_csv_path,
            "series_csv_path": series_csv_path,
            "import_path": import_path,
            "sample_path": sample_path,
            "timeseries_series_table": series_table,
            "timeseries_values_table": values_table,
            "timeseries_series_path": import_path,
            "timeseries_values_path": timeseries_values_path,
            "timeseries_values_duplicate_mask": duplicate_mask_values,
            "populate_timeseries_table": populate_joined_df,
            "populate_timeseries_path": populate_path,
            "populate_timeseries_paths": populate_paths,
            "mongo_uri_used": None,
            "mongo_inserted_count": None,
            "mongo_processed_files": None,
            "mongo_db_name": None,
            "mongo_collection_name": None,
            "zip_path": zip_path,
        }

    import_table, duplicate_mask = build_location_import_table(
        out=out,
        original_input_data=data,
    )

    import_path = OUTPUT_DIR / f"import_locations_{stem}.txt"
    sample_path = OUTPUT_DIR / f"import_locations_{stem}_sample.txt"

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

    zip_path = OUTPUT_DIR / f"{stem}_location_outputs.zip"
    zip_outputs([with_wkt_path, import_path, sample_path], zip_path)

    return {
        "gdf": gdf,
        "mode": "location",
        "import_table": import_table,
        "duplicate_mask": duplicate_mask,
        "with_wkt_path": with_wkt_path,
        "import_path": import_path,
        "sample_path": sample_path,
        "parameters_csv_path": None,
        "series_csv_path": None,
        "timeseries_series_table": None,
        "timeseries_values_table": None,
        "timeseries_series_path": None,
        "timeseries_values_path": None,
        "timeseries_values_duplicate_mask": None,
        "import_definition_table": None,
        "import_definition_duplicate_mask": None,
        "populate_timeseries_table": None,
        "populate_timeseries_path": None,
        "populate_timeseries_paths": None,
        "mongo_uri_used": None,
        "mongo_inserted_count": None,
        "mongo_processed_files": None,
        "mongo_db_name": None,
        "mongo_collection_name": None,
        "zip_path": zip_path,
    }