#!/usr/bin/env python3
"""Regression checks for PGXP seams, safe interpolation phases and stock AV defaults."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
frame_source = (ROOT / "src/mods/ape_frame_rate_plugin.cpp").read_text(encoding="utf-8")
guard = re.search(r"if\s*\(\s*index\s*>\s*1\s*\|\|(?P<conditions>[^)]*)\)\s*\{\s*replay\.invalidate\(\)", frame_source)
if not guard:
    raise SystemExit("Could not locate frame-smoothing invalidation guard.")
conditions = guard.group("conditions")
if not re.search(r"\bmode\s*!=\s*3\b", conditions):
    raise SystemExit("Frame smoothing must capture only phase 3 (active gameplay), not title/loading/transition frames.")
finish = re.search(r"void\s+finish\s*\([^)]*\)\s*\{(?P<body>.*?)\n\}", frame_source, re.S)
if not finish or not re.search(r"psx_mod_read_byte\(\s*0x800F447C\s*\)\s*!=\s*3", finish.group("body")):
    raise SystemExit("Frame smoothing must re-check the gameplay phase before submitting an interpolated pass.")
config = (ROOT / "game.toml").read_text(encoding="utf-8")
if 'aspect_ratio = "4:3"' not in config:
    raise SystemExit("The stock 4:3 presentation default was lost.")
if "pgxp_mod_only = true" not in config:
    raise SystemExit("PGXP must be controlled by its single mod feature, so the off state stays fully stock.")
if not re.search(r"(?m)^pgxp_tolerance\s*=\s*-1(?:\.0)?\s*$", config):
    raise SystemExit("The hook-flavor PGXP runtime must not clamp precise vertices back to integer pixels.")
if re.search(r"(?m)^pgxp_tolerance\s*=\s*0\.5\s*$", config):
    raise SystemExit("The stale 0.5 px tolerance clamp must not return.")
if not re.search(r"(?m)^pgxp_position_fallback\s*=\s*false\s*$", config):
    raise SystemExit("The high-coverage hook build must use dataflow-only precision, not the position fallback cache.")
if not re.search(r"(?m)^pgxp_preserve_projection\s*=\s*true\s*$", config):
    raise SystemExit("The high-coverage hook build must preserve the exact GTE projection.")
manifest = (ROOT / "mods/preloaded/packages/psx.enhancement.pgxp/1.0.0/manifest.toml").read_text(encoding="utf-8")
if "default_enabled = false" not in manifest or 'default = "true"' not in manifest:
    raise SystemExit("PGXP must remain optional/off by default while CPU precision propagation is on when selected.")
ws_manifest = (ROOT / "mods/preloaded/packages/ape.enhancement.widescreen/1.0.0/manifest.toml").read_text(encoding="utf-8")
if "Experimental" not in ws_manifest or "default_enabled = false" not in ws_manifest:
    raise SystemExit("Widescreen must remain explicitly experimental and off by default until its visual artifacts are resolved.")
issues = (ROOT / "ISSUES.md").read_text(encoding="utf-8")
for title in ("Widescreen: distance (draw-distance) pop-in", "circus balls pop/cull"):
    if title not in issues:
        raise SystemExit(f"Known unverified audiovisual issue was removed: {title}")
print("AV guardrails passed: hook-build PGXP uses dataflow-only exact projection without a tolerance clamp, interpolation is gameplay-only, stock 4:3 remains available, and Widescreen remains experimental/off by default.")
