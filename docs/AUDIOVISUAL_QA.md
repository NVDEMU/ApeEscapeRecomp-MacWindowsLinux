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

- The project now pins PSXRecomp `4102438ab4c5aadf010878029d0324ef6382e521`, which contains the PGXP renderer depth buffer and seam-expansion implementation. `game.toml` enables `pgxp_depth_buffer = true` and `pgxp_seam = "wide"` to target hairline gaps between high-resolution opaque 3D triangles. The PGXP manifest also enables its precise-culling option when the optional PGXP mod is selected.
- `pgxp_tolerance = -1.0` remains unclamped for the high-coverage hook build; `pgxp_position_fallback = false` avoids importing unrelated cached world fractions into CPU-built 2D vertices, and `pgxp_preserve_projection = true` preserves exact GTE projection for eligible vertices. CPU precision propagation remains enabled **within the PGXP feature**. PGXP itself remains opt-in/off by default.
- Renderer seam expansion only targets eligible opaque 3D triangles. It does not promise to correct every texture warp, every transparency/sprite path, or whole-scene/cutscene shaking. Broad shaking that also occurs with PGXP off needs a separate stock-4:3 baseline comparison.
- Widescreen still uses the projection-squash-and-stretch path. Its known culling/background geometry artifacts are not fixed by PGXP; Widescreen remains experimental and disabled by default. Use stock 4:3 for the faithful reference presentation while those issues are investigated.
- Interpolated Rendering captures/submits extra draw passes only during phase 3 (active gameplay). Title/attract, stage-select, loading, flyovers, warp-ins, and transition phases are not replayed.

Required manual A/B: use the same save/checkpoint, internal resolution, and camera position. First capture PGXP off in stock 4:3; then enable PGXP and inspect the same ground grid, moving geometry, and an in-engine cutscene/camera turn. Compare Widescreen off/on separately, and test Frame Smoothing only after those cases are clean. Capture at least 8 seconds per arm and inspect for hairline gaps, texture swim, cutscene wobble, tearing, and stutter. Also verify broad scene shaking with PGXP and Frame Smoothing disabled. Source-level guardrails are not live visual validation.
