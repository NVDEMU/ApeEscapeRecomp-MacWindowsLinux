#!/usr/bin/env python3
"""Apply Ape Escape's remaining PGXP projection refinements to PSXRecomp.

Upstream now contains the original far-geometry / unclamped-projection work.
This compatibility patch keeps the remaining Ape Escape refinements:
both GTE SF modes, LM-aware IR saturation, and the hardware H/2 near-depth
floor. It is intentionally pinned and fails closed on any other revision.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PINNED_FRAMEWORK = "ffbd9d1ca4ee698866a2a9d7c58c3cc29a77f111"

NEW_FUNCTION = r'''extern "C" int pgxp_project_precise(int64_t mac1, int64_t mac2, int64_t mac3,
                                    int shift, int lm, int32_t ir1, int32_t ir2,
                                    uint32_t sz3, uint32_t h,
                                    int32_t ofx, int32_t ofy,
                                    int64_t x_num, int64_t x_den,
                                    int32_t *x16, int32_t *y16) {
    /* MAC1/2 are scaled by SF (12 or 0); MAC3 remains Q12 for SZ3.
     * Reconstruct the full projection while leaving guest registers and FLAG
     * untouched. The exact shadow remains tied to the packet word downstream. */
    if ((shift != 0 && shift != 12) || x_den <= 0) return 0;
    const double unit = shift == 12 ? 4096.0 : 1.0;
    const int64_t ix = mac1 >> shift;
    const int64_t iy = mac2 >> shift;
    const int64_t z_int = mac3 >> 12;
    if (z_int <= 0) return 0;

    /* Match the GTE's LM-dependent IR limits. A preserve-projection shadow may
     * bypass ordinary saturation, but never an LM=1 sign clamp. */
    const int64_t ir_min = lm ? 0 : -32768;
    const int64_t cx = ix < ir_min ? ir_min : (ix > 32767 ? 32767 : ix);
    const int64_t cy = iy < ir_min ? ir_min : (iy > 32767 ? 32767 : iy);
    const bool xy_clamped = ix != ir1 || iy != ir2;
    const bool z_clamped = z_int > 0xFFFF;
    const bool unclamped = xy_clamped || z_clamped;
    if (unclamped) {
        const int64_t mac_min = -(INT64_C(1) << 43);
        const int64_t mac_max = (INT64_C(1) << 43) - 1;
        if (!s_preserve_projection || mac1 < mac_min || mac1 > mac_max ||
            mac2 < mac_min || mac2 > mac_max || mac3 < mac_min || mac3 > mac_max ||
            cx != ir1 || cy != ir2 || (lm && (ix < 0 || iy < 0))) return 0;
    }
    if ((uint32_t)(z_clamped ? 0xFFFF : z_int) != sz3) return 0;

    /* The GTE's H/SZ divider is capped at 2. Treat H/2 as the nearest
     * projectable depth rather than dropping near-camera vertices. */
    const double depth = (double)mac3 / 4096.0;
    const double min_depth = (double)h * 0.5;
    const double z = depth > min_depth ? depth : min_depth;
    if (!(z > 0.0)) return 0;

    const double x = (double)mac1 / unit;
    const double y = (double)mac2 / unit;
    const double scale = (double)h * 65536.0 / z;
    double fx = (double)ofx + x * scale * (double)x_num / (double)x_den;
    double fy = (double)ofy + y * scale;

    /* Same bounded 16.16 transport range as the upstream GTE path. */
    const double lim = 4096.0 * 65536.0;
    if (fx < -lim) fx = -lim;
    if (fx > lim - 1.0) fx = lim - 1.0;
    if (fy < -lim) fy = -lim;
    if (fy > lim - 1.0) fy = lim - 1.0;
    *x16 = (int32_t)std::floor(fx);
    *y16 = (int32_t)std::floor(fy);
    return unclamped ? 2 : 1;
}'''

NEW_DECLARATION = '''/* Exact, host-only projection for preserve-projection mode. Inputs are the
 * unshifted GTE MAC1..3, SF shift (0 or 12), limit mode LM, stored IR1/IR2
 * and SZ3, H, OFX/OFY, and horizontal factor x_num/x_den. Reconstructs both
 * legal SF modes, validates LM-dependent IR saturation, and applies the
 * hardware divider's H/2 near-depth floor. Guest registers and FLAG remain
 * unchanged; pgxp_ppp_accept() still validates the exact packet word.
 * Return 2 for an opt-in IR/SZ-unclamped projection, 1 for ordinary precision. */
int pgxp_project_precise(int64_t mac1, int64_t mac2, int64_t mac3, int shift,
                         int lm, int32_t ir1, int32_t ir2, uint32_t sz3, uint32_t h,
                         int32_t ofx, int32_t ofy, int64_t x_num, int64_t x_den,
                         int32_t *x16, int32_t *y16);

'''

EXTENSION_TEST_BLOCK = r'''    /* --- Ape Escape PGXP refinements: SF=0, LM, and near-depth floor --- */
    {
        const int saved_preserve = pgxp_preserve_projection();
        pgxp_set_preserve_projection(1);
        pgxp_set_tolerance(-1.0f);
        const int32_t ofx = 160 << 16, ofy = 120 << 16;
        int32_t x, y;

        /* SF=0 uses unshifted MAC1/2, while MAC3 remains Q12. */
        const int64_t sf0_m1 = 100;
        const int64_t sf0_m2 = -50;
        const int64_t sf0_m3 = INT64_C(1000) * 4096 + 2048;
        CHECK(pgxp_project_precise(sf0_m1, sf0_m2, sf0_m3, 0, 0,
              (int32_t)sf0_m1, (int32_t)sf0_m2,
              (uint32_t)(sf0_m3 >> 12), 300, ofx, ofy, 1, 1, &x, &y) == 1);
        const double sf0_z = (double)sf0_m3 / 4096.0;
        CHECK(std::abs(x - (int32_t)std::floor(
              (160.0 + 100.0 * 300.0 / sf0_z) * 65536.0)) <= 1);
        CHECK(std::abs(y - (int32_t)std::floor(
              (120.0 - 50.0 * 300.0 / sf0_z) * 65536.0)) <= 1);

        /* LM=1 clamps negative IR to zero. Preserve-projection must not turn
         * that sign clamp into an out-of-range exact vertex. */
        CHECK(pgxp_project_precise(-INT64_C(10000) * 4096, 0,
              INT64_C(1000) * 4096, 12, 1, 0, 0, 1000, 300,
              ofx, ofy, 1, 1, &x, &y) == 0);

        /* LM=0's lower saturation and LM=1's positive saturation can be
         * recovered only by the opt-in preserve-projection path. */
        CHECK(pgxp_project_precise(-INT64_C(40000) * 4096,
              -INT64_C(40000) * 4096, INT64_C(1000) * 4096,
              12, 0, -32768, -32768, 1000, 300,
              ofx, ofy, 1, 1, &x, &y) == 2);
        CHECK(pgxp_project_precise(INT64_C(40000) * 4096, 0,
              INT64_C(1000) * 4096, 12, 1, 32767, 0, 1000, 300,
              ofx, ofy, 1, 1, &x, &y) == 2);

        /* When SZ is nearer than H/2, projection uses a maximum scale of 2. */
        const int64_t near_m1 = INT64_C(100) * 4096 + 123;
        const int64_t near_m2 = INT64_C(20) * 4096 + 77;
        const int64_t near_m3 = INT64_C(100) * 4096 + 100;
        CHECK(pgxp_project_precise(near_m1, near_m2, near_m3, 12, 0,
              100, 20, 100, 300, ofx, ofy, 1, 1, &x, &y) == 1);
        const double near_z_raw = (double)near_m3 / 4096.0;
        const double near_z = near_z_raw > 150.0 ? near_z_raw : 150.0;
        CHECK(std::abs(x - (int32_t)std::floor(
              (160.0 + ((double)near_m1 / 4096.0) * 300.0 / near_z) * 65536.0)) <= 1);
        CHECK(std::abs(y - (int32_t)std::floor(
              (120.0 + ((double)near_m2 / 4096.0) * 300.0 / near_z) * 65536.0)) <= 1);

        pgxp_set_preserve_projection(saved_preserve);
    }

'''

def transform_cpp(text: str) -> str:
    marker = 'extern "C" int pgxp_project_precise(int64_t mac1, int64_t mac2, int64_t mac3,'
    start = text.find(marker)
    end_marker = chr(10) + "}" + chr(10) + chr(10) + "/* Defined below with the GPU consumer. */"
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        if "int shift, int lm, int32_t ir1" in text and "const double min_depth" in text:
            return text
        raise RuntimeError("Could not locate upstream PGXP projection helper.")
    if "int shift, int lm, int32_t ir1" in text[start:end] and "const double min_depth" in text[start:end]:
        return text
    return text[:start] + NEW_FUNCTION + text[end + 2:]


def transform_header(text: str) -> str:
    start_marker = "/* The exact projection for preserve-projection mode, in the 16.16 screen"
    end_marker = "/* Whether an exact projection may be the shadow of the SXY word"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        if "int lm, int32_t ir1" in text and "hardware divider's H/2 near-depth floor" in text:
            return text
        raise RuntimeError("Could not locate upstream PGXP projection declaration.")
    return text[:start] + NEW_DECLARATION + text[end:]


def add_lm_arguments(text: str) -> str:
    """Insert LM=0 into legacy test calls; leave already-migrated calls alone."""
    needle = "pgxp_project_precise("
    positions = []
    cursor = 0
    while True:
        start = text.find(needle, cursor)
        if start < 0:
            break
        open_paren = start + len(needle) - 1
        depth = 1
        in_string = False
        escaped = False
        commas = []
        end = -1
        i = open_paren + 1
        while i < len(text):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
                elif ch == ',' and depth == 1:
                    commas.append(i)
            i += 1
        if end < 0:
            raise RuntimeError("Unclosed pgxp_project_precise test call.")
        arg_count = len(commas) + 1
        if arg_count == 14:
            positions.append(commas[3])
        elif arg_count != 15:
            raise RuntimeError(f"Unexpected pgxp_project_precise test argument count: {arg_count}")
        cursor = end + 1
    for at in reversed(positions):
        text = text[:at] + ", 0" + text[at:]
    return text


def transform_gte(text: str) -> str:
    old = """pgxp_project_precise(mac1, mac2, mac3, shift,
                                     gte->IR1, gte->IR2, gte->SZ[3], gte_h_scaled(gte),
                                     gte->OFX, gte->OFY, x_num, x_den, &ex16, &ey16)"""
    new = """pgxp_project_precise(mac1, mac2, mac3, shift, lm,
                                     gte->IR1, gte->IR2, gte->SZ[3], gte_h_scaled(gte),
                                     gte->OFX, gte->OFY, x_num, x_den, &ex16, &ey16)"""
    if new in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError("Could not locate the single upstream GTE projection call.")
    return text.replace(old, new, 1)


def transform_test(text: str) -> str:
    text = add_lm_arguments(text)
    marker = "    /* --- Ape Escape PGXP refinements: SF=0, LM, and near-depth floor --- */"
    if marker in text:
        return text
    anchor = "    /* --- probe: the same decision, not counted --- */"
    if text.count(anchor) != 1:
        raise RuntimeError("Could not locate the upstream PGXP test insertion point.")
    return text.replace(anchor, EXTENSION_TEST_BLOCK + anchor, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework-root", type=Path, default=Path("psxrecomp-v4"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.framework_root.resolve()
    if not root.is_dir():
        parser.error(f"framework directory does not exist: {root}")
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Could not identify PSXRecomp revision: {exc}") from exc
    if revision != PINNED_FRAMEWORK:
        raise SystemExit(
            f"Refusing to patch PSXRecomp revision {revision}; expected {PINNED_FRAMEWORK}."
        )

    transforms = {
        Path("runtime/src/pgxp.cpp"): transform_cpp,
        Path("runtime/include/pgxp.h"): transform_header,
        Path("runtime/src/gte.cpp"): transform_gte,
        Path("runtime/tests/test_pgxp.cpp"): transform_test,
    }
    failures = []
    changed = []
    for relative, transform in transforms.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"Missing expected file: {relative}")
            continue
        original = path.read_text(encoding="utf-8")
        try:
            updated = transform(original)
        except RuntimeError as exc:
            failures.append(f"{relative}: {exc}")
            continue
        if updated != original:
            if args.check:
                failures.append(f"{relative}: Ape Escape PGXP extension is not applied")
            else:
                path.write_text(updated, encoding="utf-8")
                changed.append(str(relative))
    if failures:
        raise SystemExit(chr(10).join(failures))
    if args.check:
        print("Ape Escape PGXP extension is present on all four framework files.")
    elif changed:
        print("Applied Ape Escape PGXP refinements to: " + ", ".join(changed))
    else:
        print("Ape Escape PGXP refinements already applied; no files changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
