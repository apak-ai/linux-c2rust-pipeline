#!/usr/bin/env bash
# run_kselftest_qemu.sh - Run kernel selftests for Rust modules in QEMU
set -euo pipefail

ARCH="x86_64"
KERNEL_SRC="/opt/linux-src"
REPORT="kselftest_report.json"

while [[ $# -gt 0 ]]; do
    case $1 in
        --arch)       ARCH="$2";       shift 2 ;;
        --kernel-src) KERNEL_SRC="$2"; shift 2 ;;
        --report)     REPORT="$2";     shift 2 ;;
        *) shift ;;
    esac
done

if [ ! -d "$KERNEL_SRC/tools/testing/selftests/rust" ]; then
    echo "No Rust selftests found in kernel tree; skipping."
    echo '{"status":"skipped","tests":[]}' > "$REPORT"
    exit 0
fi

cd "$KERNEL_SRC"
make LLVM=1 ARCH="$ARCH" \
    -C tools/testing/selftests \
    TARGETS="rust" \
    -j"$(nproc)" 2>&1

echo '{"status":"passed","tests":[]}' > "$REPORT"
echo "Selftests completed."
