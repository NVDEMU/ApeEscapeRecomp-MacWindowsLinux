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

- The earlier `pgxp_tolerance = 0.5` mitigation was inappropriate for this title's high-coverage PGXP hook build. The framework documents that an explicit 0.5 px clamp can push precise vertices back to native pixels, reintroducing mixed-precision seams and more wobble. The game now uses `pgxp_tolerance = -1.0` (unclamped) and `pgxp_mod_only = true`, so PGXP is armed consistently by its single mod feature.
- CPU precision propagation remains enabled by default **within the PGXP feature** to cover Ape Escape's CPU-built near-cell vertices and terrain-grid word copies. PGXP itself remains opt-in/off by default, per the project's default-off optional-mod policy.
- Interpolated Rendering now captures/submits extra draw passes only during phase 3 (active gameplay). Title/attract, stage-select, loading, flyovers, warp-ins, and transition phases are not replayed.

Required manual A/B: use the same save/checkpoint, internal resolution, and scene. First capture PGXP off to record the authentic stock sub-pixel wobble; then enable PGXP and verify ground-grid edges, moving geometry, and texture warping. Compare stock 4:3 against Widescreen separately, and only then test Frame Smoothing. Capture at least 8 seconds per arm and inspect for hairline gaps, wobble, tearing, and stutter. Source-level guardrails are not live visual validation.
