#!/usr/bin/env python3
"""Regression checks for PGXP cracks, safe interpolation, and faithful defaults."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
frame_source = (ROOT / "src/mods/ape_frame_rate_plugin.cpp").read_text(encoding="utf-8")
guard = re.search(
    r"if\s*\(\s*index\s*>\s*1\s*\|\|(?P<conditions>[^)]*)\)\s*\{\s*replay\.invalidate\(\)",
    frame_source,
)
if not guard:
    raise SystemExit("Could not locate frame-smoothing invalidation guard.")
conditions = guard.group("conditions")
if not re.search(r"\bmode\s*!=\s*3\b", conditions):
    raise SystemExit("Frame smoothing must capture only phase 3 (active gameplay).")
finish = re.search(r"void\s+finish\s*\([^)]*\)\s*\{(?P<body>.*?)\n\}", frame_source, re.S)
if not finish or not re.search(r"psx_mod_read_byte\(\s*0x800F447C\s*\)\s*!=\s*3", finish.group("body")):
    raise SystemExit("Frame smoothing must re-check the gameplay phase before submitting an interpolated pass.")

config = (ROOT / "game.toml").read_text(encoding="utf-8")
if 'aspect_ratio = "4:3"' not in config:
    raise SystemExit("The stock 4:3 presentation default was lost.")
if "pgxp_mod_only = true" not in config:
    raise SystemExit("PGXP must be controlled by its single optional mod feature.")
if not re.search(r"(?m)^pgxp_tolerance\s*=\s*-1(?:\.0)?\s*$", config):
    raise SystemExit("The hook-flavor PGXP runtime must not clamp precise vertices back to integer pixels.")
if re.search(r"(?m)^pgxp_tolerance\s*=\s*0\.5\s*$", config):
    raise SystemExit("The stale 0.5 px tolerance clamp must not return.")
if not re.search(r"(?m)^pgxp_position_fallback\s*=\s*false\s*$", config):
    raise SystemExit("The high-coverage hook build must use dataflow-only precision.")
if not re.search(r"(?m)^pgxp_preserve_projection\s*=\s*true\s*$", config):
    raise SystemExit("The high-coverage hook build must preserve the exact GTE projection.")
if not re.search(r"(?m)^pgxp_depth_buffer\s*=\s*true\s*$", config):
    raise SystemExit("PGXP seam expansion requires the renderer depth buffer.")
if not re.search(r'(?m)^pgxp_seam\s*=\s*"wide"\s*$', config):
    raise SystemExit("Ape Escape must enable wide PGXP seam expansion above native resolution.")

expected_framework_pin = "4102438ab4c5aadf010878029d0324ef6382e521"
pins = (ROOT / "framework_pins.txt").read_text(encoding="utf-8").splitlines()
if f"psxrecomp-v4={expected_framework_pin}" not in pins:
    raise SystemExit("framework_pins.txt must name the PGXP depth/seam framework pin.")
framework = ROOT / "psxrecomp-v4"
if (framework / ".git").exists():
    checked_out_pin = subprocess.run(
        ["git", "-C", str(framework), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if checked_out_pin != expected_framework_pin:
        raise SystemExit(
            f"Framework checkout ({checked_out_pin}) disagrees with expected PGXP renderer pin ({expected_framework_pin})."
        )

manifest = (ROOT / "mods/preloaded/packages/psx.enhancement.pgxp/1.0.0/manifest.toml").read_text(encoding="utf-8")
if "default_enabled = false" not in manifest or 'default = "true"' not in manifest:
    raise SystemExit("PGXP must remain optional/off by default while CPU precision propagation is on when selected.")
option_blocks = re.findall(r"(?ms)^\[\[option\]\]\n.*?(?=^\[\[(?:option|plugin)\]\]|\Z)", manifest)
culling_blocks = [block for block in option_blocks if re.search(r'(?m)^id = "culling"$', block)]
if len(culling_blocks) != 1 or not re.search(r'(?m)^default = "true"$', culling_blocks[0]):
    raise SystemExit("Precise culling must be available and default on only when the optional PGXP mod is selected.")

ws_manifest = (ROOT / "mods/preloaded/packages/ape.enhancement.widescreen/1.0.0/manifest.toml").read_text(encoding="utf-8")
if "Experimental" not in ws_manifest or "default_enabled = false" not in ws_manifest:
    raise SystemExit("Widescreen must remain explicitly experimental and off by default.")
issues = (ROOT / "ISSUES.md").read_text(encoding="utf-8")
for title in ("Widescreen: distance (draw-distance) pop-in", "circus balls pop/cull"):
    if title not in issues:
        raise SystemExit(f"Known unverified audiovisual issue was removed: {title}")
print("AV guardrails passed: pinned PGXP depth/seam support is configured, precise culling is confined to the default-off PGXP mod, interpolation is gameplay-only, and Widescreen remains experimental/off by default.")
