#!/usr/bin/env python3
"""Patch POSIX getifaddrs usage that Cafe OS does not provide.

Only the opt-in Wii U build runs this script. On Wii U we disable local NIC
enumeration used by the desktop LAN-lobby picker; the runtime's normal sockets,
controller, audio, rendering, and disc paths remain compiled as usual. The patch
is idempotent and fails closed when the pinned upstream anchors drift.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

INCLUDE_MARKER = "/* Wii U portability: Cafe OS has no POSIX ifaddrs API. */"
FUNCTION_MARKER = "// Wii U portability: skip host-NIC enumeration on Cafe OS."


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
        print(f"Wii U portability patch: source not found: {source_path}", file=sys.stderr)
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
/* Wii U portability: Cafe OS has no POSIX ifaddrs API. */
#if !defined(PSX_APE_WIIU_PORT)
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
#if defined(PSX_APE_WIIU_PORT)
        // Wii U portability: skip host-NIC enumeration on Cafe OS.
        // The desktop LAN-lobby picker can list interfaces; Cafe OS does not
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

    # Cafe OS's toolchain does not provide POSIX dlopen/dlsym either. On Wii U,
    # use the existing no-dynamic-overlay stubs. The actual overlay code will
    # execute through the interpreter selected above.
    overlay_path = args.framework_root / "runtime" / "src" / "overlay_posix.c"
    if not overlay_path.is_file():
        print(f"Wii U portability patch: source not found: {overlay_path}", file=sys.stderr)
        return 2
    overlay = overlay_path.read_text(encoding="utf-8-sig")
    overlay_old = "#ifndef _WIN32\n\n#include <dirent.h>\n#include <dlfcn.h>\n#include <sys/stat.h>"
    overlay_new = "#if !defined(_WIN32) && !defined(PSX_APE_WIIU_PORT)\n\n#include <dirent.h>\n#include <dlfcn.h>\n#include <sys/stat.h>"
    if overlay_new not in overlay:
        overlay = replace_exactly_once(
            overlay, overlay_old, overlay_new, "dynamic overlay loader platform block"
        )
        overlay_path.write_text(overlay, encoding="utf-8", newline="\n")

    # The runtime debug server uses byte-order helpers that Cafe OS's POSIX
    # compatibility headers do not consistently expose. Keep the debug server
    # buildable on Wii U with big-endian PowerPC conversions, scoped to this
    # opt-in target only.
    debug_path = args.framework_root / "runtime" / "src" / "debug_server.c"
    if not debug_path.is_file():
        print(f"Wii U portability patch: source not found: {debug_path}", file=sys.stderr)
        return 2
    debug = debug_path.read_text(encoding="utf-8-sig")
    debug_marker = "/* Wii U portability: byte-order helpers for Cafe OS. */"
    if debug_marker not in debug:
        # Place the macros after the source's headers so they cannot rewrite
        # declarations inside libc headers.
        last_include = debug.rfind("#include")
        if last_include < 0:
            raise RuntimeError("debug server has no include block")
        insert_at = debug.find("\n", last_include)
        if insert_at < 0:
            raise RuntimeError("debug server include block is malformed")
        debug_compat = """
/* Wii U portability: byte-order helpers for Cafe OS. */
#if defined(PSX_APE_WIIU_PORT)
#include <stdint.h>
#ifndef INADDR_LOOPBACK
#define INADDR_LOOPBACK 0x7f000001U
#endif
#ifndef htonl
#define htonl(value) ((uint32_t)(value))
#endif
#ifndef htons
#define htons(value) ((uint16_t)(value))
#endif
#endif
"""
        debug = debug[:insert_at + 1] + debug_compat + debug[insert_at + 1:]
        debug_path.write_text(debug, encoding="utf-8", newline="\n")

    # Cafe OS's socket layer does not declare SO_SNDTIMEO. Keep the optional
    # debug-send helper in its original nonblocking mode on Wii U; its total
    # send budget remains enforced by the existing loop.
    debug_timeout_marker = "/* Wii U portability: SO_SNDTIMEO is unavailable on Cafe OS. */"
    if debug_timeout_marker not in debug:
        old_timeout = """    int flags = fcntl(sock, F_GETFL, 0);
    fcntl(sock, F_SETFL, flags & ~O_NONBLOCK);
    struct timeval tmo = { 2, 0 };
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tmo, sizeof(tmo));"""
        new_timeout = """    int flags = fcntl(sock, F_GETFL, 0);
#if !defined(PSX_APE_WIIU_PORT)
    fcntl(sock, F_SETFL, flags & ~O_NONBLOCK);
    struct timeval tmo = { 2, 0 };
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tmo, sizeof(tmo));
#else
    /* Wii U portability: SO_SNDTIMEO is unavailable on Cafe OS.
     * Keep the socket in its original nonblocking mode. */
#endif"""
        debug = replace_exactly_once(debug, old_timeout, new_timeout, "Wii U send timeout guard")
        debug_path.write_text(debug, encoding="utf-8", newline="\\n")

    # Cafe OS does not ship POSIX ucontext.h. Add a real cooperative PowerPC
    # fiber backend for Wii U rather than stubbing thread Wii Ues (the PS1
    # BIOS scheduler depends on preserving separate stacks).
    fiber_path = args.framework_root / "runtime" / "src" / "psx_fiber.c"
    if not fiber_path.is_file():
        print(f"Wii U portability patch: source not found: {fiber_path}", file=sys.stderr)
        return 2
    fiber = fiber_path.read_text(encoding="utf-8-sig")
    fiber_anchor = "#else /* POSIX: ucontext */\n\n#ifndef _XOPEN_SOURCE"
    fiber_backend = r"""#elif defined(PSX_APE_WIIU_PORT) /* Wii U: cooperative PowerPC fibers */

#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef struct psx_fiber_impl {
    uintptr_t sp;              /* 0 */
    uint32_t r2;                /* 4: EABI small-data/TOC register */
    uint32_t r13;               /* 8: EABI reserved register */
    uint32_t gpr14_31[18];      /* 12..83 */
    uint32_t lr;                /* 84 */
    uint64_t fpr14_31[18];      /* 88..231 */
    void* stack;                /* 232 */
    psx_fiber_entry entry;      /* 236 */
    void* arg;                  /* 240 */
} psx_fiber_impl;

static psx_fiber_impl* s_current = NULL;

static void psx_fiber_trampoline(void)
{
    psx_fiber_impl* f = s_current;
    if (!f || !f->entry) abort();
    f->entry(f->arg);
    abort();
}

/* Save/restore the PowerPC EABI callee-saved register bank and stack pointer. */
__attribute__((naked)) static void psx_fiber_switch_asm(psx_fiber_impl* from, psx_fiber_impl* to)
{
    __asm__ volatile(
        "stw 1, 0(3)\n"
        "stw 2, 4(3)\n"
        "stw 13, 8(3)\n"
        "stmw 14, 12(3)\n"
        "mflr 0\n"
        "stw 0, 84(3)\n"
        "stfd 14, 88(3)\n"
        "stfd 15, 96(3)\n"
        "stfd 16, 104(3)\n"
        "stfd 17, 112(3)\n"
        "stfd 18, 120(3)\n"
        "stfd 19, 128(3)\n"
        "stfd 20, 136(3)\n"
        "stfd 21, 144(3)\n"
        "stfd 22, 152(3)\n"
        "stfd 23, 160(3)\n"
        "stfd 24, 168(3)\n"
        "stfd 25, 176(3)\n"
        "stfd 26, 184(3)\n"
        "stfd 27, 192(3)\n"
        "stfd 28, 200(3)\n"
        "stfd 29, 208(3)\n"
        "stfd 30, 216(3)\n"
        "stfd 31, 224(3)\n"
        "lwz 1, 0(4)\n"
        "lwz 2, 4(4)\n"
        "lwz 13, 8(4)\n"
        "lmw 14, 12(4)\n"
        "lwz 0, 84(4)\n"
        "mtlr 0\n"
        "lfd 14, 88(4)\n"
        "lfd 15, 96(4)\n"
        "lfd 16, 104(4)\n"
        "lfd 17, 112(4)\n"
        "lfd 18, 120(4)\n"
        "lfd 19, 128(4)\n"
        "lfd 20, 136(4)\n"
        "lfd 21, 144(4)\n"
        "lfd 22, 152(4)\n"
        "lfd 23, 160(4)\n"
        "lfd 24, 168(4)\n"
        "lfd 25, 176(4)\n"
        "lfd 26, 184(4)\n"
        "lfd 27, 192(4)\n"
        "lfd 28, 200(4)\n"
        "lfd 29, 208(4)\n"
        "lfd 30, 216(4)\n"
        "lfd 31, 224(4)\n"
        "blr\n"
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
    f->lr = (uint32_t)(uintptr_t)psx_fiber_trampoline;
    __asm__ volatile("mr %0,2" : "=r"(f->r2));
    __asm__ volatile("mr %0,13" : "=r"(f->r13));
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
    print("Applied Wii U network and dynamic-overlay portability patches")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Wii U portability patch: {exc}", file=sys.stderr)
        raise SystemExit(3)
