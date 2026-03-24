import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    APP_LOGO_PATH,
    APP_UPDATE_URL,
    CURRENT_VERSION,
    GITHUB_LATEST_RELEASE_API,
)
from .sections import (
    build_detected_group,
    build_export_group,
    build_options_group,
    build_timeseries_group,
    build_typed_group,
)
from .styles import MAIN_STYLESHEET
from .widgets import CardFrame


class WindowSetupMixin:
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._build_top_bar(root_layout)
        self._build_scroll_body(root_layout)

    def _build_top_bar(self, root_layout):
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

    def _build_scroll_body(self, root_layout):
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

        body_layout.addWidget(self._build_hero_card())
        body_layout.addWidget(self._build_toolbar_card())

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

        body_layout.addWidget(self._build_file_card())
        body_layout.addWidget(self._build_output_mode_card())

        self.editor_card = self._build_editor_card()
        body_layout.addWidget(self.editor_card)
        self.editor_card.setVisible(False)

        self.detected_group = build_detected_group(self)
        self.export_group = build_export_group(self)
        self.typed_group = build_typed_group(self)
        self.options_group = build_options_group(self)

        self.grid_wrap = CardFrame()
        grid_wrap_layout = QVBoxLayout(self.grid_wrap)
        grid_wrap_layout.setContentsMargins(18, 18, 18, 18)

        self.settings_grid = QGridLayout()
        self.settings_grid.setHorizontalSpacing(18)
        self.settings_grid.setVerticalSpacing(18)
        grid_wrap_layout.addLayout(self.settings_grid)
        body_layout.addWidget(self.grid_wrap)

        self.timeseries_group = build_timeseries_group(self)
        body_layout.addWidget(self.timeseries_group)

        self.apply_responsive_layout()

        body_layout.addWidget(self._build_help_card())
        body_layout.addWidget(self._build_output_card(), stretch=1)

        self._connect_signals()
        self.update_output_mode_ui()

    def _build_hero_card(self):
        hero_card = CardFrame()
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(8)

        title = QLabel("Generic Geospatial Processing Tool")
        title.setObjectName("heroTitle")

        subtitle = QLabel(
            "Process CSV, Excel, Shapefile, GeoJSON, and GeoPackage files into "
            "location and time-series AQUASAFE outputs."
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)

        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        return hero_card

    def _build_toolbar_card(self):
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
        return toolbar_card

    def _build_file_card(self):
        file_card = CardFrame()
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(18, 14, 18, 14)
        file_layout.setSpacing(10)

        file_label = QLabel("Selected input file")
        file_label.setObjectName("sectionLabel")

        file_row = QHBoxLayout()
        file_row.setSpacing(10)

        from PyQt6.QtWidgets import QComboBox

        self.file_combo = QComboBox()
        self.file_combo.setObjectName("fileCombo")
        self.file_combo.setMinimumHeight(44)
        self.file_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.file_combo.setEditable(True)
        self.file_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.browse_file_btn = QPushButton("Browse")
        self.browse_file_btn.setObjectName("softButton")
        self.browse_file_btn.setMinimumHeight(44)

        file_row.addWidget(self.file_combo, 1)
        file_row.addWidget(self.browse_file_btn)

        self.file_info = QLabel("No input file loaded.")
        self.file_info.setObjectName("fileInfoLabel")
        self.file_info.setWordWrap(True)

        file_layout.addWidget(file_label)
        file_layout.addLayout(file_row)
        file_layout.addWidget(self.file_info)
        return file_card

    def _build_output_mode_card(self):
        output_mode_card = CardFrame()
        output_mode_layout = QVBoxLayout(output_mode_card)
        output_mode_layout.setContentsMargins(18, 14, 18, 14)
        output_mode_layout.setSpacing(10)

        output_mode_title = QLabel("Output Type")
        output_mode_title.setObjectName("sectionTitle")

        radio_row = QHBoxLayout()
        radio_row.setSpacing(16)

        self.location_radio = QRadioButton("Location Data")
        self.location_radio.setChecked(True)

        self.timeseries_radio = QRadioButton("Time Series Data")

        radio_row.addWidget(self.location_radio)
        radio_row.addWidget(self.timeseries_radio)
        radio_row.addStretch(1)

        self.output_mode_note = QLabel(
            "Choose whether to create the standard location import or the time-series import."
        )
        self.output_mode_note.setObjectName("fileInfoLabel")
        self.output_mode_note.setWordWrap(True)

        output_mode_layout.addWidget(output_mode_title)
        output_mode_layout.addLayout(radio_row)
        output_mode_layout.addWidget(self.output_mode_note)
        return output_mode_card

    def _build_editor_card(self):
        editor_card = CardFrame()
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(18, 18, 18, 18)
        editor_layout.setSpacing(12)

        editor_header = QHBoxLayout()
        editor_title = QLabel("Input Data Editor")
        editor_title.setObjectName("sectionTitle")

        self.add_column_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder),
            "Add Column",
        )
        self.delete_column_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
            "Delete Selected Columns",
        )
        self.add_row_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "Add Row",
        )
        self.delete_rows_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
            "Delete Selected Rows",
        )
        self.undo_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack),
            "Undo",
        )
        self.redo_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward),
            "Redo",
        )
        self.apply_edits_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            "Apply Table Edits",
        )
        self.reload_data_btn = self.make_icon_tool_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
            "Reload Original Data",
        )

        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)

        editor_header.addWidget(editor_title)
        editor_header.addStretch(1)
        editor_header.addWidget(self.add_column_btn)
        editor_header.addWidget(self.delete_column_btn)
        editor_header.addWidget(self.add_row_btn)
        editor_header.addWidget(self.delete_rows_btn)
        editor_header.addWidget(self.undo_btn)
        editor_header.addWidget(self.redo_btn)
        editor_header.addWidget(self.apply_edits_btn)
        editor_header.addWidget(self.reload_data_btn)

        self.editor_note_label = QLabel(
            "This editor appears only when processing fails, so you can fix the input data and try again."
        )
        self.editor_note_label.setObjectName("fileInfoLabel")
        self.editor_note_label.setWordWrap(True)

        self.input_table = QTableWidget()
        self.input_table.setObjectName("inputTable")
        self.input_table.setAlternatingRowColors(True)
        self.input_table.setMinimumHeight(260)
        self.input_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.input_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.input_table.horizontalHeader().setStretchLastSection(True)

        editor_layout.addLayout(editor_header)
        editor_layout.addWidget(self.editor_note_label)
        editor_layout.addWidget(self.input_table)
        return editor_card

    def _build_help_card(self):
        help_card = CardFrame()
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(18, 14, 18, 14)

        help_label = QLabel(
            "<b>How to use the fields</b><br>"
            "• Enter the database connection details in the app.<br>"
            "• Password is hidden while typing.<br>"
            "• Run processing first.<br>"
            "• If processing fails, the Input Data Editor will appear so you can fix the data.<br>"
            "• Choose a source column if the value already exists in your file.<br>"
            "• Type a value if you want the same value on every row.<br>"
            "• Date can be exported as its own column and formatted using Date in / Date out.<br>"
            "• parameters.csv is recreated on every run."
        )
        help_label.setObjectName("helpLabel")
        help_label.setWordWrap(True)
        help_label.setTextFormat(Qt.TextFormat.RichText)

        help_layout.addWidget(help_label)
        return help_card

    def _build_output_card(self):
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
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        preview_title = QLabel("Output Preview")
        preview_title.setObjectName("sectionTitle")

        self.preview_table = QTableWidget()
        self.preview_table.setObjectName("previewTable")
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMinimumHeight(260)
        self.preview_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview_table.horizontalHeader().setStretchLastSection(True)

        output_layout.addWidget(log_title)
        output_layout.addWidget(self.log_output)
        output_layout.addWidget(preview_title)
        output_layout.addWidget(self.preview_table)
        return output_card

    def _connect_signals(self):
        if hasattr(self, "add_mapping_btn"):
            self.add_mapping_btn.clicked.connect(self.add_timeseries_mapping_row)
        if hasattr(self, "remove_mapping_btn"):
            self.remove_mapping_btn.clicked.connect(self.remove_selected_timeseries_mapping_rows)
        if hasattr(self, "generate_parameters_btn"):
            self.generate_parameters_btn.clicked.connect(self.on_generate_parameters_clicked)

        self.add_files_btn.clicked.connect(self.add_files)
        self.scan_btn.clicked.connect(lambda: self.scan_current_folder(initial=False))
        self.browse_file_btn.clicked.connect(self.browse_for_input_file)
        self.add_column_btn.clicked.connect(self.add_column)
        self.delete_column_btn.clicked.connect(self.delete_selected_columns)
        self.add_row_btn.clicked.connect(self.add_row)
        self.delete_rows_btn.clicked.connect(self.delete_selected_rows)
        self.undo_btn.clicked.connect(self.undo_edit)
        self.redo_btn.clicked.connect(self.redo_edit)
        self.apply_edits_btn.clicked.connect(self.apply_table_edits)
        self.reload_data_btn.clicked.connect(self.reload_original_data)
        self.open_output_btn.clicked.connect(self.open_output_folder)
        self.update_btn.clicked.connect(self.open_update_link)
        self.file_combo.currentIndexChanged.connect(self.on_file_changed)

        if self.file_combo.lineEdit() is not None:
            self.file_combo.lineEdit().editingFinished.connect(self.on_file_changed)

        self.input_table.itemChanged.connect(self.on_input_table_item_changed)
        self.location_radio.toggled.connect(self.update_output_mode_ui)
        self.timeseries_radio.toggled.connect(self.update_output_mode_ui)
        self.run_btn.clicked.connect(self.on_run_clicked)
        self.save_zip_btn.clicked.connect(self.on_save_zip_clicked)

    def current_output_type(self) -> str:
        if hasattr(self, "timeseries_radio") and self.timeseries_radio.isChecked():
            return "time_series"
        return "location"

    def update_output_mode_ui(self):
        mode = self.current_output_type()
        is_timeseries = mode == "time_series"
        self.timeseries_group.setVisible(is_timeseries)

        if mode == "time_series":
            self.output_mode_note.setText(
                "Time-series mode creates the time-series outputs and can optionally insert the generated "
                "populate CSV files into MongoDB after successful processing."
            )
        else:
            self.output_mode_note.setText(
                "Location mode creates the standard location import text file."
            )


    def make_icon_tool_button(self, icon, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("iconToolButton")
        btn.setIcon(icon)
        btn.setToolTip(tooltip)
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(42, 42)
        return btn

    def show_editor(self):
        self.editor_card.setVisible(True)
        QTimer.singleShot(0, lambda: self.scroll_area.ensureWidgetVisible(self.editor_card))

    def hide_editor(self):
        self.editor_card.setVisible(False)

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
        self.setStyleSheet(MAIN_STYLESHEET)

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