import json
import shutil
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from PyQt6.QtCore import Qt, QTimer, QUrl, QSize
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from processing import (
    DESCRIPTION_CANDIDATES,
    DATE_CANDIDATES,
    ID_CANDIDATES,
    LAT_CANDIDATES,
    LON_CANDIDATES,
    OUTPUT_DIR,
    SUPPORTED_PRIMARY_EXTS,
    find_candidate,
    guess_default_input_file,
    list_primary_input_files_from_folder,
    process_file,
    read_input_file,
)

CURRENT_VERSION = "1.0.1"
APP_UPDATE_URL = "https://github.com/ZoloKiala/desktop_safe/releases/latest"
GITHUB_OWNER = "ZoloKiala"
GITHUB_REPO = "desktop_safe"
GITHUB_LATEST_RELEASE_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return base_path / relative_path


APP_LOGO_PATH = resource_path("assets/aquasafe.png")


class CardFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("cardFrame")
        self.setFrameShape(QFrame.Shape.NoFrame)


class GeospatialProcessingWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AQUASAFE {CURRENT_VERSION} - Generic Geospatial Processing Tool")

        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(int(available.width() * 0.88), 1500),
                min(int(available.height() * 0.88), 950),
            )
        else:
            self.resize(1400, 900)

        self.setMinimumSize(980, 700)

        self.candidate_files: list[str] = []
        self.data = None
        self.is_geo = False
        self.input_file: str | None = None
        self.result: dict | None = None
        self.latest_release_url = APP_UPDATE_URL

        self._build_ui()
        self._apply_styles()
        self.scan_current_folder(initial=True)
        QTimer.singleShot(1200, self.check_for_updates)

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # =========================================================
        # Top navbar
        # =========================================================
        self.top_bar = QFrame()
        self.top_bar.setObjectName("topBar")
        self.top_bar.setFixedHeight(84)

        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(20, 10, 20, 10)
        top_bar_layout.setSpacing(14)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("logoLabel")
        self.logo_label.setFixedSize(190, 52)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.logo_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.brand_text_label = QLabel("AQUASAFE")
        self.brand_text_label.setObjectName("appTitleLabel")
        self.brand_text_label.setVisible(False)

        self._load_logo()

        top_bar_layout.addWidget(self.logo_label)
        top_bar_layout.addWidget(self.brand_text_label)
        top_bar_layout.addStretch(1)

        self.open_output_btn = QPushButton("Output Folder")
        self.open_output_btn.setObjectName("headerButton")

        self.update_btn = QPushButton("Download Latest Update")
        self.update_btn.setObjectName("headerButton")

        top_bar_layout.addWidget(self.open_output_btn)
        top_bar_layout.addWidget(self.update_btn)

        root_layout.addWidget(self.top_bar)

        # =========================================================
        # Scrollable main content
        # =========================================================
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        body = QWidget()
        body.setObjectName("bodyRoot")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(26, 24, 26, 24)
        body_layout.setSpacing(16)

        self.scroll_area.setWidget(body)
        root_layout.addWidget(self.scroll_area)

        # =========================================================
        # Hero card
        # =========================================================
        hero_card = CardFrame()
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(8)

        title = QLabel("Generic Geospatial Processing Tool")
        title.setObjectName("heroTitle")

        subtitle = QLabel(
            "Process CSV, Excel, Shapefile, GeoJSON, and GeoPackage files into "
            "WKT CSV, import TXT, sample TXT, and ZIP outputs."
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)

        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        body_layout.addWidget(hero_card)

        # =========================================================
        # Toolbar card
        # =========================================================
        toolbar_card = CardFrame()
        toolbar_layout = QHBoxLayout(toolbar_card)
        toolbar_layout.setContentsMargins(18, 14, 18, 14)
        toolbar_layout.setSpacing(12)

        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.setObjectName("primaryButton")

        self.scan_btn = QPushButton("Scan Current Folder")
        self.scan_btn.setObjectName("softButton")

        self.run_btn = QPushButton("Run Processing")
        self.run_btn.setObjectName("primaryButton")

        self.save_zip_btn = QPushButton("Save ZIP As")
        self.save_zip_btn.setObjectName("softButton")
        self.save_zip_btn.setEnabled(False)

        toolbar_layout.addWidget(self.add_files_btn)
        toolbar_layout.addWidget(self.scan_btn)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.run_btn)
        toolbar_layout.addWidget(self.save_zip_btn)

        body_layout.addWidget(toolbar_card)

        # =========================================================
        # Update / success banners
        # =========================================================
        self.update_label = QLabel("")
        self.update_label.setObjectName("updateLabel")
        self.update_label.setWordWrap(True)
        self.update_label.setVisible(False)
        body_layout.addWidget(self.update_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        body_layout.addWidget(self.status_label)

        # =========================================================
        # File selection card
        # =========================================================
        file_card = CardFrame()
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(18, 14, 18, 14)
        file_layout.setSpacing(10)

        file_label = QLabel("Selected input file")
        file_label.setObjectName("sectionLabel")

        self.file_combo = QComboBox()
        self.file_combo.setObjectName("fileCombo")
        self.file_combo.setMinimumHeight(44)
        self.file_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.file_info = QLabel("No input file loaded.")
        self.file_info.setObjectName("fileInfoLabel")
        self.file_info.setWordWrap(True)

        file_layout.addWidget(file_label)
        file_layout.addWidget(self.file_combo)
        file_layout.addWidget(self.file_info)

        body_layout.addWidget(file_card)

        # =========================================================
        # Responsive settings grid
        # =========================================================
        self.detected_group = self._build_detected_group()
        self.export_group = self._build_export_group()
        self.typed_group = self._build_typed_group()
        self.options_group = self._build_options_group()

        self.grid_wrap = CardFrame()
        grid_wrap_layout = QVBoxLayout(self.grid_wrap)
        grid_wrap_layout.setContentsMargins(18, 18, 18, 18)

        self.settings_grid = QGridLayout()
        self.settings_grid.setHorizontalSpacing(18)
        self.settings_grid.setVerticalSpacing(18)
        grid_wrap_layout.addLayout(self.settings_grid)

        body_layout.addWidget(self.grid_wrap)
        self.apply_responsive_layout()

        # =========================================================
        # Help card
        # =========================================================
        help_card = CardFrame()
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(18, 14, 18, 14)

        help_label = QLabel(
            "<b>How to use the fields</b><br>"
            "• Choose a source column if the value already exists in your file.<br>"
            "• Type a value if you want the same value on every row.<br>"
            "• Leave both blank to use defaults or auto behavior.<br>"
            "• Level3 falls back to the ID column or generated row numbers."
        )
        help_label.setObjectName("helpLabel")
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)

        help_layout.addWidget(help_label)
        body_layout.addWidget(help_card)

        # =========================================================
        # Output card
        # =========================================================
        output_card = CardFrame()
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(18, 18, 18, 18)
        output_layout.setSpacing(12)

        log_title = QLabel("Processing Log")
        log_title.setObjectName("sectionTitle")

        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(200)
        self.log_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )

        preview_title = QLabel("Preview")
        preview_title.setObjectName("sectionTitle")

        self.preview_table = QTableWidget()
        self.preview_table.setObjectName("previewTable")
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMinimumHeight(260)
        self.preview_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setStretchLastSection(True)

        output_layout.addWidget(log_title)
        output_layout.addWidget(self.log_output)
        output_layout.addWidget(preview_title)
        output_layout.addWidget(self.preview_table)

        body_layout.addWidget(output_card, stretch=1)

        self.add_files_btn.clicked.connect(self.add_files)
        self.scan_btn.clicked.connect(lambda: self.scan_current_folder(initial=False))
        self.open_output_btn.clicked.connect(self.open_output_folder)
        self.update_btn.clicked.connect(self.open_update_link)
        self.file_combo.currentIndexChanged.connect(self.on_file_changed)
        self.run_btn.clicked.connect(self.on_run_clicked)
        self.save_zip_btn.clicked.connect(self.on_save_zip_clicked)

    def _build_detected_group(self):
        group = QGroupBox("Detected / Source Columns")
        group.setObjectName("formGroup")
        form = QFormLayout(group)
        form.setContentsMargins(14, 18, 14, 14)
        form.setSpacing(12)

        self.lat_combo = QComboBox()
        self.lon_combo = QComboBox()
        self.date_combo = QComboBox()
        self.id_combo = QComboBox()
        self.auto_desc_combo = QComboBox()

        form.addRow("Latitude:", self.lat_combo)
        form.addRow("Longitude:", self.lon_combo)
        form.addRow("Date:", self.date_combo)
        form.addRow("ID:", self.id_combo)
        form.addRow("Desc col:", self.auto_desc_combo)
        return group

    def _build_export_group(self):
        group = QGroupBox("Final Export Field Sources")
        group.setObjectName("formGroup")
        form = QFormLayout(group)
        form.setContentsMargins(14, 18, 14, 14)
        form.setSpacing(12)

        self.level1_source_combo = QComboBox()
        self.level2_source_combo = QComboBox()
        self.level3_source_combo = QComboBox()
        self.description_source_combo = QComboBox()

        form.addRow("L1 source:", self.level1_source_combo)
        form.addRow("L2 source:", self.level2_source_combo)
        form.addRow("L3 source:", self.level3_source_combo)
        form.addRow("Desc src:", self.description_source_combo)
        return group

    def _build_typed_group(self):
        group = QGroupBox("Typed Fallback Values")
        group.setObjectName("formGroup")
        form = QFormLayout(group)
        form.setContentsMargins(14, 18, 14, 14)
        form.setSpacing(12)

        self.level1_edit = QLineEdit()
        self.level2_edit = QLineEdit()
        self.level3_edit = QLineEdit()
        self.description_edit = QLineEdit()

        form.addRow("Level1:", self.level1_edit)
        form.addRow("Level2:", self.level2_edit)
        form.addRow("Level3:", self.level3_edit)
        form.addRow("Description:", self.description_edit)
        return group

    def _build_options_group(self):
        group = QGroupBox("Options")
        group.setObjectName("formGroup")
        form = QFormLayout(group)
        form.setContentsMargins(14, 18, 14, 14)
        form.setSpacing(12)

        self.date_in_edit = QLineEdit()
        self.date_out_edit = QLineEdit("%y-%m-%d")
        self.reproject_chk = QCheckBox("Reproject geo to EPSG:4326")
        self.reproject_chk.setChecked(True)
        self.points_only_chk = QCheckBox("Require point geometry")

        form.addRow("Date in:", self.date_in_edit)
        form.addRow("Date out:", self.date_out_edit)
        form.addRow("", self.reproject_chk)
        form.addRow("", self.points_only_chk)
        return group

    def _load_logo(self):
        if APP_LOGO_PATH.exists():
            pixmap = QPixmap(str(APP_LOGO_PATH))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    QSize(170, 46),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.logo_label.setPixmap(scaled)
                self.brand_text_label.setVisible(False)
                return

        self.logo_label.clear()
        self.brand_text_label.setVisible(True)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f3f5f7;
            }

            QWidget#centralRoot, QWidget#bodyRoot {
                background: #f3f5f7;
                color: #1b2745;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 14px;
            }

            QLabel {
                background: transparent;
                color: #1b2745;
            }

            QFrame#topBar {
                background: #1c2856;
                border: none;
            }

            QLabel#logoLabel,
            QLabel#appTitleLabel {
                background: transparent;
                color: white;
            }

            QLabel#appTitleLabel {
                font-size: 20px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }

            QLabel#heroTitle {
                background: transparent;
                font-size: 24px;
                font-weight: 700;
                color: #1b2745;
            }

            QLabel#heroSubtitle {
                background: transparent;
                font-size: 14px;
                color: #657089;
            }

            QLabel#sectionTitle {
                background: transparent;
                font-size: 16px;
                font-weight: 700;
                color: #1b2745;
            }

            QLabel#sectionLabel {
                background: transparent;
                font-size: 13px;
                font-weight: 600;
                color: #5d6a82;
            }

            QLabel#fileInfoLabel,
            QLabel#helpLabel {
                background: transparent;
                color: #5f6b82;
                font-size: 13px;
            }

            QLabel#statusLabel {
                background: #e8f7ec;
                color: #1f6b3b;
                border: 1px solid #b7e4c7;
                border-radius: 10px;
                padding: 10px 12px;
                font-weight: 600;
            }

            QLabel#updateLabel {
                background: #fff4d6;
                color: #8a6116;
                border: 1px solid #f0d58a;
                border-radius: 10px;
                padding: 10px 12px;
                font-weight: 600;
            }

            QFrame#cardFrame {
                background: #ffffff;
                border: 1px solid #d8e0ea;
                border-radius: 16px;
            }

            QGroupBox#formGroup {
                background: #f8fafc;
                border: 1px solid #dde4ee;
                border-radius: 14px;
                margin-top: 10px;
                font-weight: 700;
                color: #223154;
            }

            QGroupBox#formGroup::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                background: transparent;
            }

            QPushButton {
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 600;
                min-height: 20px;
            }

            QPushButton#primaryButton {
                background: #2a56d4;
                color: white;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background: #204bc4;
            }

            QPushButton#softButton,
            QPushButton#headerButton {
                background: #e6ecf5;
                color: #1d2b4d;
                border: 1px solid #d3dce8;
            }

            QPushButton#softButton:hover,
            QPushButton#headerButton:hover {
                background: #dce5f0;
            }

            QPushButton:disabled {
                background: #cfd8e3;
                color: #7b8797;
            }

            QLineEdit,
            QComboBox,
            QTextEdit {
                background: white;
                border: 1px solid #d7deea;
                border-radius: 10px;
                padding: 8px 10px;
                color: #1b2745;
            }

            QLineEdit:focus,
            QComboBox:focus,
            QTextEdit:focus {
                border: 1px solid #5b86ff;
            }

            QComboBox {
                min-height: 22px;
                padding-right: 26px;
            }

            QScrollArea {
                border: none;
                background: #f3f5f7;
            }

            QTableWidget {
                background: white;
                border: 1px solid #d7deea;
                border-radius: 12px;
                gridline-color: #e8edf4;
                selection-background-color: #dfe9ff;
                selection-color: #1b2745;
            }

            QHeaderView::section {
                background: #eef3f8;
                color: #1b2745;
                border: none;
                border-bottom: 1px solid #d7deea;
                padding: 8px;
                font-weight: 700;
            }

            QTextEdit#logOutput {
                background: #fbfcfe;
                border: 1px solid #d7deea;
                border-radius: 12px;
            }

            QCheckBox {
                background: transparent;
                spacing: 8px;
            }
            """
        )

    def normalize_version(self, version_text: str) -> tuple[int, ...]:
        text = str(version_text).strip().lower().lstrip("v")
        parts = []
        for piece in text.split("."):
            try:
                parts.append(int(piece))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    def check_for_updates(self):
        try:
            req = Request(
                GITHUB_LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "AQUASAFE-Desktop",
                },
            )

            with urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))

            latest_tag = str(data.get("tag_name", "")).strip()
            latest_url = str(data.get("html_url", APP_UPDATE_URL)).strip() or APP_UPDATE_URL

            if latest_tag and self.normalize_version(latest_tag) > self.normalize_version(CURRENT_VERSION):
                self.latest_release_url = latest_url
                self.show_update_status(
                    f"New version available: {latest_tag}. Click 'Download Latest Update' to install it."
                )
                self.update_btn.setText(f"Update Available ({latest_tag})")
                self.update_btn.setToolTip(f"A newer release is available: {latest_tag}")
            else:
                self.latest_release_url = APP_UPDATE_URL
                self.clear_update_status()
                self.update_btn.setText("Download Latest Update")
                self.update_btn.setToolTip("Open the latest release page")

        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, OSError):
            self.latest_release_url = APP_UPDATE_URL
            self.clear_update_status()
            self.update_btn.setText("Download Latest Update")
            self.update_btn.setToolTip("Open the latest release page")

    def apply_responsive_layout(self):
        while self.settings_grid.count():
            self.settings_grid.takeAt(0)

        width = self.width()

        if width < 1180:
            self.settings_grid.addWidget(self.detected_group, 0, 0)
            self.settings_grid.addWidget(self.export_group, 1, 0)
            self.settings_grid.addWidget(self.typed_group, 2, 0)
            self.settings_grid.addWidget(self.options_group, 3, 0)
            self.settings_grid.setColumnStretch(0, 1)
            self.settings_grid.setColumnStretch(1, 0)
        else:
            self.settings_grid.addWidget(self.detected_group, 0, 0)
            self.settings_grid.addWidget(self.export_group, 0, 1)
            self.settings_grid.addWidget(self.typed_group, 1, 0)
            self.settings_grid.addWidget(self.options_group, 1, 1)
            self.settings_grid.setColumnStretch(0, 1)
            self.settings_grid.setColumnStretch(1, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "settings_grid"):
            self.apply_responsive_layout()

    def clear_status(self):
        self.status_label.clear()
        self.status_label.setVisible(False)

    def show_success_status(self, message: str):
        self.status_label.setText(message)
        self.status_label.setVisible(True)

    def clear_update_status(self):
        self.update_label.clear()
        self.update_label.setVisible(False)

    def show_update_status(self, message: str):
        self.update_label.setText(message)
        self.update_label.setVisible(True)

    def log(self, text: str):
        self.log_output.append(text)

    def set_combo_options(self, combo: QComboBox, options: list[str], selected: str):
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(options)
        idx = combo.findText(selected)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

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
            self.data = None
            self.is_geo = False
            self.input_file = None
            self.result = None
            self.save_zip_btn.setEnabled(False)
            self.file_info.setText("No supported input files loaded.")
            self.clear_preview()
            self.clear_status()
            return

        target = select_file if select_file in self.candidate_files else self.candidate_files[0]
        index = self.file_combo.findText(target)
        self.file_combo.setCurrentIndex(index)
        self.load_file_into_state(target)
        self.refresh_dropdowns_for_current_file()

    def load_file_into_state(self, file_path: str):
        self.data, self.is_geo = read_input_file(file_path)
        self.input_file = file_path
        self.result = None
        self.save_zip_btn.setEnabled(False)

    def current_non_geometry_columns(self) -> list[str]:
        if self.data is None:
            return []
        return [c for c in self.data.columns if c != "geometry"]

    def refresh_dropdowns_for_current_file(self):
        cols = self.current_non_geometry_columns()
        options = ["(none)"] + [str(c) for c in cols]

        lat_guess = find_candidate(cols, LAT_CANDIDATES) or "(none)"
        lon_guess = find_candidate(cols, LON_CANDIDATES) or "(none)"
        date_guess = find_candidate(cols, DATE_CANDIDATES) or "(none)"
        id_guess = find_candidate(cols, ID_CANDIDATES) or "(none)"
        desc_guess = find_candidate(cols, DESCRIPTION_CANDIDATES) or "(none)"

        self.set_combo_options(self.lat_combo, options, lat_guess)
        self.set_combo_options(self.lon_combo, options, lon_guess)
        self.set_combo_options(self.date_combo, options, date_guess)
        self.set_combo_options(self.id_combo, options, id_guess)
        self.set_combo_options(self.auto_desc_combo, options, desc_guess)

        self.set_combo_options(self.level1_source_combo, options, "(none)")
        self.set_combo_options(self.level2_source_combo, options, "(none)")
        self.set_combo_options(self.level3_source_combo, options, "(none)")
        self.set_combo_options(
            self.description_source_combo,
            ["(none)", "(auto detected description column)"] + [str(c) for c in cols],
            "(auto detected description column)" if desc_guess != "(none)" else "(none)",
        )

        self.lat_combo.setEnabled(not self.is_geo)
        self.lon_combo.setEnabled(not self.is_geo)

        self.file_info.setText(
            f"<b>Input file:</b> {self.input_file}<br>"
            f"<b>Geospatial input:</b> {self.is_geo}<br>"
            f"<b>Rows:</b> {len(self.data):,}"
        )
        self.file_info.setTextFormat(Qt.TextFormat.RichText)

    def combo_value_or_none(self, combo: QComboBox):
        value = combo.currentText()
        return None if value == "(none)" else value

    def on_file_changed(self):
        file_path = self.file_combo.currentText().strip()
        if not file_path:
            return

        try:
            self.load_file_into_state(file_path)
            self.refresh_dropdowns_for_current_file()
            self.clear_preview()
            self.log_output.clear()
            self.clear_status()
            self.log(f"Loaded: {file_path}")
        except Exception as e:
            self.handle_error("Failed to load file", e)

    def on_run_clicked(self):
        self.log_output.clear()
        self.clear_status()

        try:
            self.result = process_file(
                input_file=self.input_file,
                data=self.data,
                is_geo=self.is_geo,
                lat_col=self.combo_value_or_none(self.lat_combo),
                lon_col=self.combo_value_or_none(self.lon_combo),
                date_col=self.combo_value_or_none(self.date_combo),
                id_col=self.combo_value_or_none(self.id_combo),
                auto_desc_col=self.combo_value_or_none(self.auto_desc_combo),
                level1_source=self.level1_source_combo.currentText(),
                level2_source=self.level2_source_combo.currentText(),
                level3_source=self.level3_source_combo.currentText(),
                description_source=self.description_source_combo.currentText(),
                level1_text=self.level1_edit.text(),
                level2_text=self.level2_edit.text(),
                level3_text=self.level3_edit.text(),
                description_text=self.description_edit.text(),
                date_input_format=self.date_in_edit.text().strip() or None,
                date_output_format=self.date_out_edit.text().strip() or "%y-%m-%d",
                auto_reproject_to_wgs84=self.reproject_chk.isChecked(),
                require_point_geometry=self.points_only_chk.isChecked(),
            )

            self.save_zip_btn.setEnabled(True)

            result = self.result
            self.log("Processing complete.\n")
            self.log(f"WKT CSV:    {result['with_wkt_path']}")
            self.log(f"Import TXT: {result['import_path']}")
            self.log(f"Sample TXT: {result['sample_path']}")
            self.log(f"ZIP:        {result['zip_path']}")
            self.log(f"Rows:       {len(result['import_table']):,}")

            duplicate_count = int(result["duplicate_mask"].sum())
            if duplicate_count:
                self.log(
                    f"\nWarning: {duplicate_count} duplicate row(s) found for Level1/Level2/Level3."
                )
                preview_dup = (
                    result["import_table"]
                    .loc[result["duplicate_mask"]]
                    .sort_values(["Level1", "Level2", "Level3"])
                    .head(20)
                )
                self.log(preview_dup.to_string(index=False))
            else:
                self.log("\nNo duplicate Level1/Level2/Level3 combinations found.")

            self.populate_preview_table(result["import_table"].head(200))
            self.show_success_status(
                f"Success: processing completed. {len(result['import_table']):,} rows exported. "
                f"ZIP created: {result['zip_path'].name}"
            )

            QMessageBox.information(
                self,
                "Success",
                (
                    "Processing completed successfully.\n\n"
                    f"Rows processed: {len(result['import_table']):,}\n"
                    f"ZIP created: {result['zip_path'].name}"
                ),
            )

        except Exception as e:
            self.save_zip_btn.setEnabled(False)
            self.clear_preview()
            self.clear_status()
            self.handle_error("Processing failed", e)

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