#!/usr/bin/env python3
"""
validate_boot_log.py
Parse a QEMU serial log and verify expected boot success markers.
"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log_file')
    ap.add_argument('--expect-string',  action='append', default=[])
    ap.add_argument('--forbid-strings', action='append', default=[])
    args = ap.parse_args()

    log = Path(args.log_file).read_text(errors='replace')
    lines = log.splitlines()

    errors = []
    warnings = []

    # Check for forbidden strings (kernel panic, oops, etc.)
    for forbidden in args.forbid_strings:
        matching = [l for l in lines if forbidden.lower() in l.lower()]
        if matching:
            errors.append(f"FORBIDDEN string '{forbidden}' found:")
            for m in matching[:5]:
                errors.append(f"  {m}")

    # Check for expected strings (boot test PASSED)
    for expected in args.expect_string:
        if not any(expected.lower() in l.lower() for l in lines):
            errors.append(f"Expected string '{expected}' NOT found in boot log")

    # Summary stats
    total_lines = len(lines)
    rust_lines  = sum(1 for l in lines if 'rust' in l.lower())
    print(f"Boot log: {total_lines} lines, {rust_lines} mention 'rust'")

    if errors:
        print(f"\nBoot validation FAILED ({len(errors)} issue(s)):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("Boot validation PASSED")


if __name__ == '__main__':
    main()
