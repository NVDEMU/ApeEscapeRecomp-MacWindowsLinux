#!/usr/bin/env python3
"""Regression tests for changelog section selection and release-note rendering."""
from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "render_release_notes.py"
SPEC = importlib.util.spec_from_file_location("render_release_notes", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("could not import release-note generator")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SAMPLE = """# Changelog

## [Unreleased]

### Added
- New nightly feature.

## [1.0.0] - 2026-10-17

### Added
- First version.

## [1.2.0] - 2026-12-01

### Fixed
- A release-specific fix.
"""


def main() -> int:
    if "New nightly feature" not in MODULE.extract_section(SAMPLE, "Unreleased"):
        raise SystemExit("Unreleased section selection failed")
    if "First version" not in MODULE.extract_section(SAMPLE, "1.0.0"):
        raise SystemExit("versioned changelog section selection failed")
    name, title = MODULE.section_for_ref("refs/heads/master", "v1.0.0")
    if name != "Unreleased" or "Nightly" not in title:
        raise SystemExit("master ref must select Unreleased notes")
    name, title = MODULE.section_for_ref("refs/tags/macos-v1.2.0", "v1.0.0")
    if name != "1.2.0" or "v1.2.0" not in title:
        raise SystemExit("tag ref must select the matching release section")
    notes = MODULE.render_notes(SAMPLE, "refs/tags/macos-v1.2.0", "v1.0.0")
    for token in ("A release-specific fix", "CHANGELOG.md", "retail PlayStation BIOS are not included"):
        if token not in notes:
            raise SystemExit(f"generated release notes missing: {token}")
    try:
        MODULE.extract_section(SAMPLE, "9.9.9")
    except ValueError:
        pass
    else:
        raise SystemExit("missing versioned section must fail rather than publish empty notes")
    print("Release-note generator: Unreleased/tag selection, footer, and missing-section guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
