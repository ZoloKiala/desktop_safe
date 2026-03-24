import sys
from pathlib import Path

CURRENT_VERSION = "1.0.3"
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
        base_path = Path(__file__).resolve().parent.parent
    return base_path / relative_path


APP_LOGO_PATH = resource_path("assets/aquasafe.png")