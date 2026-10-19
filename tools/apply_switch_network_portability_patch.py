#!/usr/bin/env python3
"""Patch POSIX getifaddrs usage that libnx does not provide.

Only the opt-in Switch build runs this script. On Switch we disable local NIC
enumeration used by the desktop LAN-lobby picker; the runtime's normal sockets,
controller, audio, rendering, and disc paths remain compiled as usual. The patch
is idempotent and fails closed when the pinned upstream anchors drift.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

INCLUDE_MARKER = "/* Switch portability: libnx has no POSIX ifaddrs API. */"
FUNCTION_MARKER = "// Switch portability: skip host-NIC enumeration on libnx."


def replace_exactly_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one source anchor, found {count}; refusing to patch"
        )
    return source.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-root", required=True, type=Path)
    args = parser.parse_args()

    source_path = args.framework_root / "runtime" / "src" / "main.cpp"
    if not source_path.is_file():
        print(f"Switch portability patch: source not found: {source_path}", file=sys.stderr)
        return 2

    source = source_path.read_text(encoding="utf-8-sig")
    if INCLUDE_MARKER not in source:
        old_headers = """#include <arpa/inet.h>
#include <fcntl.h>
#include <ifaddrs.h>
#include <netdb.h>
#include <net/if.h>
#include <netinet/in.h>"""
        new_headers = """#include <arpa/inet.h>
#include <fcntl.h>
/* Switch portability: libnx has no POSIX ifaddrs API. */
#if !defined(PSX_RYUJINX_SDCARD_SCAN)
#include <ifaddrs.h>
#include <net/if.h>
#endif
#include <netdb.h>
#include <netinet/in.h>"""
        source = replace_exactly_once(source, old_headers, new_headers, "network header block")

    if FUNCTION_MARKER not in source:
        old_function = """#else
        struct ifaddrs* ifa = nullptr;
        if (getifaddrs(&ifa) != 0 || !ifa) return;
        for (struct ifaddrs* i = ifa; i; i = i->ifa_next) {
            if (!i->ifa_addr || i->ifa_addr->sa_family != AF_INET) continue;
            if (!(i->ifa_flags & IFF_UP) || (i->ifa_flags & IFF_LOOPBACK)) continue;
            auto* sin = reinterpret_cast<sockaddr_in*>(i->ifa_addr);
            char ip[64] = {};
            if (!inet_ntop(AF_INET, &sin->sin_addr, ip, sizeof(ip))) continue;
            push(ip, i->ifa_name ? i->ifa_name : "");
        }
        freeifaddrs(ifa);
#endif
    }"""
        new_function = """#else
#if defined(PSX_RYUJINX_SDCARD_SCAN)
        // Switch portability: skip host-NIC enumeration on libnx.
        // The desktop LAN-lobby picker can list interfaces; libnx does not
        // expose getifaddrs(), so leave the optional address list empty.
        (void)push;
#else
        struct ifaddrs* ifa = nullptr;
        if (getifaddrs(&ifa) != 0 || !ifa) return;
        for (struct ifaddrs* i = ifa; i; i = i->ifa_next) {
            if (!i->ifa_addr || i->ifa_addr->sa_family != AF_INET) continue;
            if (!(i->ifa_flags & IFF_UP) || (i->ifa_flags & IFF_LOOPBACK)) continue;
            auto* sin = reinterpret_cast<sockaddr_in*>(i->ifa_addr);
            char ip[64] = {};
            if (!inet_ntop(AF_INET, &sin->sin_addr, ip, sizeof(ip))) continue;
            push(ip, i->ifa_name ? i->ifa_name : "");
        }
        freeifaddrs(ifa);
#endif
#endif
    }"""
        source = replace_exactly_once(source, old_function, new_function, "local-interface enumeration")

    # libnx's toolchain does not provide POSIX dlopen/dlsym either. On Switch,
    # use the existing no-dynamic-overlay stubs. The actual overlay code will
    # execute through the interpreter selected above.
    overlay_path = args.framework_root / "runtime" / "src" / "overlay_posix.c"
    if not overlay_path.is_file():
        print(f"Switch portability patch: source not found: {overlay_path}", file=sys.stderr)
        return 2
    overlay = overlay_path.read_text(encoding="utf-8-sig")
    overlay_old = "#ifndef _WIN32\n\n#include <dirent.h>\n#include <dlfcn.h>\n#include <sys/stat.h>"
    overlay_new = "#if !defined(_WIN32) && !defined(PSX_RYUJINX_SDCARD_SCAN)\n\n#include <dirent.h>\n#include <dlfcn.h>\n#include <sys/stat.h>"
    if overlay_new not in overlay:
        overlay = replace_exactly_once(
            overlay, overlay_old, overlay_new, "dynamic overlay loader platform block"
        )
        overlay_path.write_text(overlay, encoding="utf-8", newline="\n")

    # The runtime debug server uses byte-order helpers that libnx's POSIX
    # compatibility headers do not consistently expose. Keep the debug server
    # buildable on Switch with AArch64 little-endian conversions, scoped to this
    # opt-in target only.
    debug_path = args.framework_root / "runtime" / "src" / "debug_server.c"
    if not debug_path.is_file():
        print(f"Switch portability patch: source not found: {debug_path}", file=sys.stderr)
        return 2
    debug = debug_path.read_text(encoding="utf-8-sig")
    debug_marker = "/* Switch portability: byte-order helpers for libnx. */"
    if debug_marker not in debug:
        debug_prefix = """/* Switch portability: byte-order helpers for libnx. */
#if defined(PSX_RYUJINX_SDCARD_SCAN)
#include <stdint.h>
#ifndef INADDR_LOOPBACK
#define INADDR_LOOPBACK 0x7f000001U
#endif
#ifndef htonl
#define htonl(value) __builtin_bswap32((uint32_t)(value))
#endif
#ifndef htons
#define htons(value) __builtin_bswap16((uint16_t)(value))
#endif
#endif
"""
        debug = debug_prefix + debug
        debug_path.write_text(debug, encoding="utf-8", newline="\n")

    # libnx does not ship POSIX ucontext.h. Add a real cooperative AArch64
    # fiber backend for Switch rather than stubbing thread switches (the PS1
    # BIOS scheduler depends on preserving separate stacks).
    fiber_path = args.framework_root / "runtime" / "src" / "psx_fiber.c"
    if not fiber_path.is_file():
        print(f"Switch portability patch: source not found: {fiber_path}", file=sys.stderr)
        return 2
    fiber = fiber_path.read_text(encoding="utf-8-sig")
    fiber_anchor = "#else /* POSIX: ucontext */\n\n#ifndef _XOPEN_SOURCE"
    fiber_backend = r"""#elif defined(PSX_RYUJINX_SDCARD_SCAN) /* Switch: cooperative AArch64 fibers */

#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef struct psx_fiber_impl {
    uintptr_t sp;
    uint64_t x19_x30[12];
    uint64_t d8_d15[8];
    void* stack;
    psx_fiber_entry entry;
    void* arg;
} psx_fiber_impl;

static psx_fiber_impl* s_current = NULL;

static void psx_fiber_trampoline(void)
{
    psx_fiber_impl* f = s_current;
    if (!f || !f->entry) abort();
    f->entry(f->arg);
    abort();
}

/* Save/restore AAPCS64 callee-saved integer and FP registers plus SP.
 * The saved LR doubles as the initial entry PC for a newly created fiber. */
__attribute__((naked)) static void psx_fiber_switch_asm(psx_fiber_impl* from, psx_fiber_impl* to)
{
    __asm__ volatile(
        "stp x19, x20, [x0, #8]\n"
        "stp x21, x22, [x0, #24]\n"
        "stp x23, x24, [x0, #40]\n"
        "stp x25, x26, [x0, #56]\n"
        "stp x27, x28, [x0, #72]\n"
        "stp x29, x30, [x0, #88]\n"
        "mov x2, sp\n"
        "str x2, [x0]\n"
        "stp d8, d9, [x0, #104]\n"
        "stp d10, d11, [x0, #120]\n"
        "stp d12, d13, [x0, #136]\n"
        "stp d14, d15, [x0, #152]\n"
        "ldr x2, [x1]\n"
        "mov sp, x2\n"
        "ldp x19, x20, [x1, #8]\n"
        "ldp x21, x22, [x1, #24]\n"
        "ldp x23, x24, [x1, #40]\n"
        "ldp x25, x26, [x1, #56]\n"
        "ldp x27, x28, [x1, #72]\n"
        "ldp x29, x30, [x1, #88]\n"
        "ldp d8, d9, [x1, #104]\n"
        "ldp d10, d11, [x1, #120]\n"
        "ldp d12, d13, [x1, #136]\n"
        "ldp d14, d15, [x1, #152]\n"
        "ret\n"
    );
}

psx_fiber_t psx_fiber_convert_thread(void)
{
    if (!s_current) {
        s_current = (psx_fiber_impl*)calloc(1, sizeof(*s_current));
        if (!s_current) return NULL;
    }
    return (psx_fiber_t)s_current;
}
psx_fiber_t psx_fiber_current(void) { return (psx_fiber_t)s_current; }

psx_fiber_t psx_fiber_create(size_t stack_size, psx_fiber_entry entry, void* arg)
{
    if (stack_size < 16384) stack_size = 16384;
    psx_fiber_impl* f = (psx_fiber_impl*)calloc(1, sizeof(*f));
    if (!f) return NULL;
    f->stack = malloc(stack_size);
    if (!f->stack) { free(f); return NULL; }
    f->entry = entry;
    f->arg = arg;
    uintptr_t top = ((uintptr_t)f->stack + stack_size) & ~(uintptr_t)15;
    f->sp = top;
    f->x19_x30[11] = (uintptr_t)psx_fiber_trampoline; /* x30 at offset 88 */
    return (psx_fiber_t)f;
}

void psx_fiber_switch(psx_fiber_t target)
{
    psx_fiber_impl* to = (psx_fiber_impl*)target;
    psx_fiber_impl* from = s_current;
    if (!to || !from || to == from) return;
    s_current = to;
    psx_fiber_switch_asm(from, to);
}

void psx_fiber_destroy(psx_fiber_t fiber)
{
    psx_fiber_impl* f = (psx_fiber_impl*)fiber;
    if (!f || f == s_current) return;
    free(f->stack);
    free(f);
}

#else /* POSIX: ucontext */

#ifndef _XOPEN_SOURCE""";
    if fiber_backend not in fiber:
        fiber = replace_exactly_once(fiber, fiber_anchor, fiber_backend, "ucontext backend insertion")
        fiber_path.write_text(fiber, encoding="utf-8", newline="\n")

    source_path.write_text(source, encoding="utf-8", newline="\n")
    print("Applied Switch network and dynamic-overlay portability patches")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Switch portability patch: {exc}", file=sys.stderr)
        raise SystemExit(3)
