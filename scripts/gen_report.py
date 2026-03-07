#!/usr/bin/env python3
"""
gen_report.py
Aggregate all stage artifacts into a single pipeline Markdown report.
"""
import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone


STAGE_ICONS = {
    'pass':    '✅',
    'fail':    '❌',
    'warn':    '⚠️',
    'skip':    '⏭️',
    'unknown': '❓',
}


def read_artifact(path: Path, pattern: str) -> str:
    files = list(path.rglob(pattern))
    if files:
        return files[0].read_text(errors='replace')
    return ""


def detect_status(text: str) -> str:
    if not text:
        return 'skip'
    text_lower = text.lower()
    if any(k in text_lower for k in ['failed', 'error:', 'panic:', 'abi-breaking']):
        return 'fail'
    if any(k in text_lower for k in ['warning', 'warn:']):
        return 'warn'
    if any(k in text_lower for k in ['passed', 'pass:', 'success']):
        return 'pass'
    return 'unknown'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifacts-dir', required=True)
    ap.add_argument('--output',        required=True)
    ap.add_argument('--format',        default='markdown')
    args = ap.parse_args()

    art = Path(args.artifacts_dir)
    ts  = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    sections = []
    sections.append(f"# Linux C→Rust Pipeline Report\n\n_Generated: {ts}_\n")

    # Stage 1: Conversion
    sections.append("## Stage 1: C→Rust Conversion\n")
    for log in sorted(art.rglob('transpile_*.log')):
        stem = log.stem.replace('transpile_', '')
        text = log.read_text(errors='replace')
        unsafe_match = re.search(r'Unsafe block count:\s*(\d+)', text)
        unsafe_count = unsafe_match.group(1) if unsafe_match else 'N/A'
        status = detect_status(text)
        icon = STAGE_ICONS[status]
        sections.append(f"- {icon} `{stem}` — {status.upper()}, unsafe blocks: `{unsafe_count}`")

    sections.append("")

    # Stage 2: Security
    sections.append("## Stage 2: Security Evaluation\n")

    clippy = read_artifact(art, 'clippy_report.txt')
    clippy_status = detect_status(clippy)
    sections.append(f"### Clippy {STAGE_ICONS[clippy_status]}\n")
    if clippy:
        err_count = clippy.count('error[')
        warn_count = clippy.count('warning[')
        sections.append(f"- Errors: `{err_count}`, Warnings: `{warn_count}`")

    geiger = read_artifact(art, 'geiger_summary.txt')
    geiger_status = detect_status(geiger)
    sections.append(f"\n### Unsafe Audit (cargo-geiger) {STAGE_ICONS[geiger_status]}\n")
    if geiger:
        sections.append(f"```\n{geiger[:1000]}\n```")

    audit = read_artifact(art, 'audit_report.json')
    if audit:
        try:
            audit_data = json.loads(audit)
            vulns = audit_data.get('vulnerabilities', {}).get('count', 0)
            audit_status = 'fail' if vulns > 0 else 'pass'
        except Exception:
            audit_status = detect_status(audit)
            vulns = 'N/A'
        sections.append(f"\n### Vulnerability Scan {STAGE_ICONS[audit_status]}\n")
        sections.append(f"- Known vulnerabilities: `{vulns}`")

    miri = read_artifact(art, 'miri_report.txt')
    miri_status = detect_status(miri)
    sections.append(f"\n### Miri (UB detection) {STAGE_ICONS[miri_status]}\n")
    if miri:
        ub_count = miri.count('UNDEFINED BEHAVIOR')
        sections.append(f"- UB instances: `{ub_count}`")

    sections.append("")

    # Stage 3: Compatibility
    sections.append("## Stage 3: Compatibility\n")

    abi = read_artifact(art, 'abi_diff.log')
    abi_status = detect_status(abi) if abi else 'skip'
    sections.append(f"### ABI Diff {STAGE_ICONS[abi_status]}")
    if 'ABI-BREAKING' in (abi or ''):
        breaking = re.findall(r'!! (.+)', abi)
        for b in breaking[:10]:
            sections.append(f"  - ❌ {b}")

    sym = read_artifact(art, 'symbol_compat.log')
    sym_status = detect_status(sym) if sym else 'skip'
    sections.append(f"\n### Symbol Compatibility {STAGE_ICONS[sym_status]}")

    for arch in ['x86_64', 'arm64', 'riscv64']:
        integ = read_artifact(art, f'integration_{arch}.log')
        if integ:
            st = detect_status(integ)
            sections.append(f"\n### Integration Tests ({arch}) {STAGE_ICONS[st]}")

    for arch in ['x86_64', 'arm64']:
        kbuild = read_artifact(art, f'kbuild_{arch}.log')
        if kbuild:
            st = detect_status(kbuild)
            sections.append(f"\n### Kbuild ({arch}) {STAGE_ICONS[st]}")

    sections.append("")

    # Stage 4: Build & Test
    sections.append("## Stage 4: Build & Boot Test\n")

    for arch in ['x86_64', 'arm64', 'riscv64']:
        build_log = read_artifact(art, f'build_{arch}.log')
        if build_log:
            st = detect_status(build_log)
            sections.append(f"### Kernel Build ({arch}) {STAGE_ICONS[st]}")

    kunit = read_artifact(art, 'kunit_results.log')
    if kunit:
        passed = kunit.count('ok -')
        failed = kunit.count('not ok')
        kunit_status = 'fail' if failed > 0 else 'pass'
        sections.append(f"\n### KUnit Tests {STAGE_ICONS[kunit_status]}")
        sections.append(f"- Passed: `{passed}`, Failed: `{failed}`")

    for arch in ['x86_64', 'arm64']:
        boot_log = read_artifact(art, f'boot_log_{arch}.txt')
        if boot_log:
            boot_pass = 'Boot test PASSED' in boot_log
            boot_panic = any(k in boot_log for k in ['Kernel panic', 'BUG:', 'Oops:'])
            st = 'fail' if boot_panic or not boot_pass else 'pass'
            sections.append(f"\n### QEMU Boot Test ({arch}) {STAGE_ICONS[st]}")
            if boot_panic:
                sections.append("  - ❌ Kernel panic/oops detected")

    # Overall summary
    all_text = '\n'.join(sections)
    fail_count = all_text.count(STAGE_ICONS['fail'])
    warn_count = all_text.count(STAGE_ICONS['warn'])
    overall = 'FAILED' if fail_count > 0 else ('WARNED' if warn_count > 0 else 'PASSED')
    icon = STAGE_ICONS['fail'] if fail_count > 0 else \
           STAGE_ICONS['warn'] if warn_count > 0 else \
           STAGE_ICONS['pass']

    sections.append(f"\n---\n## Overall: {icon} {overall}")
    sections.append(f"- Critical failures: `{fail_count}`")
    sections.append(f"- Warnings: `{warn_count}`")

    Path(args.output).write_text('\n'.join(sections))
    print(f"Report written to {args.output}")


if __name__ == '__main__':
    main()
