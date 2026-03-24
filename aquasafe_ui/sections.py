from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QVBoxLayout,
)


def build_detected_group(window):
    group = QGroupBox("Detected / Source Columns")
    group.setObjectName("formGroup")

    form = QFormLayout(group)
    form.setContentsMargins(14, 18, 14, 14)
    form.setSpacing(12)

    window.lat_combo = QComboBox()
    window.lon_combo = QComboBox()
    window.date_combo = QComboBox()
    window.id_combo = QComboBox()
    window.auto_desc_combo = QComboBox()

    form.addRow("Latitude:", window.lat_combo)
    form.addRow("Longitude:", window.lon_combo)
    form.addRow("Date:", window.date_combo)
    form.addRow("ID:", window.id_combo)
    form.addRow("Desc col:", window.auto_desc_combo)

    return group


def build_export_group(window):
    group = QGroupBox("Final Export Field Sources")
    group.setObjectName("formGroup")

    form = QFormLayout(group)
    form.setContentsMargins(14, 18, 14, 14)
    form.setSpacing(12)

    window.level1_source_combo = QComboBox()
    window.level2_source_combo = QComboBox()
    window.level3_source_combo = QComboBox()
    window.date_source_combo = QComboBox()
    window.description_source_combo = QComboBox()

    form.addRow("L1 source:", window.level1_source_combo)
    form.addRow("L2 source:", window.level2_source_combo)
    form.addRow("L3 source:", window.level3_source_combo)
    form.addRow("Date src:", window.date_source_combo)
    form.addRow("Desc src:", window.description_source_combo)

    return group


def build_typed_group(window):
    group = QGroupBox("Typed Fallback Values")
    group.setObjectName("formGroup")

    form = QFormLayout(group)
    form.setContentsMargins(14, 18, 14, 14)
    form.setSpacing(12)

    window.level1_edit = QLineEdit()
    window.level2_edit = QLineEdit()
    window.level3_edit = QLineEdit()
    window.date_text_edit = QLineEdit()
    window.description_edit = QLineEdit()

    form.addRow("Level1:", window.level1_edit)
    form.addRow("Level2:", window.level2_edit)
    form.addRow("Level3:", window.level3_edit)
    form.addRow("Date:", window.date_text_edit)
    form.addRow("Description:", window.description_edit)

    return group


def build_options_group(window):
    group = QGroupBox("Options")
    group.setObjectName("formGroup")

    form = QFormLayout(group)
    form.setContentsMargins(14, 18, 14, 14)
    form.setSpacing(12)

    window.date_in_edit = QLineEdit()
    window.date_out_edit = QLineEdit("%Y-%m-%d")
    window.reproject_chk = QCheckBox("Reproject geo to EPSG:4326")
    window.reproject_chk.setChecked(True)
    window.points_only_chk = QCheckBox("Require point geometry")

    form.addRow("Date in:", window.date_in_edit)
    form.addRow("Date out:", window.date_out_edit)
    form.addRow("", window.reproject_chk)
    form.addRow("", window.points_only_chk)

    return group


def build_timeseries_group(window):
    group = QGroupBox("Time Series Settings")
    group.setObjectName("formGroup")

    layout = QVBoxLayout(group)
    layout.setContentsMargins(14, 18, 14, 14)
    layout.setSpacing(12)

    # ------------------------------------------------------------------
    # Hidden database section
    # ------------------------------------------------------------------
    # These widgets are kept so file_ops_mixin fallback logic still works,
    # but the connection section is hidden from the user.
    window.db_group = QGroupBox("Database Connection")
    window.db_group.setObjectName("formGroup")

    db_group_layout = QVBoxLayout(window.db_group)
    db_group_layout.setContentsMargins(0, 0, 0, 0)
    db_group_layout.setSpacing(8)

    db_form = QFormLayout()
    db_form.setSpacing(12)

    window.db_host_edit = QLineEdit()
    window.db_port_edit = QLineEdit()
    window.db_name_edit = QLineEdit()
    window.db_user_edit = QLineEdit()
    window.db_password_edit = QLineEdit()
    window.db_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

    window.db_host_edit.setPlaceholderText("Host")
    window.db_port_edit.setPlaceholderText("Port")
    window.db_name_edit.setPlaceholderText("Database")
    window.db_user_edit.setPlaceholderText("User")
    window.db_password_edit.setPlaceholderText("Password")

    db_form.addRow("Host:", window.db_host_edit)
    db_form.addRow("Port:", window.db_port_edit)
    db_form.addRow("Database:", window.db_name_edit)
    db_form.addRow("User:", window.db_user_edit)
    db_form.addRow("Password:", window.db_password_edit)

    db_group_layout.addLayout(db_form)
    window.db_group.setVisible(False)
    layout.addWidget(window.db_group)

    db_note = QLabel(
        "Database credentials are loaded from local secrets.toml for the time-series workflow."
    )
    db_note.setObjectName("fileInfoLabel")
    db_note.setWordWrap(True)
    layout.addWidget(db_note)

    # ------------------------------------------------------------------
    # Parameters button
    # ------------------------------------------------------------------
    top_button_row = QHBoxLayout()
    top_button_row.setSpacing(10)

    window.generate_parameters_btn = QPushButton("Generate parameters.csv")
    window.generate_parameters_btn.setObjectName("softButton")

    top_button_row.addWidget(window.generate_parameters_btn)
    top_button_row.addStretch(1)
    layout.addLayout(top_button_row)

    # ------------------------------------------------------------------
    # Mapping table
    # ------------------------------------------------------------------
    mapping_label = QLabel("Parameter Mappings")
    mapping_label.setObjectName("sectionTitle")
    layout.addWidget(mapping_label)

    # Hidden compatibility combo expected by file_ops_mixin
    window.timeseries_value_source_combo = QComboBox()
    window.timeseries_value_source_combo.setVisible(False)
    layout.addWidget(window.timeseries_value_source_combo)

    window.timeseries_mapping_table = QTableWidget(0, 5)
    window.timeseries_mapping_table.setObjectName("inputTable")
    window.timeseries_mapping_table.setHorizontalHeaderLabels(
        ["Parameter", "Source Column", "Unit", "Dataset Name", "Dataset ID"]
    )
    window.timeseries_mapping_table.setMinimumHeight(220)
    window.timeseries_mapping_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch
    )
    window.timeseries_mapping_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
    )
    window.timeseries_mapping_table.setSelectionMode(
        QTableWidget.SelectionMode.ExtendedSelection
    )

    layout.addWidget(window.timeseries_mapping_table)

    button_row = QHBoxLayout()
    button_row.setSpacing(10)

    window.add_mapping_btn = QPushButton("Add Mapping")
    window.add_mapping_btn.setObjectName("softButton")

    window.remove_mapping_btn = QPushButton("Remove Selected Mapping")
    window.remove_mapping_btn.setObjectName("softButton")

    button_row.addWidget(window.add_mapping_btn)
    button_row.addWidget(window.remove_mapping_btn)
    button_row.addStretch(1)
    layout.addLayout(button_row)

    mapping_note = QLabel(
        "Use 'Generate parameters.csv' to fetch Parameter and Unit information and populate the mapping table."
    )
    mapping_note.setObjectName("fileInfoLabel")
    mapping_note.setWordWrap(True)
    layout.addWidget(mapping_note)

    return group