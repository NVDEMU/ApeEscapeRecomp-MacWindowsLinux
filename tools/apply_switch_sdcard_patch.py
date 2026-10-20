#!/usr/bin/env python3
"""Apply the experimental Switch/Ryujinx disc auto-discovery patch to psxrecomp.

This is intentionally scoped to the experimental Switch configure path. It does
not change normal desktop builds. The patch is idempotent and fails closed when
its upstream insertion point changes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

MARKER = '    // Go straight to the native picker. A preliminary modal was redundant,'
PATCH_MARKER = '    // Experimental Switch/Ryujinx SD-card fallback (project patch).'

PATCH = '''#if defined(PSX_RYUJINX_SDCARD_SCAN)\n    // Experimental Switch/Ryujinx SD-card fallback (project patch).
    // The emulator's host-side /sdcard directory is only visible when the
    // runtime actually exposes it; on a Switch-like guest, sdmc:/ is the
    // virtual SD mount. Check both forms, plus the app-relative data folder.
    // This runs only when the project enables APE_SWITCH_PORT at configure time.
    {
        namespace ape_fs = std::filesystem;
        const ape_fs::path exe_dir = exe_dir_from_argv(argv0);
        const std::vector<ape_fs::path> roots = {
            exe_dir / "data",
            exe_dir / "sdcard" / "switch" / "ApeEscapeRecomp" / "data",
            // Ryujinx's configured virtual SD root is exposed as sdmc:/ to
            // guest homebrew; some test/runtime wrappers also expose a host-like
            // /sdcard tree. Check the title folder and the whole SD root.
            ape_fs::path("/sdcard/switch/ApeEscapeRecomp/data"),
            ape_fs::path("/sdcard/switch/ApeEscapeRecomp"),
            ape_fs::path("/sdcard/switch"),
            ape_fs::path("/sdcard"),
            ape_fs::path("sdmc:/switch/ApeEscapeRecomp/data"),
            ape_fs::path("/switch/ApeEscapeRecomp/data"),
            ape_fs::path("switch/ApeEscapeRecomp/data")
        };
        const char* const names[] = {
            "Ape Escape (USA).cue", "Ape Escape (USA).bin",
            "Ape Escape.cue", "Ape Escape.bin",
            "SCUS_944.23.cue", "SCUS_944.23.bin"
        };
        std::error_code ape_ec;
        for (const auto& root : roots) {
            for (const char* name : names) {
                const ape_fs::path candidate = root / name;
                ape_ec.clear();
                if (!ape_fs::exists(candidate, ape_ec) || ape_fs::is_directory(candidate, ape_ec))
                    continue;
                const ape_fs::path normalized = normalize_disc_path_for_launch(candidate);
                ape_ec.clear();
                if (ape_fs::exists(normalized, ape_ec) &&
                    validate_disc_for_launch(normalized, game_id)) {
                    std::fprintf(stderr, "psxrecomp: found game disc via SD-card fallback: %s\\n",
                                 normalized.string().c_str());
                    write_cached_path(argv0, "disc.cfg", normalized);
                    return normalized;
                }
            }
        }

        // Accommodate user-renamed images in the Ryujinx virtual SD card.
        // Search only a shallow, bounded depth so a large SD card cannot stall
        // startup. Duplicate roots are harmless; inaccessible paths are ignored.
        for (const auto& root : roots) {
            ape_ec.clear();
            if (!ape_fs::is_directory(root, ape_ec)) continue;
            ape_fs::recursive_directory_iterator it(
                root, ape_fs::directory_options::skip_permission_denied, ape_ec), end;
            while (!ape_ec && it != end) {
                if (it.depth() >= 4 && it->is_directory(ape_ec))
                    it.disable_recursion_pending();
                if (!it->is_directory(ape_ec)) {
                    const std::string ext = it->path().extension().string();
                    std::string lower_ext = ext;
                    for (char& ch : lower_ext)
                        ch = (char)std::tolower((unsigned char)ch);
                    if (lower_ext == ".cue" || lower_ext == ".bin" ||
                        lower_ext == ".chd" || lower_ext == ".img" ||
                        lower_ext == ".iso" || lower_ext == ".car") {
                        std::string filename = it->path().filename().string();
                        std::string lower_name = filename;
                        for (char& ch : lower_name)
                            ch = (char)std::tolower((unsigned char)ch);
                        if (lower_name.find("ape") != std::string::npos ||
                            lower_name.find("scus_944") != std::string::npos) {
                            const ape_fs::path normalized =
                                normalize_disc_path_for_launch(it->path());
                            ape_ec.clear();
                            if (ape_fs::exists(normalized, ape_ec) &&
                                validate_disc_for_launch(normalized, game_id)) {
                                std::fprintf(stderr,
                                    "psxrecomp: found game disc via SD-card scan: %s\\n",
                                    normalized.string().c_str());
                                write_cached_path(argv0, "disc.cfg", normalized);
                                return normalized;
                            }
                        }
                    }
                }
                        it.increment(ape_ec);
            }
        }
    }
#endif

'''
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-root", required=True, type=Path)
    args = parser.parse_args()
    source = args.framework_root / "runtime" / "src" / "main.cpp"
    if not source.is_file():
        print(f"Switch SD-card patch: framework source not found: {source}", file=sys.stderr)
        return 2
    text = source.read_text(encoding="utf-8-sig")
    if PATCH_MARKER in text:
        print("Switch SD-card patch already applied")
        return 0
    if text.count(MARKER) != 1:
        print("Switch SD-card patch: expected exactly one disc-picker marker; refusing to patch",
              file=sys.stderr)
        return 3
    text = text.replace(MARKER, PATCH + MARKER, 1)
    source.write_text(text, encoding="utf-8", newline="\n")
    print("Applied Switch/Ryujinx SD-card disc discovery patch")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
