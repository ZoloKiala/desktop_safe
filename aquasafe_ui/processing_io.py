from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .processing_constants import SUPPORTED_PRIMARY_EXTS
from .processing_utils import normalize_column_names


def list_primary_input_files_from_folder(folder: str | Path = ".") -> list[str]:
    folder = Path(folder)
    files_found: list[str] = []
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


def zip_outputs(paths: list[Path], zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if path and Path(path).exists():
                zf.write(path, arcname=Path(path).name)
    return zip_path