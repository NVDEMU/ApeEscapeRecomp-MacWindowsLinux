#!/usr/bin/env python3
"""Apply compile-time Switch/libnx portability fixes to the pinned psxrecomp runtime.

Only the experimental APE_SWITCH_PORT build invokes this script. It deliberately
selects the existing software GPU rasterizer and disables host-only helpers that
require desktop OpenGL, POSIX process spawning, or dynamic BIOS-module building.
The patches are idempotent and fail closed if the pinned source changes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def read_text(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"required framework source not found: {path}")
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def replace_once(value: str, old: str, new: str, label: str) -> str:
    count = value.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one source anchor, found {count}; refusing to patch"
        )
    return value.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.framework_root

    # The upstream runtime source list unconditionally includes both desktop
    # renderers. Switch has neither desktop GL nor Vulkan loader libraries; use
    # the runtime's built-in software rasterizer instead.
    cmake_path = root / "runtime" / "runtime.cmake"
    cmake = read_text(cmake_path)
    cmake_marker = "# Switch portability: exclude host GL/Vulkan renderers on libnx."
    if cmake_marker not in cmake:
        anchor = ")\n# TCP `disasm` command only (debug_server.c); stripped with the rest of the TCP\n"
        insertion = """) 
# Switch portability: exclude host GL/Vulkan renderers on libnx.
if(APE_SWITCH_PORT)
    list(REMOVE_ITEM PSXRECOMP_RUNTIME_SOURCES
        ${PSXRECOMP_ROOT}/runtime/src/gpu_gl_renderer.c
        ${PSXRECOMP_ROOT}/runtime/src/gpu_vk_renderer.c)
endif()
# TCP `disasm` command only (debug_server.c); stripped with the rest of the TCP
"""
        # Avoid formatting drift from the source's close-paren line.
        insertion = insertion.replace(") \n", ")\n")
        cmake = replace_once(cmake, anchor, insertion, "runtime source-list close")
        write_text(cmake_path, cmake)

    # gpu_render.c still exposes OpenGL/Vulkan as selectable config values. With
    # their implementations omitted, provide null backends so its established
    # software fallback handles such requests without unresolved symbols.
    render_path = root / "runtime" / "src" / "gpu_render.c"
    render = read_text(render_path)
    render_marker = "/* Switch portability: desktop GL/Vulkan are not linked. */"
    if render_marker not in render:
        old = """/* Supplied by gpu_gl_renderer.c; returns NULL until the GL backend is ready. */
extern const GpuRenderBackend *gl_backend_get(void);
/* Supplied by gpu_vk_renderer.c; returns NULL until the Vulkan backend is
 * ready (init succeeded). When Vulkan isn't compiled in it returns NULL. */
extern const GpuRenderBackend *vk_backend_get(void);"""
        new = """/* Switch portability: desktop GL/Vulkan are not linked. */
#if defined(PSX_RYUJINX_SDCARD_SCAN)
static const GpuRenderBackend *gl_backend_get(void) { return NULL; }
static const GpuRenderBackend *vk_backend_get(void) { return NULL; }
#else
/* Supplied by gpu_gl_renderer.c; returns NULL until the GL backend is ready. */
extern const GpuRenderBackend *gl_backend_get(void);
/* Supplied by gpu_vk_renderer.c; returns NULL until the Vulkan backend is
 * ready (init succeeded). When Vulkan isn't compiled in it returns NULL. */
extern const GpuRenderBackend *vk_backend_get(void);
#endif"""
        render = replace_once(render, old, new, "renderer backend declarations")
        write_text(render_path, render)

    # Runtime overlay autocompilation shells out to /bin/sh, forks, pipes, and
    # waits for child processes. Those facilities do not exist in libnx; Switch
    # runs guest code with the interpreter and leaves overlay builds disabled.
    auto_path = root / "runtime" / "src" / "autocompile.c"
    auto = read_text(auto_path)
    auto_marker = "/* Switch portability: no process-spawned overlay compiler on libnx. */"
    if auto_marker not in auto:
        anchor = "#ifndef PSX_OVERLAY_FLAVOR\n"
        stubs = r'''/* Switch portability: no process-spawned overlay compiler on libnx. */
#if defined(PSX_RYUJINX_SDCARD_SCAN)
void autocompile_configure(const char *cmd, const char *cwd) {
    (void)cmd; (void)cwd;
}
int autocompile_configured(void) { return 0; }
void autocompile_set_cache_paths(const char *cache_dir, const char *captures) {
    (void)cache_dir; (void)captures;
}
int autocompile_toolchain_available(void) { return 0; }
int autocompile_busy(void) { return 0; }
int autocompile_request(void) { return 0; }
void autocompile_poll_main(void) {}
void autocompile_shutdown(void) {}
int autocompile_status_json(char *out, int cap) {
    static const char status[] =
        "{\"busy\":false,\"configured\":false,\"degraded\":true,"
        "\"degraded_reason\":\"overlay autocompile is unavailable on Switch; "
        "overlays execute in the interpreter\",\"runs\":0,\"fails\":0}";
    int n;
    if (!out || cap <= 0) return 0;
    n = snprintf(out, (size_t)cap, "%s", status);
    if (n < 0) return 0;
    return n >= cap ? cap - 1 : n;
}
const char *autocompile_degraded_reason(void) {
    return "overlay autocompile is unavailable on Switch; overlays execute in the interpreter";
}
#else
'''
        auto = replace_once(auto, anchor, stubs + anchor, "autocompile implementation start")
        auto = auto.rstrip() + "\n\n#endif /* PSX_RYUJINX_SDCARD_SCAN */\n"
        write_text(auto_path, auto)

    # The retail BIOS dynamic-module builder also shells out through popen. It is
    # optional; bundled OpenBIOS and statically linked BIOS backends remain usable.
    bios_path = root / "runtime" / "src" / "psx_bios_module.c"
    bios = read_text(bios_path)
    bios_marker = "/* Switch portability: external BIOS module builds are unavailable on libnx. */"
    if bios_marker not in bios:
        old = '    FILE *p = popen(cmd, "r");\n'
        new = '''#elif defined(PSX_RYUJINX_SDCARD_SCAN)
    /* Switch portability: external BIOS module builds are unavailable on libnx. */
    (void)cmd;
    return -1;
#else
    FILE *p = popen(cmd, "r");
'''
        bios = replace_once(bios, old, new, "BIOS module process launcher")
        write_text(bios_path, bios)

    # timespec_get is absent in the devkitPro newlib used by this cross-build.
    # This statistic is diagnostic only, so use the runtime's already-portable
    # monotonic millisecond clock and convert it to the existing nanosecond unit.
    dma_path = root / "runtime" / "src" / "dma.c"
    dma = read_text(dma_path)
    dma_marker = "/* Switch portability: libnx diagnostic clock fallback. */"
    if dma_marker not in dma:
        old = """#else
    struct timespec ts; timespec_get(&ts, TIME_UTC);   /* C11; diagnostics only */
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#endif
}"""
        new = """#elif defined(PSX_RYUJINX_SDCARD_SCAN)
    /* Switch portability: libnx diagnostic clock fallback. */
    extern uint64_t psx_host_mono_ms(void);
    return psx_host_mono_ms() * 1000000ull;
#else
    struct timespec ts; timespec_get(&ts, TIME_UTC);   /* C11; diagnostics only */
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#endif
}"""
        dma = replace_once(dma, old, new, "DMA host diagnostic clock")
        write_text(dma_path, dma)

    print("Applied Switch renderer, overlay-compiler, BIOS-builder, and clock portability patches")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Switch runtime portability patch: {exc}", file=sys.stderr)
        raise SystemExit(3)
