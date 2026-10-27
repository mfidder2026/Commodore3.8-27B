"""One interface over the skillset syntax checkers.

Every checker runs as a subprocess so its own printing and ``sys.exit`` calls
stay contained, and is normalized to a :class:`CheckResult` with the shared
exit-code convention: 0 = clean, 1 = errors found, 2 = checker could not run.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Toolchain, load_toolchain


@dataclass
class Issue:
    severity: str            # "ERROR" or "WARN"
    message: str
    line: int | None = None  # BASIC line number or source line, as the checker reports it
    code: str | None = None


@dataclass
class CheckResult:
    checker: str
    exit_code: int
    issues: list[Issue] = field(default_factory=list)
    raw_output: str = ""

    @property
    def errors(self) -> int:
        return sum(i.severity == "ERROR" for i in self.issues)

    @property
    def warnings(self) -> int:
        return sum(i.severity == "WARN" for i in self.issues)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict:
        return {
            "checker": self.checker,
            "exit_code": self.exit_code,
            "errors": self.errors,
            "warnings": self.warnings,
            "issues": [asdict(i) for i in self.issues],
        }


# language key -> (repo, script)
CHECKERS = {
    "c64-basic": ("c64_basic_ai_skillset", "c64_syntax_checker.py"),
    "c128-basic": ("c128_basic_ai_skillset", "c128_syntax_checker.py"),
    "c64-kickass": ("c64_kickass_ai_skillset", "c64_ka_syntax_checker.py"),
}

def _run(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=60,
    )


def _parse_json(proc: subprocess.CompletedProcess) -> list[Issue]:
    data = json.loads(proc.stdout)
    return [
        Issue(i["severity"], i["message"], i.get("line"), i.get("code"))
        for i in data["issues"]
    ]


def check_file(path: str | Path, language: str, toolchain: Toolchain | None = None) -> CheckResult:
    toolchain = toolchain or load_toolchain()
    if language not in CHECKERS:
        return CheckResult(language, 2, raw_output=f"no checker for language {language!r}")
    repo, script_name = CHECKERS[language]
    script = toolchain.external_dir / repo / script_name
    if not script.is_file():
        return CheckResult(language, 2, raw_output=f"checker not found: {script} (run scripts/fetch_external.sh)")

    try:
        proc = _run(script, [str(path), "--json"])
    except subprocess.TimeoutExpired:
        return CheckResult(language, 2, raw_output="checker timed out")
    raw = proc.stdout + proc.stderr

    if proc.returncode not in (0, 1):
        return CheckResult(language, 2, raw_output=raw)
    try:
        issues = _parse_json(proc)
    except (json.JSONDecodeError, KeyError) as exc:
        return CheckResult(language, 2, raw_output=f"unparseable checker output: {exc}\n{raw}")

    result = CheckResult(language, 0, issues, raw)
    if result.errors or proc.returncode == 1:
        result.exit_code = 1
    return result


def check_source(source: str, language: str, toolchain: Toolchain | None = None) -> CheckResult:
    suffix = ".asm" if language.endswith("kickass") else ".bas"
    with tempfile.TemporaryDirectory(prefix="c38-check-") as tmp:
        path = Path(tmp) / f"source{suffix}"
        path.write_text(source, encoding="utf-8")
        return check_file(path, language, toolchain)
