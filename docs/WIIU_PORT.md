# Ape Escape Recompiled — Experimental Wii U port

This is an **experimental port branch**, isolated from the desktop release and
the Nintendo Switch experiment. It targets native Wii U homebrew using devkitPro
WUT and Wii U SDL2. It is not a claim that the game has already been validated
on real hardware.

## Build artifact

The GitHub Actions workflow on the `wiiu-port` branch attempts to compile the
actual generated Ape Escape game code and package it as an `.rpx`. The game
disc and retail BIOS are not bundled. Use a disc image sourced from your own
legally obtained copy.

## SD-card game-data layout

Put a matching CUE/BIN pair or a supported disc image in one of these locations:

```text
SD:/wiiu/apeescape/Ape Escape (USA).cue
SD:/wiiu/apeescape/Ape Escape (USA).bin
```

Alternative supported folders include:

```text
SD:/wiiu/apps/ApeEscapeRecomp/data/
SD:/wiiu/apps/ApeEscapeRecomp/roms/
```

The runtime patch tries these folders first, then shallow-scans the configured SD
root for names containing `Ape` or `SCUS_944` and validates candidate disc files.
For CUE/BIN, keep the CUE file's referenced track filename accurate. CHD may be
discovered by its filename; whether it can be opened on Wii U depends on the
pinned runtime's disc-image support and should be verified in testing.

## Running on Aroma

Aroma supports native RPX homebrew from SD. Copy the build's `.rpx` into a
homebrew location on the SD card and launch it from your usual Aroma workflow.
Keep the game files in `SD:/wiiu/apeescape/` to avoid relying on the application's
working directory.

The first milestone is to verify that the RPX launches, the runtime logs show a
valid disc was found, and the game reaches the title screen. Audio, controller
mapping, save paths, video output, performance, and full-stage playthrough still
need real-console testing.

## Testing through Cemu

Cemu supports launching an RPX directly using **File → Load** (or its RPX
launch option in the installed version). That is useful for iterating on
startup, renderer, input, and basic game loading without copying each test build
to the console.

Cemu's host filesystem is not automatically the Wii U's physical SD card. If
disc discovery does not find files by itself, create a host folder that mirrors
the SD layout and pass it as a Cemu virtual mount to `/vol/external01` using
Cemu's `--cos-mounts` option. Then place the disc under
`wiiu/apeescape/` within that host folder. Exact command-line behavior can vary
by Cemu version, so check its launch settings/help if that option is unavailable.

Cemu testing does **not** replace hardware testing: filesystem mapping,
timing, memory limits, SDL2 video/audio, controller behavior, and software
renderer performance may differ on the real Wii U.

## Current limitations

- The Wii U runtime patches are experimental and need CI and hardware validation.
- The game and BIOS are not bundled or fetched by this workflow.
- Dynamic overlay compilation, external BIOS-module builds, and external
  `xdelta`-based derived-disc mods are disabled on this target.
- Desktop-only soundtrack tooling and optional launcher integrations are not
  expected to be available on the first Wii U milestone.
