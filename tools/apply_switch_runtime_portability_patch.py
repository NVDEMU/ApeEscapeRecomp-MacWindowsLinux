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

    # Keep the renderer source files: they own shared runtime APIs/state used by
    # render_pass.c, debug_server.c, and the software rasterizer. On Switch we
    # force the software backend and provide inert GL entrypoints only for link
    # compatibility; the real GL backend must never be initialized.
    cmake_path = root / "runtime" / "runtime.cmake"
    cmake = read_text(cmake_path)
    old_marker = "# Switch portability: exclude host GL/Vulkan renderers on libnx."
    new_marker = "# Switch portability: retain renderer APIs and add the GL link shim."
    if old_marker in cmake:
        old_block = """# Switch portability: exclude host GL/Vulkan renderers on libnx.
if(APE_SWITCH_PORT)
    list(REMOVE_ITEM PSXRECOMP_RUNTIME_SOURCES
        ${PSXRECOMP_ROOT}/runtime/src/gpu_gl_renderer.c
        ${PSXRECOMP_ROOT}/runtime/src/gpu_vk_renderer.c)
endif()"""
        new_block_cmake = """# Switch portability: retain renderer APIs and add the GL link shim.
if(APE_SWITCH_PORT)
    list(APPEND PSXRECOMP_RUNTIME_SOURCES
        ${PSXRECOMP_ROOT}/runtime/src/gpu_gl_switch_shim.c)
endif()"""
        cmake = replace_once(cmake, old_block, new_block_cmake, "renderer source-list patch")
    elif new_marker not in cmake:
        anchor = ")\n# TCP `disasm` command only (debug_server.c); stripped with the rest of the TCP\n"
        insertion = """) 
# Switch portability: retain renderer APIs and add the GL link shim.
if(APE_SWITCH_PORT)
    list(APPEND PSXRECOMP_RUNTIME_SOURCES
        ${PSXRECOMP_ROOT}/runtime/src/gpu_gl_switch_shim.c)
endif()
# TCP `disasm` command only (debug_server.c); stripped with the rest of the TCP
"""
        insertion = insertion.replace(") \n", ")\n")
        cmake = replace_once(cmake, anchor, insertion, "runtime source-list close")

    # Never enable the real Vulkan backend on the Switch toolchain. Keep its
    # source file so it contributes its upstream inert API stubs.
    old_vk_option = 'option(PSX_ENABLE_VULKAN "Build the Vulkan renderer backend when SDK tools are available" ON)'
    new_vk_option = """if(APE_SWITCH_PORT)
    option(PSX_ENABLE_VULKAN "Build the Vulkan renderer backend when SDK tools are available" OFF)
else()
    option(PSX_ENABLE_VULKAN "Build the Vulkan renderer backend when SDK tools are available" ON)
endif()"""
    if new_vk_option not in cmake:
        cmake = replace_once(cmake, old_vk_option, new_vk_option, "Vulkan option default")
    write_text(cmake_path, cmake)

    # Switch-only desktop OpenGL entrypoints. SDL/OpenGL headers supply the
    # declarations; definitions are inert and are never used for rendering.
    # The GL renderer translation unit is kept for its shared non-GL APIs/state.
    glshim_path = root / "runtime" / "src" / "gpu_gl_switch_shim.c"
    glshim_marker = "Switch-only OpenGL link shim; software rendering is forced in main.cpp."
    glshim = r'''/* Switch-only OpenGL link shim; software rendering is forced in main.cpp.
 *
 * The PSX runtime's GL renderer translation unit also owns shared render-pass
 * APIs and backdrop-stretch state used by other runtime modules. Retain that
 * unit for ABI completeness, but this target cannot create a desktop GL context.
 * The main Switch entrypoint forces GR_BACKEND_SOFTWARE; these inert symbols
 * only satisfy references from the unused GL implementation and its diagnostics.
 */
#include "psx_sdl.h"
#if defined(PSX_SDL3)
#include <SDL3/SDL_opengl.h>
#else
#include <SDL_opengl.h>
#endif
#include <stddef.h>

GLAPI void APIENTRY glBindTexture(GLenum, GLuint) {}
GLAPI void APIENTRY glClear(GLbitfield) {}
GLAPI void APIENTRY glClearColor(GLclampf, GLclampf, GLclampf, GLclampf) {}
GLAPI void APIENTRY glClearDepth(GLclampd) {}
GLAPI void APIENTRY glClearStencil(GLint) {}
GLAPI void APIENTRY glColorMask(GLboolean, GLboolean, GLboolean, GLboolean) {}
GLAPI void APIENTRY glCopyTexImage2D(GLenum, GLint, GLenum, GLint, GLint, GLsizei, GLsizei, GLint) {}
GLAPI void APIENTRY glCopyTexSubImage2D(GLenum, GLint, GLint, GLint, GLint, GLint, GLsizei, GLsizei) {}
GLAPI void APIENTRY glDeleteTextures(GLsizei, const GLuint *) {}
GLAPI void APIENTRY glDepthFunc(GLenum) {}
GLAPI void APIENTRY glDepthMask(GLboolean) {}
GLAPI void APIENTRY glDisable(GLenum) {}
GLAPI void APIENTRY glDrawArrays(GLenum, GLint, GLsizei) {}
GLAPI void APIENTRY glEnable(GLenum) {}
GLAPI void APIENTRY glFinish(void) {}
GLAPI void APIENTRY glFlush(void) {}
GLAPI void APIENTRY glGenTextures(GLsizei n, GLuint *textures) {
    if (textures) for (GLsizei i = 0; i < n; ++i) textures[i] = 0;
}
GLAPI void APIENTRY glGetBooleanv(GLenum, GLboolean *data) {
    if (data) for (int i = 0; i < 4; ++i) data[i] = GL_FALSE;
}
GLAPI GLenum APIENTRY glGetError(void) { return GL_NO_ERROR; }
GLAPI void APIENTRY glGetIntegerv(GLenum, GLint *data) {
    if (data) for (int i = 0; i < 4; ++i) data[i] = 0;
}
GLAPI const GLubyte *APIENTRY glGetString(GLenum) { return NULL; }
GLAPI void APIENTRY glGetTexImage(GLenum, GLint, GLenum, GLenum, void *) {}
GLAPI void APIENTRY glGetTexParameteriv(GLenum, GLenum, GLint *params) {
    if (params) *params = 0;
}
GLAPI GLboolean APIENTRY glIsEnabled(GLenum) { return GL_FALSE; }
GLAPI void APIENTRY glLineWidth(GLfloat) {}
GLAPI void APIENTRY glPixelStorei(GLenum, GLint) {}
GLAPI void APIENTRY glReadBuffer(GLenum) {}
GLAPI void APIENTRY glReadPixels(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *) {}
GLAPI void APIENTRY glScissor(GLint, GLint, GLsizei, GLsizei) {}
GLAPI void APIENTRY glStencilFunc(GLenum, GLint, GLuint) {}
GLAPI void APIENTRY glStencilMask(GLuint) {}
GLAPI void APIENTRY glStencilOp(GLenum, GLenum, GLenum) {}
GLAPI void APIENTRY glTexImage2D(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *) {}
GLAPI void APIENTRY glTexParameteri(GLenum, GLenum, GLint) {}
GLAPI void APIENTRY glTexSubImage2D(GLenum, GLint, GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, const void *) {}
GLAPI void APIENTRY glViewport(GLint, GLint, GLsizei, GLsizei) {}
'''
    if not glshim_path.is_file() or glshim_marker not in read_text(glshim_path):
        write_text(glshim_path, glshim)

    # gpu_render.c still exposes OpenGL/Vulkan as selectable config values. With
    # their implementations omitted, provide null backends so its established
    # software fallback handles such requests without unresolved symbols.
    render_path = root / "runtime" / "src" / "gpu_render.c"
    render = read_text(render_path)
    render_marker = "/* Switch portability: hardware renderers are not selected on libnx. */"
    if render_marker not in render:
        old = """/* Supplied by gpu_gl_renderer.c; returns NULL until the GL backend is ready. */
extern const GpuRenderBackend *gl_backend_get(void);
/* Supplied by gpu_vk_renderer.c; returns NULL until the Vulkan backend is
 * ready (init succeeded). When Vulkan isn't compiled in it returns NULL. */
extern const GpuRenderBackend *vk_backend_get(void);"""
        new = """/* Switch portability: hardware renderers are not selected on libnx. */
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
        old = '#else\n    FILE *p = popen(cmd, "r");\n'
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

    # A software backend is mandatory: there is no desktop GL context on libnx.
    main_path = root / "runtime" / "src" / "main.cpp"
    main = read_text(main_path)
    main_marker = "/* Switch portability: force the software renderer on libnx. */"
    if main_marker not in main:
        anchor = "#endif\n    /* Netplay: CPU VRAM is digest/snap authority. Prefer dual-raster OpenGL"
        replacement = """#endif
#if defined(PSX_RYUJINX_SDCARD_SCAN)
    /* Switch portability: force the software renderer on libnx. */
    g_headless_opengl = 0;
    g_video_renderer = 0;
    std::fprintf(stdout, "psxrecomp: Switch build forces software GPU rendering\\n");
#endif
    /* Netplay: CPU VRAM is digest/snap authority. Prefer dual-raster OpenGL"""
        main = replace_once(main, anchor, replacement, "Switch software-renderer selection")
        write_text(main_path, main)

    # Mods that materialize a derived disc currently launch an external xdelta
    # process (fork/exec/waitpid). Disable only that optional operation on Switch.
    mod_path = root / "runtime" / "src" / "mod_runtime.cpp"
    mod_runtime = read_text(mod_path)
    mod_marker = "/* Switch portability: derived-disc xdelta execution is unavailable on libnx. */"
    if mod_marker not in mod_runtime:
        old = "#else\n    const pid_t child = fork();\n"
        new = """#elif defined(PSX_RYUJINX_SDCARD_SCAN)
    /* Switch portability: derived-disc xdelta execution is unavailable on libnx. */
    (void)executable; (void)source; (void)patch; (void)output;
    if (error) *error = "derived-disc mod patches are not supported by this Switch build";
    return false;
#else
    const pid_t child = fork();
"""
        mod_runtime = replace_once(mod_runtime, old, new, "Switch derived-disc process launcher")
        write_text(mod_path, mod_runtime)

    # The PSX renderer is software on libnx, but that does not control SDL's
    # separate 2D frame-presenter. The standard SDL2 libnx driver may not offer
    # an accelerated renderer; requesting one makes SDL_CreateRenderer fail and
    # main() returns straight back to Homebrew Menu before the game can start.
    # Explicitly select SDL's portable software presenter for this target only.
    sdl_present_marker = "/* Switch portability: use SDL's software 2D presentation renderer. */"
    if sdl_present_marker not in main:
        old_presenter = """    Uint32 rflags = SDL_RENDERER_ACCELERATED |
                    (present_effective_swap_interval() != 0
                         ? SDL_RENDERER_PRESENTVSYNC : 0u);
    sdl_renderer = SDL_CreateRenderer(sdl_window, -1, rflags);
    if (!sdl_renderer)
        sdl_renderer = SDL_CreateRenderer(sdl_window, -1, SDL_RENDERER_ACCELERATED);
    if (!sdl_renderer) {
        std::fprintf(stderr, "SDL_CreateRenderer failed: %s\\n", SDL_GetError());
        return 1;
    }"""
        new_presenter = """#if defined(PSX_RYUJINX_SDCARD_SCAN)
    /* Switch portability: use SDL's software 2D presentation renderer. */
    Uint32 rflags = SDL_RENDERER_SOFTWARE;
    sdl_renderer = SDL_CreateRenderer(sdl_window, -1, rflags);
#else
    Uint32 rflags = SDL_RENDERER_ACCELERATED |
                    (present_effective_swap_interval() != 0
                         ? SDL_RENDERER_PRESENTVSYNC : 0u);
    sdl_renderer = SDL_CreateRenderer(sdl_window, -1, rflags);
    if (!sdl_renderer)
        sdl_renderer = SDL_CreateRenderer(sdl_window, -1, SDL_RENDERER_ACCELERATED);
#endif
    if (!sdl_renderer) {
        std::fprintf(stderr, "SDL_CreateRenderer failed: %s\\n", SDL_GetError());
        return 1;
    }"""
        main = replace_once(main, old_presenter, new_presenter, "Switch SDL software presenter")
        write_text(main_path, main)

    print("Applied Switch software-renderer, GL-link, overlay-compiler, BIOS-builder, derived-disc, and clock portability patches")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Switch runtime portability patch: {exc}", file=sys.stderr)
        raise SystemExit(3)
