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
if not finish or "psx_mod_read_byte(0x800F447C)!=3" not in finish.group("body"):
    raise SystemExit("Frame smoothing must re-check the gameplay phase before submitting an interpolated pass.")
config = (ROOT / "game.toml").read_text(encoding="utf-8")
if 'aspect_ratio = "4:3"' not in config:
    raise SystemExit("The stock 4:3 presentation default was lost.")
if "pgxp_tolerance = 0.5" not in config:
    raise SystemExit("Ape Escape's PGXP seam clamp must stay at the framework-validated 0.5 px.")
if "pgxp_cpu_mode = true" not in config:
    raise SystemExit("Ape Escape CPU-mode PGXP propagation must stay enabled for terrain-grid vertices.")
issues = (ROOT / "ISSUES.md").read_text(encoding="utf-8")
for title in ("Widescreen: distance (draw-distance) pop-in", "circus balls pop/cull"):
    if title not in issues:
        raise SystemExit(f"Known unverified audiovisual issue was removed: {title}")
print("AV guardrails passed: PGXP seam clamp and CPU propagation are set, interpolation is gameplay-only, stock 4:3 remains available, and known widescreen defects remain documented.")
