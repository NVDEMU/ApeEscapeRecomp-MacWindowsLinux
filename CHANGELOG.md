# Changelog


All notable changes to Ape Escape Recompiled — Enhanced Edition are recorded here. Nightly release notes are generated from the **Unreleased** section; tagged releases use the section matching their version.

## [Unreleased]

### Fixed
- Fixed the data-folder button's conflicting ImGui ID and made it open the full user home folder; folder buttons now use unique IDs.

### Fixed
- Fixed the duplicate Open Data Folder ImGui ID; Quick Tools now opens the user's home folder separately from the app-specific data folder, with unique IDs for all folder buttons.

### Fixed
- Fixed accessibility settings being skipped because the helper declaration marker collided with the UI insertion check; accessibility controls now have a dedicated visible launcher page.

### Added
- Added a C/C++ lint workflow that checks formatting on changed lines and excludes generated game translations and third-party submodules.
- Fixed the OST volume slider to show a smooth 0–100% range, and added boot-time shuffle autoplay from locally cached songs only; playback advances to another random cached track when a song ends without downloading during startup. Music files remain in per-user data and are not bundled in releases.
- Mod Manager filters for all, enabled, disabled, experimental, and needs-attention features, plus confirmed Original Experience, Visual Enhancements, and Challenge Run presets.
- Confirmation dialogs for Enable All and Disable All to avoid accidentally changing the whole mod selection.
- Setup Doctor checks for the selected disc, disc identity, custom BIOS path, app-data write access, and save-backup availability, with a copyable diagnostic report and shortcuts to repair actions.
- Controller Test Lab with live gamepad button, stick, and trigger indicators plus an optional rumble test.
- Save Protection Center backup history, selected-snapshot restore, folder export, and configurable retention from 5 to 50 snapshots.
- Update & Release Center with installed build metadata, an in-app updater entry point, Nightly release access, and a changelog link.
- Automated release notes generated from this changelog for Nightly and version-tagged releases.

### Changed
- Save restoration now delays retention pruning until after the chosen backup is applied, preventing a selected old snapshot from being pruned before restore completes.
- The Mods page follows the active filter when selecting feature/package details and confirms bulk toggles before applying them.
- Removed the duplicate Nightly updater button from Update & Release Center; the single dedicated updater control prevents conflicting Dear ImGui IDs and accidental double-starts.


### Fixed
- Moved the OST player entry into Settings → Audio and opened the full player in a separate resizable window, avoiding clipping below the Settings layout.
- Closed the Nightly manifest generator’s missing Python heredoc terminator, which prevented the release-publishing shell step from parsing correctly.
- Corrected the pinned launcher’s malformed SDL3 preprocessor guard, which had stopped Windows, macOS, and Linux builds before release packaging.
- Added independent GitHub Actions workflow validation and security auditing with actionlint and zizmor; zizmor findings are advisory while existing workflows are reviewed.

## [1.0.0] - 2026-10-17

### Added
- Established the 1.0.0 version line using `packaging/release/VERSION` as the canonical app-version source for desktop and Android builds.
- Added the project-branded launcher, accessibility preferences, manual Monkepedia checklist, Stage Knowledge Cards, Daily Challenge, and Save Protection Center.
- Added default-off optional enhancements and gameplay challenges, including widescreen, PGXP, interpolated rendering, gameplay assists, challenge rules, and quality-of-life tools.
- Added Windows/macOS Nightly update and rollback support, with package checksum verification in the updater.

### Notes
- The base game disc and retail PlayStation BIOS are not included in releases. Users must provide their own game image.
- Linux AppImage updates are installed manually; macOS builds are ad-hoc signed and are not notarized.
