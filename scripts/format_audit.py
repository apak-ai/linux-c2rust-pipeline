#!/usr/bin/env python3
"""Format cargo audit JSON report into a readable summary."""
import json, sys

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "audit_report.json"
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: could not parse audit report: {e}")
        return

    vulns = data.get("vulnerabilities", {})
    found = vulns.get("found", [])
    count = vulns.get("count", len(found))

    warnings = data.get("warnings", {})
    yanked  = warnings.get("yanked", [])
    unsound = warnings.get("unsound", [])

    print(f"### cargo audit summary")
    print(f"- Vulnerabilities: {count}")
    print(f"- Yanked crates:   {len(yanked)}")
    print(f"- Unsound crates:  {len(unsound)}")

    if found:
        print("\n#### Vulnerabilities")
        for v in found:
            adv = v.get("advisory", {})
            pkg = v.get("package", {})
            print(f"  - [{adv.get('id', 'N/A')}] {pkg.get('name', '?')} {pkg.get('version', '?')}: {adv.get('title', 'No title')}")

    if yanked:
        print("\n#### Yanked crates")
        for w in yanked:
            pkg = w.get("package", {})
            print(f"  - {pkg.get('name', '?')} {pkg.get('version', '?')}")

    if unsound:
        print("\n#### Unsound crates")
        for w in unsound:
            pkg = w.get("package", {})
            print(f"  - {pkg.get('name', '?')} {pkg.get('version', '?')}")

if __name__ == "__main__":
    main()
