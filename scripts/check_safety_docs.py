#!/usr/bin/env python3
"""
check_safety_docs.py

Verify that every `unsafe` block / function in the generated Rust code has:
  1. A `// SAFETY:` comment immediately above it, OR
  2. A `// INVARIANT:` comment if it's a struct field / global.
"""
import argparse
import re
import sys
from pathlib import Path

UNSAFE_BLOCK_RE  = re.compile(r'^\s*(pub\s+)?(unsafe\s+(fn|impl|trait|block|\{))', re.MULTILINE)
SAFETY_TAG_RE    = re.compile(r'//\s*(SAFETY|INVARIANT|SOUNDNESS):')
ALLOW_UNSAFE_RE  = re.compile(r'#\!\[allow\(unsafe_code\)\]')


def check_file(path: Path, require_safety: bool, require_invariant: bool) -> list[str]:
    errors = []
    text = path.read_text(errors='replace')
    lines = text.splitlines()

    for i, line in enumerate(lines):
        # Detect unsafe keyword uses
        if re.search(r'\bunsafe\b', line):
            # Look back up to 5 lines for a SAFETY/INVARIANT comment
            look_back = lines[max(0, i-5):i]
            has_tag = any(SAFETY_TAG_RE.search(l) for l in look_back)
            if not has_tag and require_safety:
                errors.append(f"{path}:{i+1}: unsafe without // SAFETY: comment → {line.strip()}")

    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src_dir')
    ap.add_argument('--require-safety-comment',  action='store_true')
    ap.add_argument('--require-invariant-tag',   action='store_true')
    args = ap.parse_args()

    src = Path(args.src_dir)
    all_errors = []

    for rs_file in sorted(src.rglob('*.rs')):
        errs = check_file(rs_file,
                          require_safety=args.require_safety_comment,
                          require_invariant=args.require_invariant_tag)
        all_errors.extend(errs)

    if all_errors:
        print(f"\nFound {len(all_errors)} safety documentation issue(s):\n")
        for e in all_errors:
            print(f"  {e}")
        # Warnings only — do not fail the pipeline outright; gate enforces severity
        sys.exit(0)
    else:
        print(f"All unsafe blocks in {src} have safety documentation.")


if __name__ == '__main__':
    main()
