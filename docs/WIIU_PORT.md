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

Cemu can be used for **optional desktop-side smoke testing** of the RPX, but it
is not required to build the project and it does not replace testing on a real
Wii U. Whether you can run Cemu on a particular computer depends on that
computer's operating system, graphics support, installed software, and the
permissions or policies set by its owner or administrator. This documentation
does not imply that Cemu is available or permitted on school-managed computers.

Cemu's launch options include selecting a game with `-g` / `--game` and
mounting a host directory into the emulated Wii U filesystem with
`--cos-mounts`. See the
[Cemu launch-options implementation](https://github.com/cemu-project/Cemu/blob/main/src/config/LaunchSettings.cpp)
for current details; options can change between Cemu versions.

Create a host folder that mirrors the SD-card layout and place your own dumped
game image here:

```text
CemuWiiUSD/
└── wiiu/
    └── apeescape/
        ├── Ape Escape (USA).cue
        └── Ape Escape (USA).bin
```

On Windows, for example, launch Cemu with:

```powershell
Cemu.exe -g "C:\\path\\to\\ApeEscapeRecomp.rpx" --cos-mounts "C:\\CemuWiiUSD:/vol/external01/" --forward-console-logging
```

On macOS, the same idea from Terminal is:

```bash
"/Applications/Cemu.app/Contents/MacOS/Cemu" \
  -g "$PWD/ApeEscapeRecomp.rpx" \
  --cos-mounts "$HOME/CemuWiiUSD:/vol/external01/" \
  --forward-console-logging
```

The SD auto-discovery patch checks `/vol/external01/wiiu/apeescape/` so this
mount mirrors the console layout. If Cemu is installed elsewhere, adjust the
executable path. You can also use the GUI's RPX load option for basic launch
testing, but the explicit mount is useful for checking SD-based disc discovery.

CI-based Cemu tests run in a separate GitHub Actions environment. A CI result
does not establish that Cemu will run on your own computer, and a grey or blank
Cemu window is not proof that the game rendered correctly.

Cemu testing does **not** replace hardware testing: filesystem mapping, timing,
memory limits, SDL2 video/audio, controller behavior, and software renderer
performance may differ on the real Wii U.

## Current limitations

- The Wii U runtime patches are experimental and need CI and hardware validation.
- The game and BIOS are not bundled or fetched by this workflow.
- Dynamic overlay compilation, external BIOS-module builds, and external
  `xdelta`-based derived-disc mods are disabled on this target.
- Desktop-only soundtrack tooling and optional launcher integrations are not
  expected to be available on the first Wii U milestone.
