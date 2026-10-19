#!/usr/bin/env python3
"""Apply the clean-room PGXP projection correction to the pinned PSXRecomp tree."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

PINNED_FRAMEWORK = "4102438ab4c5aadf010878029d0324ef6382e521"

NEW_FUNCTION = r'''extern "C" int pgxp_project_precise(int64_t mac1, int64_t mac2, int64_t mac3,
                                    int shift, int lm, uint32_t h,
                                    int32_t ofx, int32_t ofy,
                                    int64_t x_num, int64_t x_den,
                                    int32_t *x16, int32_t *y16) {
    /* Reconstruct the sub-pixel projection from the GTE's unshifted MACs.
     * MAC1/2 use the selected SF scale; MAC3 remains Q12 for SZ/depth. Keep
     * both legal GTE SF modes, and mirror its IR saturation before projection.
     * This is shadow-only: the guest's integer registers and FLAG are final. */
    if ((shift != 0 && shift != 12) || x_den <= 0) return 0;
    const double unit = shift != 0 ? 4096.0 : 1.0;
    double irx = (double)mac1 / unit;
    double iry = (double)mac2 / unit;

    /* LM=1 clamps IR to [0, 32767]; LM=0 clamps it to [-32768, 32767]. */
    if (lm) {
        if (irx < 0.0) irx = 0.0;
        if (iry < 0.0) iry = 0.0;
    } else {
        if (irx < -32768.0) irx = -32768.0;
        if (iry < -32768.0) iry = -32768.0;
    }
    if (irx > 32767.0) irx = 32767.0;
    if (iry > 32767.0) iry = 32767.0;

    /* The hardware H/SZ divider is capped at 2. Using H/2 as the minimum
     * depth preserves sub-pixel information for near-camera vertices without
     * changing guest-visible state. A nonpositive depth is degenerate only
     * when H is also zero, so fail closed in that case. */
    const double depth = (double)mac3 / 4096.0;
    const double z = depth > (double)h * 0.5 ? depth : (double)h * 0.5;
    if (!(z > 0.0)) return 0;

    const double k = (double)h * 65536.0 / z;
    double fx = (double)ofx + irx * k * (double)x_num / (double)x_den;
    double fy = (double)ofy + iry * k;

    /* Keep the same bounded 16.16 transport range as the GTE path. */
    const double lim = 4096.0 * 65536.0;
    if (fx < -lim) fx = -lim;
    if (fx > lim - 1.0) fx = lim - 1.0;
    if (fy < -lim) fy = -lim;
    if (fy > lim - 1.0) fy = lim - 1.0;
    *x16 = (int32_t)std::floor(fx);
    *y16 = (int32_t)std::floor(fy);
    return 1;
}'''

NEW_DECLARATION = '''/* Exact, host-only projection for preserve-projection mode. Inputs are the
 * unshifted GTE MAC1..3, the SF shift (0 or 12), limit-mode LM, H, OFX/OFY,
 * and the horizontal factor x_num/x_den (1/1 in normal 4:3). Reconstructs
 * fractional IR values with the GTE saturation limits and applies the
 * hardware divider's H/2 near-depth floor. This changes no guest register;
 * pgxp_ppp_accept() validates the result against the actual packet word. */
int pgxp_project_precise(int64_t mac1, int64_t mac2, int64_t mac3,
                         int shift, int lm, uint32_t h,
                         int32_t ofx, int32_t ofy, int64_t x_num, int64_t x_den,
                         int32_t *x16, int32_t *y16);

'''

NEW_TEST_BLOCK = r'''    /* --- pgxp_project_precise: GTE limits, near depth, and both SF modes --- */
    {
        const int32_t ofx = 160 << 16, ofy = 120 << 16;
        int32_t x = 0, y = 0;

        /* Ordinary SF=1 projection retains fractional MAC bits. */
        const int64_t m1 = 100 * 4096 + 1234;
        const int64_t m2 = -50 * 4096 + 777;
        const int64_t m3 = 1000 * 4096 + 2048;
        CHECK(pgxp_project_precise(m1, m2, m3, 12, 0, 300, ofx, ofy,
                                   1, 1, &x, &y) == 1);
        const double ex = 160.0 + (double)m1 * 300.0 / (double)m3;
        const double ey = 120.0 + (double)m2 * 300.0 / (double)m3;
        CHECK(x == (int32_t)std::floor(ex * 65536.0));
        CHECK(y == (int32_t)std::floor(ey * 65536.0));

        /* Widescreen scales only the projected X offset, not OFX. */
        int32_t xs = 0, ys = 0;
        CHECK(pgxp_project_precise(m1, m2, m3, 12, 0, 300, ofx, ofy,
                                   3, 4, &xs, &ys) == 1);
        CHECK(ys == y);
        CHECK(xs == (int32_t)std::floor((160.0 +
                                         (double)m1 * 300.0 / (double)m3 * 0.75) *
                                        65536.0));

        /* SF=0 uses its unshifted MAC scale instead of rejecting the vertex. */
        CHECK(pgxp_project_precise(1000, -500, 1000 * 4096LL, 0, 0, 300,
                                   ofx, ofy, 1, 1, &x, &y) == 1);
        CHECK(x == (int32_t)std::floor(460.0 * 65536.0));
        CHECK(y == (int32_t)std::floor(-30.0 * 65536.0));

        /* A depth below H/2 uses the GTE's capped divide rather than falling
         * back to the integer IR projection. */
        CHECK(pgxp_project_precise(100 * 4096LL, -50 * 4096LL, 100 * 4096LL,
                                   12, 0, 300, ofx, ofy, 1, 1, &x, &y) == 1);
        CHECK(x == (int32_t)std::floor(360.0 * 65536.0));
        CHECK(y == (int32_t)std::floor(20.0 * 65536.0));

        /* Match LM's coordinate limits before projecting saturated IRs. */
        CHECK(pgxp_project_precise(40000 * 4096LL, -40000 * 4096LL,
                                   1000 * 4096LL, 12, 1, 1, ofx, ofy,
                                   1, 1, &x, &y) == 1);
        CHECK(x == (int32_t)std::floor((160.0 + 32767.0 / 1000.0) * 65536.0));
        CHECK(y == (int32_t)std::floor(120.0 * 65536.0));
        CHECK(pgxp_project_precise(-40000 * 4096LL, 40000 * 4096LL,
                                   1000 * 4096LL, 12, 0, 1, ofx, ofy,
                                   1, 1, &x, &y) == 1);
        CHECK(x == (int32_t)std::floor((160.0 - 32768.0 / 1000.0) * 65536.0));
        CHECK(y == (int32_t)std::floor((120.0 + 32767.0 / 1000.0) * 65536.0));

        /* Values above the 16-bit SZ range still yield a candidate; packet-word
         * validation remains the final acceptance gate. */
        const int64_t large_z = (int64_t)0x12345 << 12;
        CHECK(pgxp_project_precise(100 * 4096LL, -50 * 4096LL, large_z,
                                   12, 0, 300, ofx, ofy, 1, 1, &x, &y) == 1);
        CHECK(x == (int32_t)std::floor((160.0 + 100.0 * 300.0 / 0x12345) *
                                       65536.0));
        CHECK(y == (int32_t)std::floor((120.0 - 50.0 * 300.0 / 0x12345) *
                                       65536.0));

        /* Zero H projects to the screen offset for positive depth. */
        CHECK(pgxp_project_precise(m1, m2, m3, 12, 0, 0, ofx, ofy,
                                   1, 1, &x, &y) == 1);
        CHECK(x == ofx && y == ofy);

        /* Fail closed on unsupported SF or a nonpositive horizontal factor. */
        CHECK(pgxp_project_precise(m1, m2, m3, 6, 0, 300, ofx, ofy,
                                   1, 1, &x, &y) == 0);
        CHECK(pgxp_project_precise(m1, m2, m3, 12, 0, 300, ofx, ofy,
                                   1, 0, &x, &y) == 0);
    }

'''

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 0:
        if new in text:
            return text
        raise RuntimeError(f"Expected source anchor for {label} was not found; refusing to patch unknown upstream code.")
    if count != 1:
        raise RuntimeError(f"Expected one source anchor for {label}, found {count}.")
    return text.replace(old, new, 1)

def transform_cpp(text: str) -> str:
    marker = 'extern "C" int pgxp_project_precise(int64_t mac1, int64_t mac2, int64_t mac3,'
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("Could not locate the pinned PGXP projection helper.")
    end = text.find("\n/* Defined below with the GPU consumer. */", start)
    if end < 0:
        raise RuntimeError("Could not locate the PGXP projection helper terminator.")
    current = text[start:end]
    if "const double depth = (double)mac3 / 4096.0;" in current and "int shift, int lm, uint32_t h," in current:
        return text
    return text[:start] + NEW_FUNCTION + text[end:]

def transform_header(text: str) -> str:
    start_marker = "/* The exact projection for preserve-projection mode, in the 16.16 screen"
    end_marker = "/* Whether an exact projection may be the shadow of the SXY word"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        if "int shift, int lm, uint32_t h," in text and "hardware divider's H/2 near-depth floor" in text:
            return text
        raise RuntimeError("Could not locate the pinned PGXP projection API declaration.")
    return text[:start] + NEW_DECLARATION + text[end:]

def transform_gte(text: str) -> str:
    old = """pgxp_project_precise(mac1, mac2, mac3, shift, gte->IR1, gte->IR2,
                                     gte->SZ[3], gte_h_scaled(gte), gte->OFX, gte->OFY,
                                     x_num, x_den, &ex16, &ey16)"""
    new = """pgxp_project_precise(mac1, mac2, mac3, shift, lm,
                                     gte_h_scaled(gte), gte->OFX, gte->OFY,
                                     x_num, x_den, &ex16, &ey16)"""
    return replace_once(text, old, new, "GTE projection call")

def transform_test(text: str) -> str:
    start_marker = "    /* --- pgxp_project_precise: the exact projection and its qualifiers --- */"
    end_marker = "    /* --- probe: the same decision, not counted --- */"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        if "GTE limits, near depth, and both SF modes" in text:
            return text
        raise RuntimeError("Could not locate the existing PGXP projection tests.")
    return text[:start] + NEW_TEST_BLOCK + text[end:]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework-root", type=Path, default=Path("psxrecomp-v4"))
    parser.add_argument("--check", action="store_true", help="fail if the patch is not already applied")
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
        raise SystemExit(f"Could not identify the PSXRecomp submodule revision: {exc}") from exc
    if revision != PINNED_FRAMEWORK:
        raise SystemExit(
            f"Refusing to patch unexpected PSXRecomp revision {revision}; expected {PINNED_FRAMEWORK}."
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
                failures.append(f"{relative}: PGXP projection patch is not applied")
            else:
                path.write_text(updated, encoding="utf-8")
                changed.append(str(relative))
    if failures:
        raise SystemExit("\n".join(failures))
    if args.check:
        print("PGXP projection patch is present on all four pinned framework files.")
    elif changed:
        print("Applied PGXP projection correction to: " + ", ".join(changed))
    else:
        print("PGXP projection correction already applied; no files changed.")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
