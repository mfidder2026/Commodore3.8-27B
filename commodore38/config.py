"""Locations of external tools.

Resolution order per setting: environment variable, then ``toolchain.local.toml``
in the repo root, then an auto-detected default. Example toolchain.local.toml::

    vice_bin = "/Applications/vice-arm64-gtk3-3.9/bin"
    kickass_jar = "/Users/me/tools/KickAss/KickAss.jar"
    java = "/opt/homebrew/opt/openjdk/bin/java"
"""

from __future__ import annotations

import glob
import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _local_settings() -> dict:
    path = REPO_ROOT / "toolchain.local.toml"
    if path.is_file():
        with path.open("rb") as fh:
            return tomllib.load(fh)
    return {}


def _detect_vice_bin() -> str | None:
    found = shutil.which("x64sc")
    if found:
        return str(Path(found).parent)
    candidates = sorted(glob.glob("/Applications/vice-*/bin"), reverse=True)
    return candidates[0] if candidates else None


def _detect_java() -> str | None:
    for candidate in ("/opt/homebrew/opt/openjdk/bin/java", "/usr/local/opt/openjdk/bin/java"):
        if os.access(candidate, os.X_OK):
            return candidate
    # /usr/bin/java on macOS is a stub that fails without an installed JDK.
    return shutil.which("java")


@dataclass(frozen=True)
class Toolchain:
    external_dir: Path
    vice_bin: str | None
    java: str | None
    kickass_jar: str | None

    def vice(self, emulator: str) -> str | None:
        if not self.vice_bin:
            return None
        path = Path(self.vice_bin) / emulator
        return str(path) if path.exists() else None


def load_toolchain() -> Toolchain:
    local = _local_settings()

    def get(key: str, default=None):
        return os.environ.get("C38_" + key.upper()) or local.get(key) or default

    return Toolchain(
        external_dir=Path(get("external_dir", REPO_ROOT / "external")),
        vice_bin=get("vice_bin") or _detect_vice_bin(),
        java=get("java") or _detect_java(),
        kickass_jar=get("kickass_jar"),
    )
