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
manifest = (ROOT / "mods/preloaded/packages/psx.enhancement.pgxp/1.0.0/manifest.toml").read_text(encoding="utf-8")
if "default_enabled = false" not in manifest or 'default = "true"' not in manifest:
    raise SystemExit("PGXP must remain optional/off by default while CPU precision propagation is on when selected.")
issues = (ROOT / "ISSUES.md").read_text(encoding="utf-8")
for title in ("Widescreen: distance (draw-distance) pop-in", "circus balls pop/cull"):
    if title not in issues:
        raise SystemExit(f"Known unverified audiovisual issue was removed: {title}")
print("AV guardrails passed: PGXP uses the unclamped hook path behind one default-off mod switch, interpolation is gameplay-only, stock 4:3 remains available, and known widescreen defects remain documented.")
