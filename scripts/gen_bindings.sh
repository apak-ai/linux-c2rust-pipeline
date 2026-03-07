#!/usr/bin/env bash
# gen_bindings.sh
# Generate Rust FFI bindings from kernel headers using bindgen.
# Mirrors what the kernel's rust/Makefile does for rust/bindings/bindings_generated.rs
set -euo pipefail

KERNEL_SRC=""
OUTPUT=""
ARCH="x86_64"

usage() { echo "Usage: $0 --kernel-src <path> --output <file> --arch <arch>"; exit 1; }

while [[ $# -gt 0 ]]; do
    case $1 in
        --kernel-src) KERNEL_SRC="$2"; shift 2 ;;
        --output)     OUTPUT="$2";     shift 2 ;;
        --arch)       ARCH="$2";       shift 2 ;;
        *)            usage ;;
    esac
done

[ -n "$KERNEL_SRC" ] || usage
[ -n "$OUTPUT"     ] || usage

mkdir -p "$(dirname "$OUTPUT")"

# Kernel-specific bindgen flags (mirrors rust/Makefile in the kernel tree)
BINDGEN_FLAGS=(
    --use-core
    --with-derive-default
    --ctypes-prefix "core::ffi"
    --no-layout-tests
    --no-debug ".*"
    --size_t-is-usize
    --rustified-enum ".*"
    --allowlist-file "$KERNEL_SRC/include/linux/.*"
    --allowlist-file "$KERNEL_SRC/include/uapi/linux/.*"
    --blocklist-type "__kernel_.*"     # use kernel's own type aliases
    --blocklist-type ".*__bindgen.*"
    --raw-line "#![allow(dead_code, non_snake_case, non_upper_case_globals, non_camel_case_types, clippy::all)]"
)

CLANG_ARGS=(
    "-I$KERNEL_SRC/include"
    "-I$KERNEL_SRC/arch/$ARCH/include"
    "-I$KERNEL_SRC/arch/$ARCH/include/generated"
    "-I$KERNEL_SRC/include/uapi"
    "-I$KERNEL_SRC/arch/$ARCH/include/uapi"
    "-D__KERNEL__"
    "-DMODULE"
    "-DRUST_BINDINGS"
    "-nostdinc"
    "-isystem$(clang -print-file-name=include)"
)

echo "[gen_bindings] Running bindgen for $ARCH..."

bindgen \
    "$KERNEL_SRC/rust/bindings/bindings_helper.h" \
    "${BINDGEN_FLAGS[@]}" \
    -- \
    "${CLANG_ARGS[@]}" \
    > "$OUTPUT" 2>&1

echo "[gen_bindings] Generated $OUTPUT ($(wc -l < "$OUTPUT") lines)"
