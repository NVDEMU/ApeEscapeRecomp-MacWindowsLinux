#!/usr/bin/env python3
"""Static integration checks for project-owned launcher features."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
patch = (ROOT / "tools/apply_recomp_ui_update_patch.py").read_text(encoding="utf-8")
helper = (ROOT / "tools/launcher_extra_views.inc").read_text(encoding="utf-8")
guide = (ROOT / "docs/MOD_DEVELOPER_TOOLKIT.md").read_text(encoding="utf-8")
template = (ROOT / "templates/mod-plugin/example_plugin.c").read_text(encoding="utf-8")

required_views = (
    "LNG_VIEW_DAILY_CHALLENGE",
    "LNG_VIEW_STAGE_GUIDE",
    "LNG_VIEW_MOD_TOOLKIT",
    "LNG_VIEW_ACCESSIBILITY",
    "ape_escape_draw_daily_challenge",
    "ape_escape_draw_stage_guide",
    "ape_escape_draw_mod_toolkit",
    "ape_escape_draw_save_protection_center",
    "ape_escape_draw_ost_player_settings",
    "APE_ESCAPE_EXTRA_LAUNCHER_BODY",
)
for token in required_views:
    if token not in patch:
        raise SystemExit(f"launcher patch is missing integration marker: {token}")
if "AUDIO_SETTINGS_ANCHOR" not in patch or "OST_SETTINGS_ENTRY_MARKER" not in patch:
    raise SystemExit("OST player is not wired into the Audio settings card")
# Accessibility visibility is an end-to-end route, not merely a declared helper.
for token in (
    'ACCESSIBILITY_VIEW_MARKER = "APE_ESCAPE_ACCESSIBILITY_VIEW"',
    'ACCESSIBILITY_NAV_MARKER = "APE_ESCAPE_ACCESSIBILITY_NAV"',
    'ACCESSIBILITY_BODY_MARKER = "APE_ESCAPE_ACCESSIBILITY_BODY"',
    'launcher_model_set_view(m, LNG_VIEW_ACCESSIBILITY)',
    'case LNG_VIEW_ACCESSIBILITY:',
    'ape_escape_draw_accessibility_settings(th); break;',
):
    if token not in patch:
        raise SystemExit(f"Accessibility page wiring is missing: {token}")
if "ACCESSIBILITY_FUNCTION_MARKER not in launcher_text" not in patch:
    raise SystemExit("Accessibility helper definition must be checked independently from page wiring")
if "if ACCESSIBILITY_NAV_MARKER not in launcher_text:" not in patch:
    raise SystemExit("Accessibility navigation must use a distinct call-site marker")
if 'const int count = 6 + (m->mods ? 1 : 0) +' not in patch:
    raise SystemExit("Navigation sizing does not account for the Accessibility button")
if "LEGACY_ACCESSIBILITY_CALL in launcher_text" not in patch:
    raise SystemExit("A clipped legacy Settings-bottom accessibility entry is not cleaned up")
ost_start = helper.index("static void ape_escape_draw_ost_player_settings")
ost_end = helper.index(chr(10) + "#else" + chr(10) + "static void ape_escape_draw_ost_player_settings", ost_start)
ost_settings = helper[ost_start:ost_end]
if 'ImGui::Button("Open OST Player"' not in ost_settings or 'ImGui::Button("Close OST Player"' not in ost_settings:
    raise SystemExit("OST player needs visible inline open/close controls in Audio settings")
if "ape_escape_ost_draw(th);" not in ost_settings:
    raise SystemExit("Open OST Player must draw the player inline in the same Audio settings function")
if 'ImGui::Begin("Ape Escape OST Player"' in helper:
    raise SystemExit("OST player must not use the previous detached ImGui window")
if 'ImGui::SliderFloat("OST volume",&volume_percent,0.0f,100.0f,"%.0f%%")' not in helper:
    raise SystemExit("OST volume slider must display a full 0–100 percent range")
if "ape_escape_audio_set_volume(volume_percent/100.0f)" not in helper:
    raise SystemExit("OST percent slider value must be normalized before passing it to the audio backend")
if "OST_RANDOM_INCLUDE_MARKER" not in patch or "OST_BOOT_AUTOPLAY_MARKER" not in patch:
    raise SystemExit("OST random autoplay standard headers or frame-loop startup hook are missing")
autoplay_block = helper[helper.index("static void ape_escape_ost_update_autoplay"):helper.index("static void ape_escape_ost_draw")]
if "ape_escape_ost_refresh()" in autoplay_block or "ape_escape_ost_download(" in autoplay_block:
    raise SystemExit("Boot shuffle autoplay must not initiate network requests or downloads")
if "ape_escape_ost_play_random_cached(-1)" not in autoplay_block or "s_ape_ost_shuffle_autoplay" not in autoplay_block:
    raise SystemExit("OST boot autoplay must select a random cached song and shuffle onward")
if "EXTRA_HELPERS_PATH = Path(\"tools/launcher_extra_views.inc\")" not in patch:
    raise SystemExit("launcher patch does not load the project-owned feature source")

for token in (
    "ape_escape_draw_save_protection_center(m, th, quick_button_w, quick_gap);",
    "ape_escape_draw_setup_doctor(m, th);",
    "ape_escape_draw_controller_test_lab(th);",
    "ape_escape_draw_update_release_center(th);",
):
    if token not in patch:
        raise SystemExit(f"Quick Tools is missing launcher integration: {token}")
if patch.count("const auto safety_snapshot = ape_escape_create_save_backup();") != 2:
    raise SystemExit("updater and rollback must each create a safety snapshot before launch")
button_start = patch.index("BUTTON = r'''")
button_end = patch.index("'''", button_start + len("BUTTON = r'''"))
updater_button_source = patch[button_start:button_end]
updater_button_count = updater_button_source.count('ImGui::Button("Check for Nightly Updates"') + helper.count('ImGui::Button("Check for Nightly Updates"')
if updater_button_count != 1:
    raise SystemExit(f"Expected one visible Nightly updater button to avoid duplicate ImGui IDs, found {updater_button_count}")
if 'ImGui::Button("Open User Folder##quick_tools"' not in patch:
    raise SystemExit("Quick Tools must expose a uniquely identified Open User Folder button")
if "ape_escape_open_folder(ape_escape_user_home_directory());" not in patch:
    raise SystemExit("Open User Folder must open the user's home directory")
if 'ImGui::Button("Open User Folder##setup_doctor"' not in helper:
    raise SystemExit("Setup Doctor must expose a uniquely identified Open User Folder button")
if "ape_escape_open_folder(ape_escape_user_home_directory());" not in helper:
    raise SystemExit("Setup Doctor's Open User Folder must open the full user home directory")
for button in (
    'ImGui::Button("Open User Folder##quick_tools"',
    'ImGui::Button("Open Save Folder##quick_tools"',
    'ImGui::Button("Open Disc Folder##quick_tools"',
    'ImGui::Button("Open User Folder##setup_doctor"',
):
    if patch.count(button) + helper.count(button) != 1:
        raise SystemExit(f"Folder button must have one unique ImGui ID: {button}")
if "ape_escape_open_folder(ape_escape_data_directory());" in helper:
    raise SystemExit("Setup Doctor folder button should open the full user folder, not only app-specific data")

if 'ImGui::Button("Open Data Folder"' in patch or 'ImGui::Button("Open Data Folder"' in helper:
    raise SystemExit("Duplicate plain Open Data Folder ImGui IDs remain")
if "static std::filesystem::path ape_escape_user_home_directory()" not in patch:
    raise SystemExit("User home directory resolver is missing")

for token in (
    "ape_escape_create_save_backup",
    "ape_escape_restore_save_backup",
    "BACKUP_INFO.txt",
    "ape_escape_latest_save_backup",
    "ape_escape_prune_save_backups",
    "Create Safety Backup and Restore",
    "ape_escape_list_save_backups",
    "ape_escape_export_save_backup",
    "s_ape_save_backup_retention",
    "ape_escape_draw_setup_doctor",
    "ape_escape_draw_controller_test_lab",
    "ape_escape_draw_update_release_center",
    "ape_escape_draw_mod_manager_overhaul",
    "static int s_ape_mod_filter = 0;",
    "static void mod_note_error(LauncherModel* m);",
    "ImGui::ColorConvertFloat4ToU32(col(th.border))",
    "SDL_RumbleGamepad(gamepad",
    "SDL_GAMEPAD_BUTTON_DPAD_RIGHT",
    "APE_ESCAPE_NEW_FEATURES_HELPER",
    "APE_ESCAPE_WINDOWS_PATH_SEPARATOR_FIX",
    "static_cast<char>(std::filesystem::path::preferred_separator)",
    "APE_ESCAPE_OST_PLAYER",
    "ape_escape_audio_play",
    "ape_escape_ost_download",
    "archive.org/details/ape-escape-1999-ost",
    "SDL_CreateProcess",
    "ape_escape_audio_seek",
    "ost-player",
    "ape_escape_ost_update_autoplay",
    "ape_escape_ost_play_random_cached",
    "ape_escape_ost_cached_track_indices",
    "s_ape_ost_boot_autoplay_checked",
    "s_ape_ost_shuffle_autoplay",
    "std::shuffle",
    "ape_escape_audio_duration",
    "ape_escape_audio_position",
):
    if token not in helper:
        raise SystemExit(f"launcher helper is missing: {token}")
restore = helper[helper.index("static bool ape_escape_restore_save_backup"):helper.index("/* SAVE PROTECTION CENTER")]
if restore.index("ape_escape_create_save_backup(false)") > restore.index("ape_escape_copy_regular_tree("):
    raise SystemExit("restore must create a pre-restore safety backup before copying snapshot files")
if "ape_escape_prune_save_backups(s_ape_save_backup_retention)" not in restore:
    raise SystemExit("restore must prune backups only after the selected snapshot has been copied")
if "skip_save_protection" not in helper:
    raise SystemExit("backup creation does not exclude its own backup directory")
if "std::max(5, std::min(50, value))" not in helper or "s_ape_save_backup_retention" not in helper:
    raise SystemExit("backup history does not expose a bounded configurable retention limit")
if "files not present in the snapshot are not deleted" not in helper:
    raise SystemExit("save restore safety behavior is not described")

for token in (
    "ape_escape_today_challenge",
    "ape_escape_daily_next",
    "ape_escape_save_daily_history",
    "ape_escape_daily_challenges.tsv",
    "Enable matching Challenge Pack features",
    "no scores are uploaded",
):
    # The stored history helper is intentionally local-only and uses a date-derived seed.
    if token not in helper:
        raise SystemExit(f"Daily Challenge implementation is missing: {token}")
if "*state ^= *state << 13u" not in helper or "*state ^= *state >> 17u" not in helper or "*state ^= *state << 5u" not in helper:
    raise SystemExit("daily challenge generator is missing its deterministic xorshift steps")

stage_ids = {int(value) for value in re.findall(r"case (\d+): return \"", helper)}
expected_stage_ids = {0, 1, 2, 10, 11, 12, 20, 21, 22, 30, 31, 32, 40, 41, 42, 50, 51, 52, 60}
if stage_ids != expected_stage_ids:
    raise SystemExit(f"Stage Guide tips do not cover the expected roster IDs: {stage_ids!r}")
if "source_url" not in patch or "f[6]" not in patch:
    raise SystemExit("Stage Guide cannot access the catalogue's source-page URLs")

for token in ("PSX_MOD_CONSTRUCTOR", "psx_mod_game_started", "psx_mod_read_half", "psx_mod_register_vblank_plugin"):
    if token not in template:
        raise SystemExit(f"read-only plugin template is missing API usage: {token}")
if "psx_mod_write" in template:
    raise SystemExit("minimal plugin example must remain read-only")
for token in ("Save Protection Center", "Daily Challenge", "Stage Guide", "Mod Developer Toolkit"):
    if token not in guide:
        raise SystemExit(f"developer guide missing integration context: {token}")

for filename in ("tools/package_macos.sh", "tools/package_release.ps1", "tools/package_appimage.sh"):
    package = (ROOT / filename).read_text(encoding="utf-8")
    if "MOD_DEVELOPER_TOOLKIT.md" not in package or "example_plugin.c" not in package:
        raise SystemExit(f"{filename} does not ship the mod developer guide and template")

for token in (
    "APE_ESCAPE_MOD_MANAGER_DECLS",
    "APE_ESCAPE_MOD_FEATURE_FILTER",
    "APE_ESCAPE_MOD_PACKAGE_FILTER",
    "APE_ESCAPE_MOD_MANAGER_TOOLS",
    "APE_ESCAPE_CONFIRM_BULK_MOD_ACTIONS",
):
    if token not in patch:
        raise SystemExit(f"Mod Manager patch is missing integration marker: {token}")

print("Launcher feature integration, visible Accessibility page, OST player, mod manager controls, save protection, daily challenge, stage guide, and plugin toolkit checks passed.")
