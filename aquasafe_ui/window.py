from PyQt6.QtWidgets import QApplication, QMainWindow

from .constants import APP_UPDATE_URL, CURRENT_VERSION
from .editor_mixin import EditorMixin
from .file_ops_mixin import FileOpsMixin
from .setup_mixin import WindowSetupMixin

import pandas as pd


class GeospatialProcessingWindow(WindowSetupMixin, EditorMixin, FileOpsMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AQUASAFE {CURRENT_VERSION} - Generic Geospatial Processing Tool")

        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                min(int(available.width() * 0.88), 1500),
                min(int(available.height() * 0.90), 980),
            )
        else:
            self.resize(1450, 950)

        self.setMinimumSize(1000, 720)

        self.candidate_files = []
        self.original_data = None
        self.data = None
        self.is_geo = False
        self.input_file = None
        self.result = None
        self.latest_release_url = APP_UPDATE_URL
        self.editor_columns = []

        self.undo_stack = []
        self.redo_stack = []
        self._last_table_snapshot = pd.DataFrame()
        self._suspend_table_item_changed = False

        self._build_ui()
        self._apply_styles()
        self.scan_current_folder(initial=True)
        self.update_output_mode_ui()