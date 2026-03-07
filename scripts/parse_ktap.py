#!/usr/bin/env python3
"""
parse_ktap.py
Parse KTAP output from KUnit and convert to JUnit XML.
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


PLAN_RE   = re.compile(r'^TAP version|^1\.\.(\d+)')
RESULT_RE = re.compile(r'^(ok|not ok)\s+(\d+)\s+-\s+(.+?)(?:\s+#\s+(.+))?$')
SUBTEST_RE = re.compile(r'^\s+#\s+(.+)')


def parse_ktap(text: str):
    suites = []
    current_suite = None
    tests = []

    for line in text.splitlines():
        # Suite header: "# Subtest: suite_name"
        m = re.match(r'^\s+# Subtest:\s+(.+)', line)
        if m:
            if current_suite and tests:
                suites.append((current_suite, tests))
            current_suite = m.group(1).strip()
            tests = []
            continue

        # Test result line
        m = RESULT_RE.match(line.strip())
        if m:
            status, num, name, directive = m.groups()
            skip = bool(directive and 'SKIP' in directive.upper())
            tests.append({
                'status':    status,
                'num':       int(num),
                'name':      name.strip(),
                'directive': directive,
                'skip':      skip,
            })

    if current_suite and tests:
        suites.append((current_suite, tests))

    return suites


def to_junit(suites, output_path: Path):
    root = ET.Element('testsuites')

    total_pass = total_fail = total_skip = 0

    for suite_name, tests in suites:
        passed = sum(1 for t in tests if t['status'] == 'ok' and not t['skip'])
        failed = sum(1 for t in tests if t['status'] == 'not ok')
        skipped = sum(1 for t in tests if t['skip'])
        total_pass += passed
        total_fail += failed
        total_skip += skipped

        ts = ET.SubElement(root, 'testsuite',
                           name=suite_name,
                           tests=str(len(tests)),
                           failures=str(failed),
                           skipped=str(skipped))
        for t in tests:
            tc = ET.SubElement(ts, 'testcase',
                               name=t['name'],
                               classname=suite_name)
            if t['status'] == 'not ok':
                fail = ET.SubElement(tc, 'failure', message='Test failed')
                fail.text = f"KUnit test '{t['name']}' failed"
            elif t['skip']:
                ET.SubElement(tc, 'skipped',
                              message=t['directive'] or 'SKIP')

    root.set('tests',    str(total_pass + total_fail + total_skip))
    root.set('failures', str(total_fail))
    root.set('skipped',  str(total_skip))

    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    tree.write(output_path, encoding='unicode', xml_declaration=True)
    return total_pass, total_fail, total_skip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log_file')
    ap.add_argument('--junit-output', required=True)
    ap.add_argument('--fail-on-error', action='store_true')
    args = ap.parse_args()

    text = Path(args.log_file).read_text(errors='replace')
    suites = parse_ktap(text)

    if not suites:
        print("WARNING: No KTAP test results found in log")
        # Write empty JUnit
        root = ET.Element('testsuites', tests='0', failures='0', skipped='0')
        ET.ElementTree(root).write(args.junit_output,
                                   encoding='unicode',
                                   xml_declaration=True)
        return

    passed, failed, skipped = to_junit(suites, Path(args.junit_output))
    print(f"KUnit results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"JUnit XML written to {args.junit_output}")

    if failed > 0 and args.fail_on_error:
        sys.exit(1)


if __name__ == '__main__':
    main()
