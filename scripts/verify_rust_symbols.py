#!/usr/bin/env python3
"""Verify that expected Rust symbols are present in vmlinux."""
import sys, argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True)
    args = parser.parse_args()

    nm_output = sys.stdin.read()
    present = set(nm_output.split())

    try:
        expected = [l.strip() for l in open(args.expected) if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        print(f"Warning: {args.expected} not found, skipping symbol check")
        return

    missing = [s for s in expected if s not in present]
    if missing:
        print(f"MISSING SYMBOLS ({len(missing)}):")
        for s in missing:
            print(f"  - {s}")
        sys.exit(1)
    else:
        print(f"All {len(expected)} expected Rust symbols present.")

if __name__ == "__main__":
    main()
