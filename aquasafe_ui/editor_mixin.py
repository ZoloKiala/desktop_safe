import pandas as pd
import geopandas as gpd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QTableWidgetItem,
)


class EditorMixin:
    def reset_history(self):
        self.undo_stack = []
        self.redo_stack = []
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)

    def current_table_snapshot(self) -> pd.DataFrame:
        return self.extract_editor_dataframe().copy()

    def push_undo_snapshot(self):
        snapshot = self.current_table_snapshot()
        self.undo_stack.append(snapshot.copy())
        if len(self.undo_stack) > 50:
            self.undo_stack = self.undo_stack[-50:]
        self.redo_stack = []
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(False)

 
  
    def set_inputs_enabled(self, enabled: bool):
        widgets = [
            getattr(self, "file_combo", None),
            getattr(self, "browse_btn", None),
            getattr(self, "add_files_btn", None),
            getattr(self, "scan_btn", None),

            getattr(self, "lat_combo", None),
            getattr(self, "lon_combo", None),
            getattr(self, "date_combo", None),
            getattr(self, "id_combo", None),
            getattr(self, "auto_desc_combo", None),

            getattr(self, "level1_source_combo", None),
            getattr(self, "level2_source_combo", None),
            getattr(self, "level3_source_combo", None),
            getattr(self, "date_source_combo", None),
            getattr(self, "description_source_combo", None),

            getattr(self, "level1_edit", None),
            getattr(self, "level2_edit", None),
            getattr(self, "level3_edit", None),
            getattr(self, "date_text_edit", None),
            getattr(self, "description_edit", None),

            getattr(self, "date_in_edit", None),
            getattr(self, "date_out_edit", None),
            getattr(self, "reproject_chk", None),
            getattr(self, "points_only_chk", None),

            getattr(self, "add_row_btn", None),
            getattr(self, "delete_rows_btn", None),
            getattr(self, "undo_btn", None),
            getattr(self, "redo_btn", None),

            # Time-series only widgets
            getattr(self, "db_host_edit", None),
            getattr(self, "db_port_edit", None),
            getattr(self, "db_name_edit", None),
            getattr(self, "db_user_edit", None),
            getattr(self, "db_password_edit", None),
            getattr(self, "timeseries_mapping_table", None),
            getattr(self, "add_mapping_btn", None),
            getattr(self, "remove_mapping_btn", None),
            getattr(self, "timeseries_value_source_combo", None),

            getattr(self, "output_type_combo", None),
            getattr(self, "run_btn", None),
            getattr(self, "save_zip_btn", None),
        ]

        for widget in widgets:
            if widget is not None:
                widget.setEnabled(enabled)


    def populate_input_table(self, df: pd.DataFrame | None, reset_history: bool = True):
        self._suspend_table_item_changed = True
        self.input_table.clear()

        if df is None:
            self.input_table.setRowCount(0)
            self.input_table.setColumnCount(0)
            self.editor_columns = []
            self._suspend_table_item_changed = False
            if reset_history:
                self.reset_history()
                self._last_table_snapshot = pd.DataFrame()
            return

        if self.is_geo and "geometry" in df.columns:
            display_df = df.drop(columns=["geometry"]).copy()
        else:
            display_df = df.copy()

        self.editor_columns = [str(c) for c in display_df.columns]

        self.input_table.setRowCount(len(display_df))
        self.input_table.setColumnCount(len(display_df.columns))
        self.input_table.setHorizontalHeaderLabels(self.editor_columns)

        for row_idx, (_, row) in enumerate(display_df.iterrows()):
            for col_idx, value in enumerate(row):
                text = "" if pd.isna(value) else str(value)
                self.input_table.setItem(row_idx, col_idx, QTableWidgetItem(text))

        self.input_table.resizeColumnsToContents()
        self._suspend_table_item_changed = False
        self._last_table_snapshot = display_df.copy()

        if reset_history:
            self.reset_history()

    def clear_input_table(self):
        self.input_table.clear()
        self.input_table.setRowCount(0)
        self.input_table.setColumnCount(0)
        self.editor_columns = []
        self.reset_history()
        self._last_table_snapshot = pd.DataFrame()

    def extract_editor_dataframe(self) -> pd.DataFrame:
        column_names = []
        for col in range(self.input_table.columnCount()):
            header_item = self.input_table.horizontalHeaderItem(col)
            column_names.append(header_item.text() if header_item else f"Column_{col + 1}")

        rows = []
        for row in range(self.input_table.rowCount()):
            row_data = {}
            for col, col_name in enumerate(column_names):
                item = self.input_table.item(row, col)
                row_data[col_name] = item.text() if item is not None else ""
            rows.append(row_data)

        return pd.DataFrame(rows, columns=column_names)

    def sync_editor_to_data(self):
        if self.data is None:
            raise ValueError("No data is loaded.")

        edited_df = self.extract_editor_dataframe()

        if self.is_geo:
            if "geometry" not in self.data.columns:
                raise ValueError("Geometry column is missing from the geospatial dataset.")
            if len(edited_df) != len(self.data):
                raise ValueError(
                    "For geospatial files, row count cannot be changed because geometry must stay aligned."
                )

            geometry = self.data["geometry"].reset_index(drop=True)
            new_df = edited_df.reset_index(drop=True).copy()
            combined = pd.concat([new_df, geometry], axis=1)
            self.data = gpd.GeoDataFrame(
                combined,
                geometry="geometry",
                crs=getattr(self.data, "crs", None),
            )
        else:
            self.data = edited_df.copy()

    def set_data_from_editor_df(self, editor_df: pd.DataFrame, refresh_ui: bool = True, reset_history: bool = False):
        if self.data is None:
            self.data = editor_df.copy()
            if refresh_ui:
                self.populate_input_table(self.data, reset_history=reset_history)
                self.refresh_dropdowns_for_current_file()
            return

        if self.is_geo:
            if "geometry" not in self.data.columns:
                raise ValueError("Geometry column is missing from the geospatial dataset.")
            if len(editor_df) != len(self.data):
                raise ValueError(
                    "For geospatial files, row count cannot be changed because geometry must stay aligned."
                )

            geometry = self.data["geometry"].reset_index(drop=True)
            combined = editor_df.reset_index(drop=True).copy()
            combined["geometry"] = geometry
            self.data = gpd.GeoDataFrame(
                combined,
                geometry="geometry",
                crs=getattr(self.data, "crs", None),
            )
        else:
            self.data = editor_df.copy()

        if refresh_ui:
            self.populate_input_table(self.data, reset_history=reset_history)
            self.refresh_dropdowns_for_current_file()

    def apply_table_edits(self):
        try:
            self.sync_editor_to_data()
            self.refresh_dropdowns_for_current_file()
            self.populate_input_table(self.data, reset_history=False)
            self.show_success_status("Table edits applied successfully.")
            self.log("Table edits applied.")
        except Exception as e:
            self.handle_error("Could not apply table edits", e)

    def reload_original_data(self):
        if self.original_data is None:
            return
        self.data = self.original_data.copy()
        self.result = None
        self.save_zip_btn.setEnabled(False)
        self.populate_input_table(self.data, reset_history=True)
        self.refresh_dropdowns_for_current_file()
        self.clear_status()
        self.hide_editor()
        self.log("Reloaded original data.")

    def add_column(self):
        if self.data is None:
            QMessageBox.information(self, "No data", "Load a file first.")
            return

        column_name, ok = QInputDialog.getText(self, "Add Column", "Column name:")
        if not ok or not column_name.strip():
            return

        column_name = column_name.strip()

        existing_headers = {
            self.input_table.horizontalHeaderItem(i).text()
            for i in range(self.input_table.columnCount())
            if self.input_table.horizontalHeaderItem(i) is not None
        }
        if column_name in existing_headers:
            QMessageBox.warning(self, "Column exists", f"The column '{column_name}' already exists.")
            return

        default_value, _ = QInputDialog.getText(
            self,
            "Default Value",
            f"Default value for '{column_name}' (optional):",
        )

        editor_df = self.current_table_snapshot()
        self.push_undo_snapshot()
        editor_df[column_name] = default_value

        self.set_data_from_editor_df(editor_df, refresh_ui=True, reset_history=False)
        self._last_table_snapshot = editor_df.copy()
        self.show_success_status(f"Column '{column_name}' added.")
        self.log(f"Added column: {column_name}")

    def delete_selected_columns(self):
        if self.data is None:
            QMessageBox.information(self, "No data", "Load a file first.")
            return

        selected_columns = sorted(
            {index.column() for index in self.input_table.selectedIndexes()},
            reverse=True,
        )
        if not selected_columns:
            QMessageBox.information(self, "No selection", "Select one or more columns to delete.")
            return

        editor_df = self.current_table_snapshot()
        column_names = list(editor_df.columns)
        columns_to_delete = [column_names[i] for i in selected_columns]

        reply = QMessageBox.question(
            self,
            "Delete columns",
            "Delete these columns?\n\n" + "\n".join(columns_to_delete),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.push_undo_snapshot()
        editor_df = editor_df.drop(columns=columns_to_delete)

        self.set_data_from_editor_df(editor_df, refresh_ui=True, reset_history=False)
        self._last_table_snapshot = editor_df.copy()
        self.show_success_status(f"Deleted {len(columns_to_delete)} column(s).")
        self.log(f"Deleted columns: {', '.join(columns_to_delete)}")

    def add_row(self):
        if self.data is None:
            QMessageBox.information(self, "No data", "Load a file first.")
            return

        if self.is_geo:
            QMessageBox.information(
                self,
                "Not allowed",
                "Adding rows is disabled for geospatial files because geometry must stay aligned.",
            )
            return

        editor_df = self.current_table_snapshot()
        self.push_undo_snapshot()

        blank_row = {col: "" for col in editor_df.columns}
        editor_df = pd.concat([editor_df, pd.DataFrame([blank_row])], ignore_index=True)

        self.set_data_from_editor_df(editor_df, refresh_ui=True, reset_history=False)
        self._last_table_snapshot = editor_df.copy()
        self.show_success_status("New blank row added.")
        self.log("Added a new row.")

    def delete_selected_rows(self):
        if self.data is None:
            QMessageBox.information(self, "No data", "Load a file first.")
            return

        if self.is_geo:
            QMessageBox.information(
                self,
                "Not allowed",
                "Deleting rows is disabled for geospatial files because geometry must stay aligned.",
            )
            return

        selected_rows = sorted({index.row() for index in self.input_table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "No selection", "Select one or more rows to delete.")
            return

        editor_df = self.current_table_snapshot()
        self.push_undo_snapshot()
        editor_df = editor_df.drop(index=selected_rows).reset_index(drop=True)

        self.set_data_from_editor_df(editor_df, refresh_ui=True, reset_history=False)
        self._last_table_snapshot = editor_df.copy()
        self.show_success_status(f"Deleted {len(selected_rows)} row(s).")
        self.log(f"Deleted {len(selected_rows)} row(s).")

    def undo_edit(self):
        if not self.undo_stack:
            QMessageBox.information(self, "Undo", "Nothing to undo.")
            return

        current_snapshot = self.current_table_snapshot()
        self.redo_stack.append(current_snapshot.copy())

        snapshot = self.undo_stack.pop()
        self.set_data_from_editor_df(snapshot, refresh_ui=True, reset_history=False)
        self._last_table_snapshot = snapshot.copy()

        self.undo_btn.setEnabled(len(self.undo_stack) > 0)
        self.redo_btn.setEnabled(True)
        self.show_success_status("Undo applied.")

    def redo_edit(self):
        if not self.redo_stack:
            QMessageBox.information(self, "Redo", "Nothing to redo.")
            return

        current_snapshot = self.current_table_snapshot()
        self.undo_stack.append(current_snapshot.copy())

        snapshot = self.redo_stack.pop()
        self.set_data_from_editor_df(snapshot, refresh_ui=True, reset_history=False)
        self._last_table_snapshot = snapshot.copy()

        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(len(self.redo_stack) > 0)
        self.show_success_status("Redo applied.")

    def on_input_table_item_changed(self, _item):
        if self._suspend_table_item_changed:
            return

        current_snapshot = self.current_table_snapshot()

        if self._last_table_snapshot.empty:
            self._last_table_snapshot = current_snapshot.copy()
            return

        if current_snapshot.equals(self._last_table_snapshot):
            return

        self.undo_stack.append(self._last_table_snapshot.copy())
        if len(self.undo_stack) > 50:
            self.undo_stack = self.undo_stack[-50:]

        self.redo_stack = []
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(False)
        self._last_table_snapshot = current_snapshot.copy()

    def populate_preview_table(self, df: pd.DataFrame):
        self.preview_table.clear()
        self.preview_table.setRowCount(len(df))
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])

        for row_idx, (_, row) in enumerate(df.iterrows()):
            for col_idx, value in enumerate(row):
                text = "" if pd.isna(value) else str(value)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.preview_table.setItem(row_idx, col_idx, item)

    def clear_preview(self):
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)

    def handle_error(self, title: str, error: Exception):
        self.log(f"{title}\n{error}")
        QMessageBox.critical(self, title, str(error))