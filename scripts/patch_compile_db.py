#!/usr/bin/env python3
"""Patch compile_commands.json to include kernel headers."""
import json, os, sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "compile_commands.json"
kinclude = os.environ.get("KERNEL_INCLUDE", "")

db = json.load(open(db_path))
for e in db:
    if kinclude and kinclude not in e.get("command", ""):
        e["command"] = e["command"].replace(" -c ", f" -I{kinclude} -c ")

json.dump(db, open(db_path, "w"), indent=2)
print(f"Patched {len(db)} entries in {db_path}")
