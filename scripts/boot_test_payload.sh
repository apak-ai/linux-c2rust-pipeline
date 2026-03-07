#!/bin/sh
# boot_test_payload.sh
# Runs inside the QEMU VM to validate that Rust kernel modules are functional.
# Must output "Boot test PASSED" on success (checked by validate_boot_log.py).
set -e

PASS=0
FAIL=0

check() {
    local desc="$1"
    local result="$2"
    if [ "$result" = "ok" ]; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "--- Rust Module Boot Tests ---"

# Test 1: Verify Rust module presence in /proc/modules
if grep -q 'rust_' /proc/modules 2>/dev/null; then
    check "Rust modules loaded" "ok"
else
    # Modules may be built-in; check sysfs
    if [ -d /sys/module ] && ls /sys/module/ | grep -q 'rust_'; then
        check "Rust modules loaded (built-in)" "ok"
    else
        check "Rust modules loaded" "fail"
    fi
fi

# Test 2: Check dmesg for Rust initialization messages
dmesg_output=$(dmesg 2>/dev/null || cat /dev/kmsg 2>/dev/null || echo "")
if echo "$dmesg_output" | grep -q 'Rust'; then
    check "Rust initialization in dmesg" "ok"
else
    check "Rust initialization in dmesg" "fail"
fi

# Test 3: No oops/panics in dmesg
if echo "$dmesg_output" | grep -qE 'Oops:|Kernel panic|BUG:'; then
    check "No kernel oops/panic" "fail"
else
    check "No kernel oops/panic" "ok"
fi

# Test 4: Validate /proc/kallsyms contains Rust symbols
if grep -q 'rust_' /proc/kallsyms 2>/dev/null; then
    check "Rust symbols in kallsyms" "ok"
else
    check "Rust symbols in kallsyms" "fail"
fi

# Test 5: Test any /sys/kernel/rust/ entries (future kernel ABI)
if [ -d /sys/kernel/rust ]; then
    check "Rust sysfs interface present" "ok"
else
    check "Rust sysfs interface present (skip - not required)" "ok"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
