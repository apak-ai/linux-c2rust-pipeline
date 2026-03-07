#!/usr/bin/env bash
# gen_compile_commands.sh
# Generate compile_commands.json for C files using Bear + kernel Makefile.
# Fallback: use the kernel's built-in scripts/clang-tools/gen_compile_commands.py
set -euo pipefail

KERNEL_SRC="${KERNEL_SRC:-/opt/linux-src}"
ARCH="${ARCH:-x86_64}"
LLVM="${LLVM:-1}"
JOBS="${JOBS:-$(nproc)}"
OUT="${OUT:-compile_commands.json}"

if [ ! -d "$KERNEL_SRC" ]; then
    echo "ERROR: KERNEL_SRC=$KERNEL_SRC does not exist." >&2
    exit 1
fi

cd "$KERNEL_SRC"

echo "[gen_compile_commands] Building with Bear to capture compile commands..."
if command -v bear &>/dev/null; then
    make defconfig
    bear -- make LLVM=$LLVM ARCH=$ARCH -j"$JOBS" vmlinux 2>/dev/null || true
    cp compile_commands.json "$OLDPWD/$OUT"
else
    # Kernel >= 5.17 has a native generator
    make LLVM=$LLVM ARCH=$ARCH defconfig
    make LLVM=$LLVM ARCH=$ARCH -j"$JOBS" \
        scripts/clang-tools/gen_compile_commands.py || true
    python3 scripts/clang-tools/gen_compile_commands.py \
        -d . \
        -o "$OLDPWD/$OUT" \
        2>&1
fi

if [ ! -f "$OLDPWD/$OUT" ]; then
    echo "ERROR: Failed to generate $OUT" >&2
    exit 1
fi

echo "[gen_compile_commands] Done → $OUT ($(jq length "$OLDPWD/$OUT") entries)"
