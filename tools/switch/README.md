# Experimental Nintendo Switch testing

This folder documents the **native homebrew port attempt**. It is not a claim that a working Switch build exists yet.

## SD-card layout

Copy the built NRO to:

```
sdmc:/
└── switch/
    └── ApeEscapeRecomp/
        ├── ApeEscapeRecomp.nro
        └── data/
            ├── Ape Escape.cue
            └── Ape Escape.bin
```

The CUE must reference the matching BIN track using the correct filename. Keep all tracks referenced by a multi-track CUE beside it. Do not put the CUE/BIN inside the Nintendo folder. `hbmenu.nro`, when used, belongs at the SD-card root.

## Emulator test

1. Build/download the experimental artifact from the GitHub Actions run named **Switch homebrew (experimental)**.
2. Extract the ZIP into the emulator's virtual SD-card root, preserving the `switch/ApeEscapeRecomp` directory.
3. Add your own dumped Ape Escape (USA / SCUS-944.23) disc image under `switch/ApeEscapeRecomp/data/`. The experimental runtime also checks the Ryujinx virtual SD-card mount (`sdmc:/switch/ApeEscapeRecomp/data`) and common `/sdcard` paths, including a bounded shallow scan for files named for Ape Escape or `SCUS_944.23`.
4. Launch Homebrew Menu and start ApeEscapeRecomp. If direct NRO launch cannot access SD storage in your emulator build, initialize Homebrew Menu first and launch it from there.
5. Record whether it starts, reaches the game window, recognizes the disc, renders a frame, accepts controller input, and produces audio. If Ryujinx stores its virtual SD files in a host-side `sdcard` directory, keep the normal `switch/ApeEscapeRecomp/data` tree inside that virtual SD root; the guest runtime cannot automatically read arbitrary host folders that Ryujinx does not expose to the guest.

## Current limitations

The existing project runtime was designed around desktop SDL and host-side overlay compilation/dynamic loading. Nintendo Switch requires a libnx-compatible platform layer, supported rendering backend, input/audio/filesystem adaptation, and a Switch-compatible overlay strategy. The workflow intentionally attempts to configure and compile the **real project**, not a fake probe. A failed configure/build is diagnostic evidence, not a playable release. Do not distribute a package as working unless the workflow produces an NRO and that NRO has been launched successfully in an emulator or on hardware.

The game disc is not bundled. Use only a disc image you are entitled to use.
