#!/usr/bin/env python3
"""
parse_geiger.py
Parse cargo-geiger JSON output and enforce unsafe code thresholds.
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('report')
    ap.add_argument('--threshold-unsafe-fns',   type=int, default=100)
    ap.add_argument('--threshold-unsafe-exprs',  type=int, default=500)
    ap.add_argument('--fail-on-exceed',          action='store_true')
    args = ap.parse_args()

    data = json.loads(Path(args.report).read_text())

    total_unsafe_fns   = 0
    total_unsafe_exprs = 0
    packages = []

    # cargo-geiger JSON structure varies by version; handle common layouts
    pkgs = data.get('packages', data.get('crates', []))
    for pkg in pkgs:
        name = pkg.get('package', {}).get('name', pkg.get('name', 'unknown'))
        counters = pkg.get('unsafety', {})

        used = counters.get('used', {})
        fns    = used.get('functions', {}).get('unsafe', 0)
        exprs  = used.get('exprs',     {}).get('unsafe', 0)

        total_unsafe_fns   += fns
        total_unsafe_exprs += exprs

        if fns > 0 or exprs > 0:
            packages.append((name, fns, exprs))

    print(f"{'Package':<40} {'Unsafe Fns':>12} {'Unsafe Exprs':>14}")
    print("-" * 68)
    for name, fns, exprs in sorted(packages, key=lambda x: -x[1]):
        marker = " ⚠" if fns > 10 or exprs > 50 else ""
        print(f"{name:<40} {fns:>12} {exprs:>14}{marker}")
    print("-" * 68)
    print(f"{'TOTAL':<40} {total_unsafe_fns:>12} {total_unsafe_exprs:>14}")

    exceeded = False
    if total_unsafe_fns > args.threshold_unsafe_fns:
        print(f"\nWARN: Unsafe function count {total_unsafe_fns} "
              f"exceeds threshold {args.threshold_unsafe_fns}")
        exceeded = True
    if total_unsafe_exprs > args.threshold_unsafe_exprs:
        print(f"\nWARN: Unsafe expression count {total_unsafe_exprs} "
              f"exceeds threshold {args.threshold_unsafe_exprs}")
        exceeded = True

    if exceeded and args.fail_on_exceed:
        print("\nFAIL: Unsafe code thresholds exceeded.")
        sys.exit(1)
    else:
        print("\nPASS: Unsafe code within acceptable thresholds.")


if __name__ == '__main__':
    main()
