#!/usr/bin/env python3
"""
evaluate_pipeline.py
Final pipeline pass/fail decision based on all collected artifacts.
"""
import argparse
import sys
from pathlib import Path


def check_dir(art: Path, pattern: str, bad_strings: list[str]) -> tuple[bool, list[str]]:
    issues = []
    for f in art.rglob(pattern):
        text = f.read_text(errors='replace')
        for bad in bad_strings:
            if bad.lower() in text.lower():
                issues.append(f"{f.name}: contains '{bad}'")
    return len(issues) == 0, issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifacts-dir',          required=True)
    ap.add_argument('--fail-on-security-issues', action='store_true')
    ap.add_argument('--fail-on-compat-failures', action='store_true')
    ap.add_argument('--fail-on-boot-failure',    action='store_true')
    args = ap.parse_args()

    art = Path(args.artifacts_dir)
    all_issues = []
    pipeline_ok = True

    # Security checks
    if args.fail_on_security_issues:
        ok, issues = check_dir(art, 'clippy_report.txt',
                               ['error[', 'error: aborting'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[SECURITY/clippy] {i}" for i in issues])

        ok, issues = check_dir(art, 'audit_report.json',
                               ['"count": [^0]', '"vulnerabilities"'])
        # audit failures handled differently
        for f in art.rglob('audit_report.json'):
            import json
            try:
                data = json.loads(f.read_text())
                vulns = data.get('vulnerabilities', {}).get('count', 0)
                if vulns and int(str(vulns)) > 0:
                    pipeline_ok = False
                    all_issues.append(f"[SECURITY/audit] {vulns} known vulnerabilities")
            except Exception:
                pass

        ok, issues = check_dir(art, 'miri_report.txt', ['UNDEFINED BEHAVIOR'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[SECURITY/miri] {i}" for i in issues])

        ok, issues = check_dir(art, 'policy_report.txt', ['FAIL:', 'RESULT: FAILED'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[SECURITY/policy] {i}" for i in issues])

    # Compatibility checks
    if args.fail_on_compat_failures:
        ok, issues = check_dir(art, 'abi_diff.log', ['ABI-BREAKING CHANGES'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[COMPAT/abi] {i}" for i in issues])

        ok, issues = check_dir(art, 'symbol_compat.log', ['MISSING SYMBOLS'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[COMPAT/symbols] {i}" for i in issues])

        ok, issues = check_dir(art, 'kbuild_*.log', ['error:', 'Error 1', 'FAILED'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[COMPAT/kbuild] {i}" for i in issues])

    # Boot checks
    if args.fail_on_boot_failure:
        ok, issues = check_dir(art, 'boot_log_*.txt',
                               ['Kernel panic', 'BUG:', 'Oops:', 'WARNING:'])
        if not ok:
            pipeline_ok = False
            all_issues.extend([f"[BOOT/panic] {i}" for i in issues])

        for f in art.rglob('boot_log_*.txt'):
            if 'Boot test PASSED' not in f.read_text(errors='replace'):
                pipeline_ok = False
                all_issues.append(f"[BOOT] {f.name}: 'Boot test PASSED' not found")

    # Final verdict
    print("\n" + "="*60)
    if pipeline_ok and not all_issues:
        print("PIPELINE RESULT: ALL CHECKS PASSED")
        print("="*60)
        sys.exit(0)
    else:
        print(f"PIPELINE RESULT: FAILED ({len(all_issues)} issue(s))")
        print("="*60)
        for issue in all_issues:
            print(f"  !! {issue}")
        sys.exit(1)


if __name__ == '__main__':
    main()
