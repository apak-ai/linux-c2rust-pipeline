#!/usr/bin/env python3
"""
abi_diff.py  --  Detect ABI-breaking changes between two bindgen snapshots.

An ABI break is defined as:
  - A struct/union field being removed or renamed
  - A function signature changing (return type or parameter types)
  - A type's size changing (detected via layout comments bindgen emits)
  - A constant value changing (kernel ABI-stable constants)
"""
import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Struct:
    name: str
    fields: list[str] = field(default_factory=list)
    size_comment: str = ""


@dataclass
class Function:
    name: str
    signature: str


@dataclass
class Constant:
    name: str
    value: str


STRUCT_RE = re.compile(r'^pub struct (\w+)\s*\{')
FIELD_RE  = re.compile(r'^\s+pub (\w+)\s*:\s*(.+),')
FN_RE     = re.compile(r'^pub (?:unsafe )?(?:extern "C" )?fn (\w+)\s*\(([^)]*)\)\s*(?:->\s*(\S+))?')
CONST_RE  = re.compile(r'^pub const (\w+)\s*:\s*\w+\s*=\s*(.+);')
SIZE_RE   = re.compile(r'//\s*size:\s*(\d+)')


def parse_bindings(path: Path) -> tuple[dict, dict, dict]:
    structs: dict[str, Struct] = {}
    functions: dict[str, Function] = {}
    constants: dict[str, Constant] = {}
    current_struct = None

    for line in path.read_text().splitlines():
        m = STRUCT_RE.match(line)
        if m:
            current_struct = Struct(name=m.group(1))
            structs[current_struct.name] = current_struct
            continue

        if current_struct:
            fm = FIELD_RE.match(line)
            if fm:
                current_struct.fields.append(f"{fm.group(1)}: {fm.group(2)}")
            sm = SIZE_RE.search(line)
            if sm:
                current_struct.size_comment = sm.group(1)
            if line.strip() == '}':
                current_struct = None
            continue

        fm = FN_RE.match(line)
        if fm:
            sig = f"({fm.group(2)}) -> {fm.group(3) or 'void'}"
            functions[fm.group(1)] = Function(fm.group(1), sig)

        cm = CONST_RE.match(line)
        if cm:
            constants[cm.group(1)] = Constant(cm.group(1), cm.group(2))

    return structs, functions, constants


def diff_bindings(old_path: Path, new_path: Path, fail_on_breaking: bool) -> bool:
    old_structs, old_fns, old_consts = parse_bindings(old_path)
    new_structs, new_fns, new_consts = parse_bindings(new_path)

    breaking: list[str] = []
    warnings: list[str] = []

    # Struct changes
    for name, old_s in old_structs.items():
        if name not in new_structs:
            breaking.append(f"REMOVED struct: {name}")
            continue
        new_s = new_structs[name]
        for f in old_s.fields:
            if f not in new_s.fields:
                breaking.append(f"FIELD REMOVED/CHANGED in {name}: {f}")
        if old_s.size_comment and new_s.size_comment:
            if old_s.size_comment != new_s.size_comment:
                breaking.append(f"SIZE CHANGED {name}: {old_s.size_comment} → {new_s.size_comment}")

    # Function signature changes
    for name, old_fn in old_fns.items():
        if name not in new_fns:
            breaking.append(f"REMOVED function: {name}")
        elif old_fn.signature != new_fns[name].signature:
            breaking.append(f"SIGNATURE CHANGED {name}:"
                            f"\n  old: {old_fn.signature}"
                            f"\n  new: {new_fns[name].signature}")

    # New functions/structs = additions (not breaking)
    for name in new_structs:
        if name not in old_structs:
            warnings.append(f"NEW struct: {name}")
    for name in new_fns:
        if name not in old_fns:
            warnings.append(f"NEW function: {name}")

    # Constant value changes (potentially breaking for ABI-stable values)
    for name, old_c in old_consts.items():
        if name in new_consts and old_c.value != new_consts[name].value:
            breaking.append(f"CONSTANT VALUE CHANGED {name}: {old_c.value!r} → {new_consts[name].value!r}")

    if warnings:
        print("\nAdditions (non-breaking):")
        for w in warnings:
            print(f"  + {w}")

    if breaking:
        print(f"\nABI-BREAKING CHANGES ({len(breaking)}):")
        for b in breaking:
            print(f"  !! {b}")
        if fail_on_breaking:
            return False
    else:
        print("\nNo ABI-breaking changes detected.")

    return True


def main():
    ap = argparse.ArgumentParser(description='Compare bindgen ABI snapshots')
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--fail-on-breaking', action='store_true')
    args = ap.parse_args()

    ok = diff_bindings(Path(args.old), Path(args.new), args.fail_on_breaking)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
