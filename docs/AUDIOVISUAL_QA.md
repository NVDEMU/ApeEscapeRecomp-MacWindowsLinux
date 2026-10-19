# Audio / video regression checks

A source-level review has not established a universal audio/video defect in the stock 4:3 presentation. The renderer is reverse-engineered; avoid global timing or audio changes based only on a hunch.

## Known open visual defects

- **Very wide FOV draw-distance pop-in:** the experimental Extended Draw Distance mod targets some ordering-table depth-bucket drops. Separate game-side far-clip tests may still pop. It remains off by default.
- **Title/attract circus-ball popping on widescreen:** visibility and trajectory near Spike putting on his hat are not fully traced. The previous experiment to submit objects earlier was rejected because it did not prove correct motion/culling.

## Reproducible smoke-test matrix

1. Stock **4:3**, OpenGL, frame smoothing off: cold boot, title/attract, intro FMV, gameplay, pause/resume, death/retry, stage exit and memory-card load/save.
2. Audio continuity: music and effects during title-to-gameplay transitions, pause/resume, stage transitions, FMV start/stop, save/load screens, and return to Time Station.
3. Frame smoothing off/on on the same route. Inspect moving geometry, transitions/menu frames, audio timing, and frame pacing separately. Extra render passes must not advance guest gameplay or the audio timeline.
4. Widescreen 16:9 and 21:9: compare matched frames around the title hat animation, HUD/gadget wheel, near/far scenery, and stage transitions. Keep the stock 4:3 capture for comparison.
5. Save-state/rewind: test whether visual state, current stage, timer and audio resume consistently, repeating each case at least three times.

Compilation alone cannot establish that the game is glitch-free.

## Crabby Beach performance regression

The title's `[timing]` config scales recompiled CPU instruction charging by 2 only when byte `0x800F447C == 3` (active level gameplay). VBlank, timers, CD, SPU and DMA remain on the PlayStation clock. The test suite also verifies that the pinned PSXRecomp parser/runtime implement this gate.

For manual A/B validation after framework or timing changes:

1. Load the same Crabby Beach checkpoint with optional mods disabled. Capture at least 8 seconds of active gameplay and compare delayed frames and cadence against an unscaled build; the upstream's measured target was approximately 30 FPS without delayed gameplay frames.
2. Confirm title/attract, Professor's stage-select briefing, level flyovers and warp-ins retain the original pacing.
3. Check music/effects continuity, timer behavior, pause/resume, area transitions, memory-card save/load and save-state save/load.
4. Treat stage-clear results and in-level boss cutscenes as not yet cleared by this optimization until they receive explicit playtesting.


## QuiverLauncher reports — PGXP seams and modded rendering stutter (2026-10-18)

Two external reports on the macOS Nightly described (1) residual PGXP wobble and visible floor-tile seams in widescreen, and (2) background wobble/tearing/stutter when optional mods are enabled.

- The game override previously set `pgxp_tolerance = 1.0`, looser than the framework's Ape Escape visual-isolation value of `0.5`. The configuration now uses `0.5`; `pgxp_cpu_mode = true` remains enabled because the framework's terrain-grid fix depends on CPU-mode precision propagation.
- Interpolated Rendering now captures/submits extra draw passes only during phase 3 (active gameplay). Title/attract, stage-select, loading, flyovers, warp-ins, and transition phases are not replayed.
- Frame interpolation remains optional and disabled by default. When reproducing stutter, test stock 4:3 first, then PGXP alone, Widescreen alone, and finally the combination; only add Interpolated Rendering after those are clean.

Required manual A/B: same save/checkpoint, same internal resolution and scene, PGXP off/on, tolerance 0.5, and Widescreen off/on. Capture at least 8 seconds each. Inspect ground-grid edges for hairline gaps, moving geometry for residual wobble, and frame pacing for tearing/stutters. Separately compare interpolation off/on in active gameplay and confirm title/briefing/flyover/warp-in screens stay free of extra replay passes. Source-level guardrails do not replace these live captures.
