#!/usr/bin/env python3
"""Render Nightly and versioned GitHub release notes from CHANGELOG.md."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\](?:\s+-\s+.*)?\s*$")


def extract_section(changelog: str, wanted: str) -> str:
    lines = changelog.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            starts.append((index, match.group("name").strip()))
    for position, (line_index, name) in enumerate(starts):
        if name.casefold() != wanted.casefold():
            continue
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        section = "\n".join(lines[line_index + 1:end]).strip()
        if not section:
            raise ValueError(f"Changelog section [{wanted}] is empty")
        return section
    raise ValueError(f"Changelog section [{wanted}] was not found")


def section_for_ref(ref: str, current_version: str) -> tuple[str, str]:
    normalized_version = current_version.strip().lstrip("vV")
    if ref in ("master", "refs/heads/master") or ref.startswith("refs/heads/"):
        return "Unreleased", f"Nightly — v{normalized_version}"
    if ref.startswith("refs/tags/"):
        tag = ref.removeprefix("refs/tags/")
        version = tag.removeprefix("macos-").lstrip("vV")
        if not version:
            raise ValueError(f"Could not derive a version from tag {tag!r}")
        return version, f"Ape Escape Recompiled — v{version}"
    return "Unreleased", f"Development build — v{normalized_version}"


def render_notes(changelog: str, ref: str, current_version: str) -> str:
    section_name, title = section_for_ref(ref, current_version)
    section = extract_section(changelog, section_name)
    footer = (
        "---\n\n"
        "**Package notes:** Windows x64, macOS arm64/Intel packages, and Linux x86_64 "
        "AppImage are attached when their build jobs succeed. macOS packages are ad-hoc "
        "signed and are not notarized. Linux AppImage updates are manual.\n\n"
        "The original game disc image and retail PlayStation BIOS are not included. "
        "The packaged OpenBIOS is MIT-licensed.\n\n"
        "See the full [CHANGELOG.md](https://github.com/NVDEMU/ApeEscapeRecomp-MacWindowsLinux/blob/master/CHANGELOG.md)."
    )
    return f"# {title}\n\n{section}\n\n{footer}\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", required=True, help="Git ref, such as refs/heads/master or refs/tags/macos-v1.1.0")
    parser.add_argument("--version-file", type=Path, required=True)
    parser.add_argument("--changelog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        changelog = args.changelog.read_text(encoding="utf-8")
        notes = render_notes(changelog, args.ref, version)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(notes, encoding="utf-8")
    print(f"Rendered {args.output} from CHANGELOG.md for {args.ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
