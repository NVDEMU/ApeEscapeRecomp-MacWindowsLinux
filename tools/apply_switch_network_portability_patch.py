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

    # The native desktop target intentionally links a no-op interpreter.
    # Switch cannot JIT/dlopen overlays, so enable the framework's real MIPS
    # interpreter as the safe fallback for overlay code not in generated C.
    runtime_cmake = args.framework_root / "runtime" / "runtime.cmake"
    if not runtime_cmake.is_file():
        print(f"Switch portability patch: source not found: {runtime_cmake}", file=sys.stderr)
        return 2
    runtime = runtime_cmake.read_text(encoding="utf-8-sig")
    interpreter_old = """    if(PSXRT_ORACLE)
        set(mode_source ${PSXRECOMP_ROOT}/runtime/src/psx_interpreter.c)
    else()
        set(mode_source ${PSXRECOMP_ROOT}/runtime/src/stub_interpreter.c)
    endif()"""
    interpreter_new = """    if(PSXRT_ORACLE OR PSX_SWITCH_INTERPRETER_FALLBACK)
        set(mode_source ${PSXRECOMP_ROOT}/runtime/src/psx_interpreter.c)
    else()
        set(mode_source ${PSXRECOMP_ROOT}/runtime/src/stub_interpreter.c)
    endif()"""
    if interpreter_new not in runtime:
        runtime = replace_exactly_once(
            runtime, interpreter_old, interpreter_new, "interpreter source selection"
        )
        runtime_cmake.write_text(runtime, encoding="utf-8", newline="\n")

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

    source_path.write_text(source, encoding="utf-8", newline="\n")
    print("Applied Switch network, dynamic-overlay, and interpreter-fallback portability patches")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Switch portability patch: {exc}", file=sys.stderr)
        raise SystemExit(3)
