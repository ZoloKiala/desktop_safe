from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os

try:
    import tomllib as tomli  # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli  # Python <3.11
    except ModuleNotFoundError:
        tomli = None


@dataclass(frozen=True)
class Credentials:
    uri: str
    token: str | None = None


class CredentialsError(RuntimeError):
    pass


def get_credentials(profile: str, config_path: str | Path | None = None) -> Credentials:
    profile_key = _canon(profile)

    env_creds = _from_env(profile_key)
    if env_creds is not None:
        return env_creds

    if config_path is None:
        candidates = [
            Path("secrets.toml"),
            Path("secrets.json"),
            Path.home() / ".config" / "myapp" / "secrets.toml",
            Path.home() / ".config" / "myapp" / "secrets.json",
        ]
    else:
        candidates = [Path(config_path)]

    for p in candidates:
        if p.exists():
            file_creds = _from_file(p, profile)
            if file_creds is not None:
                return file_creds

    raise CredentialsError(
        f"Missing credentials for profile={profile!r}. "
        f"Set env vars or add to secrets.toml/secrets.json."
    )


def _canon(profile: str) -> str:
    return profile.strip().upper().replace("-", "_").replace(" ", "_")


def _from_env(profile_key: str) -> Credentials | None:
    prefix = f"MYAPP_{profile_key}_"
    uri = os.getenv(prefix + "URI")
    token = os.getenv(prefix + "TOKEN")

    if uri:
        return Credentials(uri=uri, token=token)

    return None


def _from_file(path: Path, profile: str) -> Credentials | None:
    data = _load_secrets_file(path)

    if not isinstance(data, dict):
        return None

    section = _get_section_case_insensitive(data, profile)
    if not isinstance(section, dict):
        return None

    uri = section.get("uri") or section.get("URI")
    token = section.get("token") or section.get("TOKEN")

    if not uri:
        raise CredentialsError(
            f"Profile {profile!r} found in {path}, but 'uri' is missing."
        )

    return Credentials(uri=str(uri), token=str(token) if token is not None else None)


def _get_section_case_insensitive(data: dict, profile: str) -> dict | None:
    target_raw = profile.strip()
    target_canon = _canon(profile)

    for key, value in data.items():
        if not isinstance(key, str):
            continue
        if key == target_raw or _canon(key) == target_canon:
            return value

    return None


def _load_secrets_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    raw = path.read_bytes()

    if suffix == ".json":
        return json.loads(raw.decode("utf-8"))

    if suffix == ".toml":
        if tomli is None:
            raise CredentialsError(
                "TOML support is unavailable. Use Python 3.11+ or install tomli."
            )
        return tomli.loads(raw.decode("utf-8"))

    raise CredentialsError(f"Unsupported secrets file type: {path}")