import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
import psycopg2

from cred import get_credentials

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QTableWidgetItem,
    QComboBox,
)

from .processing import (
    ensure_series_csv,
    find_candidate,
    guess_default_input_file,
    list_primary_input_files_from_folder,
    load_series_table,
    process_file,
    read_input_file,
)
from .processing_constants import (
    DESCRIPTION_CANDIDATES,
    DATE_CANDIDATES,
    ID_CANDIDATES,
    LAT_CANDIDATES,
    LON_CANDIDATES,
    OUTPUT_DIR,
    SUPPORTED_PRIMARY_EXTS,
)
from .processing_mongo import (
    DEFAULT_MONGO_COLLECTION_NAME,
    DEFAULT_MONGO_DB_NAME,
    DEFAULT_MONGO_PROFILE,
    insert_path_to_mongo,
    resolve_mongo_uri,
)


class FileOpsMixin:
    PARAMETER_LOOKUP_SQL = """
    select
        p."Id" as "ParameterId",
        p."Name" as "ParameterName",
        pu."Id" as "UnitId",
        pu."Unit" as "Unit",
        pu."Name" as "UnitName"
    from public."Parameters" p
    join public."ParameterUnits" pu
        on pu."ParameterId" = p."Id"
    order by p."Id"
    """

    def log(self, text: str):
        self.log_output.append(text)

    def set_combo_options(self, combo, options: list[str], selected: str):
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(options)
        idx = combo.findText(selected)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def normalize_lookup_text(self, value: str) -> str:
        text = str(value).strip()

        text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        text = text.lower()
        text = text.replace("_", " ").replace("-", " ")
        text = text.replace("%", " pct ")

        text = re.sub(r"\bdesc\b", "description", text)
        text = re.sub(r"\bpct\b", " percent ", text)
        text = re.sub(r"\s+", " ", text).strip()

        replacements = {
            "soilmoisture": "soil moisture",
            "soil moisture percent": "soil moisture",
            "soil moisture pct": "soil moisture",
            "soil moisture percentage": "soil moisture",
            "evelation": "elevation",
            "precip": "precipitation",
            "temp": "temperature",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return " ".join(text.split())

    def load_db_inputs_from_secrets(
        self,
        profile: str = "POSTGRES",
        secrets_file: str | Path = "secrets.toml",
    ) -> dict:
        creds = get_credentials(profile, secrets_file)
        uri = str(creds.uri).strip()

        parsed = urlparse(uri)
        if parsed.scheme not in {"postgresql", "postgres"}:
            raise ValueError(f"Unsupported database URI scheme: {parsed.scheme}")

        db_name = parsed.path.lstrip("/")
        if not db_name:
            raise ValueError("Database URI is missing the database name.")

        return {
            "db_host": parsed.hostname or "",
            "db_port": str(parsed.port or 5432),
            "db_name": db_name,
            "db_user": unquote(parsed.username or ""),
            "db_password": unquote(parsed.password or ""),
        }

    def resolve_mongo_uri_for_run(self) -> str:
        candidate_files = [
            Path("secrets.toml"),
            Path("secrets_tut.toml"),
            Path("secrets_tut (1).toml"),
        ]

        last_error = None

        for secrets_file in candidate_files:
            try:
                if secrets_file.exists():
                    mongo_uri = resolve_mongo_uri(
                        profile=DEFAULT_MONGO_PROFILE,
                        secrets_file=secrets_file,
                    )
                    self.log(f"Loaded Mongo credentials from: {secrets_file}")
                    return mongo_uri
            except Exception as e:
                last_error = e

        try:
            return resolve_mongo_uri(profile=DEFAULT_MONGO_PROFILE)
        except Exception as e:
            last_error = e

        raise ValueError(
            "Missing MongoDB credentials. Add the profile "
            f"'{DEFAULT_MONGO_PROFILE}' to secrets.toml "
            "or provide a valid secrets file."
            + (f"\n\nLast error: {last_error}" if last_error else "")
        )

    def validate_parameter_lookup_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            raise ValueError("No parameters were returned from the lookup source.")

        required = {"ParameterId", "ParameterName", "UnitId", "Unit"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                "Parameter lookup data is missing required columns: "
                + ", ".join(sorted(missing))
            )

        df = df.copy()
        df["ParameterName"] = df["ParameterName"].fillna("").astype(str).str.strip()
        df["Unit"] = df["Unit"].fillna("").astype(str).str.strip()

        if "UnitName" in df.columns:
            df["UnitName"] = df["UnitName"].fillna("").astype(str).str.strip()
        else:
            df["UnitName"] = ""

        df["ParameterName_norm"] = df["ParameterName"].map(self.normalize_lookup_text)
        return df

    def load_parameter_lookup_from_db(self) -> pd.DataFrame:
        db = self.validate_db_inputs()

        conn = None
        try:
            conn = psycopg2.connect(
                host=db["db_host"],
                port=int(db["db_port"]),
                dbname=db["db_name"],
                user=db["db_user"],
                password=db["db_password"],
                connect_timeout=6,
            )
            df = pd.read_sql_query(self.PARAMETER_LOOKUP_SQL, conn)
        finally:
            if conn is not None:
                conn.close()

        return self.validate_parameter_lookup_df(df)

    def load_parameter_lookup_from_csv(self, csv_path: str | Path) -> pd.DataFrame:
        csv_path = Path(csv_path).resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"Selected parameter catalog not found:\n{csv_path}")

        df = pd.read_csv(csv_path)
        return self.validate_parameter_lookup_df(df)

    def prompt_for_parameter_catalog_csv(self) -> Path | None:
        start_dir = ""
        existing = getattr(self, "parameter_catalog_path", None)
        if existing:
            try:
                start_dir = str(Path(existing).resolve().parent)
            except Exception:
                start_dir = ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select parameter_catalog.csv",
            start_dir,
            "CSV files (*.csv);;All files (*)",
        )
        if not file_path:
            return None

        selected = Path(file_path).resolve()
        self.parameter_catalog_path = selected
        return selected

    def prompt_for_series_csv(self) -> Path | None:
        start_dir = ""
        existing = getattr(self, "series_catalog_path", None)
        if existing:
            try:
                start_dir = str(Path(existing).resolve().parent)
            except Exception:
                start_dir = ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Series.csv",
            start_dir,
            "CSV files (*.csv);;All files (*)",
        )
        if not file_path:
            return None

        selected = Path(file_path).resolve()
        self.series_catalog_path = selected
        return selected

    def load_parameter_lookup(self) -> tuple[pd.DataFrame, str]:
        db_error = None

        try:
            df = self.load_parameter_lookup_from_db()
            return df, "database"
        except Exception as e:
            db_error = e
            self.log(f"Database parameter lookup failed: {e}")

        reply = QMessageBox.question(
            self,
            "Database lookup failed",
            (
                "Could not load parameters from the database.\n\n"
                "Do you want to upload parameter_catalog.csv instead?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply != QMessageBox.StandardButton.Yes:
            raise ValueError(f"Database lookup failed:\n{db_error}")

        selected_path = self.prompt_for_parameter_catalog_csv()
        if selected_path is None:
            raise ValueError("Database lookup failed and no parameter_catalog.csv was selected.")

        try:
            df = self.load_parameter_lookup_from_csv(selected_path)
            self.log(f"Loaded parameter catalog from: {selected_path}")
            return df, "uploaded_csv"
        except Exception as csv_error:
            raise ValueError(
                "Could not load parameter lookup from database or uploaded CSV.\n\n"
                f"Database error:\n{db_error}\n\n"
                f"Uploaded CSV error:\n{csv_error}"
            ) from csv_error

    def resolve_series_csv_for_run(self, db_kwargs: dict) -> Path:
        db_error = None
        preferred = getattr(self, "series_catalog_path", None)

        try:
            series_csv_path = ensure_series_csv(
                preferred_file=preferred,
                db_host=db_kwargs.get("db_host", ""),
                db_port=db_kwargs.get("db_port", ""),
                db_name=db_kwargs.get("db_name", ""),
                db_user=db_kwargs.get("db_user", ""),
                db_password=db_kwargs.get("db_password", ""),
                always_create=False,
            )
            self.series_catalog_path = Path(series_csv_path).resolve()
            return Path(series_csv_path).resolve()
        except Exception as e:
            db_error = e
            self.log(f"Series.csv generation from database failed: {e}")

        reply = QMessageBox.question(
            self,
            "Series.csv generation failed",
            (
                "Could not generate Series.csv from the database.\n\n"
                "Do you want to upload Series.csv instead?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if reply != QMessageBox.StandardButton.Yes:
            raise ValueError(f"Series.csv generation failed:\n{db_error}")

        selected_path = self.prompt_for_series_csv()
        if selected_path is None:
            raise ValueError("Series.csv generation failed and no Series.csv was selected.")

        try:
            load_series_table(selected_path)
            self.series_catalog_path = selected_path
            self.log(f"Loaded Series.csv from: {selected_path}")
            return selected_path
        except Exception as csv_error:
            raise ValueError(
                "Could not load Series.csv from database or uploaded CSV.\n\n"
                f"Database error:\n{db_error}\n\n"
                f"Uploaded CSV error:\n{csv_error}"
            ) from csv_error

    def lookup_parameter_for_source_column(self, source_column: str, lookup_df: pd.DataFrame) -> dict:
        source_norm = self.normalize_lookup_text(source_column)

        exact = lookup_df.loc[lookup_df["ParameterName_norm"] == source_norm].copy()
        if not exact.empty:
            preferred = exact.loc[exact["Unit"].ne("-") & exact["Unit"].ne("")]
            chosen = preferred.iloc[0] if not preferred.empty else exact.iloc[0]
            return {
                "parameter_id": str(chosen.get("ParameterId", "")).strip(),
                "parameter": str(chosen.get("ParameterName", "")).strip(),
                "unit_id": str(chosen.get("UnitId", "")).strip(),
                "unit": str(chosen.get("Unit", "")).strip(),
                "matched": True,
                "score": 1.0,
            }

        best_norm = None
        best_score = 0.0

        for candidate_norm in lookup_df["ParameterName_norm"].dropna().unique():
            candidate_norm = str(candidate_norm).strip()
            if not candidate_norm:
                continue

            score = SequenceMatcher(None, source_norm, candidate_norm).ratio()
            if score > best_score:
                best_score = score
                best_norm = candidate_norm

        if best_norm is not None and best_score >= 0.82:
            fuzzy = lookup_df.loc[lookup_df["ParameterName_norm"] == best_norm].copy()
            preferred = fuzzy.loc[fuzzy["Unit"].ne("-") & fuzzy["Unit"].ne("")]
            chosen = preferred.iloc[0] if not preferred.empty else fuzzy.iloc[0]
            return {
                "parameter_id": str(chosen.get("ParameterId", "")).strip(),
                "parameter": str(chosen.get("ParameterName", "")).strip(),
                "unit_id": str(chosen.get("UnitId", "")).strip(),
                "unit": str(chosen.get("Unit", "")).strip(),
                "matched": True,
                "score": best_score,
            }

        return {
            "parameter_id": "",
            "parameter": "",
            "unit_id": "",
            "unit": "",
            "matched": False,
            "score": 0.0,
        }

    def candidate_timeseries_source_columns(self) -> list[str]:
        cols = [str(c) for c in self.current_non_geometry_columns()]
        excluded = {"(none)", "geometry"}

        for combo_name in [
            "lat_combo",
            "lon_combo",
            "date_combo",
            "id_combo",
            "auto_desc_combo",
            "level1_source_combo",
            "level2_source_combo",
            "level3_source_combo",
            "description_source_combo",
        ]:
            combo = getattr(self, combo_name, None)
            if combo is not None:
                value = combo.currentText().strip()
                if value and not value.startswith("("):
                    excluded.add(value)

        date_src = self.export_date_source_value()
        if date_src and date_src != "__detected_date__":
            excluded.add(str(date_src))

        return [c for c in cols if c not in excluded]

    def on_generate_parameters_clicked(self):
        if self.current_output_type() != "time_series":
            QMessageBox.information(
                self,
                "Time-series only",
                "This button is only used in time-series mode.",
            )
            return

        if self.data is None:
            QMessageBox.warning(self, "No data", "Load an input file first.")
            return

        if not hasattr(self, "timeseries_mapping_table"):
            QMessageBox.warning(self, "Missing table", "Time-series mapping table is not available.")
            return

        try:
            lookup_df, lookup_source = self.load_parameter_lookup()
        except Exception as e:
            QMessageBox.warning(self, "Parameter lookup failed", str(e))
            return

        self.sync_editor_to_data()
        self.refresh_dropdowns_for_current_file()
        self.refresh_timeseries_mapping_source_combos()

        source_columns = self.candidate_timeseries_source_columns()
        if not source_columns:
            QMessageBox.warning(
                self,
                "No parameter columns found",
                "No candidate source columns were found after excluding ID, date, coordinates, and description fields.",
            )
            return

        existing_by_source = {}
        for row in range(self.timeseries_mapping_table.rowCount()):
            source_combo = self.timeseries_mapping_table.cellWidget(row, 1)
            dataset_name_item = self.timeseries_mapping_table.item(row, 3)
            dataset_id_item = self.timeseries_mapping_table.item(row, 4)

            source_column = source_combo.currentText().strip() if source_combo else "(none)"
            if source_column == "(none)":
                continue

            existing_by_source[source_column] = {
                "dataset_name": dataset_name_item.text().strip() if dataset_name_item else "",
                "dataset_id": dataset_id_item.text().strip() if dataset_id_item else "",
            }

        self.timeseries_mapping_table.setRowCount(0)

        generated_rows = []
        unmatched = []

        for col in source_columns:
            looked_up = self.lookup_parameter_for_source_column(col, lookup_df)

            if not looked_up["matched"]:
                unmatched.append(col)
                continue

            existing = existing_by_source.get(col, {})
            parameter = looked_up["parameter"]
            unit = looked_up["unit"]
            dataset_name = existing.get("dataset_name", "")
            dataset_id = existing.get("dataset_id", "")

            self.add_timeseries_mapping_row(
                parameter=parameter,
                source_column=col,
                unit=unit,
                dataset_name=dataset_name,
                dataset_id=dataset_id,
            )

            generated_rows.append(
                {
                    "ParameterId": looked_up["parameter_id"],
                    "ParameterName": parameter,
                    "UnitId": looked_up["unit_id"],
                    "Unit": unit,
                }
            )

        if not generated_rows:
            QMessageBox.warning(
                self,
                "No matches found",
                "None of the source columns matched any parameter in the lookup source.",
            )
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        draft_csv_path = OUTPUT_DIR / "parameters.csv"

        params_df = pd.DataFrame(generated_rows).drop_duplicates().copy()
        params_df = params_df[["ParameterId", "ParameterName", "UnitId", "Unit"]]
        params_df.to_csv(draft_csv_path, index=False)

        source_label = {
            "database": "database",
            "uploaded_csv": "uploaded parameter catalog",
        }.get(lookup_source, lookup_source)

        self.log(f"Draft parameters.csv created from {source_label}: {draft_csv_path}")
        self.log(f"Generated {len(params_df)} matched parameter row(s).")

        if unmatched:
            self.log("Skipped non-parameter columns:")
            for col in unmatched:
                self.log(f"  - {col}")

        self.show_success_status(
            f"Draft parameters.csv created with {len(params_df)} row(s): {draft_csv_path.name}"
        )

        msg = (
            f"Draft parameters.csv created successfully.\n\n"
            f"Lookup source: {source_label}\n"
            f"Rows: {len(params_df)}\n"
            f"File: {draft_csv_path}"
        )
        if unmatched:
            msg += "\n\nSkipped non-parameter columns:\n- " + "\n- ".join(unmatched)

        QMessageBox.information(self, "parameters.csv created", msg)

    def browse_for_input_file(self):
        filter_text = (
            "Supported files (*.csv *.xlsx *.xls *.shp *.geojson *.json *.gpkg);;"
            "CSV (*.csv);;"
            "Excel (*.xlsx *.xls);;"
            "Vector files (*.shp *.geojson *.json *.gpkg);;"
            "All files (*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(self, "Select input file", "", filter_text)
        if not file_path:
            return

        file_path = str(Path(file_path).resolve())
        if file_path not in self.candidate_files:
            self.candidate_files.append(file_path)
            self.candidate_files = sorted(set(self.candidate_files))

        self.refresh_file_combo(select_file=file_path)
        self.file_combo.setEditText(file_path)

    def add_files(self):
        filter_text = (
            "Supported files (*.csv *.xlsx *.xls *.shp *.geojson *.json *.gpkg);;"
            "CSV (*.csv);;"
            "Excel (*.xlsx *.xls);;"
            "Vector files (*.shp *.geojson *.json *.gpkg);;"
            "All files (*)"
        )
        files, _ = QFileDialog.getOpenFileNames(self, "Select input files", "", filter_text)
        if not files:
            return

        valid = [
            str(Path(f).resolve())
            for f in files
            if Path(f).suffix.lower() in SUPPORTED_PRIMARY_EXTS
        ]
        if not valid:
            QMessageBox.warning(self, "No supported files", "No supported input files were selected.")
            return

        self.candidate_files = sorted(set(self.candidate_files + valid))
        self.refresh_file_combo(select_file=guess_default_input_file(valid))
        self.log(f"Added {len(valid)} supported file(s).")
        self.clear_status()

    def scan_current_folder(self, initial: bool):
        found = list_primary_input_files_from_folder(".")
        self.candidate_files = found
        self.refresh_file_combo(select_file=guess_default_input_file(found))

        if not initial:
            if found:
                self.log(f"Found {len(found)} supported file(s) in the current folder.")
            else:
                self.log("No supported input files found in the current folder.")
            self.clear_status()

    def refresh_file_combo(self, select_file: str | None = None):
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        self.file_combo.addItems(self.candidate_files)
        self.file_combo.blockSignals(False)

        if not self.candidate_files:
            self.original_data = None
            self.data = None
            self.is_geo = False
            self.input_file = None
            self.result = None
            self.save_zip_btn.setEnabled(False)
            self.file_info.setText("No supported input files loaded.")
            self.clear_preview()
            self.clear_input_table()
            self.clear_status()
            self.hide_editor()
            return

        target = select_file if select_file in self.candidate_files else self.candidate_files[0]
        index = self.file_combo.findText(target)
        self.file_combo.setCurrentIndex(index)
        self.file_combo.setEditText(target)
        self.load_file_into_state(target)
        self.refresh_dropdowns_for_current_file()

    def load_file_into_state(self, file_path: str):
        loaded_data, is_geo = read_input_file(file_path)
        self.original_data = loaded_data.copy()
        self.data = loaded_data.copy()
        self.is_geo = is_geo
        self.input_file = file_path
        self.result = None
        self.save_zip_btn.setEnabled(False)
        self.populate_input_table(self.data, reset_history=True)

    def current_non_geometry_columns(self) -> list[str]:
        if self.data is None:
            return []
        return [c for c in self.data.columns if c != "geometry"]

    def add_timeseries_mapping_row(
        self,
        parameter: str = "",
        source_column: str = "(none)",
        unit: str = "",
        dataset_name: str = "",
        dataset_id: str = "",
    ):
        if not hasattr(self, "timeseries_mapping_table"):
            return

        row = self.timeseries_mapping_table.rowCount()
        self.timeseries_mapping_table.insertRow(row)

        self.timeseries_mapping_table.setItem(row, 0, QTableWidgetItem(parameter))

        combo = QComboBox()
        combo.addItems(["(none)"] + self.current_non_geometry_columns())
        idx = combo.findText(source_column)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.timeseries_mapping_table.setCellWidget(row, 1, combo)

        self.timeseries_mapping_table.setItem(row, 2, QTableWidgetItem(unit))
        self.timeseries_mapping_table.setItem(row, 3, QTableWidgetItem(dataset_name))
        self.timeseries_mapping_table.setItem(row, 4, QTableWidgetItem(dataset_id))

    def remove_selected_timeseries_mapping_rows(self):
        if not hasattr(self, "timeseries_mapping_table"):
            return

        selected_rows = sorted(
            {index.row() for index in self.timeseries_mapping_table.selectedIndexes()},
            reverse=True,
        )
        if not selected_rows:
            QMessageBox.information(self, "No selection", "Select one or more mapping rows to delete.")
            return

        for row in selected_rows:
            self.timeseries_mapping_table.removeRow(row)

    def refresh_timeseries_mapping_source_combos(self):
        if not hasattr(self, "timeseries_mapping_table"):
            return

        options = ["(none)"] + self.current_non_geometry_columns()
        for row in range(self.timeseries_mapping_table.rowCount()):
            combo = self.timeseries_mapping_table.cellWidget(row, 1)
            if combo is None:
                continue
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(options)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def collect_timeseries_mappings(self) -> list[dict]:
        if self.current_output_type() != "time_series":
            return []

        if not hasattr(self, "timeseries_mapping_table"):
            return []

        mappings = []

        for row in range(self.timeseries_mapping_table.rowCount()):
            parameter_item = self.timeseries_mapping_table.item(row, 0)
            combo = self.timeseries_mapping_table.cellWidget(row, 1)
            unit_item = self.timeseries_mapping_table.item(row, 2)
            dataset_name_item = self.timeseries_mapping_table.item(row, 3)
            dataset_id_item = self.timeseries_mapping_table.item(row, 4)

            parameter = parameter_item.text().strip() if parameter_item else ""
            source_column = combo.currentText().strip() if combo else "(none)"
            unit = unit_item.text().strip() if unit_item else ""
            dataset_name = dataset_name_item.text().strip() if dataset_name_item else ""
            dataset_id = dataset_id_item.text().strip() if dataset_id_item else ""

            if not any([parameter, source_column != "(none)", unit, dataset_name, dataset_id]):
                continue

            if not parameter:
                raise ValueError(f"Mapping row {row + 1}: Parameter is required.")
            if source_column == "(none)":
                raise ValueError(f"Mapping row {row + 1}: Source Column is required.")
            if not unit:
                raise ValueError(f"Mapping row {row + 1}: Unit is required.")
            if not dataset_name:
                raise ValueError(f"Mapping row {row + 1}: Dataset Name is required.")
            if not dataset_id:
                raise ValueError(f"Mapping row {row + 1}: Dataset ID is required.")

            mappings.append(
                {
                    "parameter": parameter,
                    "source_column": source_column,
                    "unit": unit,
                    "dataset_name": dataset_name,
                    "dataset_id": dataset_id,
                }
            )

        return mappings

    def refresh_dropdowns_for_current_file(self):
        cols = self.current_non_geometry_columns()
        options = ["(none)"] + [str(c) for c in cols]

        lat_guess = find_candidate(cols, LAT_CANDIDATES) or "(none)"
        lon_guess = find_candidate(cols, LON_CANDIDATES) or "(none)"
        date_guess = find_candidate(cols, DATE_CANDIDATES) or "(none)"
        id_guess = find_candidate(cols, ID_CANDIDATES) or "(none)"
        desc_guess = find_candidate(cols, DESCRIPTION_CANDIDATES) or "(none)"

        self.set_combo_options(getattr(self, "lat_combo", None), options, lat_guess)
        self.set_combo_options(getattr(self, "lon_combo", None), options, lon_guess)
        self.set_combo_options(getattr(self, "date_combo", None), options, date_guess)
        self.set_combo_options(getattr(self, "id_combo", None), options, id_guess)
        self.set_combo_options(getattr(self, "auto_desc_combo", None), options, desc_guess)

        self.set_combo_options(getattr(self, "level1_source_combo", None), options, "(none)")
        self.set_combo_options(getattr(self, "level2_source_combo", None), options, "(none)")
        self.set_combo_options(getattr(self, "level3_source_combo", None), options, "(none)")
        self.set_combo_options(
            getattr(self, "date_source_combo", None),
            ["(none)", "(detected date column)"] + [str(c) for c in cols],
            "(detected date column)" if date_guess != "(none)" else "(none)",
        )
        self.set_combo_options(
            getattr(self, "description_source_combo", None),
            ["(none)", "(auto detected description column)"] + [str(c) for c in cols],
            "(auto detected description column)" if desc_guess != "(none)" else "(none)",
        )

        ts_value_combo = getattr(self, "timeseries_value_source_combo", None)
        if ts_value_combo is not None:
            self.set_combo_options(ts_value_combo, options, "(none)")

        if hasattr(self, "lat_combo"):
            self.lat_combo.setEnabled(not self.is_geo)
        if hasattr(self, "lon_combo"):
            self.lon_combo.setEnabled(not self.is_geo)
        if hasattr(self, "add_row_btn"):
            self.add_row_btn.setEnabled(not self.is_geo)
        if hasattr(self, "delete_rows_btn"):
            self.delete_rows_btn.setEnabled(not self.is_geo)

        if hasattr(self, "editor_note_label"):
            if self.is_geo:
                self.editor_note_label.setText(
                    "This editor appears only when processing fails. You can edit attribute values and add/delete columns. Geometry is preserved automatically, and row count cannot be changed for geospatial files."
                )
            else:
                self.editor_note_label.setText(
                    "This editor appears only when processing fails. You can edit cell values, add/delete columns, add/delete rows, and use undo/redo before trying again."
                )

        extra_note = ""
        if self.is_geo:
            extra_note = "<br><b>Note:</b> Geometry is preserved separately and is not shown in the editor."

        self.file_info.setText(
            f"<b>Input file:</b> {self.input_file}<br>"
            f"<b>Geospatial input:</b> {self.is_geo}<br>"
            f"<b>Rows:</b> {len(self.data):,}{extra_note}"
        )
        self.file_info.setTextFormat(Qt.TextFormat.RichText)

    def combo_value_or_none(self, combo):
        if combo is None:
            return None
        value = combo.currentText().strip()
        return None if value == "(none)" else value

    def export_date_source_value(self):
        combo = getattr(self, "date_source_combo", None)
        if combo is None:
            return None

        value = combo.currentText().strip()
        if value == "(none)":
            return None
        if value == "(detected date column)":
            return "__detected_date__"
        return value

    def validate_db_inputs(self):
        if self.current_output_type() != "time_series":
            return {}

        try:
            db = self.load_db_inputs_from_secrets(
                profile="POSTGRES",
                secrets_file="secrets.toml",
            )
            self.log("Loaded Postgres credentials from: secrets.toml")
            return db
        except Exception as secret_error:
            self.log(f"DB secrets lookup failed, falling back to hidden UI fields: {secret_error}")

        required_widgets = [
            "db_host_edit",
            "db_port_edit",
            "db_name_edit",
            "db_user_edit",
            "db_password_edit",
        ]
        for name in required_widgets:
            if not hasattr(self, name):
                raise ValueError(
                    "Database credentials were not found in secrets.toml, "
                    "and the database fields are not available in the UI."
                )

        fields = {
            "Host": self.db_host_edit.text().strip(),
            "Port": self.db_port_edit.text().strip(),
            "Database": self.db_name_edit.text().strip(),
            "User": self.db_user_edit.text().strip(),
            "Password": self.db_password_edit.text().strip(),
        }

        missing = [label for label, value in fields.items() if not value]
        if missing:
            raise ValueError(
                "Missing database credentials. Add a [POSTGRES] uri to secrets.toml "
                "or provide these values in the hidden fallback fields: "
                + ", ".join(missing)
            )

        try:
            int(fields["Port"])
        except ValueError:
            raise ValueError("Port must be a valid number.")

        return {
            "db_host": fields["Host"],
            "db_port": fields["Port"],
            "db_name": fields["Database"],
            "db_user": fields["User"],
            "db_password": fields["Password"],
        }

    def on_file_changed(self):
        file_path = self.file_combo.currentText().strip()
        if not file_path:
            return

        path_obj = Path(file_path)

        if not path_obj.exists():
            self.file_info.setText(
                f"<b>Input file:</b> {file_path}<br>"
                "<span style='color:#b45309;'>File not found yet. Edit the path or click Browse.</span>"
            )
            self.file_info.setTextFormat(Qt.TextFormat.RichText)
            return

        if path_obj.suffix.lower() not in SUPPORTED_PRIMARY_EXTS:
            self.file_info.setText(
                f"<b>Input file:</b> {file_path}<br>"
                "<span style='color:#b91c1c;'>Unsupported file type.</span>"
            )
            self.file_info.setTextFormat(Qt.TextFormat.RichText)
            return

        try:
            resolved = str(path_obj.resolve())
            if resolved not in self.candidate_files:
                self.candidate_files.append(resolved)
                self.candidate_files = sorted(set(self.candidate_files))

            self.load_file_into_state(resolved)
            self.refresh_dropdowns_for_current_file()
            self.clear_preview()
            self.log_output.clear()
            self.clear_status()
            self.hide_editor()
            self.log(f"Loaded: {resolved}")
        except Exception as e:
            self.handle_error("Failed to load file", e)

    def on_run_clicked(self):
        self.log_output.clear()
        self.clear_status()
        self.set_inputs_enabled(False)
        self.run_btn.setText("Processing...")

        try:
            file_path = self.file_combo.currentText().strip()
            if not file_path:
                raise ValueError("Please select or type an input file.")

            path_obj = Path(file_path)
            if not path_obj.exists():
                raise ValueError("The selected input file does not exist.")

            if path_obj.suffix.lower() not in SUPPORTED_PRIMARY_EXTS:
                raise ValueError("The selected input file type is not supported.")

            resolved_path = str(path_obj.resolve())
            if self.input_file != resolved_path:
                self.load_file_into_state(resolved_path)
                self.refresh_dropdowns_for_current_file()

            self.sync_editor_to_data()
            self.refresh_dropdowns_for_current_file()

            db_kwargs = {}
            series_file = None

            if self.current_output_type() == "time_series":
                db_kwargs = self.validate_db_inputs()
                series_file = self.resolve_series_csv_for_run(db_kwargs)

            self.result = process_file(
                input_file=self.input_file,
                data=self.data,
                is_geo=self.is_geo,
                lat_col=self.combo_value_or_none(getattr(self, "lat_combo", None)),
                lon_col=self.combo_value_or_none(getattr(self, "lon_combo", None)),
                date_col=self.combo_value_or_none(getattr(self, "date_combo", None)),
                id_col=self.combo_value_or_none(getattr(self, "id_combo", None)),
                auto_desc_col=self.combo_value_or_none(getattr(self, "auto_desc_combo", None)),
                level1_source=getattr(self, "level1_source_combo", None).currentText()
                if hasattr(self, "level1_source_combo") else "(none)",
                level2_source=getattr(self, "level2_source_combo", None).currentText()
                if hasattr(self, "level2_source_combo") else "(none)",
                level3_source=getattr(self, "level3_source_combo", None).currentText()
                if hasattr(self, "level3_source_combo") else "(none)",
                date_source=self.export_date_source_value(),
                description_source=getattr(self, "description_source_combo", None).currentText()
                if hasattr(self, "description_source_combo") else "(none)",
                level1_text=self.level1_edit.text() if hasattr(self, "level1_edit") else "",
                level2_text=self.level2_edit.text() if hasattr(self, "level2_edit") else "",
                level3_text=self.level3_edit.text() if hasattr(self, "level3_edit") else "",
                date_text=self.date_text_edit.text() if hasattr(self, "date_text_edit") else "",
                description_text=self.description_edit.text() if hasattr(self, "description_edit") else "",
                date_input_format=self.date_in_edit.text().strip()
                if hasattr(self, "date_in_edit") and self.date_in_edit.text().strip() else None,
                date_output_format=self.date_out_edit.text().strip()
                if hasattr(self, "date_out_edit") and self.date_out_edit.text().strip() else "%Y-%m-%d",
                auto_reproject_to_wgs84=self.reproject_chk.isChecked()
                if hasattr(self, "reproject_chk") else True,
                require_point_geometry=self.points_only_chk.isChecked()
                if hasattr(self, "points_only_chk") else False,
                output_type=self.current_output_type(),
                timeseries_mappings=self.collect_timeseries_mappings(),
                series_file=series_file,
                **db_kwargs,
            )

            self.save_zip_btn.setEnabled(True)
            self.hide_editor()

            result = self.result
            mode = result.get("mode", self.current_output_type())

            with_wkt_path = result.get("with_wkt_path")
            parameters_csv_path = result.get("parameters_csv_path")
            series_csv_path = result.get("series_csv_path")
            import_path = result.get("import_path")
            sample_path = result.get("sample_path")
            timeseries_series_path = result.get("timeseries_series_path")
            populate_timeseries_path = result.get("populate_timeseries_path")
            zip_path = result.get("zip_path")
            import_table = result.get("import_table")
            duplicate_mask = result.get("duplicate_mask")

            self.log("Processing complete.\n")
            self.log(f"Mode:       {mode}")

            if with_wkt_path:
                self.log(f"WKT CSV:    {with_wkt_path}")

            if parameters_csv_path:
                self.log(f"Params CSV: {parameters_csv_path}")

            if series_csv_path:
                self.log(f"Series CSV: {series_csv_path}")

            if import_path:
                self.log(f"Import TXT: {import_path}")

            if sample_path:
                self.log(f"Sample TXT: {sample_path}")

            if mode == "time_series" and timeseries_series_path:
                self.log(f"Series TXT: {timeseries_series_path}")

            if populate_timeseries_path:
                self.log(f"Populate CSV: {populate_timeseries_path}")

            if zip_path:
                self.log(f"ZIP:        {zip_path}")

            if import_table is not None:
                self.log(f"Rows:       {len(import_table):,}")

            duplicate_count = int(duplicate_mask.sum()) if duplicate_mask is not None else 0
            if duplicate_count and import_table is not None:
                self.log(f"\nWarning: {duplicate_count} duplicate row(s) found.")
                preview_dup = import_table.loc[duplicate_mask].head(20)
                self.log(preview_dup.to_string(index=False))
            else:
                self.log("\nNo duplicate key combinations found.")

            if import_table is not None:
                self.populate_preview_table(import_table.head(200))

            mongo_inserted_count = None
            mongo_processed_files = []
            mongo_db_name = None
            mongo_collection_name = None

            if mode == "time_series" and populate_timeseries_path:
                reply = QMessageBox.question(
                    self,
                    "Insert to MongoDB",
                    (
                        "Time-series files were generated successfully.\n\n"
                        "Do you want to insert the generated populate CSV files into MongoDB now?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        populate_dir = Path(populate_timeseries_path).resolve().parent

                        mongo_uri = self.resolve_mongo_uri_for_run()
                        mongo_inserted_count, mongo_processed_files = insert_path_to_mongo(
                            source_path=populate_dir,
                            mongo_uri=mongo_uri,
                            db_name=DEFAULT_MONGO_DB_NAME,
                            collection_name=DEFAULT_MONGO_COLLECTION_NAME,
                        )
                        mongo_db_name = DEFAULT_MONGO_DB_NAME
                        mongo_collection_name = DEFAULT_MONGO_COLLECTION_NAME

                        self.log(f"Mongo DB:    {mongo_db_name}")
                        self.log(f"Mongo Coll:  {mongo_collection_name}")
                        self.log(f"Inserted:    {mongo_inserted_count:,}")

                        if mongo_processed_files:
                            self.log("Mongo files:")
                            for p in mongo_processed_files:
                                self.log(f"  - {p}")

                    except Exception as mongo_error:
                        QMessageBox.warning(
                            self,
                            "MongoDB insert failed",
                            f"Time-series files were created, but MongoDB insertion failed.\n\n{mongo_error}",
                        )

            zip_name = zip_path.name if zip_path else "output.zip"
            row_count = len(import_table) if import_table is not None else 0

            success_message = (
                "Processing completed successfully.\n\n"
                f"Mode: {mode}\n"
                f"Rows processed: {row_count:,}\n"
                f"ZIP created: {zip_name}"
            )

            if mongo_inserted_count is not None:
                success_message += (
                    f"\n\nMongoDB insertion completed.\n"
                    f"Database: {mongo_db_name}\n"
                    f"Collection: {mongo_collection_name}\n"
                    f"Inserted documents: {mongo_inserted_count:,}"
                )

            self.show_success_status(
                f"Success: processing completed. {row_count:,} rows exported. "
                f"ZIP created: {zip_name}"
            )

            QMessageBox.information(self, "Success", success_message)

        except Exception as e:
            self.result = None
            self.save_zip_btn.setEnabled(False)
            self.clear_preview()
            self.clear_status()
            self.show_editor()
            self.handle_error("Processing failed", e)
            self.file_combo.setFocus()
            if self.file_combo.lineEdit() is not None:
                self.file_combo.lineEdit().selectAll()
        finally:
            self.set_inputs_enabled(True)
            self.run_btn.setText("Run Processing")

    def on_save_zip_clicked(self):
        if not self.result:
            QMessageBox.information(self, "Nothing to save", "Run processing first.")
            return

        default_name = self.result["zip_path"].name
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Save ZIP As",
            str((Path.cwd() / default_name).resolve()),
            "ZIP archive (*.zip)",
        )
        if not target:
            return

        target_path = Path(target)
        if target_path.suffix.lower() != ".zip":
            target_path = target_path.with_suffix(".zip")

        shutil.copy2(self.result["zip_path"], target_path)
        QMessageBox.information(self, "ZIP saved", f"Saved ZIP to:\n{target_path}")

    def open_output_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUT_DIR.resolve())))

    def open_update_link(self):
        QDesktopServices.openUrl(QUrl(self.latest_release_url))