#!/usr/bin/env bash
# build_initramfs.sh
# Build a minimal initramfs with a test payload for QEMU boot validation.
set -euo pipefail

ARCH="x86_64"
OUTPUT="initramfs.cpio.gz"
TEST_SCRIPT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --arch)         ARCH="$2";        shift 2 ;;
        --output)       OUTPUT="$2";      shift 2 ;;
        --test-script)  TEST_SCRIPT="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# Minimal rootfs layout
mkdir -p "$WORK"/{bin,proc,sys,dev,tmp,etc}

# Statically-linked busybox for sh/mount/etc
if command -v busybox &>/dev/null; then
    cp "$(which busybox)" "$WORK/bin/busybox"
    for cmd in sh mount umount echo cat ls insmod rmmod; do
        ln -sf busybox "$WORK/bin/$cmd"
    done
else
    echo "WARNING: busybox not found; using dash as /bin/sh" >&2
    if command -v dash &>/dev/null; then
        cp "$(which dash)" "$WORK/bin/sh"
    else
        echo "ERROR: no shell available for initramfs" >&2
        exit 1
    fi
fi

# Copy test payload
if [ -n "$TEST_SCRIPT" ] && [ -f "$TEST_SCRIPT" ]; then
    cp "$TEST_SCRIPT" "$WORK/test_payload.sh"
    chmod +x "$WORK/test_payload.sh"
fi

# Write /init
cat > "$WORK/init" <<'INIT_EOF'
#!/bin/sh
# Minimal init for kernel boot test
set -e

mount -t proc  none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null || true

echo "=== Kernel Boot Test Init ==="
echo "Kernel: $(uname -r)"
echo "Arch:   $(uname -m)"

# Run the test payload if present
if [ -x /test_payload.sh ]; then
    /test_payload.sh
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "Boot test PASSED"
    else
        echo "Boot test FAILED (exit $EXIT_CODE)"
    fi
else
    echo "Boot test PASSED (no payload, basic boot OK)"
fi

# Poweroff
echo o > /proc/sysrq-trigger 2>/dev/null || \
    busybox poweroff -f 2>/dev/null || \
    /sbin/poweroff -f 2>/dev/null || \
    sleep 5
INIT_EOF
chmod +x "$WORK/init"

# Pack into cpio
(
    cd "$WORK"
    find . | cpio -H newc -o --quiet
) | gzip -9 > "$OUTPUT"

echo "[build_initramfs] Created $OUTPUT ($(du -sh "$OUTPUT" | cut -f1))"
