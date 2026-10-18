# Changelog

- Added a Settings-based OST player with Archive.org track search, on-demand downloads, play/pause, next/previous, seeking, and saved volume. Music files remain in per-user data and are not bundled in releases.

All notable changes to Ape Escape Recompiled — Enhanced Edition are recorded here. Nightly release notes are generated from the **Unreleased** section; tagged releases use the section matching their version.

## [Unreleased]

### Added
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

## [1.0.0] - 2026-10-17

### Added
- Established the 1.0.0 version line using `packaging/release/VERSION` as the canonical app-version source for desktop and Android builds.
- Added the project-branded launcher, accessibility preferences, manual Monkepedia checklist, Stage Knowledge Cards, Daily Challenge, and Save Protection Center.
- Added default-off optional enhancements and gameplay challenges, including widescreen, PGXP, interpolated rendering, gameplay assists, challenge rules, and quality-of-life tools.
- Added Windows/macOS Nightly update and rollback support, with package checksum verification in the updater.

### Notes
- The base game disc and retail PlayStation BIOS are not included in releases. Users must provide their own game image.
- Linux AppImage updates are installed manually; macOS builds are ad-hoc signed and are not notarized.
